# GitHub Operation Notes

Current verified local release: v6.9.0.

The repository is private and currently serves as the engineering/bootstrap surface. Active automation covers source-state CI, Dependency Review, Dependabot, minimal workflow permissions, and full-SHA pinning for third-party Actions.

The local v6.9.0 release passed 439 tests, clean extraction, compileall, extension JavaScript syntax checks, CLI smoke tests, archive verification, and deterministic rebuild comparison.

CodeQL is retained as a ready-to-enable template but is not active in this private repository under the current plan. Do not place runtime SQLite databases, recordings, diagnostics, credentials, tokens, or local caches in Git.
