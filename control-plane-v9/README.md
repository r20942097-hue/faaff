# Production Control Plane v9.1 — committed runtime extraction

`extract_source.py` verifies `runtime-manifest.json` against a pinned SHA-256,
checks the exact set, byte length and SHA-256 of the 15 committed runtime files,
rejects source links, and copies the verified bytes into a fresh output directory.
Existing output directories are refused; source verification finishes before any output is created.

Source baseline: `a302d0c6cf9d3db4360a6ce7c56976acaa906561`.
This uses the reviewable runtime tree already present in that commit.
It does not claim byte identity with the former 18-file embedded bootstrap.
The historical `.gz.b64` payload is unused: its Git blob contains a literal
`[... ELLIPSIZATION ...]` marker and fails both the declared SHA-256 and strict Base64 decoding.

Run locally in a fresh checkout:

```bash
python control-plane-v9/extract_source.py --out /tmp/control-plane-v9
python -m compileall -q /tmp/control-plane-v9/tools
python /tmp/control-plane-v9/tools/ci_selftest.py
python /tmp/control-plane-v9/tools/static_safety_check.py /tmp/control-plane-v9
```

The CI self-test checks schema migrations, fail-closed Candidate/Stable eligibility,
local Candidate promotion, two-role local Stable promotion and event-chain integrity.
Its temporary database contains synthetic gates. Passing does not establish real
Windows/browser/WP10/RPLAY acceptance or authorize product promotion.
No remote publication, PR merge, artifact deletion or Library mutation is performed.
