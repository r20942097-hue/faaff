import unittest

import validate_filters as vf


class ValidatorTests(unittest.TestCase):
    def test_repository_state_is_valid(self):
        errors, _warnings = vf.validate()
        self.assertEqual(errors, [])

    def test_valid_hostname(self):
        for host in ["example.com", "sub.example.co.jp", "xn--bcher-kva.example"]:
            with self.subTest(host=host):
                self.assertTrue(vf.valid_hostname(host))

    def test_invalid_hostname(self):
        for host in [
            "localhost",
            "127.0.0.1",
            "example",
            ".example.com",
            "example.com.",
            "example..com",
            "-example.com",
            "example-.com",
            "exa_mple.com",
        ]:
            with self.subTest(host=host):
                self.assertFalse(vf.valid_hostname(host))

    def test_safe_repo_path_rejects_parent_escape(self):
        self.assertIsNone(vf.safe_repo_path("../outside.txt"))

    def test_conservative_rule_shape(self):
        self.assertIsNotNone(vf.hostname_rule.fullmatch("||example.com^$third-party"))
        self.assertIsNone(vf.hostname_rule.fullmatch("||example.com^"))
        self.assertIsNone(vf.hostname_rule.fullmatch("example.com"))
        self.assertIsNone(vf.hostname_rule.fullmatch("||example.com^$document"))


if __name__ == "__main__":
    unittest.main()
