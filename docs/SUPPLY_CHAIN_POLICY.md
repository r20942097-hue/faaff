# Supply chain policy v4

Candidate requirements include SBOM and provenance records with payload digests. Use CycloneDX 1.7 SBOMs and SLSA provenance v1 in in-toto Statement v1 envelopes. Bind SBOM metadata.component to product/version and provenance subject to the artifact filename/digest.

This pack checks basic structure and binding; it does not generate production dependency inventories, sign records, verify signatures, award SLSA levels, or establish trust in a producer. Keep the actual SBOM/provenance validation and attestation verification result with its evidence record.

Published release identities are immutable. Use trusted build inputs and an appropriate attestation workflow for each product. Repository security settings, Dependency Graph and release immutability need separate configuration; no such setting was changed in this run.

Exclude API keys, cookies, authenticated browser profiles and private tokens from artifact/evidence inputs.
