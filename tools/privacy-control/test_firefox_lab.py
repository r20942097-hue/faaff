"""Offline tests for XPI provenance and Firefox real-HTTP evidence gating."""
import copy
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_firefox_xpi import LOCKFILE, verify_bytes, verify_lock
from firefox_ubo_probe import LabServer
from verify_firefox_report import audit


class FirefoxXpiPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))

    def test_signed_extension_is_exactly_pinned(self):
        self.assertTrue(verify_lock(self.lock))
        self.assertEqual(self.lock["tag"], "1.75.0")
        self.assertEqual(self.lock["size"], 4650100)

    def test_tampered_url_or_digest_rejected(self):
        for key, wrong in (
            ("url", "https://example.com/extension.xpi"),
            ("asset", "unsigned.zip"),
            ("tag", "latest"),
            ("sha256", "0"),
            ("size", 1),
            ("publication", "GO"),
        ):
            item = copy.deepcopy(self.lock)
            item[key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_lock(item)
        with self.assertRaises(ValueError):
            verify_bytes(b"fake", self.lock)

    def test_local_http_fixture_serves_only_synthetic_routes(self):
        server = LabServer()
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url = "http://127.0.0.1:" + str(server.server_port)
            with urlopen(url + "/index?host=probe.scorecardresearch.com&token=abc", timeout=4) as r:
                body = r.read().decode()
            self.assertIn("probe.scorecardresearch.com", body)
            self.assertNotIn("<script", body)
            with urlopen(url + "/asset.png?token=abc", timeout=4) as r:
                self.assertEqual(r.status, 200)
            self.assertTrue(server.observed("abc"))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)

    def example_report(self):
        return {
            "schema":"upc-firefox-ubo-loopback/v1",
            "status":"PASS",
            "firefox_version":"157.0",
            "official_ubo_version":self.lock["tag"],
            "xpi_sha256":self.lock["sha256"],
            "target":"probe.scorecardresearch.com",
            "baseline":"RECEIVED","control_before":"RECEIVED",
            "extension_on":"BLOCKED",
            "control_while_installed":"RECEIVED",
            "same_origin_while_installed":"RECEIVED",
            "control_site_relation":"SAME_SITE_DIFFERENT_HOST",
            "independent_third_party_control":"RECEIVED",
            "target_specificity":"PROVISIONAL_LOOPBACK_ONLY",
            "after_uninstall":"RECEIVED",
            "network_scope":"RFC5737_TEST_NET_IP_ASSIGNED_TO_CI_LOOPBACK",
            "actual_live_websites":"NOT_RUN",
            "actual_user_configuration":"NOT_VERIFIED",
            "real_signed_url_safety":"NOT_RUN",
            "published_rules":0,
            "release":"NO_GO",
        }

    def test_minimal_record_audits(self):
        self.assertEqual(audit(self.example_report(), self.lock), [])

    def test_blocked_third_party_control_must_be_reported_as_partial(self):
        record = self.example_report()
        record["status"] = "PARTIAL"
        record["independent_third_party_control"] = "BLOCKED_IN_SYNTHETIC_LOOPBACK"
        record["target_specificity"] = "NOT_ESTABLISHED"
        self.assertEqual(audit(record, self.lock), [])
        record["status"] = "PASS"
        self.assertTrue(audit(record, self.lock))

    def test_forged_lifecycle_or_safety_claim_rejected(self):
        for field, value in (
            ("baseline", "NO_REQUEST"),
            ("extension_on", "NOT_RUN"),
            ("after_uninstall", "NOT_RUN"),
            ("control_while_installed", "BLOCKED"),
            ("actual_live_websites", "PASS"),
            ("actual_user_configuration", "PASS"),
            ("real_signed_url_safety", "PASS"),
            ("network_scope", "UNKNOWN"),
            ("published_rules", 1),
            ("release", "GO"),
            ("firefox_version", "mock"),
        ):
            entry = self.example_report()
            entry[field] = value
            with self.subTest(field=field):
                self.assertTrue(audit(entry, self.lock))


if __name__ == "__main__":
    unittest.main()
