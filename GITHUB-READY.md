# GitHub Operation Notes

Current verified local release: v6.8.1.

Verified release SHA-256:
`8350cd2fbb9afb626c4060ca89b2e7d985d9d00e5823aad2afd4727c25d0f729`

The repository is private and currently serves as the GitHub engineering/bootstrap surface. Active automation covers source-state CI, Dependency Review, Dependabot, minimal workflow permissions, and full-SHA pinning for third-party Actions.

The current CI run validates source synchronization state. Full Python/Windows runtime matrix execution begins once the complete runtime source tree is synchronized into the repository.

CodeQL is retained as a ready-to-enable template but is not active in this private repository under the current plan.

Do not place runtime SQLite databases, recordings, diagnostics, credentials, tokens, or local caches in Git.
