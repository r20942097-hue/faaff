# Changelog

## v5.10.0 — 2026-09-27

- Persist recovery attribution across process restarts.
- Make recovery-effectiveness learning idempotent by context ID.
- Add recency decay, stale-evidence limits, effective-trial minimums, and conservative Wilson-style selection.
- Add Python package metadata and CLI entry point.
- Add Ubuntu/Windows CI across Python 3.11–3.14.
- Add CodeQL, Dependency Review, Dependabot, deterministic release packaging, and artifact attestation.
- Pin third-party GitHub Actions to full commit SHAs.
- Harden protected remote Bridge health/readiness endpoints.
