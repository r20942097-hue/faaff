import tempfile
import unittest
from pathlib import Path
from ai.ci_workflow_audit import (
    audit,validate_document,EXPECTED_GROUP,EXPECTED_CANCEL
)

class WorkflowGovernanceTest(unittest.TestCase):
    def base(self):
        return {"name":"Test","on":{"pull_request":{"paths":[".github/workflows/test.yml"]}},
            "permissions":{"contents":"read"},
            "concurrency":{"group":EXPECTED_GROUP,"cancel-in-progress":EXPECTED_CANCEL},
            "jobs":{"check":{"runs-on":"ubuntu-24.04","steps":[
                {"uses":"actions/checkout@"+"a"*40}]}}}

    def test_valid_workflow(self):
        self.assertEqual(validate_document(".github/workflows/test.yml",self.base()),[])
    def test_unscoped_group_rejected(self):
        s=self.base()
        s["concurrency"]["group"]="shared-all-prs"
        self.assertIn("UNSAFE_CONCURRENCY_GROUP",validate_document(".github/workflows/test.yml",s))
    def test_always_cancel_rejected(self):
        s=self.base()
        s["concurrency"]["cancel-in-progress"]=True
        self.assertIn("UNSAFE_CANCEL_POLICY",validate_document(".github/workflows/test.yml",s))
    def test_no_concurrency_rejected(self):
        s=self.base()
        del s["concurrency"]
        self.assertIn("NO_WORKFLOW_CONCURRENCY",validate_document(".github/workflows/test.yml",s))
    def test_non_codeql_write_permissions_rejected(self):
        s=self.base()
        s["permissions"]["contents"]="write"
        self.assertIn("ROOT_PERMISSIONS_NOT_MINIMAL",validate_document(".github/workflows/test.yml",s))
    def test_scoped_codeql_write_allowed(self):
        s=self.base()
        s["permissions"]["security-events"]="write"
        self.assertEqual(validate_document(".github/workflows/codeql.yml",s),[])
    def test_unpinned_action_rejected(self):
        s=self.base()
        s["jobs"]["check"]["steps"][0]["uses"]="actions/checkout@v7"
        self.assertIn("UNPINNED_ACTION",validate_document(".github/workflows/test.yml",s))
    def test_privileged_trigger_rejected(self):
        s=self.base()
        s["on"]["pull_request_target"]=None
        self.assertIn("PRIVILEGED_TRIGGER",validate_document(".github/workflows/test.yml",s))
    def test_self_path_required(self):
        s=self.base()
        s["on"]["pull_request"]["paths"]=["ai/other.py"]
        self.assertIn("WORKFLOW_FILE_NOT_IN_PR_PATHS",validate_document(".github/workflows/test.yml",s))
    def test_missing_workflow_dir_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=audit(tmp)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(r["release_readiness"],"NO_GO")
    def test_actual_yaml_parsed_not_only_regex(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/".github/workflows/test.yml"
            f.parent.mkdir(parents=True)
            content=("name: Example\non:\n  pull_request:\n"
                     "    paths: ['.github/workflows/test.yml']\n"
                     "permissions:\n  contents: read\n"
                     "concurrency:\n  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}\n"
                     "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n"
                     "jobs:\n  check:\n    runs-on: ubuntu-24.04\n"
                     "    steps:\n      - uses: actions/checkout@"+"a"*40+"\n")
            f.write_text(content,encoding="utf-8")
            r=audit(tmp)
            self.assertEqual(r["status"],"PASS",r)
            self.assertEqual(r["checked"],1)
            self.assertEqual(r["product_e2e"],"NOT_RUN")

if __name__=="__main__":
    unittest.main()
