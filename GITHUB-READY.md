# GitHub Operation Notes

The repository is private and is intended as the source-of-truth development repository.

Recommended main-branch policy:
- Require pull requests for changes to `main`.
- Require CI and CodeQL before merge.
- Keep workflow permissions minimal.
- Keep runtime databases, recordings, diagnostics, credentials, and local caches out of Git.
- Use version tags for deterministic release builds.

Release workflow builds the ZIP, computes SHA-256, runs tests, and creates artifact provenance. Publishing a GitHub Release remains a deliberate owner action.
