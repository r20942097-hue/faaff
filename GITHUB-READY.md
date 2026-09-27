# GitHub Operation Notes

The repository is private and currently serves as the GitHub engineering/bootstrap surface for Universal Live Watcher.

Current verified local release: v6.3.0.

The complete tested runtime source is preserved in the deterministic local release artifact because the connected GitHub interface does not currently provide a direct bulk local-tree upload workflow.

Active repository automation:
- CI with explicit source-synchronization detection.
- Dependency Review.
- Dependabot.
- Minimal workflow permissions.
- Full-SHA pinning for third-party Actions.

CodeQL is retained as a ready-to-enable template for repositories/plans where code scanning is available. It is not active in this repository.

Do not place runtime SQLite databases, recordings, diagnostics, credentials, tokens, or local caches in Git.
