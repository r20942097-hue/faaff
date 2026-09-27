# Source synchronization

Verified local source snapshot: Universal Live Watcher v6.3.0.

Verified release ZIP SHA-256:
`a888fbbaac4fc5ebf343bd842aa2009001dacc6cbe6ab81988623be135ff5674`

The connected GitHub interface exposes individual repository file operations and Git object operations, but the complete tested runtime tree is not currently mirrored into this repository. The repository is intentionally treated as an engineering/bootstrap surface, not as the source-of-truth runtime checkout.

The complete verified runtime source is preserved in the deterministic local release ZIP.

Active GitHub automation currently covers source-state CI, Dependency Review, and Dependabot. Release packaging is verified locally. CodeQL is retained as a non-triggering template because code scanning is not available for this private repository under the current plan.
