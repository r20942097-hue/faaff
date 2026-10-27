# GitHub Operation Notes

Current verified local release: v6.10.0.

> 2026-10-27 注記: このリポジトリは現在 **public** です。以下の「private」に関する記述は過去の状態で、現状と一致しません。Watcher ランタイムソースは `main` にありません（README 参照）。

The repository was private at the time of writing and currently serves as the engineering/bootstrap surface. Active automation covers source-state CI, Dependency Review, Dependabot, minimal workflow permissions, and full-SHA pinning for third-party Actions.

The local v6.10.0 release passed 441 tests, clean extraction, compileall, extension JavaScript syntax checks, CLI smoke tests, archive verification, and deterministic rebuild comparison.

CodeQL is retained as a ready-to-enable template but is not active in this private repository under the current plan. Do not place runtime SQLite databases, recordings, diagnostics, credentials, tokens, or local caches in Git.
