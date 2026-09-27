# Source synchronization

Verified local source snapshot: Universal Live Watcher v6.1.0.

Verified release ZIP SHA-256:
`78dc39c027aa771635d9715ef5af4f72b495913544cdbaebcafd466a0c0de895`

The connected GitHub interface exposes individual repository file operations but no bulk local-tree upload operation. This repository therefore intentionally remains an engineering/bootstrap surface until full source synchronization is available.

CI and CodeQL explicitly detect this state. They do not represent the bootstrap repository as a complete tested runtime checkout.

The complete verified ZIP is maintained outside this GitHub bootstrap tree at the local release artifact path.
