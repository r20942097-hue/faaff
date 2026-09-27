# Security Scan Status

The current GitHub repository is private. GitHub documents that code scanning on private repositories requires GitHub Code Security / GitHub Advanced Security. On GitHub Free or Pro, code scanning is available only for public repositories.

The active repository therefore does not run a CodeQL workflow that would be rejected by the current plan. The ready-to-enable workflow is kept at `.github/workflows/codeql.yml.template`.

Local verification continues through the 391-test suite, manifest/network security tests, Bridge authentication tests, subprocess isolation tests, and deterministic release checks.

This status does not claim that local tests are equivalent to GitHub-hosted CodeQL scanning.
