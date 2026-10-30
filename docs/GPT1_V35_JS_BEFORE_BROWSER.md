# GPT1 v3.5 — JavaScript evidence required before isolated product browser load

## Motivation
Previously the isolated product browser gate required ZIP/manifest integrity but did not require the independent `extension_js_preflight` to finish successfully. A candidate with missing Node tooling, unrecognized worker imports or failed JS syntax could still reach browser load.

## Changes
Before creating a synthetic or product browser profile, `isolated_extension_e2e.inspect()` now invokes `extension_js_preflight.inspect(archive, trusted_sha256, selected_root)`. A pass requires **all**:
- result `PASS_SYNTAX_REFS_ONLY` (not `PARTIAL`)
- candidate SHA256 exactly equals the independently supplied trusted digest
- selected root exactly matches the validated MV3 root
- a positive integer number of JS scripts checked (not a boolean)
- no issues, warnings or syntax failures
- `release_decision=CANDIDATE_NO_GO`

On failure, missing dependency, incomplete or conflicting evidence, the product browser remains `NOT_RUN`. A JavaScript failure returns FAIL; unknown/partial evidence yields BLOCKED. The synthetic-only environment probe remains independent and does not need a product ZIP.

## Verification
- Local Python 3.13, `test_isolated_extension_e2e.py`: 63/63 PASS, including 10 added negative/positive tests for incomplete JS provenance and fail-closed behavior.
- Local `test_extension_js_preflight.py`: 19 PASS / 2 SKIP (the two skipped cases require the existing `artifact_gate.py` from the full GitHub checkout).
- Cross-platform GitHub checks must be observed against this PR's actual head SHA; no claim of product load is inferred from unit tests.
- No product ZIP, credentials, browser profile, signed media URL, or recording uploaded to this repo.

## Remaining gates
1. Check that synthetic MV3 worker/popup/storage succeeds using Playwright's matched Chromium and isolated non-root network namespace.
2. Verify the original candidate ZIP's trusted provenance and digest; calculating its own SHA256 is not authentication.
3. Load RPLAY v2.67 Worker and popup offline; then independently test StreamHarbor / YouTube Optimizer and Firefox temporary add-ons.
4. Synthetic HLS/DASH segments, MP4 file and restart/crash recovery are separately required, followed by Windows user-device validation.

## References
- https://playwright.dev/python/docs/chrome-extensions
- https://playwright.dev/docs/browsers
- https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle
- https://extensionworkshop.com/documentation/develop/temporary-installation-in-firefox/

**Release remains CANDIDATE_NO_GO; PUBLICATION_HOLD remains active. Main and products unchanged.**
