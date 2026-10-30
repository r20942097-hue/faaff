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

    def test_missing_receipt_rejected(self):
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
    def run_gate(self,source=None,control=None,product=None,root='ext/'):
        calls=[]
        def runner(*args,**kw):
            calls.append(kw['control'])
            return (control or {'status':'PASS'}) if kw['control'] else (product or {'status':'PASS'})
        with patch.object(gate,'isolation_check',return_value=[]), patch.object(gate,'make_control_fixture'):
            with patch.object(gate,'extract_verified_root',return_value={'files':1}):
                result=gate.inspect(Path('fixture.zip'),'0'*64,root,'net:[1]',
                    preflight=lambda *args:source or {'status':'PASS','manifest_roots':['ext/']},
                    runner=runner)
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
        self.assertEqual(r['status'],'PASS_OFFLINE_ONLY');self.assertEqual(c,[True,False]);self.assertEqual(r['release_decision'],'CANDIDATE_NO_GO')
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
        self.assertEqual(report['manifest_roots'], ['mv3/'])

    @patch.object(gate, 'supports_namespace', return_value=True)
    @patch.object(gate.os, 'geteuid', create=True, return_value=1000)
    @patch.object(gate.os, 'readlink', return_value='net:[123]')
    def test_nonloopback_route_blocked_even_without_default(self, *_):
        original = Path.read_text
        def fake_read(path, *a, **kw):
            if str(path) == '/proc/net/route':
                return 'Iface\tDestination\tGateway\tFlags\neth0\t0002000A\t00000000\t0001\n'
            if str(path) == '/proc/net/ipv6_route':
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

if __name__=='__main__':unittest.main()