# Portfolio audit — 2026-10-05

- Suite latest reference corrected from 0.50.0 to 0.51.0 using materialized archive, companion hashes and matching verification report.
- Six product/evidence/source ZIPs: companion SHA, CRC and safe paths PASS.
- Internal manifests: WP10 186, Suite 742, YouTube complete 57, YouTube evidence 12 file hashes PASS with exact coverage.
- WP10: extracted 0.38.0 suite 407 tests PASS on Linux.
- Suite: extracted 0.51.0 suite 35 modules / 366 tests PASS on Linux; source fingerprint unchanged per runner.
- YouTube dev70: original verification and all three ZIP identities reconciled. Existing test/reproducibility claims were not re-executed this turn.
- WP10 report freshness gap: embedded source-validation.json reports 326 tests; environment.json records version 0.25.0. New 407-test log is separate.
- Real environments, SBOM completeness, provenance signature/identity, stable acceptance: NOT_RUN.

This audit updates references and records integrity; it does not promote products. Original ZIPs are not modified or duplicated inside this management pack. Their exact digests are in archive-audit.json. Test counts are not summed into a cross-product quality score.
