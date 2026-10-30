# CI Governance v11 — 2026-10-30

Read-only baseline: PR #34 head `5cd9405e7e837a7dc6896dec407399c03f770c21` had 19 GitHub Actions YAML files, none with top-level concurrency; repeated PR updates scheduled overlapping expensive test matrices.

All 19 existing workflows now have a consistent per-workflow/per-PR concurrency key. `github.workflow` prevents unrelated workflows from cancelling each other. `github.event.pull_request.number` isolates distinct PRs. `github.run_id` is the fallback on push, schedule and workflow_dispatch, preventing unrelated non-PR runs from cancelling one another. `cancel-in-progress` is true only for pull_request events.

The version-locked PyYAML `ai/ci_workflow_audit.py` validates YAML structure, action SHA pins, root read-only permissions (CodeQL exception for security-events write), forbidden elevated triggers, PR path self-inclusion and cancellation policy. Nonzero failure exit; redacted evidence includes filenames, SHA-256 and issue codes. Unit tests include deliberately unsafe fixture files. This gate is configuration-oriented, **not** product E2E or proof of reduced CI billing. An actual before/after comparison of completed and cancelled GitHub Actions runs is necessary to quantify savings.

Fixed reference dependencies: chromium renderer crash fixture imports OPFS journal helper; v10 package workflow depends on its allowlisted source paths. The relevant PR paths now include these dependencies.

Sources:
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#concurrency
- https://docs.github.com/en/actions/reference/security/secure-use
- https://pypi.org/project/PyYAML/6.0.3/
- https://pypi.org/project/playwright/1.64.1/

Preserve stable product assets; no main push, force push, merge or release. Issue #31 RPLAY actual-source data loss remains unresolved. Synthetic CI acceptance is not production GO.
