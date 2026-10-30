"""Synthetic, offline unit tests. Never execute any product JavaScript."""
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import offline_product_contract_probe as probe

ROOT='rplay-stable-player-extension/'
MANIFEST={'manifest_version':3,'name':'Synthetic test fixture','version':'1.0.0',
          'background':{'service_worker':'background.js'}}


class ContractGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.zip=self.base/'synthetic.zip'
        self.files={ROOT+'manifest.json':json.dumps(MANIFEST).encode()}
        self.files.update({ROOT+m:b'const fixture = 1;' for m in probe.MODULES})

    def make_zip(self, extra=None):
        files={**self.files,**(extra or {})}
        with zipfile.ZipFile(self.zip,'w',compression=zipfile.ZIP_STORED) as z:
            for name,content in files.items():z.writestr(name,content)
        return hashlib.sha256(self.zip.read_bytes()).hexdigest()

    def stage(self):
        digest=self.make_zip()
        with tempfile.TemporaryDirectory() as t:
            result=probe.extract_pure_modules(probe.archive_bytes(self.zip,digest),ROOT,Path(t))
            self.assertEqual(result['staged_modules'],3)
            self.assertEqual(len(result['module_sha256']),3)
            return result

    def test_safe_archive_staged(self):
        self.stage()

    def test_expected_sha_mismatch_fails(self):
        self.make_zip()
        with self.assertRaisesRegex(ValueError,'ARCHIVE_DIGEST_MISMATCH'):
            probe.archive_bytes(self.zip,'0'*64)

    def test_bad_expected_sha_fails(self):
        self.make_zip()
        with self.assertRaisesRegex(ValueError,'INVALID_TRUSTED_DIGEST'):
            probe.archive_bytes(self.zip,'wrong')

    def test_missing_module_fails(self):
        del self.files[ROOT+probe.MODULES[0]]
        digest=self.make_zip()
        with self.assertRaisesRegex(ValueError,'REQUIRED_SOURCE_MODULE_MISSING'):
            probe.extract_pure_modules(probe.archive_bytes(self.zip,digest),ROOT,self.base)

    def test_wrong_manifest_worker_fails(self):
        self.files[ROOT+'manifest.json']=json.dumps({**MANIFEST,'background':{'service_worker':'other.js'}}).encode()
        digest=self.make_zip()
        with self.assertRaisesRegex(ValueError,'UNEXPECTED_MANIFEST_TARGET'):
            probe.extract_pure_modules(probe.archive_bytes(self.zip,digest),ROOT,self.base)

    def test_traversal_rejected(self):
        digest=self.make_zip({'../../outside.js':b'x'})
        with self.assertRaisesRegex(ValueError,'UNSAFE_ARCHIVE_MEMBER'):
            probe.extract_pure_modules(probe.archive_bytes(self.zip,digest),ROOT,self.base)

    def test_reserved_win_device_rejected(self):
        digest=self.make_zip({ROOT+'AUX.txt':b'a'})
        with self.assertRaisesRegex(ValueError,'UNSAFE_ARCHIVE_MEMBER'):
            probe.extract_pure_modules(probe.archive_bytes(self.zip,digest),ROOT,self.base)

    def test_windows_case_collision_rejected(self):
        digest=self.make_zip({ROOT+'HTTP_RESUME.js':b'a'})
        with self.assertRaisesRegex(ValueError,'ARCHIVE_PATH_COLLISION'):
            probe.extract_pure_modules(probe.archive_bytes(self.zip,digest),ROOT,self.base)

    def test_symlink_rejected(self):
        self.make_zip()
        with zipfile.ZipFile(self.zip,'a') as z:
            info=zipfile.ZipInfo(ROOT+'evil-link')
            info.create_system=3
            info.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(info,b'/etc/passwd')
        raw=self.zip.read_bytes()
        with self.assertRaisesRegex(ValueError,'UNSAFE_ARCHIVE_MEMBER'):
            probe.extract_pure_modules(raw,ROOT,self.base)

    def test_root_traversal_rejected(self):
        digest=self.make_zip()
        with self.assertRaisesRegex(ValueError,'INVALID_SELECTED_ROOT'):
            probe.extract_pure_modules(probe.archive_bytes(self.zip,digest),'../',self.base)

    def test_no_product_execute_on_corrupt_archive(self):
        self.zip.write_bytes(b'not zip')
        digest=hashlib.sha256(self.zip.read_bytes()).hexdigest()
        with patch.object(probe,'run_isolated') as runner:
            result=probe.inspect(self.zip,digest,ROOT,self.base/'suite',self.base/'wrapper')
            self.assertEqual(result['status'],'BLOCKED')
            self.assertEqual(result['release_decision'],'CANDIDATE_NO_GO')
            runner.assert_not_called()

    def test_no_product_execute_on_digest_mismatch(self):
        self.make_zip()
        with patch.object(probe,'run_isolated') as runner:
            result=probe.inspect(self.zip,'0'*64,ROOT,self.base/'suite',self.base/'wrapper')
            self.assertEqual(result['status'],'BLOCKED')
            self.assertEqual(result['product_browser'],'NOT_RUN')
            runner.assert_not_called()

    def test_no_e2e_or_go_on_fake_pass(self):
        digest=self.make_zip()
        with patch.object(probe,'run_isolated',return_value={'status':'PASS','count':414,'network_isolated':True,
                       'filesystem_permission_model':'NODE_PERMISSION'}):
            result=probe.inspect(self.zip,digest,ROOT,self.base/'suite',self.base/'wrapper')
        self.assertEqual(result['status'],'PASS_OFFLINE_CONTRACT_ONLY')
        for key in ('product_browser','recording','mp4_output','real_site','windows_device','firefox_device'):
            self.assertEqual(result[key],'NOT_RUN')
        self.assertEqual(result['trusted_source_provenance'],'NOT_VERIFIED')
        self.assertEqual(result['release_decision'],'CANDIDATE_NO_GO')

    def test_missing_isolation_or_count_never_passes(self):
        for case in [
          {'status':'BLOCKED'},
          {'status':'PASS','count':0,'network_isolated':True,'filesystem_permission_model':'NODE_PERMISSION'},
          {'status':'PASS','count':414,'network_isolated':False,'filesystem_permission_model':'NODE_PERMISSION'},
          {'status':'PASS','count':True,'network_isolated':True,'filesystem_permission_model':'NODE_PERMISSION'},
        ]:
            with self.subTest(case=case),patch.object(probe.subprocess,'run',return_value=type('P',(),{
                    'returncode':0,'stdout':'GPT1_ISOLATION_PROVEN_BY_WRAPPER\n'+json.dumps(case)})()):
                with patch.object(probe.shutil,'which',return_value='/bin/tool'):
                    wrapper=self.base/'w';wrapper.write_text('x')
                    suite=self.base/'t';suite.write_text('x')
                    r=probe.run_isolated(self.base,suite,wrapper)
                    self.assertEqual(r['status'],'BLOCKED')

    def test_missing_wrapper_receipt_fails_closed(self):
        with patch.object(probe.subprocess,'run',return_value=type('P',(),{
             'returncode':0,'stdout':json.dumps({'status':'PASS','count':400})})()),\
             patch.object(probe.shutil,'which',return_value='/bin/tool'):
            wrapper=self.base/'w';wrapper.write_text('x')
            suite=self.base/'t';suite.write_text('x')
            result=probe.run_isolated(self.base,suite,wrapper)
            self.assertEqual(result['status'],'BLOCKED')

    def test_zip_directory_entries_allowed(self):
        digest=self.make_zip({ROOT+'subdir/':b''})
        with tempfile.TemporaryDirectory() as temp:
            result=probe.extract_pure_modules(probe.archive_bytes(self.zip,digest),ROOT,Path(temp))
            self.assertEqual(result['staged_modules'],3)

    def test_oversized_archive_rejected_without_read(self):
        self.make_zip()
        with patch.object(probe,'MAX_ARCHIVE_BYTES',0):
            with self.assertRaisesRegex(ValueError,'ARCHIVE_EXCEEDS_SIZE_LIMIT'):
                probe.archive_bytes(self.zip,hashlib.sha256(self.zip.read_bytes()).hexdigest())


class ReviewedSuiteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.suite=Path(__file__).with_name('product_contracts.js')
        self.wrapper=Path(__file__).with_name('isolate_node.sh')

    def test_repository_runner_is_exactly_pinned(self):
        self.assertTrue(probe.reviewed_runner_files(self.suite,self.wrapper))

    def test_edited_test_script_rejected_before_execution(self):
        script=self.base/'evil.js';script.write_bytes(self.suite.read_bytes()+b'\n//surprise')
        self.assertFalse(probe.reviewed_runner_files(script,self.wrapper))
        with patch.object(probe.subprocess,'run') as exec_mock, \
             patch.object(probe.shutil,'which',return_value='/bin/test'), \
             patch.object(probe,'linux_namespace_available',return_value=True):
            result=probe.run_isolated(self.base,script,self.wrapper)
        self.assertEqual(result['reason'],'REVIEWED_SUITE_OR_WRAPPER_HASH_MISMATCH')
        exec_mock.assert_not_called()

    def test_modified_wrapper_rejected_before_execution(self):
        script=self.base/'runner.sh';script.write_bytes(self.wrapper.read_bytes()+b'\necho BYPASS')
        self.assertFalse(probe.reviewed_runner_files(self.suite,script))

    def test_missing_runner_fails_closed(self):
        self.assertFalse(probe.reviewed_runner_files(self.base/'missing',self.wrapper))

    def test_symlink_runner_rejected(self):
        link=self.base/'linked-suite.js'
        try:link.symlink_to(self.suite)
        except (OSError,NotImplementedError):self.skipTest('symlinks unavailable')
        self.assertFalse(probe.reviewed_runner_files(link,self.wrapper))

    def test_oversize_runner_refused(self):
        script=self.base/'too-large.js';script.write_bytes(b'x'*(32*1024+1))
        self.assertFalse(probe.reviewed_runner_files(script,self.wrapper))

    def _run_with_receipt(self, verdict):
        with patch.object(probe.subprocess,'run',return_value=type('Result',(),{
             'returncode':0,'stdout':'GPT1_ISOLATION_PROVEN_BY_WRAPPER\n'+json.dumps(verdict)})()), \
             patch.object(probe.shutil,'which',return_value='/bin/tool'), \
             patch.object(probe,'linux_namespace_available',return_value=True), \
             patch.object(probe.os,'readlink',return_value='net:[111]'):
            return probe.run_isolated(self.base,self.suite,self.wrapper)

    def _valid_receipt(self):
        return {'status':'PASS','count':probe.EXPECTED_COUNT,'test_scope':probe.EXPECTED_SCOPE,
                'network_isolated':True,'filesystem_permission_model':'NODE_PERMISSION'}

    def test_known_good_receipt_accepts_reviewed_fixture(self):
        # The actual subprocess is mocked. This proves the gate condition only.
        result=self._run_with_receipt(self._valid_receipt())
        self.assertEqual(result['status'],'PASS')

    def test_forged_zero_or_smaller_or_larger_count_rejected(self):
        for count in (0,1,414,416,418,100000,True,'417'):
            with self.subTest(count=count):
                case=self._valid_receipt();case['count']=count
                result=self._run_with_receipt(case)
                self.assertEqual(result['reason'],'ISOLATED_EVIDENCE_INCOMPLETE')

    def test_forged_scope_rejected(self):
        for scope in ('anything',None,'PASS',probe.EXPECTED_SCOPE+' '):
            with self.subTest(scope=scope):
                case=self._valid_receipt();case['test_scope']=scope
                self.assertEqual(self._run_with_receipt(case)['status'],'BLOCKED')

    def test_network_false_claim_rejected(self):
        for network in (False,None,1,'true'):
            with self.subTest(network=network):
                case=self._valid_receipt();case['network_isolated']=network
                self.assertEqual(self._run_with_receipt(case)['status'],'BLOCKED')

    def test_unverified_sandbox_level_not_claimed(self):
        case=self._valid_receipt()
        accepted=self._run_with_receipt(case)
        self.assertNotIn('browser_e2e',accepted)
        self.assertNotIn('release_approved',accepted)

    def test_node_permission_missing_rejected(self):
        case=self._valid_receipt();case['filesystem_permission_model']='NONE'
        self.assertEqual(self._run_with_receipt(case)['status'],'BLOCKED')

    def test_zip_special_file_types_rejected(self):
        root='rplay-stable-player-extension/'
        with zipfile.ZipFile(self.base/'special.zip','w') as z:
            z.writestr(root+'manifest.json',json.dumps({'manifest_version':3,'background':{'service_worker':'background.js'}}))
            for name in probe.MODULES:z.writestr(root+name,'const x=1;')
            info=zipfile.ZipInfo(root+'device')
            info.create_system=3
            info.external_attr=(stat.S_IFCHR|0o666)<<16
            z.writestr(info,b'foo')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'UNSAFE_ARCHIVE_MEMBER'):
                probe.extract_pure_modules((self.base/'special.zip').read_bytes(),root,Path(directory))

    def test_result_scope_retains_explicit_no_go(self):
        self.assertEqual(probe.EXPECTED_COUNT,417)
        self.assertIn('not browser/recording E2E',probe.EXPECTED_SCOPE)

if __name__=='__main__':unittest.main()
