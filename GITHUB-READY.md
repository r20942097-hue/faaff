# GitHub Operation Notes

The repository is private and currently serves as the GitHub engineering/bootstrap surface for Universal Live Watcher.

Current verified local release: v6.6.0.

Verified release SHA-256:
`6e6be97ec426dd9d9a816da42bee6278677a35d23337773de35d739b416c890e`

The complete tested runtime source is preserved in the deterministic local release artifact. The connected GitHub interface provides individual repository file and Git object operations, but the complete tested runtime tree is not presented as mirrored unless synchronization is actually complete.

Active repository automation:
- CI with explicit source-synchronization detection.
- Dependency Review.
- Dependabot.
- Minimal workflow permissions.
- Full-SHA pinning for third-party Actions.

CodeQL is retained as a ready-to-enable template for repositories/plans where code scanning is available. It is not active in this repository.

Do not place runtime SQLite databases, recordings, diagnostics, credentials, tokens, or local caches in Git.
