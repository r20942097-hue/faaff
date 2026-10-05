# Supply Chain Policy

## SBOM

Preferred interchange format: CycloneDX JSON (`bom.cdx.json` or `*.cdx.json`). Record resolved direct and transitive software components where tooling can determine them. Do not fabricate unresolved dependencies.

## Provenance

Record where, when, and how release artifacts were produced. For supported GitHub builds, prefer GitHub Artifact Attestations. For higher-assurance workflows, align provenance records with SLSA provenance concepts.

## Stable public releases

Prefer immutable GitHub releases for STABLE public releases when repository policy permits. Create the release as a draft, attach all final assets, verify them, and only then publish.

## Dependency security

Enable Dependency Graph before treating Dependency Review as an enforcement gate. When enabled, make Dependency Review a required pull-request check at an appropriate vulnerability-severity threshold.

## Secrets

Use secret scanning and push protection when available. Never include credentials, API keys, authentication databases, cookies, browser profiles, private tokens, or other live secrets in release artifacts or evidence bundles.
