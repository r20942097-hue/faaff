# GitHub Operation Notes

Current verified local release: v6.8.1.

Verified release SHA-256:
`94d30d1ec57a2a195a79df1095196341618ce41fb76b4418c93b88d65b0c37e9`

The repository is private and currently serves as the engineering/bootstrap surface. Active automation covers source-state CI, Dependency Review, Dependabot, minimal workflow permissions, and full-SHA pinning for third-party Actions.

The current CI run validates source synchronization state. Full Python/Windows runtime matrix execution begins once the complete runtime source tree is synchronized into the repository.

CodeQL is retained as a ready-to-enable template but is not active in this private repository under the current plan.

Do not place runtime SQLite databases, recordings, diagnostics, credentials, tokens, or local caches in Git.
