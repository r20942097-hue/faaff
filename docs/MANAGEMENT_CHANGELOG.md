# 4.0 — 2026-10-05

- Reproduced v3 false STABLE result for string boolean, core blocker, NO_GO and prerelease.
- Replaced truthiness flags with strictly typed product evidence records and digest binding.
- Added registry/manifest/evidence schema validation and clear CLI error codes.
- Added separate promotion policy, source/artifact integrity, SBOM/provenance payload binding and ZIP safety checks.
- Protected integration and previous-known-good references; unresolved inventory yields no archive candidates.
- Generated PROJECT_INDEX from registry and marked imported product assertions as not revalidated.
- Added negative regression tests, deterministic pack build and full content inventory verification.
- Replaced fake-success sample with a blocked example.
