# v5 — 2026-10-05

- Concurrent PR updates preserved; stronger registry v4 / manifest v2 framework retained.
- Suite references updated to 0.51.0. WP10 407 and Suite 366 tests re-run on Linux.
- Six ZIPs reconciled with companion hashes; 997 internal hashes verified.
- Read-only audit tool and four tests added; management total 44 tests.
- WP10 stale historical reports preserved separately from fresh results.

# 4.0 — 2026-10-05

- Reproduced v3 false STABLE result for string boolean, core blocker, NO_GO and prerelease.
- Replaced truthiness flags with strictly typed product evidence records and digest binding.
- Added registry/manifest/evidence schema validation and clear CLI error codes.
- Added separate promotion policy, source/artifact integrity, SBOM/provenance payload binding and ZIP safety checks.
- Protected integration and previous-known-good references; unresolved inventory yields no archive candidates.
- Generated PROJECT_INDEX from registry and marked imported product assertions as not revalidated.
- Added negative regression tests, deterministic pack build and full content inventory verification.
- Replaced fake-success sample with a blocked example.

