# Universal Control Suite — Control Plane Next Phase

This tree is a new, product-independent control-plane layer. It does **not** claim that the GitHub Release Auditor branch is a mirror of Suite v0.30, and it does not mutate any product database, install products, promote releases, perform rollback, execute evidence payloads, or make implicit network calls.

Formal input for this phase is `baseline/verified-candidate-baseline.json`, derived from the reverified Library baseline specified by the operator. Legacy product version labels are preserved exactly; `semantic_version` is a normalized comparison alias only for labels that historically omitted the patch component (`0.30 -> 0.30.0`, `1.51 -> 1.51.0`, `0.10 -> 0.10.0`).

Core properties:
- baseline Product/Release registry with PASS/FAIL/NOT_RUN/UNKNOWN preserved;
- evidence payload storage with DRAFT → REGISTERED → SEALED → ARCHIVED lifecycle;
- SEALED metadata/payload immutability through the API, plus tamper detection;
- chained append-only event log;
- pre-update snapshots, checksum validation and recovery-plan generation only;
- capability contracts without cross-product state mutation;
- offline audit CLI.

Example:

```sh
python -m ucs_control_plane baseline init baseline/verified-candidate-baseline.json --root .ucs-control-plane
python -m ucs_control_plane audit --json --root .ucs-control-plane
python -m ucs_control_plane registry verify --root .ucs-control-plane
python -m ucs_control_plane evidence verify --root .ucs-control-plane
python -m ucs_control_plane snapshot verify --root .ucs-control-plane
python -m ucs_control_plane recovery plan --root .ucs-control-plane
```

`Artifact` audit is `NOT_RUN` when baseline ZIPs are not copied into `<root>/artifacts/`; the baseline registry's historical verification state is not silently reused as a current local artifact check.
