"""No-network tests of official uBO Lite asset/provenance/observed stock claims."""
import copy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from fetch_official_ubol import LOCK,verify_lock,validate_bytes,safe_entries,unpack_verified
from chromium_dnr_probe import CONTROLS,KINDS,SENTINEL,compile_dnr
from verify_ubol_official import audit


class OfficialUBOLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock=verify_lock(json.loads(LOCK.read_text(encoding="utf-8")))
        cls.hosts,_,cls.provenance=compile_dnr()

    def test_vendor_release_lock_exact(self):
        self.assertEqual(self.lock["release_tag"],"2026.1026.1812")
        self.assertEqual(len(self.lock["sha256"]),64)
        self.assertEqual(self.lock["size"],9009606)
        with self.assertRaises(ValueError):
            changed=dict(self.lock,publication="GO")
            verify_lock(changed)
        with self.assertRaises(ValueError):
            validate_bytes(b"fabricated vendor archive",self.lock)

    def test_zip_slip_and_symlinks_are_rejected(self):
        for bad in ("../outside","/abs/manifest.json","./manifest.json",
                    "a\\b","chromium/../outside","chromium:evil"):
            with self.subTest(path=bad):
                data=BytesIO()
                with ZipFile(data,"w") as z:
                    z.writestr(bad,b"fake")
                with ZipFile(BytesIO(data.getvalue())) as z:
                    with self.assertRaises(ValueError):
                        safe_entries(z)

    def test_manifest_and_enabled_rulesets_must_match_original_release(self):
        minimal={"manifest_version":3,
                 "version":self.lock["release_tag"],
                 "permissions":["declarativeNetRequest"],
                 "background":{"service_worker":"/js/background.js"},
                 "declarative_net_request":{"rule_resources":[
                    {"id":name,"path":"/rulesets/main/"+name+".json","enabled":True}
                    for name in self.lock["expected_static_rulesets"]]}}
        data=BytesIO()
        with ZipFile(data,"w") as z:
            z.writestr("chromium/manifest.json",json.dumps(minimal))
            for name in self.lock["expected_static_rulesets"]:
                z.writestr("chromium/rulesets/main/"+name+".json","[]")
        with tempfile.TemporaryDirectory() as d:
            destination=Path(d)/"vendor"
            destination.mkdir()
            result=unpack_verified(data.getvalue(),destination,self.lock)
            self.assertEqual(result["version"],self.lock["release_tag"])
            self.assertEqual(len(result["enabled_manifest_rulesets"]),4)
            self.assertTrue((destination/"manifest.json").exists())
            with self.assertRaises(ValueError):
                unpack_verified(data.getvalue(),destination,self.lock)
        minimal["version"]="fake"
        data=BytesIO()
        with ZipFile(data,"w") as z:
            z.writestr("manifest.json",json.dumps(minimal))
            for name in self.lock["expected_static_rulesets"]:
                z.writestr("rulesets/main/"+name+".json","[]")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                unpack_verified(data.getvalue(),Path(d),self.lock)

    def example(self):
        allhosts=[*self.hosts,SENTINEL,*CONTROLS]
        baseline={host:True for host in allhosts}
        # Do not assume all blockers block all hostnames.
        stock=dict(baseline)
        stock[self.hosts[0]]=False
        def receipts(item):
            return {kind:[dict(item),dict(item)] for kind in KINDS}
        return {
            "schema":"upc-official-ubol-chromium-stock/v1",
            "result":"PASS",
            "source":"uBlockOrigin/uBOL-home",
            "official_tag":self.lock["release_tag"],
            "official_asset_sha256":self.lock["sha256"],
            "official_asset_size":self.lock["size"],
            "browser":"PLAYWRIGHT_BUNDLED_CHROMIUM",
            "official_ubol_installed":True,
            "official_enabled_static_rulesets":self.lock["expected_static_rulesets"],
            "candidate_source":self.provenance,
            "candidate_rules_installed":False,
            "candidate_hosts":self.hosts,"sentinel":SENTINEL,
            "controls":list(CONTROLS),"resource_types":list(KINDS),
            "before":receipts(baseline),
            "official_stock":receipts(stock),
            "restored":receipts(baseline),
            "first_party_candidate_receipts":{
                stage:{kind:[True,True] for kind in KINDS}
                for stage in ("baseline","dnr","restored")},
            "synthetic_protocol_safety":{
                stage:{"signed_url_preserved":True,"auth_cookie_roundtrip":True,
                       "media_range_206":True}
                for stage in ("baseline","ubol","restored")},
            "coverage":{kind:{
                "browser_baseline_received":self.hosts,
                "browser_baseline_not_received_unknown_cause":[],
                "blocked_by_official_ubol_stock_vs_browser_only":[self.hosts[0]],
                "still_received_with_official_stock":self.hosts[1:],
                "candidate_hosts_total":38,
            } for kind in KINDS},
            "comparison_limitation":"BROWSER_ONLY_VS_OFFICIAL_UBOL_NOT_UBOL_PLUS_CANDIDATES",
            "browser_baseline_missing_root_cause":"NOT_ESTABLISHED",
            "no_second_active_blocker":True,
            "outbound_proxy":"DENIED",
            "real_site_requests":"NOT_RUN",
            "user_profiles":"NOT_TOUCHED",
            "rules_published":0,"publication":"NO_GO",
        }

    def test_archived_vendor_ci_result_does_not_overstate_candidate_gain(self):
        data=json.loads((Path(__file__).resolve().parent/
                         "verification/ubol-official-stock-validation.json").read_text())
        self.assertEqual(data["schema"],"upc-official-ubol-stock-ci-index/v1")
        self.assertEqual(data["run_id"],41157094931)
        self.assertEqual(data["tested_commit"],
                         "0fe5ac4016cc814d15b582b11198fa3a64c56afc")
        self.assertEqual(data["zip_sha256"],self.lock["sha256"])
        for kind in KINDS:
            self.assertEqual(data[kind]["baseline_received"],34)
            self.assertEqual(data[kind]["blocked_by_official_stock_from_received"],33)
            self.assertEqual(data[kind]["stock_still_received"],["rudderstack.com"])
            self.assertEqual(len(data[kind]["baseline_missing_without_extension"]),4)
        self.assertFalse(data["candidate_rules_loaded_in_official_ubol"])
        self.assertEqual(data["real_website_efficacy"],"NOT_RUN")
        self.assertEqual(data["root_cause_of_pre_extension_missing_hosts"],"UNKNOWN")
        self.assertEqual(data["rules_published"],0)
        self.assertEqual(data["release"],"NO_GO")

    def test_complete_narrow_evidence_accepted(self):
        self.assertEqual(audit(self.example()),[])

    def test_protocol_safety_is_required_across_all_stock_stages(self):
        for stage in ("baseline","ubol","restored"):
            for feature in ("signed_url_preserved","auth_cookie_roundtrip","media_range_206"):
                record=self.example()
                record["synthetic_protocol_safety"][stage][feature]=False
                with self.subTest(stage=stage,feature=feature):
                    self.assertTrue(audit(record))
        record=self.example()
        del record["synthetic_protocol_safety"]["ubol"]["media_range_206"]
        self.assertTrue(audit(record))

    def test_forged_coverage_or_release_is_rejected(self):
        for field,value in (
            ("official_ubol_installed",False),("candidate_rules_installed",True),
            ("rules_published",1),("publication","GO"),
            ("source","unofficial"),("no_second_active_blocker",False),
            ("comparison_limitation","USER_STOCK_AND_CANDIDATES_VERIFIED"),
            ("official_asset_sha256","0"*64),("real_site_requests","VERIFIED")):
            x=self.example()
            x[field]=value
            with self.subTest(field=field):
                self.assertTrue(audit(x))

        x=self.example()
        x["coverage"]["script"]["still_received_with_official_stock"]=[]
        self.assertTrue(audit(x))
        x=self.example()
        x["official_stock"]["image"][0][CONTROLS[0]]=False
        self.assertTrue(audit(x))
        x=self.example()
        x["restored"]["image"][0][self.hosts[0]]=False
        self.assertTrue(audit(x))
        x=self.example()
        x["official_enabled_static_rulesets"]=["easylist"]
        self.assertTrue(audit(x))


if __name__=="__main__":
    unittest.main()
