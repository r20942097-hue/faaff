# Production Control Plane v9.1 — committed runtime extraction

`extract_source.py` verifies `runtime-manifest.json` against a pinned SHA-256,
checks the exact set, byte length and SHA-256 of the 16 committed runtime files,
rejects source links, and copies the verified bytes into a fresh output directory.
Existing output directories are refused; source verification finishes before any output is created.

Initial extraction baseline: `a302d0c6cf9d3db4360a6ce7c56976acaa906561`.
Promotion safety corrections build on `bced22cc10282070bc1f20d738a67822148d7adb`.
It does not claim byte identity with the former 18-file embedded bootstrap.
The historical `.gz.b64` payload is unused: its Git blob contains a literal
`[... ELLIPSIZATION ...]` marker and fails both the declared SHA-256 and strict Base64 decoding.

Run locally in a fresh checkout:

```bash
python control-plane-v9/extract_source.py --out control-plane-v9-ci
python -m compileall -q control-plane-v9-ci/tools
python control-plane-v9-ci/tools/test_promotion_safety.py
python control-plane-v9-ci/tools/ci_selftest.py
python control-plane-v9-ci/tools/static_safety_check.py control-plane-v9-ci
```

The CI self-test checks schema migrations, fail-closed Candidate/Stable eligibility,
local Candidate promotion, two-role local Stable promotion and event-chain integrity.
Its temporary database contains synthetic gates. Passing does not establish real
Windows/browser/WP10/RPLAY acceptance or authorize product promotion.
No remote publication, PR merge, artifact deletion or Library mutation is performed.

Promotion safety regressions reject unknown/empty profiles, missing or mismatched evidence, invalid/expired deadlines, and supplied policies that differ from the active policy. Planning and application recheck eligibility so elapsed time alone can block a stale plan. Evidence with no expiry retains its original semantics; this does not establish independent authenticity.

The dedicated CI requests Python 3.11–3.14 on Linux and Windows. A matrix definition is a request to test; successful execution must be checked on the exact HEAD. The regressions and self-test use synthetic evidence and local databases. Real game/browser/service acceptance remains unverified.
