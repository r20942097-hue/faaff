"""Pinned v2 candidate import/rollback evidence, no real browser needed."""
import copy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from firefox_candidate_probe import (
    SENTINEL, CONTROL_HOSTS, pinned_candidate_rules, managed_policy,
    write_blocked_report
)
from firefox_proxy_probe import IsolatedProxy, PAGE
from verify_firefox_candidate import audit


class CandidateManagedPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules,cls.hosts,cls.source=pinned_candidate_rules()

    def test_candidate_source_is_exactly_pinned(self):
        self.assertEqual(len(self.rules),38)
        self.assertEqual(len(self.hosts),38)
        self.assertEqual(len(set(self.hosts)),38)
        self.assertEqual(len(self.source["source_commit"]),40)
        self.assertEqual(len(self.source["git_blob_sha"]),40)

    def test_managed_storage_has_no_trusted_scriptlets(self):
        manifest=managed_policy(self.rules)
        self.assertEqual(manifest["name"],"uBlock0@raymondhill.net")
        self.assertEqual(manifest["type"],"storage")
        self.assertEqual(manifest["data"]["toOverwrite"]["filters"][:-1],self.rules)
        self.assertEqual(len(manifest["data"]["toOverwrite"]["filters"]),39)
        self.assertTrue(all("$third-party" in x for x in
                            manifest["data"]["toOverwrite"]["filters"]))
        self.assertNotIn("filterLists",manifest["data"]["toOverwrite"])
        self.assertNotIn("toAdd",manifest["data"])

    def example(self):
        allhosts=[*self.hosts,SENTINEL,*CONTROL_HOSTS]
        stage={h:False for h in allhosts}
        for control in CONTROL_HOSTS:
            stage[control]=True
        stock=dict(stage)
        stock[SENTINEL]=True
        stock[self.hosts[0]]=True
        restored=dict(stock)
        return {
            "schema":"upc-firefox-managed-candidates/v1",
            "status":"PASS",
            "mode":"EPHEMERAL_MANAGED_STORAGE_THREE_BROWSER_SESSIONS",
            "candidate_source":self.source,
            "selected_candidate_count":38,
            "candidate_hosts":self.hosts,
            "sentinel":SENTINEL,
            "stage_receipts":{"stock":stock,"candidate":stage,"restored":restored},
            "synthetic_safety":{phase:{"signed_url_preserved":True,
                                       "auth_cookie_roundtrip":True,
                                       "media_range_206":True}
                                for phase in ("stock","candidate","restored")},
            "incremental_synthetic_hosts":[self.hosts[0]],
            "incremental_synthetic_host_count":1,
            "policy_removed":True,
            "firefox_versions":{"stock":"157.0","candidate":"157.0","restored":"157.0"},
            "controls":list(CONTROL_HOSTS),
            "https_connect":"DENIED",
            "proxy_forwarding":"DISABLED",
            "real_site_efficacy":"NOT_RUN",
            "actual_user_configuration":"NOT_VERIFIED",
            "credentials_and_site_media":"NOT_RUN",
            "rules_published":0,
            "release":"NO_GO",
        }

    def test_complete_evidence_is_accepted(self):
        self.assertEqual(audit(self.example()),[])

    def test_failure_and_forged_effectiveness_rejected(self):
        for field,value in (
            ("status","PARTIAL"),("rules_published",1),("release","GO"),
            ("policy_removed",False),("real_site_efficacy","PASS"),
            ("actual_user_configuration","VERIFIED"),
            ("selected_candidate_count",39),
            ("incremental_synthetic_host_count",15)):
            with self.subTest(field=field):
                doc=self.example()
                doc[field]=value
                self.assertTrue(audit(doc))

    def test_candidate_synthetic_normal_flows_must_survive(self):
        for phase in ("stock", "candidate", "restored"):
            for name in ("signed_url_preserved", "auth_cookie_roundtrip", "media_range_206"):
                edited=self.example()
                edited["synthetic_safety"][phase][name]=False
                with self.subTest(phase=phase, name=name):
                    self.assertTrue(audit(edited))
        edited=self.example()
        del edited["synthetic_safety"]["candidate"]["media_range_206"]
        self.assertTrue(audit(edited))

    def test_incomplete_browser_rules_and_rollback_rejected(self):
        doc=self.example()
        doc["stage_receipts"]["candidate"][self.hosts[0]]=True
        self.assertTrue(audit(doc))
        doc=self.example()
        doc["stage_receipts"]["restored"][self.hosts[0]]=False
        self.assertTrue(audit(doc))
        doc=self.example()
        doc["stage_receipts"]["candidate"][CONTROL_HOSTS[0]]=False
        self.assertTrue(audit(doc))
        doc=self.example()
        doc["stage_receipts"]["candidate"][SENTINEL]=True
        self.assertTrue(audit(doc))

    def test_partial_candidate_failure_is_recorded_without_promoting_pass(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as d:
            evidence = Path(d) / "candidate-blocked.json"
            output = write_blocked_report(
                evidence, stage="candidate", reason="STAGE_VALUEERROR",
                results={"stock":{"synthetic.example.org":True}},
                versions={"stock":"157.0"},
                safety={"stock":{"signed_url_preserved":True}},
                policy_removed=True, source=self.source, xpi_sha="a"*64,
            )
            self.assertEqual(output["status"], "BLOCKED")
            self.assertEqual(output["release"], "NO_GO")
            self.assertEqual(output["candidate_activation"], "NOT_VERIFIED")
            self.assertEqual(output["rules_published"], 0)
            self.assertEqual(json.loads(evidence.read_text()), output)
            self.assertTrue(audit(output))
    def test_proxy_batch_has_allowlisted_candidate_hosts_only(self):
        server=IsolatedProxy(extra_hosts=[*self.hosts,SENTINEL])
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            token="a"*32
            conn=HTTPConnection("127.0.0.1",server.server_port,timeout=4)
            try:
                conn.request("GET",
                    f"http://{PAGE}:{server.server_port}/batch?token={token}")
                r=conn.getresponse()
                self.assertEqual(r.status,200)
                html=r.read().decode()
                for host in [*self.hosts,SENTINEL,*CONTROL_HOSTS]:
                    self.assertIn("http://"+host+":",html)
                self.assertNotIn("<script",html)
            finally:
                conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__=="__main__":
    unittest.main()
