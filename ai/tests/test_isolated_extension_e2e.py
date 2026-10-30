"""Offline negative/positive gate tests: no browser process is launched."""
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import isolated_extension_e2e as gate

class IsolationTests(unittest.TestCase):
    @patch.object(gate, 'supports_namespace', return_value=True)
    @patch.object(gate.os, 'geteuid', create=True, return_value=0)
    @patch.object(gate.os, 'readlink', return_value='net:[123]')
    def test_root_refused(self, *_):
        self.assertIn('ROOT_RUNTIME_FORBIDDEN', gate.isolation_check('net:[456]'))

    @patch.object(gate, 'supports_namespace', return_value=True)
    @patch.object(gate.os, 'geteuid', create=True, return_value=501)
    @patch.object(gate.os, 'readlink', return_value='net:[123]')
    def test_parent_namespace_equal_rejected(self, *_):
        self.assertIn('PARENT_NETNS_NOT_ISOLATED', gate.isolation_check('net:[123]'))

    @patch.object(gate, 'supports_namespace', return_value=True)
    @patch.object(gate.os, 'geteuid', create=True, return_value=501)
    @patch.object(gate.os, 'readlink', return_value='net:[123]')
    def test_missing_receipt_rejected(self, *_):
        self.assertIn('PARENT_NETNS_RECEIPT_MISSING', gate.isolation_check(None))

    def test_digest_validator(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'candidate.zip';f.write_bytes(b'not zip')
            self.assertEqual(gate.source_preflight(f,'bad')['reason'],'INVALID_EXPECTED_DIGEST')
            self.assertEqual(gate.source_preflight(f,'0'*64)['reason'],'ARCHIVE_DIGEST_MISMATCH')

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'archive.zip';f.write_bytes(b'abc')
            link=Path(d)/'link.zip'
            try: link.symlink_to(f)
            except OSError: self.skipTest('OS does not allow symlinks')
            self.assertEqual(gate.source_preflight(link,'0'*64)['reason'],'EXPECTED_REGULAR_ZIP')

class ExtractionTests(unittest.TestCase):
    def archive(self, entries):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        p=Path(tmp.name)/'test.zip'
        with zipfile.ZipFile(p,'w') as z:
            for a,b in entries:
                z.writestr(a,b)
        return p,Path(tmp.name)/'out'

    def test_good_root(self):
        p,out=self.archive([('ext/manifest.json','{"manifest_version":3}'),('ext/lib/a.js','console.log(1)')])
        r=gate.extract_verified_root(p,'ext/',out)
        self.assertEqual(r['files'],2)
        self.assertEqual((out/'lib/a.js').read_text(),'console.log(1)')

    def test_traversal_rejected(self):
        p,out=self.archive([('ext/manifest.json','{}'),('ext/../bad.js','x')])
        with self.assertRaisesRegex(ValueError,'UNSAFE_EXTENSION_MEMBER'):
            gate.extract_verified_root(p,'ext/',out)

    def test_case_collision_rejected(self):
        p,out=self.archive([('ext/manifest.json','{}'),('ext/A.js','x'),('ext/a.js','y')])
        with self.assertRaisesRegex(ValueError,'DUPLICATE_EXTENSION_MEMBER'):
            gate.extract_verified_root(p,'ext/',out)

    def test_symlink_rejected(self):
        info=zipfile.ZipInfo('ext/link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
        p,out=self.archive([('ext/manifest.json','{}'),(info,'bad')])
        with self.assertRaisesRegex(ValueError,'SYMLINK_EXTENSION_MEMBER'):
            gate.extract_verified_root(p,'ext/',out)

    def test_root_is_exact(self):
        p,out=self.archive([('ext/manifest.json','{}'),('ext2/unrelated','x')])
        gate.extract_verified_root(p,'ext/',out)
        self.assertFalse((out/'unrelated').exists())

    def test_missing_manifest(self):
        p,out=self.archive([('ext/hello.js','x')])
        with self.assertRaisesRegex(ValueError,'NO_SELECTED_ROOT_MANIFEST'):
            gate.extract_verified_root(p,'ext/',out)

    def test_bad_root(self):
        p,out=self.archive([('ext/manifest.json','{}')])
        for root in ('','../ext/','/ext/','ext','ext\\'):
            with self.subTest(root=root):
                with self.assertRaises(ValueError):gate.extract_verified_root(p,root,out)

class DecisionTests(unittest.TestCase):
    def run_gate(self,source=None,control=None,product=None,root='ext/',js=None):
        calls=[]
        def runner(*args,**kw):
            calls.append(kw['control'])
            return (control if control is not None else {'status':'PASS','worker':'PASS','worker_identity':'PASS','popup':'PASS','popup_identity':'PASS','roundtrip':'PASS'}) if kw['control'] else (product if product is not None else {'status':'PASS','worker':'PASS','worker_identity':'PASS','popup':'RENDERED_ONLY','popup_identity':'PASS'})
        with patch.object(gate,'isolation_check',return_value=[]), patch.object(gate,'make_control_fixture'):
            with patch.object(gate,'extract_verified_root',return_value={'files':1}):
                result=gate.inspect(Path('fixture.zip'),'0'*64,root,'net:[1]',
                    preflight=lambda *args:source or {'status':'PASS','manifest_roots':['ext/']},
                    runner=runner,
                    js_preflight=lambda *_: js if js is not None else {
                        'status':'PASS_SYNTAX_REFS_ONLY','sha256':'0'*64,'root':root,
                        'scripts_checked':3,'issues':[],'warnings':[],
                        'syntax_failures':[],'release_decision':'CANDIDATE_NO_GO'})
        return result,calls

    def test_source_failure_prevents_any_browser(self):
        r,c=self.run_gate(source={'status':'FAIL','reason':'hash mismatch'})
        self.assertEqual(r['status'],'FAIL');self.assertEqual(c,[])

    def test_unavailable_preflight_blocks_browser(self):
        with patch.object(gate,'isolation_check',return_value=[]):
            r=gate.inspect(Path('fixture.zip'),'0'*64,'ext/','net:[1]',
                preflight=lambda *a:(_ for _ in ()).throw(ImportError('missing')) )
        self.assertEqual(r['reason'],'SOURCE_PREFLIGHT_UNAVAILABLE_OR_INVALID')

    def test_unrelated_root_prevents_browser(self):
        r,c=self.run_gate(source={'status':'PASS','manifest_roots':['another/']})
        self.assertEqual(r['status'],'BLOCKED');self.assertEqual(c,[])

    def test_negative_control_prevents_product_execution(self):
        r,c=self.run_gate(control={'status':'BLOCKED','reason':'WORKER_NOT_OBSERVED'})
        self.assertEqual(r['reason'],'BROWSER_HARNESS_CONTROL_FAILED');self.assertEqual(c,[True])
        self.assertEqual(r['product_browser'],'NOT_RUN')

    def test_product_fail_remains_blocked(self):
        r,c=self.run_gate(product={'status':'BLOCKED','reason':'POPUP_NAVIGATION_FAILED'})
        self.assertEqual(r['status'],'BLOCKED');self.assertEqual(c,[True,False])

    def test_complete_offline_still_no_go(self):
        r,c=self.run_gate()
        self.assertEqual(r['status'],'PASS_OFFLINE_LOAD_ONLY');self.assertEqual(c,[True,False]);self.assertEqual(r['release_decision'],'CANDIDATE_NO_GO')
        self.assertEqual(r['real_site'],'NOT_RUN');self.assertEqual(r['windows_device'],'NOT_RUN')

    @patch.object(gate,'isolation_check',return_value=['ROOT_RUNTIME_FORBIDDEN'])
    def test_preconditions_stop_everything(self, _):
        def fail(*args,**kw):raise AssertionError('should not be called')
        r=gate.inspect(Path('candidate.zip'),'0'*64,'ext/','net:[1]',preflight=fail,runner=fail)
        self.assertEqual(r['reason'],'ISOLATION_PRECONDITION_FAILED')


class SyntheticControlTests(unittest.TestCase):
    def test_control_requires_worker_popup_message_and_storage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'control'
            gate.make_control_fixture(root)
            manifest = json.loads((root / 'manifest.json').read_text())
            self.assertEqual(manifest['background']['service_worker'], 'worker.js')
            self.assertEqual(manifest['action']['default_popup'], 'popup.html')
            self.assertIn('storage', manifest['permissions'])
            self.assertIn('popup.js', (root / 'popup.html').read_text())
            self.assertIn('gpt1-ping', (root / 'worker.js').read_text())
            self.assertIn('gpt1-pong', (root / 'popup.js').read_text())
            self.assertIn(gate.CONTROL_MARKER, (root / 'popup.js').read_text())
            self.assertNotIn(gate.CONTROL_MARKER, (root / 'popup.html').read_text())

    def test_roundtrip_waits_for_dynamic_marker(self):
        from unittest.mock import Mock
        page = Mock()
        page.wait_for_function.return_value = object()
        self.assertTrue(gate.verify_positive_control(page))
        page.wait_for_function.assert_called_once()
        self.assertEqual(page.wait_for_function.call_args.kwargs['arg'], gate.CONTROL_MARKER)

    def test_roundtrip_missing_signal_fails(self):
        from unittest.mock import Mock
        page = Mock()
        page.wait_for_function.return_value = None
        self.assertFalse(gate.verify_positive_control(page))

    def test_roundtrip_timeout_fails(self):
        from unittest.mock import Mock
        page = Mock()
        page.wait_for_function.side_effect = TimeoutError('no message')
        with self.assertRaises(TimeoutError):
            gate.verify_positive_control(page)

    def test_source_limits_browser_gate_to_manifest_v3(self):
        import hashlib, types
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'fixture.zip'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('manifest.json', '{}')
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            fake = types.ModuleType('extension_source_preflight')
            fake.inspect = lambda path, expected: {'status':'PASS', 'extensions': [
                {'status':'PASS', 'manifest_version':2, 'root':'mv2/'},
                {'status':'PASS', 'manifest_version':3, 'root':'.'},
                {'status':'PASS', 'manifest_version':3, 'root':'mv3/'}]}
            with patch.dict(sys.modules, {'extension_source_preflight': fake}):
                report = gate.source_preflight(p, digest)
        self.assertEqual(report['manifest_roots'], ['.', 'mv3/'])

    @patch.object(gate, 'supports_namespace', return_value=True)
    @patch.object(gate.os, 'geteuid', create=True, return_value=1000)
    @patch.object(gate.os, 'readlink', return_value='net:[123]')
    def test_nonloopback_route_blocked_even_without_default(self, *_):
        original = Path.read_text
        def fake_read(path, *a, **kw):
            if str(path).replace('\\', '/') == '/proc/net/route':
                return 'Iface\tDestination\tGateway\tFlags\neth0\t0002000A\t00000000\t0001\n'
            if str(path).replace('\\', '/') == '/proc/net/ipv6_route':
                return ''
            return original(path, *a, **kw)
        with patch.object(Path, 'read_text', fake_read):
            issues = gate.isolation_check('net:[456]')
        self.assertIn('NON_LOOPBACK_IPV4_ROUTE_PRESENT', issues)
        self.assertNotIn('DEFAULT_IPV4_ROUTE_PRESENT', issues)

    def test_worker_evaluate_api_has_no_timeout_argument(self):
        source = Path(gate.__file__).read_text()
        self.assertNotIn("version})', timeout=", source)
        try:
            from playwright.sync_api import Worker
        except ImportError:
            return  # Offline CI tests intentionally have no Playwright dependency.
        import inspect
        self.assertNotIn('timeout', inspect.signature(Worker.evaluate).parameters)

    def test_system_browser_override_is_explicit(self):
        source = Path(gate.__file__).read_text()
        self.assertIn("'SYSTEM_OVERRIDE' if browser_executable", source)
        self.assertIn("'PLAYWRIGHT_CHROMIUM'", source)


class SyntheticOnlyTests(unittest.TestCase):
    def test_synthetic_control_pass_reports_no_product(self):
        observed = []
        def runner(path, profile, **kwargs):
            observed.append((path, profile, kwargs))
            self.assertTrue((path / 'manifest.json').is_file())
            return {'status': 'PASS', 'worker': 'PASS', 'worker_identity': 'PASS', 'popup': 'PASS', 'popup_identity': 'PASS', 'roundtrip': 'PASS'}
        with patch.object(gate, 'isolation_check', return_value=[]):
            r = gate.synthetic_only('net:[4321]', runner=runner)
        self.assertEqual(r['status'], 'PASS_SYNTHETIC_ONLY')
        self.assertEqual(r['product_browser'], 'NOT_RUN')
        self.assertEqual(r['release_decision'], 'CANDIDATE_NO_GO')
        self.assertTrue(observed[0][2]['control'])
        self.assertFalse(observed[0][0].exists(), 'temporary fixture should be deleted')

    def test_synthetic_control_not_allowed_when_not_isolated(self):
        def runner(*args, **kwargs):
            raise AssertionError('must not run')
        with patch.object(gate, 'isolation_check', return_value=['DEFAULT_IPV4_ROUTE_PRESENT']):
            r = gate.synthetic_only(None, runner=runner)
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertEqual(r['synthetic_control'], 'NOT_RUN')

    def test_synthetic_control_not_proven_by_worker_only(self):
        with patch.object(gate, 'isolation_check', return_value=[]):
            r = gate.synthetic_only('net:[1]', runner=lambda *a, **k: {'status':'PASS', 'worker':'PASS', 'popup':'NOT_RUN'})
        self.assertEqual(r['reason'], 'SYNTHETIC_CONTROL_NOT_PROVEN')

    def test_synthetic_control_rejects_silent_partial_success(self):
        with patch.object(gate, 'isolation_check', return_value=[]):
            r = gate.synthetic_only('net:[1]', runner=lambda *a, **k: {'status':'PASS'})
        self.assertEqual(r['status'], 'BLOCKED')

    def test_synthetic_runner_exception_is_blocked(self):
        def runner(*args, **kwargs):
            raise RuntimeError('browser process failed')
        with patch.object(gate, 'isolation_check', return_value=[]):
            r=gate.synthetic_only('net:[1]', runner=runner)
        self.assertEqual(r['reason'],'SYNTHETIC_HARNESS_ERROR')
        self.assertEqual(r['release_decision'],'CANDIDATE_NO_GO')

    def test_synthetic_cli_rejects_product_inputs(self):
        from contextlib import redirect_stderr
        from io import StringIO
        for args in [['artifact.zip','--synthetic-only'], ['--synthetic-only','--sha256','0'*64],['--synthetic-only','--root','product/']]:
            with self.subTest(args=args), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as error:
                    gate.main(args)
            self.assertEqual(error.exception.code, 2)

    def test_product_cli_rejects_missing_inputs(self):
        from contextlib import redirect_stderr
        from io import StringIO
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as error:
                gate.main([])
        self.assertEqual(error.exception.code, 2)


class RootLevelManifestTests(unittest.TestCase):
    def test_root_level_valid_source_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / 'candidate.zip'
            manifest = {'manifest_version':3, 'name':'Synthetic fixture', 'version':'1.0',
                        'background':{'service_worker':'worker.js'}}
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('manifest.json',json.dumps(manifest))
                z.writestr('worker.js','console.log(1)')
            result=gate.extract_verified_root(p,'.',root/'out')
            self.assertEqual(result['files'],2)
            self.assertEqual(json.loads((root/'out'/'manifest.json').read_text())['manifest_version'],3)

    def test_root_level_rejects_cross_package_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'candidate.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('manifest.json','{}')
                z.writestr('../stolen','x')
            with self.assertRaisesRegex(ValueError,'UNSAFE_EXTENSION_MEMBER'):
                gate.extract_verified_root(p,'.',Path(tmp)/'out')

    def test_empty_and_absolute_roots_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'candidate.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('manifest.json','{}')
            for root in ('','./','/','../','sub//','sub/../'):
                with self.subTest(root=root), self.assertRaisesRegex(ValueError,'BAD_SELECTED_EXTENSION_ROOT'):
                    gate.extract_verified_root(p,root,Path(tmp)/'out')


class StrictEvidenceTests(unittest.TestCase):
    def test_control_missing_roundtrip_rejects_product(self):
        probe = DecisionTests()
        outcome, calls = probe.run_gate(control={'status':'PASS','worker':'PASS','popup':'PASS'})
        self.assertEqual(outcome['reason'], 'BROWSER_HARNESS_CONTROL_FAILED')
        self.assertEqual(calls, [True])

    def test_product_only_rendered_not_behavior_pass(self):
        probe = DecisionTests()
        outcome, calls = probe.run_gate()
        self.assertEqual(outcome['status'], 'PASS_OFFLINE_LOAD_ONLY')
        self.assertEqual(outcome['release_decision'], 'CANDIDATE_NO_GO')
        self.assertEqual(outcome['product_browser']['popup'], 'RENDERED_ONLY')

    def test_product_popup_cannot_claim_functional_pass(self):
        probe = DecisionTests()
        outcome, calls = probe.run_gate(product={'status':'PASS','worker':'PASS','popup':'PASS'})
        self.assertEqual(outcome['status'], 'BLOCKED')
        self.assertEqual(outcome['reason'], 'PRODUCT_OFFLINE_BROWSER_CHECK_INCOMPLETE')

    def test_synthetic_worker_popup_without_roundtrip_is_blocked(self):
        with patch.object(gate, 'isolation_check', return_value=[]):
            outcome = gate.synthetic_only('net:[1]', runner=lambda *a, **k:
                {'status':'PASS','worker':'PASS','popup':'PASS'})
        self.assertEqual(outcome['status'], 'BLOCKED')

    def test_synthetic_pass_does_not_prove_product(self):
        with patch.object(gate, 'isolation_check', return_value=[]):
            outcome = gate.synthetic_only('net:[1]', runner=lambda *a, **k:
                {'status':'PASS','worker':'PASS','worker_identity':'PASS','popup':'PASS','popup_identity':'PASS','roundtrip':'PASS'})
        self.assertEqual(outcome['status'], 'PASS_SYNTHETIC_ONLY')
        self.assertEqual(outcome['product_browser'], 'NOT_RUN')
        self.assertEqual(outcome['recording'], 'NOT_RUN')
        self.assertEqual(outcome['release_decision'], 'CANDIDATE_NO_GO')


if __name__=='__main__':unittest.main()

class RuntimeIdentityTests(unittest.TestCase):
    def setUp(self):
        self.ident = 'a' * 32
        self.manifest = {'background': {'service_worker': 'js/background.js'}}
        self.url = f'chrome-extension://{self.ident}/js/background.js'

    def test_expected_worker_script_and_id(self):
        self.assertEqual(gate.worker_extension_id(self.url, self.manifest), self.ident)

    def test_different_worker_script_is_rejected(self):
        self.assertIsNone(gate.worker_extension_id(self.url.replace('background.js', 'other.js'), self.manifest))

    def test_nonextension_worker_is_rejected(self):
        self.assertIsNone(gate.worker_extension_id(self.url.replace('chrome-extension:', 'https:'), self.manifest))

    def test_invalid_extension_id_is_rejected(self):
        self.assertIsNone(gate.worker_extension_id(self.url.replace(self.ident, 'z'*32), self.manifest))

    def test_query_and_fragment_are_rejected(self):
        for extra in ('?token=x', '#fragment'):
            with self.subTest(extra=extra):
                self.assertIsNone(gate.worker_extension_id(self.url + extra, self.manifest))

    def test_missing_declared_script_is_rejected(self):
        self.assertIsNone(gate.worker_extension_id(self.url, {'background': {}}))
        self.assertIsNone(gate.worker_extension_id(self.url, {'background': []}))

    def test_encoded_script_url_is_rejected(self):
        self.assertIsNone(gate.worker_extension_id(self.url.replace('/js/', '/js%2F'), self.manifest))

    def test_popup_origin_and_runtime_id_match(self):
        self.assertTrue(gate.popup_identity_matches(
            {'runtime_id': self.ident, 'origin': 'chrome-extension://' + self.ident}, self.ident))

    def test_popup_wrong_id_or_origin_is_rejected(self):
        for identity in ({'runtime_id': 'b'*32, 'origin': 'chrome-extension://' + self.ident},
                         {'runtime_id': self.ident, 'origin': 'https://example.test'},
                         {'runtime_id': self.ident}, {}, None):
            with self.subTest(identity=identity):
                self.assertFalse(gate.popup_identity_matches(identity, self.ident))

    def test_control_missing_worker_identity_blocks_product(self):
        probe = DecisionTests()
        outcome, calls = probe.run_gate(control={
            'status': 'PASS', 'worker': 'PASS', 'popup': 'PASS', 'roundtrip': 'PASS'})
        self.assertEqual(outcome['reason'], 'BROWSER_HARNESS_CONTROL_FAILED')
        self.assertEqual(calls, [True])

    def test_product_missing_popup_identity_blocks_pass(self):
        probe = DecisionTests()
        outcome, calls = probe.run_gate(product={
            'status': 'PASS', 'worker': 'PASS', 'worker_identity': 'PASS', 'popup': 'RENDERED_ONLY'})
        self.assertEqual(outcome['reason'], 'PRODUCT_OFFLINE_BROWSER_CHECK_INCOMPLETE')
        self.assertEqual(calls, [True, False])



class JavaScriptBeforeProductTests(unittest.TestCase):
    def test_real_gate_detects_missing_node(self):
        self.assertFalse(gate.javascript_gate_approved({'status':'PARTIAL'}, '0'*64, 'ext/'))

    def test_invalid_js_evidence_does_not_start_browser(self):
        r,c=DecisionTests().run_gate(js={'status':'FAIL','issues':['SYNTAX_ERROR']})
        self.assertEqual(r['status'],'FAIL')
        self.assertEqual(r['reason'],'JS_PREFLIGHT_NOT_FULLY_PASS_OR_WRONG_ARTIFACT')
        self.assertEqual(c,[])
        self.assertEqual(r['product_browser'],'NOT_RUN')

    def test_partial_js_evidence_blocks_browser(self):
        r,c=DecisionTests().run_gate(js={'status':'PARTIAL','warnings':['NODE_NOT_AVAILABLE']})
        self.assertEqual(r['status'],'BLOCKED')
        self.assertEqual(c,[])

    def test_digest_mismatch_blocks_js_stage(self):
        report={'status':'PASS_SYNTAX_REFS_ONLY','sha256':'f'*64,'root':'ext/',
                'scripts_checked':3,'issues':[],'warnings':[],'syntax_failures':[],
                'release_decision':'CANDIDATE_NO_GO'}
        r,c=DecisionTests().run_gate(js=report)
        self.assertEqual(c,[])
        self.assertEqual(r['status'],'BLOCKED')

    def test_missing_script_count_is_not_pass(self):
        report={'status':'PASS_SYNTAX_REFS_ONLY','sha256':'0'*64,'root':'ext/',
                'issues':[],'warnings':[],'syntax_failures':[],
                'release_decision':'CANDIDATE_NO_GO'}
        r,c=DecisionTests().run_gate(js=report)
        self.assertEqual(r['status'],'BLOCKED')
        self.assertEqual(c,[])

    def test_bool_script_count_is_not_pass(self):
        report={'status':'PASS_SYNTAX_REFS_ONLY','sha256':'0'*64,'root':'ext/',
                'scripts_checked':True,'issues':[],'warnings':[],'syntax_failures':[],
                'release_decision':'CANDIDATE_NO_GO'}
        self.assertFalse(gate.javascript_gate_approved(report,'0'*64,'ext/'))

    def test_expected_good_js_preflight_reaches_synthetic_then_product(self):
        r,c=DecisionTests().run_gate()
        self.assertEqual(c,[True,False])
        self.assertEqual(r['status'],'PASS_OFFLINE_LOAD_ONLY')
        self.assertEqual(r['js_preflight']['status'],'PASS_SYNTAX_REFS_ONLY')
        self.assertEqual(r['release_decision'],'CANDIDATE_NO_GO')

    def test_js_preflight_exception_fails_closed(self):
        with patch.object(gate,'isolation_check',return_value=[]):
            r=gate.inspect(Path('x.zip'),'0'*64,'ext/','net:[1]',
                preflight=lambda *_:{'status':'PASS','manifest_roots':['ext/']},
                js_preflight=lambda *_:(_ for _ in ()).throw(ImportError('no js checker')))
        self.assertEqual(r['reason'],'JS_PREFLIGHT_UNAVAILABLE_OR_INVALID')
        self.assertEqual(r['product_browser'],'NOT_RUN')

    def test_wrong_root_or_release_state_fails(self):
        report={'status':'PASS_SYNTAX_REFS_ONLY','sha256':'0'*64,'root':'wrong/',
                'scripts_checked':3,'issues':[],'warnings':[],'syntax_failures':[],
                'release_decision':'CANDIDATE_NO_GO'}
        self.assertFalse(gate.javascript_gate_approved(report,'0'*64,'ext/'))
        report['root']='ext/'
        report['release_decision']='GO'
        self.assertFalse(gate.javascript_gate_approved(report,'0'*64,'ext/'))

    def test_js_preflight_delegates_exact_arguments(self):
        with patch.dict(sys.modules, {'extension_js_preflight': __import__('types').SimpleNamespace(
            inspect=lambda path, sha, root: (path,sha,root))}):
            self.assertEqual(gate.javascript_preflight(Path('a.zip'),'0'*64,'ext/'),
                             (Path('a.zip'),'0'*64,'ext/'))
