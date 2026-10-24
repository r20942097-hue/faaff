from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from apply_catalogue_update import prepare


class PrepareTests(unittest.TestCase):
    def test_existing_output_is_not_changed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'work/output'
            target.mkdir(parents=True)
            (target / 'keep').write_text('existing')
            with patch('apply_catalogue_update.extract') as extractor:
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    prepare(root, 'base', 'update', 'a' * 64, 'work/output')
                extractor.assert_not_called()
            self.assertEqual((target / 'keep').read_text(), 'existing')

    def test_failed_application_removes_only_created_target(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            def extracted(archive, sha, path):
                path.mkdir(parents=True)
                (path / 'fixture').write_text('temporary')
                return 1
            with patch('apply_catalogue_update.extract', side_effect=extracted), patch('apply_catalogue_update.apply_update', side_effect=ValueError('bad fixture')):
                with self.assertRaisesRegex(ValueError, 'bad fixture'):
                    prepare(root, 'base', 'update', 'a' * 64, 'work/output')
            self.assertFalse((root / 'work/output').exists())
            self.assertEqual(list((root / 'work/catalogue-update-staging').iterdir()), [])

    def test_failed_extraction_does_not_delete_a_racing_user_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            def raced(archive, sha, path):
                path.mkdir(parents=True)
                if archive == 'base':
                    (path / 'keep').write_text('user-created fixture')
                    raise ValueError('destination now exists')
                return 1
            with patch('apply_catalogue_update.extract', side_effect=raced):
                with self.assertRaisesRegex(ValueError, 'now exists'):
                    prepare(root, 'base', 'update', 'a' * 64, 'work/output')
            self.assertEqual((root / 'work/output/keep').read_text(), 'user-created fixture')

    def test_success_prepares_new_target_and_protected_output_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            def extracted(archive, sha, path):
                path.mkdir(parents=True)
                return 1
            with patch('apply_catalogue_update.extract', side_effect=extracted), patch('apply_catalogue_update.apply_update', return_value=17):
                self.assertEqual(prepare(root, 'base', 'update', 'a' * 64, 'work/output'), 17)
            self.assertTrue((root / 'work/output').is_dir())
            with self.assertRaises(ValueError):
                prepare(root, 'base', 'update', 'a' * 64, 'work/.git/output')
