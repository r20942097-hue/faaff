# Release evidence checklist

- Actual product id, SemVer and externally configured risk class.
- Exact source archive hash, repository and commit; exact artifact hash and size.
- Product-scope evidence records bound to the same source and artifact.
- Regression, clean extraction, archive integrity and reproducibility records.
- Actual SBOM and provenance payloads, their hashes and validation records.
- Runtime acceptance and rollback records when required by policy.
- Candidate/stable blocker reasons retained until resolved by evidence.
- GO declaration alone is insufficient; eligibility must pass all gates.
- Signed attestation verification is a separate trust check.
- Exact generated PROJECT_INDEX, required KEEP/rollback references and independent evidence retention.
