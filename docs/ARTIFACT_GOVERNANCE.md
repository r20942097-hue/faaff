# Artifact Governance

## Sources of truth

- Portfolio status: `PROJECT_INDEX.md` and `docs/project_registry.json`
- Per-release identity: `RELEASE_MANIFEST.json`
- Dependency inventory: `bom.cdx.json`
- Build provenance: artifact attestation / provenance record
- Test details: product-specific test report
- Historical changes: product CHANGELOG

Do not make two files authoritative for the same concern.

## Lifecycle

`RESEARCH -> PROTOTYPE -> DEV -> CANDIDATE -> STABLE`

Blocking states: `NO_GO`, `INCOMPLETE`, `BLOCKED_ENVIRONMENT`.

Use SemVer-compatible `X.Y.Z`, `X.Y.Z-dev.N`, and `X.Y.Z-rc.N` where practical. Published release contents are immutable; a byte change requires a new version.

## Evidence precedence

1. Exact product-level release evidence.
2. Exact integration/Suite evidence.
3. Exact checksum-only evidence.
4. Version or filename observation.

Lower evidence cannot override a higher-level blocker. Integration evidence does not create a standalone product release automatically.

## CANDIDATE gate

Require exact source identity, exact artifact digest, regression tests, clean-extract/package safety, reproducible build when supported, and no unresolved core-function blocker.

## STABLE gate

Additionally require real target-environment acceptance when behavior depends on a browser, OS, game, service, or hardware; rollback/recovery where persistent state can change; successful end-to-end primary use; complete release manifest; SBOM where required; and provenance/attestation where required.

## Retention

Keep CURRENT, STABLE, PREVIOUS_KNOWN_GOOD and their evidence in the active area. Archive older intermediate versions only after preserving unique regression, recovery, and provenance evidence.
