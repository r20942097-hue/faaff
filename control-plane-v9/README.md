# Production Control Plane v9.1

This directory contains the reviewable/reproducible source bootstrap for the v9.1 completion candidate.

The source payload is stored as `source/control-plane-v9.1-bootstrap.py.gz.b64` to keep the stacked PR compact. `extract_source.py` verifies the encoded payload SHA-256, decompresses the bootstrap, verifies the bootstrap SHA-256, and extracts the 18 embedded source files. The extracted tree includes the SQLite base schema, v9/v9.1 migrations, promotion policy, dependency model, state/event logic, promotion transaction code, verifier, safety scanner, and CI self-test.

Verified payload identities:

- encoded payload SHA-256: `a608b9365dd57881cab1009cabfe24c1af0b7c59ec944e053a85c2c7d6f4251c`
- bootstrap SHA-256: `b20979eaf275754addfa573c29ac684bf04579c68bbe96c006363ae84cab28cc`
- embedded source manifest SHA-256: `feb5bd2d8abcf23893d2d958418a18e1b9cc7cf4061042d4eb8257904d5da56a`

Run locally:

```bash
python control-plane-v9/extract_source.py --out /tmp/control-plane-v9
python /tmp/control-plane-v9/tools/ci_selftest.py
```

The CI self-test checks schema migrations, fail-closed Candidate/Stable eligibility, one-role Candidate promotion, two-role Stable promotion, event-chain verification, and the no-external-mutation static safety scan.

Safety boundary: this source does not merge PRs, publish releases, mutate Library files, or delete artifacts. External adapters remain dry-run only. Real Windows/browser/WP10/RPLAY acceptance remains product-owned and is not inferred from synthetic tests.
