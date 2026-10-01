# Universal Control Suite v0.30 intake audit

Audit date: 2026-09-30 (UTC)

## Evidence boundary

This checkout does **not** contain the three declared candidate ZIP files, a
Suite workspace source tree, or its Completion, Verification, Delivery
Evidence, registry, compatibility, and release-evidence records. The checkout
instead contains the GitHub bootstrap documents for Universal Live Watcher
v6.10.0; `SOURCE-SYNC.md` explicitly says that its complete runtime source is
maintained outside this repository. This also does not match the requested
retained Universal Live Watcher version 6.49.12.

Consequently, no historical PASS was promoted to a current PASS. ZIP SHA-256,
CRC, source-to-ZIP byte equality, clean deployment, isolated-environment tests,
Control Center lifecycle behavior, browser tests, and Windows acceptance are
all **NOT RUN**. Creating a v0.31 product archive without its v0.30 baseline
would neither preserve the product boundaries nor provide a defensible
rollback, so no product candidate was fabricated.

## Work completed safely

An offline, read-only intake auditor was added. It checks SHA-256 before parsing
an archive, then rejects duplicate entries, unsafe or non-canonical paths,
symbolic links, encrypted entries, excessive entry counts and expanded sizes,
extreme compression ratios, CRC failures, cross-platform case/Unicode path
collisions, Windows device names, unsafe Unix permission metadata, and
unexpected Windows executable/script suffixes. Executables are fail-closed
unless an inventory explicitly allowlists their exact archive paths. The tool
does not extract, import, or execute candidate content and performs no network
access.

Candidate files must be regular, non-symlink files and are rejected before
hashing when the compressed archive itself exceeds the configured bound. The
same open file handle is used for hashing and ZIP parsing to remove a path-swap
window. CRC/content validation streams fixed-size chunks under an actual-byte
ceiling and is skipped after unsafe metadata is detected, so validating an
already-rejected ZIP cannot accidentally decompress a bomb. Reports are
written through a same-directory temporary file, flushed, and atomically
replaced to avoid leaving a partially written release decision.

The checked-in inventory records the three supplied names and digests. The
machine-readable audit result accurately records all three as **NOT RUN**
because the files are absent. It is deterministic and contains no timestamp or
machine-specific absolute path.

To repeat the intake when artifacts are staged in an isolated directory:

```bash
python tools/audit_suite_release.py \
  --inventory release/suite-v0.30-inventory.json \
  --artifact-dir /path/to/isolated/artifacts \
  --output verification-suite-v0.30.json
```

The command exits `1` for any **FAIL**, `2` for any **NOT RUN**, and `0` only
when every candidate is **PASS**. Thus it is safe to use directly as a release
gate. Missing candidates remain **NOT RUN** (rather than FAIL) in the report so
the evidence is accurate, while still blocking publication. An explicit
`--allow-not-run` inspection option returns success for an incomplete inventory;
it must never be used as a release gate.

## Current classification

| Item | Result | Reason |
|---|---|---|
| Auditor unit and negative-boundary tests | PASS | Executed in this checkout |
| Deterministic missing-artifact report comparison | PASS | Executed in this checkout |
| Candidate ZIP SHA/CRC/content inspection | NOT RUN | ZIP files absent |
| SHA ledger and Suite evidence cross-check | NOT RUN | Suite ledgers absent |
| Source, clean ZIP, isolated venv tests | NOT RUN | Suite source and ZIP absent |
| Clean deployment and Control Center preview | NOT RUN | Suite source and ZIP absent |
| Real Windows acceptance | NOT RUN | No Windows host or candidate |
| Real browser / youtube.com acceptance | NOT RUN | No extension candidate or browser evidence |
| Real RPLAY production validation | NOT RUN | No authorization, source, or production environment |

## Required continuation input

Stage the three immutable ZIPs and the corresponding v0.30 workspace/evidence
bundle without overwriting this checkout. The next audit must first compare
their digests and internal ledgers, then extract only after the archive checks
pass into a new temporary directory. Lifecycle changes should begin only after
the v0.30 source and its rollback material are verified.
