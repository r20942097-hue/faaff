# Phase 3 Security Intake

This directory starts Phase 3 without modifying or rebuilding the verified Phase 2 artifact.

The first gate is deliberately scope-aware. It verifies the detached SHA-256 for the committed Phase 2 source ZIP, validates ZIP paths/CRC/symlink safety, inventories dependency declarations from supported manifests, and emits a deterministic declaration-level CycloneDX 1.6 document.

This is not a vulnerability-clearance result. The current repository scope does not contain the complete dependency-bearing source trees for the full Candidate Baseline, so coverage is `PARTIAL` and vulnerability posture remains `UNKNOWN`. The generated SBOM is `DECLARATION_ONLY`: no package resolution, transitive graph, installed-version verification, registry lookup, or vulnerability matching is performed.

Promotion rules:

- `UNKNOWN`, `NOT_RUN`, and `DECLARATION_ONLY` must never be promoted to `PASS`.
- A complete vulnerability gate requires all dependency-bearing product source trees or equivalent immutable build inputs.
- Any malformed dependency manifest, unsafe archive path, symlink entry, CRC failure, or archive SHA mismatch fails closed.
- The verified Phase 2 source ZIP is an immutable input to this Phase 3 workstream.
