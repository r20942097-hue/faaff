# Development environment v5 — verified source-intake guard (2026-10-30)

**Release status: NO_GO.** Do not infer product E2E from infrastructure CI, synthetic browser tests, or file hashes.

## Evidence from user-provided source archives (local, read-only)
- `DEV_ENV_v4.2.1_REAL_OPFS_JOURNAL_CI_VERIFIED_NO_GO.zip`: SHA256 `1e31fe4accbe4b8165fc4e4ca6c8c94601f549b30db2ea42a0e82fb9396bd9b9`; 27 ZIP members; CRC PASS; embedded manifest 26/26 matching byte hashes; Node synthetic contract tests 62 + 38 + 12 = 112 PASS. Actual product OPFS browser tests NOT_RUN.
- `RPLAY_Stable_Player_v2.67.0_LEDGER_ASSEMBLY_AUTO_CANDIDATE_NO_GO.zip`: SHA256 `ac9ae88db808408baf6c52099bfccc84399a4eb52381ef6780e9f12873717444`; 5,307 ZIP members; CRC PASS; four canonical `segment_store.js` copies have identical SHA256 `3f1a00b89207f8cb783f59152db6ff230c300569f79b1e1eb691353b70218b9e`.

That source hash matches [P0 Issue #31](https://github.com/r20942097-hue/faaff/issues/31): premature eviction of a valid segment before a new `.bin` and `.json` commit, leading to possible data loss after a failed write. A different archive SHA than the Issue's reproduced archive does **not** negate the same file-level defect.

## Implementation
- `ai/source_intake_guard.py` scans an explicitly supplied ZIP **without extracting or executing it**, streams its overall SHA256, checks up to four canonical source copies with bounded decompression and CRC, detects duplicate/mismatched copies, and classifies `BLOCKED_KNOWN_P0`, `BLOCKED_INTAKE`, or `NEEDS_REVIEW`. It never returns `GO`.
- `ai/test_source_intake_guard.py`: 9 pure-Python regression tests including archive hash mismatch, unknown source, multiple different copies, duplicate copies, invalid ZIP and fail-closed output.
- `environment-readiness.yml`: execute the tests on Windows and Ubuntu without storing a product archive in GitHub.
- The product ZIP stays outside the git repository. No real-stream URL, credential, cookie or recording is committed.

## Reproduction
```sh
python -m unittest ai.test_source_intake_guard -v
python ai/source_intake_guard.py INPUT_RPLAY.zip --expected-sha256 VERIFIED_64_HEX --output rplay_source_intake.json
```
Exit code 3: known P0; 2: unknown, absent, malformed, or otherwise non-accepted source. There is deliberately no product-release PASS output.

## Follow-up
1. Reconcile overlapping Draft [PR #25](https://github.com/r20942097-hue/faaff/pull/25) (journal research) and [PR #34](https://github.com/r20942097-hue/faaff/pull/34) (tooling/readiness); do not merge either automatically.
2. Stage and test a minimal **non-destructive eviction** or WAL/journal migration proposal against authentic pinned sources (not only independent synthetic code). Verify before-write, mid-write, metadata-close, quota, post-commit deletion, cross-tab concurrency, restart/corruption.
3. Run isolated Chromium/Firefox actual extension source, FFprobe packet/PTS/DTS, HLS/DASH and long-running Windows tests before any release.

## Official guidance cross-check
- GitHub Actions pinning and artifact provenance: https://docs.github.com/en/actions/how-tos/secure-your-work
- Mozilla web-ext v10 requires Node 22+: https://github.com/mozilla/extension-workshop/blob/master/src/content/documentation/develop/web-ext-command-reference.md
- Chromium extension test requirements: https://playwright.dev/docs/chrome-extensions
- ffprobe packet inspection: https://ffmpeg.org/ffprobe.html

## Exact-source synthetic defect reproduction

- An isolated Node in-memory OPFS adapter loaded the **actual** `src/segment_store.js` from the user-provided v2.67 archive, after strict SHA256 comparison.
- Injected `QuotaExceededError` while writing replacement B after saved A; B threw `SEGMENT_QUOTA_EXCEEDED` and previously committed A was no longer present (`old_A_survives=false`). Thus the Issue #31 known-bad symptom is reproduced from these exact bytes.
- `ai/reproduce_precommit_evict.cjs` is the portable reproducer. It deliberately requires the original file as a positional argument and refuses a different SHA256. The original product source is **not committed**. Run `node ai/reproduce_precommit_evict.cjs PATH_TO_VERIFIED_segment_store.js` in an isolated offline workspace.
- This is a *known-bad reproducer*, not a passing product regression, nor proof that a proposed patch is safe. Real OPFS crash, storage quota, Web Locks, saved media, and Firefox/Chromium product E2E remain NOT_RUN.

