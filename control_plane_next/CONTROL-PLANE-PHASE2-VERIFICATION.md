# Universal Control Suite Control Plane — Phase 2 Verification

Date: 2026-10-01 (Asia/Tokyo)

## Baseline boundary

Formal input is the operator-specified verified Candidate Baseline:
- Universal Control Suite 0.30
- Universal Live Watcher 6.49.12
- Windows Control 0.1.8
- AI Orchestrator 1.51
- Shared Foundation 0.10
- Browser Control 0.3.0
- Media / Download Tools 0.1.0

The GitHub `codex/universal-control-suite` branch at `b49dd9f` is treated only as the prior Release Auditor workstream, not as a complete product mirror. The unverified historical Product Registry report is not imported as baseline evidence.

## Implemented

- Baseline Product/Release Registry with artifact filename, SHA-256, size, verification state, evidence references, provenance and Candidate/Formal/Historical classification.
- Evidence payload storage with strict IDs, type checks, canonical JSON, hash/size validation, non-link regular-file checks and no payload execution.
- Lifecycle `DRAFT -> REGISTERED -> SEALED -> ARCHIVED`; ARCHIVED is an index state and does not modify sealed metadata/payload.
- Append-only hash-chained event log with required event fields and event types.
- Pre-update snapshots, atomic registry writes, fsync, checksums, recovery-plan generation only.
- Capability contracts with sealed required evidence, minimum strict SemVer, compatibility constraints, risk level and release-state checks.
- CLI: `ucs audit`, `ucs audit --json`, `ucs registry verify`, `ucs evidence verify`, `ucs snapshot verify`, plus baseline init and recovery-plan generation.

## Verification

The committed source archive was re-extracted from the Library-reverified 28,044-byte candidate, whose SHA-256 is `9baba968621dec3f1bd63c3c8b6768f120d6025c0e04332724cb384945050a2a`; Python ZIP validation and CRC checks passed.

- Unit/security/regression tests: 46 total; 45 PASS; 0 FAIL; 1 SKIP, rerun from the repaired archive in CI/local verification.
- SKIP: real Windows Junction creation/detection; current execution platform is Linux. Junction rejection code path exists via `os.path.isjunction` and must be rerun on Windows.
- Compile/static: PASS (`compileall`, AST parse).
- Static no-network-client import policy: PASS.
- Static evidence no-`eval`/`exec`/`compile` policy: PASS.
- Suite v0.30 input ZIP: SHA-256 `bc5391e02c5916aacfb9c7fa85aae1679a90efb515d1cc1ca718901a70559904`; 40 entries; ZIP CRC PASS in this session.
- Phase 2 runtime audit: Product PASS; Release PASS; Evidence PASS; Evidence Chain PASS; Capability PASS; Event Log PASS; Snapshot PASS; Artifact NOT_RUN because product ZIPs are intentionally not copied into the runtime registry root.

## Security regression coverage

PASS: path traversal, absolute path, Windows drive path, UNC path, symlink, NUL byte, Unicode normalization collision, case collision, Windows reserved names, duplicate IDs, malformed JSON, duplicate JSON keys, NaN, Infinity, oversized metadata, deeply nested JSON, modified/missing payload, hash mismatch, post-seal tamper detection, broken evidence chain, evidence cycle corruption, corrupted event, corrupt latest snapshot fallback, corrupted snapshot, interrupted write, concurrent write serialization, UNKNOWN promotion rejection, payload non-execution.

NOT_RUN: real Windows Junction construction/detection. The product runtime does not process archives; the CI-only archive verifier checks the published source ZIP for CRC, safe paths, symlinks, size limits and manifest consistency.

## Recovery / rollback

No automatic restore exists. Every registry mutation snapshots the prior valid registry. `recovery plan` selects the latest valid checksum/schema-verified snapshot and emits a plan only. Existing product states and product databases are not modified by this Control Plane.
