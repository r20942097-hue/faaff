# v5 selective audit

Management: 44 tests PASS (40 inherited framework + 4 archive-audit tests). WP10 407 / Suite 366 tests PASS on Linux. Six ZIPs passed whole-file identity/CRC/path checks; 997 internal hashes passed full coverage. YouTube tests were not re-run. See PORTFOLIO_AUDIT.md for exact scope and inherited references. Real environments and signature verification remain unverified.

# Verification report — v4

- 40 unittest methods PASS, including subcases for gate/type/path/version failures.
- v3 input CRC and all 16 content hashes PASS before audit.
- v3 reproduced STABLE_ELIGIBLE for a string false flag combined with NO_GO/core blocker/prerelease; empty registry accepted; integration/rollback references dropped.
- v4 rejects those inputs and protects all five portfolio references.
- Registry validation PASS: 10 imported projects.
- Manifest sample structurally valid; expected decision DEV_OR_NO_GO.
- Linux/Python 3.12.14 tested. Windows, other Python versions and product runtime acceptance not executed.
- Evidence authenticity/full external schemas/attestation signatures are outside the local verifier's scope.
- See SELFTEST.json for commands and captured output. Pack reproducibility/clean-extract results are recorded in the outer packaging report.

