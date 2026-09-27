# Source synchronization

Verified local source snapshot: Universal Live Watcher v6.6.0.

Verified release ZIP SHA-256:
`6e6be97ec426dd9d9a816da42bee6278677a35d23337773de35d739b416c890e`

The connected GitHub interface exposes individual repository file and Git object operations, but the complete tested runtime tree is not currently mirrored into this repository. The repository is intentionally treated as an engineering/bootstrap surface, not as the source-of-truth runtime checkout.

The complete verified runtime source is preserved in the deterministic local release ZIP.

Active GitHub automation covers source-state CI, Dependency Review, and Dependabot. Release packaging is verified locally. CodeQL is retained as a non-triggering template because code scanning is not active for this private repository under the current plan.
