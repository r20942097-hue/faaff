# GitHub Operation Notes

Current verified local release: v6.10.0.

GitHub metadata checked on 2026-10-11 reports a public repository. It currently serves as the engineering/bootstrap surface. Active automation covers source-state CI, Dependency Review, Dependabot, minimal workflow permissions, and full-SHA pinning for third-party Actions.

The local v6.10.0 release passed 441 tests, clean extraction, compileall, extension JavaScript syntax checks, CLI smoke tests, archive verification, and deterministic rebuild comparison.

A Python CodeQL workflow is prepared locally at `.github/workflows/codeql.yml`. Remote execution must be confirmed after publication; a successful scan is not inferred from local tests. Do not place runtime SQLite databases, recordings, diagnostics, credentials, tokens, or local caches in Git.
