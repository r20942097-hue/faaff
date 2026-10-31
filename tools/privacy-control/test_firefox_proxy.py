"""No-outbound proxy request routing, and honest browser evidence-gate tests."""
from http.client import HTTPConnection
import copy
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefox_proxy_probe import IsolatedProxy, HOSTS, TRACKER, PAGE
from verify_firefox_proxy import audit


class ProxyContainmentTests(unittest.TestCase):
    def setUp(self):
        self.proxy = IsolatedProxy()
        self.thread = threading.Thread(target=self.proxy.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.proxy.shutdown()
        self.proxy.server_close()
        self.thread.join(timeout=4)

    def get(self, url):
        connection = HTTPConnection("127.0.0.1", self.proxy.server_port, timeout=3)
        try:
            connection.request("GET", url)
            response = connection.getresponse()
            code, body = response.status, response.read()
            return code, body
        finally:
            connection.close()

    def test_absolute_http_request_stays_inside_synthetic_proxy(self):
        token = "a" * 32
        host = "assets.example.com"
        code, html = self.get(
            f"http://{PAGE}:{self.proxy.server_port}/index?host={host}&token={token}")
        self.assertEqual(code, 200)
        self.assertIn((f"http://{host}:{self.proxy.server_port}").encode(), html)
        code, image = self.get(
            f"http://{host}:{self.proxy.server_port}/safe.png?token={token}")
        self.assertEqual(code, 200)
        self.assertTrue(image.startswith(b"GIF89a"))
        self.assertTrue(self.proxy.seen(host, token))

    def test_unapproved_host_or_port_refused(self):
        token = "b" * 32
        for address in [
            f"http://openai.com:{self.proxy.server_port}/safe.png?token={token}",
            f"http://{PAGE}:9999/index?host={TRACKER}&token={token}",
            f"http://{PAGE}:bad/index?host={TRACKER}&token={token}",
            f"http://{PAGE}:{self.proxy.server_port}/index?host=evil.test&token={token}",
            f"http://{PAGE}:{self.proxy.server_port}/not-allowed?token={token}",
            f"http://{PAGE}:{self.proxy.server_port}/index?host={TRACKER}&token=abc",
        ]:
            with self.subTest(address=address):
                code, _ = self.get(address)
                self.assertEqual(code, 403)
        self.assertEqual(len(self.proxy.hits), 0)

    def test_signed_url_integrity_rejects_removed_or_changed_parameter(self):
        token = "c" * 32
        tag = "synthetic-campaign"
        digest = self.proxy.signed_digest(token, tag)
        base = f"http://{PAGE}:{self.proxy.server_port}/signed?token={token}"
        ok, body = self.get(base + f"&utm_source={tag}&sig={digest}")
        self.assertEqual(ok, 200)
        self.assertIn(b"UPC_SIGNED_OK", body)
        for bad in (base + f"&sig={digest}",
                    base + f"&utm_source=changed&sig={digest}",
                    base + f"&utm_source={tag}&sig=" + "0"*64):
            with self.subTest(url=bad):
                code, _ = self.get(bad)
                self.assertEqual(code, 403)

    def test_synthetic_auth_requires_session_cookie(self):
        token = "d" * 32
        base = f"http://{PAGE}:{self.proxy.server_port}"
        code, _ = self.get(base + f"/auth/check?token={token}")
        self.assertEqual(code, 403)
        connection = HTTPConnection("127.0.0.1", self.proxy.server_port, timeout=3)
        try:
            connection.request("GET", base + f"/auth/login?token={token}")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn("HttpOnly", response.getheader("Set-Cookie"))
            response.read()
            connection.request("GET", base + f"/auth/check?token={token}",
                               headers={"Cookie":"upc_lab=synthetic"})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"UPC_AUTH_COOKIE_OK")
        finally:
            connection.close()

    def test_synthetic_media_range_requires_byte_request(self):
        token = "e" * 32
        address = f"http://{PAGE}:{self.proxy.server_port}/media?token={token}"
        code, _ = self.get(address)
        self.assertEqual(code, 403)
        connection = HTTPConnection("127.0.0.1", self.proxy.server_port, timeout=3)
        try:
            connection.request("GET", address, headers={"Range":"bytes=0-31"})
            response = connection.getresponse()
            self.assertEqual(response.status, 206)
            self.assertEqual(response.getheader("Content-Range"), "bytes 0-31/256")
            self.assertEqual(response.read(), bytes(range(32)))
        finally:
            connection.close()

    def test_https_connect_refused(self):
        connection = HTTPConnection("127.0.0.1", self.proxy.server_port, timeout=3)
        try:
            connection.request("CONNECT", "example.com:443")
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
        finally:
            connection.close()
        self.assertGreaterEqual(self.proxy.denied, 1)


class ProxyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads(
            (Path(__file__).resolve().parent / "verification/firefox-ubo-xpi-lock.json").read_text())
        stages = {host: True for host in HOSTS}
        with_addon = dict(stages)
        with_addon[TRACKER] = False
        self.example = {
            "schema":"upc-firefox-isolated-proxy/v1",
            "status":"PASS", "reason":"TARGET_SPECIFIC_LOOPBACK_ONLY",
            "firefox_version":"157.0",
            "ubo_version":self.lock["tag"],
            "xpi_sha256":self.lock["sha256"],
            "network_scope":"HTTP_ONLY_RESTRICTED_PROXY_LOOPBACK_NO_FORWARD",
            "https_tunneling":"DENIED", "target_host":TRACKER,
            "controls":{"first_party":"pages.example.com","same_site":"assets.example.com",
                        "other_site":"unrelated.example.org"},
            "observations":{"before":stages,"with_addon":with_addon,"after_uninstall":stages},
            "extension_uninstalled":True,"denied_proxy_requests":1,
            "safety_controls":{phase:{"signed_url_preserved":True,
                                        "auth_cookie_roundtrip":True,
                                        "media_range_206":True}
                               for phase in ("before","with_addon","after_uninstall")},
            "real_websites":"NOT_RUN","user_profile":"NOT_TOUCHED",
            "candidate_rules_installed":False,"released_rules":0,
            "publication":"NO_GO",
        }

    def test_historic_ambiguous_trials_preserved_separately_from_new_probe(self):
        home = Path(__file__).resolve().parent / "verification"
        old = json.loads((home / "firefox-isolation-diagnostic.json").read_text())
        new = json.loads((home / "firefox-proxy-validation.json").read_text())
        self.assertEqual(old["status"], "BLOCKED")
        self.assertEqual(len(old["runs"]), 5)
        self.assertEqual(old["observed"]["target_specificity"], "NOT_ESTABLISHED")
        self.assertEqual(new["schema"], "upc-firefox-proxy-validation/v1")
        self.assertEqual(new["latest_successful_run"]["workflow_run"], 41097729808)
        self.assertEqual(new["latest_successful_run"]["result"], "PASS")
        self.assertEqual(new["latest_successful_run"]["commit"],
                         "0c921adf602441208448b87429c393e5b384c4ea")
        self.assertEqual(new["observations"]["proxy_rejected_requests"], 57)
        self.assertEqual(new["observations"]["with_addon"]["target_received"], False)
        for control in ("first_party_received", "same_site_received",
                        "unrelated_third_party_received"):
            self.assertIs(new["observations"]["with_addon"][control], True)
        self.assertTrue(all(new["observations"]["after_uninstall"].values()))
        self.assertEqual(new["limits"]["publication"], "NO_GO")
        self.assertEqual(new["limits"]["production_websites"], "NOT_RUN")

    def test_full_lifecycle_evidence_requires_controls_and_rollback(self):
        self.assertEqual(audit(self.example, self.lock), [])

    def test_invalid_pass_claim_rejected(self):
        for stage, host in [("before", TRACKER),("with_addon", "assets.example.com"),
                            ("with_addon", "unrelated.example.org"),
                            ("after_uninstall", TRACKER)]:
            record = copy.deepcopy(self.example)
            record["observations"][stage][host] = not record["observations"][stage][host]
            with self.subTest(stage=stage,host=host):
                self.assertTrue(audit(record,self.lock))

    def test_synthetic_safety_coverage_required_in_all_three_phases(self):
        for phase in ("before", "with_addon", "after_uninstall"):
            for kind in ("signed_url_preserved", "auth_cookie_roundtrip", "media_range_206"):
                edited = copy.deepcopy(self.example)
                edited["safety_controls"][phase][kind] = False
                with self.subTest(phase=phase,kind=kind):
                    self.assertTrue(audit(edited,self.lock))
        edited = copy.deepcopy(self.example)
        del edited["safety_controls"]["with_addon"]["media_range_206"]
        self.assertTrue(audit(edited,self.lock))

    def test_missing_rollback_or_forged_publication_rejected(self):
        for key,value in [("extension_uninstalled",False),
                          ("publication","GO"),("released_rules",1),
                          ("real_websites","PASS"),
                          ("network_scope","PUBLIC_NETWORK"),
                          ("candidate_rules_installed",True)]:
            record=copy.deepcopy(self.example)
            record[key]=value
            with self.subTest(key=key):
                self.assertTrue(audit(record,self.lock))

    def test_blocked_evidence_accepted_only_as_blocked(self):
        record=copy.deepcopy(self.example)
        record["status"]="BLOCKED"
        record["reason"]="BENIGN_CONTROL_BLOCKED"
        record["observations"]["with_addon"]["assets.example.com"]=False
        self.assertEqual(audit(record,self.lock),[])
        record["status"]="PASS"
        self.assertTrue(audit(record,self.lock))


if __name__=="__main__":
    unittest.main()
