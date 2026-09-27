# GitHub Operation Notes

The repository is private and currently serves as the GitHub engineering/bootstrap surface for Universal Live Watcher.

Current release: v6.2.0. The complete verified runtime source remains the local deterministic release artifact because the connected GitHub interface does not provide a bulk local-tree upload operation.

Active repository controls:
- CI with explicit source-sync detection.
- Dependency Review.
- Dependabot.
- Minimal workflow permissions.
- Full-SHA pinning for third-party Actions.

CodeQL is retained as a ready-to-enable template for repositories/plans where code scanning is available. It is not active in this repository.

Do not place runtime SQLite databases, recordings, diagnostics, credentials, tokens, or local caches in Git.