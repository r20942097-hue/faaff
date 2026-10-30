import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from ai.toolchain_inventory import parse_version, probe, collect, main

class ToolchainInventoryTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version('ffmpeg version 7.1.2-test'), '7.1.2')
        self.assertEqual(parse_version('v22.15.0'), '22.15.0')
        self.assertIsNone(parse_version('no version'))

    def test_missing_reports_no_path(self):
        result = probe('node', 'node', ['--version'], which=lambda _: None)
        self.assertEqual(result, {'status': 'MISSING', 'version': None})

    def test_present_reports_but_omits_path(self):
        command = Mock(return_value=Mock(returncode=0,stdout='git version 2.50.0',stderr=''))
        result = probe('git','git',['--version'],which=lambda _: '/user/private/git',runner=command)
        self.assertEqual(result, {'status':'AVAILABLE','version':'2.50.0'})
        self.assertNotIn('/user/private/git',json.dumps(result))

    def test_command_failure_fails_closed(self):
        command = Mock(return_value=Mock(returncode=2,stdout='v20.0.0',stderr=''))
        self.assertEqual(probe('node','node',['--version'],which=lambda _:'/bin/node',runner=command)['status'],'NOT_VERIFIED')

    def test_timeout_is_not_available(self):
        import subprocess
        def timeout(*args, **kwargs): raise subprocess.TimeoutExpired('node',10)
        self.assertEqual(probe('node','node',['--version'],which=lambda _: '/bin/node',runner=timeout)['status'],'NOT_VERIFIED')

    def test_collection_is_not_product_acceptance(self):
        report=collect()
        self.assertEqual(report['release_readiness'], 'NO_GO')
        self.assertEqual(report['browser_product_e2e'], 'NOT_RUN')
        self.assertIn('ffprobe',report['tools'])

    def test_json_output(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'evidence.json'
            with patch('builtins.print'):
                code=main(['--output',str(p)])
            self.assertEqual(code,0)
            self.assertEqual(json.loads(p.read_text())['release_readiness'],'NO_GO')

if __name__=='__main__':
    unittest.main()
