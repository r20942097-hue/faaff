# Security Scan Status

The active private GitHub repository does not run CodeQL code scanning under the current plan. A ready-to-enable template is retained at `.github/workflows/codeql.yml.template`.

Local v6.8.1 verification includes 425 tests covering manifest/network security, Bridge authentication, subprocess isolation, Recovery, recording, extension control, HLS variant failover, cross-scheme redirect handling, toolchain diagnostics, crash-safe segment journaling, session isolation, current-output journal scoping, and release integrity.

Local tests are not equivalent to GitHub-hosted CodeQL scanning.
