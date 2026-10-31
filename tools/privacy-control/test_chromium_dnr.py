"""Regression tests for the *isolated* Chromium MV3 DNR experiment."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from chromium_dnr_probe import compile_dnr,build_extension,verify_lifecycle,SENTINEL,CONTROLS,KINDS
from verify_chromium_dnr import audit


class ChromiumDNRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hosts,cls.rules,cls.source=compile_dnr()

    def test_all_candidate_rules_are_exactly_pinned(self):
        self.assertEqual(len(self.hosts),38)
        self.assertEqual(len(self.rules),39)
        self.assertEqual(len({r["id"] for r in self.rules}),39)
        self.assertEqual(len({r["condition"]["urlFilter"] for r in self.rules}),39)
        for host,rule in zip([*self.hosts,SENTINEL],self.rules):
            self.assertEqual(rule["action"],{"type":"block"})
            self.assertEqual(rule["priority"],1)
            self.assertEqual(rule["condition"]["domainType"],"thirdParty")
            self.assertEqual(rule["condition"]["urlFilter"],"||"+host+"^")
            self.assertEqual(rule["condition"]["resourceTypes"],["image","script"])
            self.assertEqual(set(rule),{"id","priority","action","condition"})

    def test_manifest_contains_only_local_ephemeral_static_rules(self):
        with tempfile.TemporaryDirectory() as d:
            directory=build_extension(Path(d),self.rules)
            manifest=json.loads((directory/"manifest.json").read_text())
            self.assertEqual(manifest["manifest_version"],3)
            self.assertEqual(manifest["permissions"],["declarativeNetRequest"])
            self.assertNotIn("webRequest",manifest["permissions"])
            self.assertNotIn("storage",manifest["permissions"])
            self.assertNotIn("update_url",manifest)
            self.assertEqual(manifest["declarative_net_request"]["rule_resources"],
                             [{"id":"upc-candidate","enabled":True,"path":"rules.json"}])
            self.assertEqual(json.loads((directory/"rules.json").read_text()),self.rules)
            self.assertFalse((directory/"package.json").exists())

    def example(self):
        targets=[*self.hosts,SENTINEL,*CONTROLS]
        stock={host:True for host in targets}
        blocked={host:(host in CONTROLS) for host in targets}
        def stage(single):
            return {kind:[dict(single),dict(single)] for kind in KINDS}
        return {
            "schema":"upc-chromium-mv3-dnr-lab/v1",
            "result":"PASS",
            "browser":"PLAYWRIGHT_BUNDLED_CHROMIUM",
            "actual_ubol_loaded":"NOT_RUN",
            "candidate_source":self.source,
            "compiled_rules":39,
            "candidate_hosts":self.hosts,
            "sentinel":SENTINEL,
            "controls":list(CONTROLS),
            "resource_types":list(KINDS),
            "baseline_receipts":stage(stock),
            "dnr_receipts":stage(blocked),
            "restored_receipts":stage(stock),
            "proxy_forwarding":"DISABLED",
            "https_connect":"DENIED",
            "real_website_traffic":"NOT_RUN",
            "real_user_stock_lists":"NOT_RUN",
            "user_browser_profiles":"NOT_TOUCHED",
            "rules_published":0,
            "release":"NO_GO",
        }

    def test_full_pass_evidence(self):
        record=self.example()
        self.assertTrue(verify_lifecycle(record["baseline_receipts"],
                                         record["dnr_receipts"],record["restored_receipts"],
                                         self.hosts))
        self.assertEqual(audit(record),[])

    def test_invalid_dnr_results_or_rollback_rejected(self):
        for field,kind,host,value in (
            ("baseline_receipts","image",self.hosts[0],False),
            ("dnr_receipts","script",self.hosts[0],True),
            ("dnr_receipts","image",CONTROLS[0],False),
            ("dnr_receipts","script",SENTINEL,True),
            ("restored_receipts","script",self.hosts[0],False),
        ):
            record=self.example()
            record[field][kind][0][host]=value
            with self.subTest(field=field,kind=kind,host=host):
                self.assertTrue(audit(record))

    def test_scope_and_identity_forgery_rejected(self):
        for key,value in (
            ("result","PARTIAL"),("actual_ubol_loaded","PASS"),
            ("real_website_traffic","VERIFIED"),
            ("real_user_stock_lists","VERIFIED"),
            ("proxy_forwarding","ENABLED"),
            ("https_connect","ALLOWED"),
            ("release","GO"),("rules_published",1),
            ("compiled_rules",38),("browser","MOCK"),
        ):
            record=self.example()
            record[key]=value
            with self.subTest(key=key):
                self.assertTrue(audit(record))

    def test_one_round_is_never_enough(self):
        for phase in ("baseline_receipts","dnr_receipts","restored_receipts"):
            record=self.example()
            record[phase]["image"].pop()
            self.assertTrue(audit(record))
        record=self.example()
        record["dnr_receipts"]["script"][1][self.hosts[0]]=True
        self.assertTrue(audit(record))


if __name__=="__main__":
    unittest.main()
