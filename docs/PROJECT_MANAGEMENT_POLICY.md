# Project Management Policy

This document is the top-level policy. Detailed rules are split into:

- `ARTIFACT_GOVERNANCE.md`
- `RETENTION_POLICY.md`
- `SUPPLY_CHAIN_POLICY.md`
- `OFFICIAL_REFERENCES.md`
- `../schemas/release-manifest.schema.json`
- `../templates/RELEASE_MANIFEST.example.json`
- `../tools/validate_release_manifest.py`
- `../tools/promotion_decision.py`

## Versioning

Use SemVer-compatible numeric versions where practical:

- `X.Y.Z`
- `X.Y.Z-dev.N`
- `X.Y.Z-rc.N`

Published release contents are immutable. Any content change requires a new version.

## Promotion states

`RESEARCH -> PROTOTYPE -> DEV -> CANDIDATE -> STABLE`

Blocking flags:

- `NO_GO`: cannot be promoted.
- `INCOMPLETE`: core functionality is incomplete.
- `BLOCKED_ENVIRONMENT`: a required target environment is unavailable.

## Evidence precedence

1. Exact product-level verification for the artifact/version.
2. Exact integration/Suite verification.
3. Checksum-only evidence.
4. Filename/version observation.

A lower evidence level does not override a higher-level NO_GO, and integration evidence does not automatically create a standalone product release.

## Candidate gate

A version can become CANDIDATE only when exact source/build identity is recorded, verification refers to that exact identity, regression tests pass, package safety/integrity passes, reproducible-build checks pass when supported, and required SBOM/provenance evidence is present.

## Stable gate

A candidate can become STABLE only when candidate gates pass, required real-environment acceptance passes, rollback/recovery is verified when persistent state can change, and unresolved blockers do not affect the advertised primary use.

Passing synthetic/offline tests alone is not sufficient for browser-, OS-, game-, service-, or hardware-dependent functionality.

## Active artifact retention

Keep in the active area:

- current candidate/development build;
- current stable build if one exists;
- one previous known-good rollback point;
- current README/CHANGELOG/test report;
- checksums/evidence for those retained artifacts.

Archive older intermediate versions after preserving unique regression, recovery, provenance, and rollback evidence.

## Git workflow

- Keep `main` as the formal baseline.
- Use task-specific branches and pull requests.
- Do not force-push or rewrite shared history.
- Do not auto-promote or auto-merge based only on passing local tests.
- Keep Library/runtime artifacts distinct from GitHub engineering/bootstrap state unless exact provenance has been established.

## Public release integrity

When STABLE public releases move to GitHub, prefer immutable releases, attach all release assets before publication, generate/retain provenance where supported, and verify local artifacts against the published release evidence.
