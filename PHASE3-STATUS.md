# Phase 3 Status

## Entry decision

Phase 2 artifact integrity is verified. No Phase 2 artifact rebuild is required. Phase 3 is authorized to proceed from the verified Phase 2 source archive without mutating it.

## Security posture at Phase 3 start

| Area | Status | Meaning |
| --- | --- | --- |
| Phase 2 artifact integrity | VERIFIED | ZIP integrity/provenance checks are accepted as the Phase 3 input boundary. |
| Dependency declaration inventory | IMPLEMENTED | Phase 3 can inventory supported manifests inside the verified Phase 2 source ZIP. |
| SBOM | DECLARATION_ONLY | CycloneDX 1.6 declaration inventory only; dependencies are not resolved. |
| Product source intake contract | IMPLEMENTED | All Candidate Baseline product identities are registered and missing inputs cannot be promoted to verified evidence. |
| External evidence validator | IMPLEMENTED | Validates the seven-product Library record while requiring GitHub scan readiness to remain false and vulnerability posture UNKNOWN. |
| GitHub-consumable product source readiness | 0/7 VERIFIED | Complete product source ZIPs are not committed/mounted into a GitHub Actions-consumable input surface. |
| Current external source re-verification | 7/7 VERIFIED_EXTERNAL | All seven Library ZIPs were re-retrieved and their SHA-256, CRC, safe paths, and symlink status checked in the current environment. |
| Gate C preflight | IMPLEMENTED / NOT_RUN | Requires the exact seven scanner-consumable sources and complete dependency, SBOM, scanner/database, and policy evidence; it cannot emit PASS. |
| Dependency Review | NOT_RUN / UNSUPPORTED | No supported repository-native Dependency Review result is being treated as evidence. |
| CodeQL | NOT_RUN | CodeQL is not active for this workstream. |
| Complete dependency-bearing source scan | NOT_RUN | No complete resolved dependency graph or vulnerability database scan has been performed; GitHub runner artifact ingress remains absent. |
| Vulnerability posture | UNKNOWN | No claim of vulnerability clearance is permitted. |

## Phase 3 Gate A

Gate A establishes a deterministic, fail-closed dependency-intake boundary around the immutable Phase 2 source ZIP. It validates the archive before reading dependency manifests and records partial coverage explicitly.

Gate A passing does not authorize a vulnerability `PASS`. It only establishes that the declaration inventory was produced from the expected verified archive without silently broadening security claims.

## Phase 3 Gate B intake contract

Gate B has a machine-readable product-source registry and validator for the seven Candidate Baseline products. A product can become repository-scan `VERIFIED` only when an immutable scanner-consumable source reference, SHA-256, and byte size are all present and structurally valid. `MISSING` entries are required to keep source reference, digest, and size null so evidence cannot be invented.

The GitHub-consumable registry remains `0/7 VERIFIED`; this is intentional because the product ZIPs are not present in the repository/runner input surface.

A separate environment-scoped record, `phase3_security/external-source-evidence.json`, captures current Library evidence without pretending GitHub can consume it. On 2026-10-01, six products were re-materialized from Library and directly rechecked against the accepted SHA ledger: AI Orchestrator 1.51, Browser Control 0.3.0, Shared Foundation 0.10, Media / Download Tools 0.1.0, Universal Control Suite 0.30, and Windows Control 0.1.8. On 2026-10-02, Universal Live Watcher 6.49.12 was retrieved and independently rechecked: its 502,993-byte ZIP matched the expected SHA-256, passed CRC and safe-path checks, and contained no symlink entries.

The current external retrieval gate is now 7/7. The GitHub-consumable registry remains 0/7 because the artifacts are not in the repository or runner input surface; external Library evidence does not satisfy that separate intake contract.

The external-evidence validator checks the seven baseline identities, per-product SHA/size/CRC and manifest counts, and the top-level verified count. It rejects any external-evidence record that claims GitHub scan readiness or vulnerability clearance.

Among the seven reverified archives, AI Orchestrator and Universal Live Watcher exposed supported dependency manifests. AI Orchestrator declares FastAPI, Pydantic and Uvicorn directly; optional groups declare Playwright, PyJWT, pytest and httpx; its build system declares setuptools. Universal Live Watcher declares setuptools and wheel in its build system; its `requirements.txt` contains comments only. No lockfile or resolved dependency graph was established by this step.

## Next gate

Gate C preflight is implemented and reports `NOT_RUN` while scanner-consumable inputs or scan evidence are missing. It requires exact dependency resolution and lock evidence, a complete CycloneDX 1.6 SBOM, scanner and vulnerability-database provenance for every product, and explicit policy results. `READY_FOR_REVIEW` is not a vulnerability `PASS`.

Provide a controlled, scanner-consumable ingress for the seven immutable source artifacts, then resolve exact dependency versions, produce complete SBOMs, and run supported vulnerability/static scanners. Preserve scanner/version/database provenance and evaluate policy without converting `UNKNOWN`, `NOT_RUN`, `UNSUPPORTED`, historical evidence, or partial results to `PASS`.
