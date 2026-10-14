import copy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configuration import validate
from manage import build, check


class ConfigurationTests(unittest.TestCase):
    def test_repository_ref_must_identify_a_full_commit(self):
        with TemporaryDirectory() as root:
            valid = {'sources': [{'name': 'repo', 'path': 'repo', 'kind': 'repository',
                                  'repository': 'https://github.com/owner/repo', 'repository_ref': 'a'*40}]}
            self.assertEqual(validate(root, valid), valid)
            for value in ['main', '../escape', True, 'a'*39]:
                invalid = copy.deepcopy(valid)
                invalid['sources'][0]['repository_ref'] = value
                with self.assertRaises(ValueError):
                    validate(root, invalid)

    def test_wrong_json_types_rejected(self):
        valid = {'sources': [{'name': 'repo', 'path': 'repo', 'kind': 'repository'}]}
        variants = []
        for field in ['name', 'path', 'kind', 'repository', 'include']:
            config = copy.deepcopy(valid)
            config['sources'][0][field] = {'unexpected': True}
            variants.append(config)
        with TemporaryDirectory() as root:
            for config in variants:
                with self.assertRaises(ValueError):
                    validate(root, config)
    def test_duplicate_root_or_unsafe_sources_rejected(self):
        valid = {'sources': [{'name': 'repo', 'path': 'repo', 'kind': 'repository'}]}
        cases = [copy.deepcopy(valid) for _ in range(4)]
        cases[0]['sources'].append(cases[0]['sources'][0])
        cases[1]['sources'][0]['path'] = '..'
        cases[2]['sources'][0]['name'] = '../escape'
        cases[3]['sources'][0]['path'] = '.'
        with TemporaryDirectory() as root:
            for config in cases:
                with self.assertRaises(ValueError):
                    validate(root, config)

    def test_generated_directory_link_rejected(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as outside:
            root = Path(directory)
            (root / 'catalog').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                validate(root, {'sources': []})

    def test_portable_mode_uses_direct_links_without_symlinks(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'repo').mkdir()
            (root / 'repo/a b.md').write_text('source')
            config = {'link_mode': 'direct', 'sources': [{'name': 'repo', 'path': 'repo', 'kind': 'repository'}]}
            build(root, config)
            self.assertEqual(check(root, config), [])
            self.assertFalse(any(p.is_symlink() for p in root.rglob('*')))
            self.assertIn('../../repo/a%20b.md', (root / 'catalog/generated/inventory.md').read_text())
            self.assertIn("'../../'+r.original", (root / 'catalog/generated/inventory.html').read_text())

    def test_ignored_layout_alias_is_rejected_even_with_link_mode(self):
        with TemporaryDirectory() as root:
            for config in [{'sources': [], 'layout': 'direct'}, {'sources': [], 'layout': 'direct', 'link_mode': 'direct'}]:
                with self.subTest(config=config), self.assertRaisesRegex(ValueError, 'link_mode'):
                    validate(root, config)
