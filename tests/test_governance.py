import copy,hashlib,json,pathlib,subprocess,sys,tempfile,unittest,zipfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from governance import *
class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.d=load(ROOT/'templates/RELEASE_MANIFEST.example.json');d=self.d
        d.update(example=False,version='1.2.3',state='DEV',release_decision='GO',blockers=[])
        (self.root/'source.zip').write_bytes(b'not-an-archive')
        # Replace source with a valid archive, rather than trusting extension.
        with zipfile.ZipFile(self.root/'source.zip','w') as z:z.writestr('source.py','print(1)')
        with zipfile.ZipFile(self.root/d['artifact']['filename'],'w') as z:z.writestr('app.py','print(1)')
        d['source']['sha256']=digest(self.root/'source.zip');d['source']['commit']='a'*40
        artifact=self.root/d['artifact']['filename'];d['artifact'].update(sha256=digest(artifact),size_bytes=artifact.stat().st_size)
        for gate in d['evidence']:
            payload=None
            if gate in ['sbom','provenance']:
                data={'bomFormat':'CycloneDX','specVersion':'1.7','metadata':{'component':{'name':d['product_id'],'version':d['version']}},'components':[]} if gate=='sbom' else {'_type':'https://in-toto.io/Statement/v1','predicateType':'https://slsa.dev/provenance/v1','predicate':{},'subject':[{'name':d['artifact']['filename'],'digest':{'sha256':d['artifact']['sha256']}}]}
                p=self.root/(gate+'-payload.json');p.write_text(json.dumps(data));payload={'path':p.name,'sha256':digest(p)}
            rec={'schema_version':1,'product_id':d['product_id'],'version':d['version'],'artifact_sha256':d['artifact']['sha256'],'source_sha256':d['source']['sha256'],'gate':gate,'passed':True,'scope':'product','details':'Synthetic regression fixture only','payload':payload}
            p=self.root/(gate+'.json');p.write_text(json.dumps(rec));d['evidence'][gate]={'path':p.name,'sha256':digest(p)}
        self.policy=load(ROOT/'policies/promotion-policy.json')
    def decide(self):return promotion(self.d,self.root,self.policy)['decision']
    def record_change(self,gate,key,value):
        p=self.root/self.d['evidence'][gate]['path'];r=load(p);r[key]=value;p.write_text(json.dumps(r));self.d['evidence'][gate]['sha256']=digest(p)
    def test_complete_fixture_stable(self):self.assertEqual(self.decide(),'STABLE_ELIGIBLE')
    def test_all_candidate_gates_required(self):
        for g in self.policy['candidate_gates']:
            with self.subTest(g=g):
                ref=self.d['evidence'][g];self.d['evidence'][g]=None;self.assertEqual(self.decide(),'DEV_OR_NO_GO');self.d['evidence'][g]=ref
    def test_real_and_rollback_missing_candidate_only(self):
        for g in ['real_environment','rollback']:
            with self.subTest(g=g):
                ref=self.d['evidence'][g];self.d['evidence'][g]=None;self.assertEqual(self.decide(),'CANDIDATE_ELIGIBLE');self.d['evidence'][g]=ref
    def test_false_string_evidence_rejected(self):
        for bad in ['false','true',1,False,None]:
            with self.subTest(bad=bad):self.record_change('tests','passed',bad);self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_example_never_promotes(self):self.d['example']=True;self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_candidate_blocker(self):self.d['blockers']=[{'scope':'candidate','reason':'Core incomplete'}];self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_stable_blocker(self):self.d['blockers']=[{'scope':'stable','reason':'Unaccepted'}];self.assertEqual(self.decide(),'CANDIDATE_ELIGIBLE')
    def test_hold_no_stable(self):self.d['release_decision']='HOLD';self.assertEqual(self.decide(),'CANDIDATE_ELIGIBLE')
    def test_cross_product_evidence(self):self.record_change('tests','product_id','other-product');self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_cross_version_evidence(self):self.record_change('tests','version','9.9.9');self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_cross_scope_evidence(self):self.record_change('tests','scope','integration');self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_source_binding(self):self.record_change('tests','source_sha256','b'*64);self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_artifact_binding(self):self.record_change('tests','artifact_sha256','b'*64);self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_artifact_tamper(self):(self.root/self.d['artifact']['filename']).write_bytes(b'changed');self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_size_tamper(self):self.d['artifact']['size_bytes']+=1;self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_record_tamper(self):(self.root/'tests.json').write_text('{}');self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_payload_tamper(self):(self.root/'sbom-payload.json').write_text('{}');self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_provenance_subject_tamper(self):
        p=self.root/'provenance-payload.json';r=load(p);r['subject'][0]['digest']['sha256']='a'*64;p.write_text(json.dumps(r));self.record_change('provenance','payload',{'path':p.name,'sha256':digest(p)});self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_malformed_sbom_metadata(self):
        p=self.root/'sbom-payload.json';r=load(p);r['metadata']=[];p.write_text(json.dumps(r));self.record_change('sbom','payload',{'path':p.name,'sha256':digest(p)});self.assertEqual(self.decide(),'DEV_OR_NO_GO')
    def test_malformed_policy_list(self):
        self.policy['candidate_gates']=[{}]
        with self.assertRaises(Invalid):self.decide()
    def test_pack_missing_or_changed(self):
        from verify_pack import verify
        folder=self.root/'pack';folder.mkdir();p=folder/'file.txt';p.write_text('ok');m=folder/'CONTENT_MANIFEST_SHA256.json';m.write_text(json.dumps({'file.txt':digest(p)}));self.assertEqual(verify(folder),1)
        p.write_text('tamper')
        with self.assertRaises(Invalid):verify(folder)
    def test_pack_unlisted_file(self):
        from verify_pack import verify
        p=self.root/'file.txt';p.write_text('ok');(self.root/'CONTENT_MANIFEST_SHA256.json').write_text(json.dumps({'file.txt':digest(p)}));(self.root/'extra.txt').write_text('extra')
        with self.assertRaises(Invalid):verify(self.root)
    def test_unknown_risk(self):
        self.d['risk_class']='unknown'
        with self.assertRaises(Invalid):self.decide()
    def test_missing_policy_gate(self):
        self.policy['candidate_gates'].pop()
        with self.assertRaises(Invalid):self.decide()
    def test_semver_invalid(self):
        for v in ['1.2','01.2.3','1.2.3-dev.01','1.2.3-','v1.2.3']:
            with self.subTest(v=v),self.assertRaises(Invalid):self.d['version']=v;validate_manifest(self.d)
    def test_stable_claim_prerelease(self):
        self.d.update(state='STABLE',version='1.2.3-rc.1')
        with self.assertRaises(Invalid):validate_manifest(self.d)
    def test_integer_boolean_size(self):
        self.d['artifact']['size_bytes']=True
        with self.assertRaises(Invalid):validate_manifest(self.d)
    def test_path_traversal(self):
        for p in ['../secret','/tmp/foo','C:/secret','a\\b']:
            with self.subTest(p=p),self.assertRaises(Invalid):safe_file(self.root,p)
    def test_symlink(self):
        (self.root/'link').symlink_to(self.root/'source.zip')
        with self.assertRaises(Invalid):safe_file(self.root,'link')
    def test_zip_traversal(self):
        p=self.root/'bad.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('../evil','x')
        with self.assertRaises(Invalid):zip_check(p)
    def test_zip_case_collision(self):
        p=self.root/'bad.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('App.py','x');z.writestr('app.py','y')
        with self.assertRaises(Invalid):zip_check(p)
    def test_registry_empty(self):
        d=load(REGISTRY);d['projects']=[]
        with self.assertRaises(Invalid):validate_registry(d)
    def test_registry_duplicate(self):
        d=load(REGISTRY);d['projects'].append(copy.deepcopy(d['projects'][0]))
        with self.assertRaises(Invalid):validate_registry(d)
    def test_registry_stable_contradiction(self):
        d=load(REGISTRY);d['projects'][0]['state']='STABLE'
        with self.assertRaises(Invalid):validate_registry(d)
    def test_registry_unknown_field(self):
        d=load(REGISTRY);d['projects'][0]['stabel']='1.0.0'
        with self.assertRaises(Invalid):validate_registry(d)
    def test_retention_all_refs(self):
        d=load(REGISTRY);p=d['projects'][0];p['integration_verified']='distinct';p['previous_known_good']='rollback'
        keep=retention(d)['projects'][0]['keep_refs'];self.assertIn('distinct',keep);self.assertIn('rollback',keep)
    def test_duplicate_json_keys(self):
        p=self.root/'bad.json';p.write_text('{"key":1,"key":2}')
        with self.assertRaises(Invalid):load(p)
    def test_nonfinite_json(self):
        p=self.root/'bad.json';p.write_text('{"key":NaN}')
        with self.assertRaises(Invalid):load(p)
    def test_index_matches_registry(self):self.assertEqual((ROOT/'PROJECT_INDEX.md').read_text(),render_index(load(REGISTRY)))
    def test_cli_malformed_no_traceback(self):
        p=self.root/'bad.json';p.write_text('{}');r=subprocess.run([sys.executable,str(ROOT/'tools/promotion_decision.py'),str(p)],capture_output=True,text=True);self.assertEqual(r.returncode,2);self.assertNotIn('Traceback',r.stderr)
if __name__=='__main__':unittest.main()
