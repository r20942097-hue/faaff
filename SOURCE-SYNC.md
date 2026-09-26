# Source synchronization

The verified Universal Live Watcher v5.11.0 source tree is maintained in the deterministic local release artifact. The connected GitHub interface used for this repository does not expose a bulk local-tree upload operation, so the repository intentionally does not claim to be a complete source checkout yet.

This prevents an incomplete tree from being mistaken for the tested application source. The CI workflow detects this state explicitly and only enables the full test matrix after the source tree is present.

Verified release ZIP SHA-256: `6e051ce31d84a8c4d3ff5346a89037effaf4b71baa83bf158a99fb8f12c54b94`.
