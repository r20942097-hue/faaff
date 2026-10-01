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

## Verify the source archive

From this directory, verify the published archive and the extracted source:

```sh
sha256sum -c SOURCE-ARCHIVE-SHA256.txt
python -m zipfile -t ucs-control-plane-phase2-source.zip
python -m zipfile -e ucs-control-plane-phase2-source.zip /tmp/ucs-control-plane-phase2-source
cd /tmp/ucs-control-plane-phase2-source
sha256sum -c SHA256SUMS.txt
python -m unittest discover -s tests -v
python -m compileall -q ucs_control_plane tests
```

The verification evidence inventories project files but deliberately excludes its own path to avoid an impossible self-checksum. Its digest and size are recorded only in the detached `SHA256SUMS.txt` manifest.

For maintainers, rebuild the archive reproducibly from an extracted source tree with `python control_plane_next/build_source_archive.py --source-dir <source-directory>`. The packaging tool rewrites `SHA256SUMS.txt`, fixes archive timestamps and file modes, and updates the detached archive digest. CI rebuilds the ZIP and requires byte-for-byte equality with the committed archive.
