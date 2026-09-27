# Security Scan Status

The current GitHub repository is private. CodeQL code scanning is not active for this repository under the current plan, so no active CodeQL workflow is presented as successful.

The ready-to-enable workflow is kept at `.github/workflows/codeql.yml.template`. This is separate from the local security test suite and must not be treated as equivalent coverage.

Local verification currently includes 396 tests covering manifest/network security, Bridge authentication, subprocess isolation, recovery, recording, extension control, and release integrity.
