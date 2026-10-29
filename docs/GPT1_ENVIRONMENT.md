# GPT1 | GitHub repository environment preflight

This repo has a **read-only, offline** structural preflight. It is supplementary to existing filter/runtime CI; it is **not** evidence of full browser, Windows device, authenticated site, recording, or release acceptance.

## Run locally

```sh
python ai/gpt1_preflight.py --json
python -m unittest discover -s ai/tests -p test_gpt1_preflight.py -v
```

**v1.1 fail-closed semantics:** missing Git metadata is `PARTIAL` (exit 2) when running locally and `FAIL` (exit 1) under `--require-git`. Invalid file/directory types, symbolic links, malformed state, non-string repository IDs and ambiguous governance values are rejected. CI invokes `--expected-repository r20942097-hue/faaff --require-git`. Only a fully evaluated structural audit is `PASS` (exit 0). Product E2E and publishing checks always remain `NOT_RUN` under this utility.

Requires Python 3.11+. The script checks `ai/PROJECT_STATE.json`, baseline repository files, the P0 / PUBLICATION_HOLD / NO_NEW_INTERNAL_PUSH governance gate, and (in Git checkouts) tracked ZIP/7z archives. Missing Git metadata produces **NOT_RUN**, never a false success.

PR CI runs Python 3.11 / 3.14 on Ubuntu and Windows. Actions are pinned to complete commit hashes, use read-only `contents` permissions and do not persist checkout credentials. The PR event has no path filter, so its checks are not left pending on documentation-only PRs.

## Boundaries

- `faaff` is the engineering/integration hub. Its `main` does **not** contain the complete Watcher runtime; a green preflight does not claim those tests ran.
- `s` is the canonical subscription repository; its stable filter paths and generated lists are not modified by preflight.
- `s` changes must be merged and then re-imported into `faaff` by a separate provenance-verified PR. A proposed PR branch is not an accepted release or pinned import.
- Do not add release archives, secrets, browser profiles, credentials, recordings, or diagnostic logs to Git.
- Keep the protected `main` branch and PUBLICATION_HOLD intact. This proposal does not merge, publish, or alter repository visibility.

Output status vocabulary: PASS / FAIL / PARTIAL / NOT_RUN. CLI exits 0 = structural PASS, 1 = FAIL, 2 = PARTIAL. A structural PASS is **not** end-to-end acceptance.

## v1.2 / cross-repository source provenance
- Offline: `python -m unittest discover -s ai/tests -p test_source_sync_guard.py -v` (15 negative/positive tests).
- Live observation (read-only): read the current public `s/main` commit and run `python ai/source_sync_guard.py --upstream-head <40-hex SHA> --json`.
- `IN_SYNC` (exit 0): observed upstream SHA matches manifest, registry and state.
- `UPSTREAM_DRIFT` (exit 2): upstream changed; this is a review signal, **not** automatic import or publication.
- `INVALID` (exit 1): malformed or contradictory metadata.
- A separate `gpt1-source-sync-audit.yml` is proposed for manual or Monday UTC execution *after merging*. No scheduled checks are active from this draft PR.
- Existing `python ai/check_hub.py` remains the byte-for-byte Git blob integrity gate. Metadata sync alone does not prove source integrity.

## v1.3 / candidate ZIP integrity gate

- CLI: `python ai/artifact_gate.py path/to/candidate.zip --json`
- Verify an expected digest with `--sha256 <64-lowercase-hex>`. Without a supplied digest, the CLI **computes** SHA-256 but cannot authenticate the origin.
- Uses only standard-library ZIP APIs and **never extracts** files, executes scripts, or reads credentials.
- Checks path traversal, duplicates (casefold + Unicode NFC), Windows reserved names, Unix ZIP symlinks, encryption, unsupported compression, CRC/data-length, nested ZIPs, global expansion/member limits, and input ZIP size.
- Supported compression methods: stored and deflated; other codecs are conservatively rejected.
- Local/regression: `python -m unittest discover -s ai/tests -p test_artifact_gate.py -v`. PR workflow runs this on Python 3.11 and 3.14, Linux and Windows.
- Hard limits are deliberately conservative for development **source ZIPs**, not multi-gigabyte recordings: 1 GiB input, 128 MiB per entry, 768 MiB cumulative expanded bytes, 50,000 global entries, up to 100 archives, max nesting depth 2. These limits are policies, not universal ZIP validity rules.
- **PASS is only ZIP structure/CRC verification**. It does NOT mean functional E2E, signed provenance, release approval, or suitability of source code.
- GitHub Actions artifact attestations should be used later for actual released binaries only if the release/publishing gate is approved; generating attestations is not itself a security verdict.

## v1.4 / product-quality evidence registry

- `ai/product_quality.json` registers **RPLAY**, **StreamHarbor**, and **YouTube Optimizer** with six distinct QA gates: source integrity, archive integrity, unit tests, extension install, real-site E2E and Windows device testing.
- Initial statuses are explicitly `NOT_RUN`. This does **not** erase or contradict external test results; it means the hub has not independently validated those records.
- `python ai/product_quality.py --json` audits the JSON structure and evidence-reference syntax; `python -m unittest discover -s ai/tests -p test_product_quality.py -v` covers 27 failure/success cases.
- `PASS` evidence must include a safe public GitHub Actions run URL or a limited relative repository path, and source/archive integrity must additionally record hashes.
- The validator **does not fetch evidence** or verify signed attestations; a syntactically valid reference is not proof of a test run.
- The output always retains `CANDIDATE_NO_GO`, including when every claimed test says `PASS`; human release approval and real browser/service validation are separate requirements.
- Never commit private URLs, browser profiles, signed stream URLs, cookies, recordings or local environment logs to the **public** repository.
- GitHub Actions runs this registry test on Linux and Windows, Python 3.11 and 3.14. Repository gates `PUBLICATION_HOLD` and `NO_NEW_INTERNAL_PUSH` remain in effect.

GitHub's current recommendations include immutable dependency locks for Actions where supported. Existing full-commit SHA pins remain unchanged; moving to a lockfile would be a separate reviewed migration, not an automatic replacement. See https://docs.github.com/en/actions/reference/security/secure-use
