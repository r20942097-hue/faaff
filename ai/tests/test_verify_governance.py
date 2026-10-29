"""Fixture tests for governance consistency; no network or external tools."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'verify_governance.py'
spec = importlib.util.spec_from_file_location('verify_governance', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in module.CANONICAL:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('stub', encoding='utf-8')
        self.commit = 'a' * 40
        self.state = {
            'schema': 'project-state/v1',
            'repository': 'r20942097-hue/faaff',
            'default_branch': 'main',
            'gates': {'P0': 'active', 'PUBLICATION_HOLD': 'active',
                      'NO_NEW_INTERNAL_PUSH': 'active'},
            'permissions': {'always_allowed': ['read'],
                            'requires_owner_approval': ['merge']},
            'pinned_import': {'source_commit': self.commit},
            'heads': {'main_before_governance_pr': '0' * 40},
        }
        self.projects = {'repositories': [{'id': 's', 'observed_head': self.commit},
                                           {'id': 'faaff', 'observed_head': '1' * 40}]}
        self.imported = {'source_commit': self.commit}
        self.save()

    def save(self):
        for path, data in [('ai/PROJECT_STATE.json', self.state),
                           ('ai/projects.json', self.projects),
                           ('ai/imports/s.json', self.imported)]:
            (self.root / path).write_text(json.dumps(data), encoding='utf-8')

    def test_clean_metadata_passes(self):
        self.assertEqual(module.verify(self.root), [])

    def test_historical_head_not_treated_as_current_head(self):
        self.state['heads']['main_before_governance_pr'] = 'f' * 40
        self.save()
        self.assertEqual(module.verify(self.root), [])

    def test_mismatched_pinned_sha_fails(self):
        self.state['pinned_import']['source_commit'] = 'b' * 40
        self.save()
        self.assertIn('s pinned source commit', ' '.join(module.verify(self.root)))

    def test_duplicate_s_repo_fails(self):
        self.projects['repositories'].append({'id': 's', 'observed_head': self.commit})
        self.save()
        self.assertIn('exactly one s repository', ' '.join(module.verify(self.root)))

    def test_invalid_schema_fails(self):
        self.state['schema'] = 'unknown'
        self.save()
        self.assertIn('unexpected PROJECT_STATE schema', module.verify(self.root))

    def test_permission_structure_fails(self):
        self.state['permissions']['always_allowed'] = []
        self.save()
        self.assertTrue(any('always_allowed' in x for x in module.verify(self.root)))

    def test_missing_required_gate_fails(self):
        del self.state['gates']['NO_NEW_INTERNAL_PUSH']
        self.save()
        self.assertTrue(any('publication gates' in x for x in module.verify(self.root)))

    def test_missing_canonical_file_fails(self):
        (self.root / 'AGENTS.md').unlink()
        self.assertTrue(any('AGENTS.md' in x for x in module.verify(self.root)))

    def test_broken_json_fails_cleanly(self):
        (self.root / 'ai/imports/s.json').write_text('not json', encoding='utf-8')
        self.assertTrue(any('invalid JSON' in x for x in module.verify(self.root)))

    def test_symlink_canonical_rejected(self):
        file = self.root / 'AGENTS.md'
        file.unlink()
        try:
            file.symlink_to(self.root / 'ai/HANDOFF.md')
        except (OSError, NotImplementedError):
            self.skipTest('symlink unsupported')
        self.assertTrue(any('symlinked' in x for x in module.verify(self.root)))


if __name__ == '__main__':
    unittest.main()
