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
            f"http://{PAGE}:{self.proxy.server_port}/index?host=evil.test&token={token}",
            f"http://{PAGE}:{self.proxy.server_port}/not-allowed?token={token}",
            f"http://{PAGE}:{self.proxy.server_port}/index?host={TRACKER}&token=abc",
        ]:
            with self.subTest(address=address):
                code, _ = self.get(address)
                self.assertEqual(code, 403)
        self.assertEqual(len(self.proxy.hits), 0)

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
            "real_websites":"NOT_RUN","user_profile":"NOT_TOUCHED",
            "candidate_rules_installed":False,"released_rules":0,
            "publication":"NO_GO",
        }

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
