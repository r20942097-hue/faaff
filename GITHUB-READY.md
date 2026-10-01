# GitHub Operation Notes

The verified Phase 2 source archive is the immutable input for the Phase 3 workstream. Phase 3 must not rebuild or silently replace that artifact.

Repository automation can verify source/archive integrity and run the Phase 3 declaration-inventory gate. Dependency Review workflow configuration may be present, but no supported Dependency Review result is treated as completed security evidence for the accepted Phase 2 decision. CodeQL is retained only as a template and is not active for this workstream.

The current repository scope does not contain the complete dependency-bearing source trees for the full Candidate Baseline. Therefore the vulnerability posture remains `UNKNOWN`, and `UNKNOWN` / `NOT_RUN` / declaration-only SBOM output must not be promoted to `PASS`.

Phase 3 Gate A inventories dependency declarations inside the verified Phase 2 source ZIP and emits a declaration-level CycloneDX 1.6 document. It does not resolve packages, enumerate transitive dependencies, verify installed versions, query registries, or perform vulnerability matching.

Do not place runtime SQLite databases, recordings, diagnostics, credentials, tokens, or local caches in Git.
