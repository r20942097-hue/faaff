# Source synchronization

Verified local source snapshot: Universal Live Watcher v6.2.0.

Verified release ZIP SHA-256:
`cc3432897cab172f57631fc9bbf4bf885c4f5fcf3628e49105861c824bc673a3`

The connected GitHub interface exposes individual repository file operations and Git object operations, but the complete tested runtime tree is not currently mirrored into this repository. The repository is therefore intentionally treated as an engineering/bootstrap surface, not as the source-of-truth runtime checkout.

The complete verified runtime source is preserved in the deterministic local release ZIP.

Active GitHub automation currently covers source-state CI, Dependency Review, and Dependabot. Release packaging and provenance remain local/ready-to-enable until the runtime source tree is synchronized.

CodeQL is retained as a non-triggering template because code scanning is not available for this current private repository under the current GitHub plan.
