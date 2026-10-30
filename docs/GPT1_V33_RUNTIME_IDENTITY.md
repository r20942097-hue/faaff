# GPT1 v3.3 | Verified MV3 runtime identity (CANDIDATE / NO_GO)

## Purpose
Keep a worker or popup belonging to another extension from satisfying the isolated E2E gate. A browser startup and a rendered HTML document do not prove a candidate extension was loaded correctly.

## Evidence and validation
- New helpers `worker_extension_id(worker_url, manifest)` and `popup_identity_matches(identity, extension_id)`.
- Require the observed worker URL to have the `chrome-extension` scheme, a valid 32-character Chromium extension ID, and exactly the MV3 script declared by `background.service_worker`.
- After opening the declared popup, require `chrome.runtime.id` and `location.origin` to match the worker extension ID.
- Negative cases reject a worker from another scheme/script/ID, query/fragment suffixes, absent manifest worker and mismatching popup IDs/origins.
- Synthetic control must additionally prove worker/popup identities and dynamic popup/worker/storage roundtrip before a product archive is considered.
- The product gate remains **offline load-only**: a rendered popup is `RENDERED_ONLY`, not proof that download, recording, restart, storage correctness or website integration works.
- All failures remain BLOCKED; release decision stays CANDIDATE_NO_GO. No production content is uploaded to GitHub CI.

## Verification (2026-10-30)
- Local Python 3.13: 53 isolated-gate unit tests PASS.
- GitHub Actions run [40996941767](https://github.com/r20942097-hue/faaff/actions/runs/40996941767): 53/53 tests PASS on Ubuntu/Windows Python 3.11 and 3.14; synthetic MV3 worker identity, popup identity and message/storage roundtrip PASS on Ubuntu 24.04. One unrelated CI matrix job SKIPPED.
- Local Python Playwright 1.57 + system Chromium 144: network-isolated nonroot browser process STARTED but synthetic worker NOT_OBSERVED => BLOCKED. This is NOT a RPLAY product defect.
- Real RPLAY v2.67/Three Addons binaries were inspected statically only: no product E2E here. Windows desktop and real sites NOT_RUN.
- GitHub `main` is untouched and PR remains Draft.

## Next gates
1. Re-run exact-product source ZIP with a *trusted* SHA256 supplied independently from the build receipt, under the isolated, known-good browser toolchain. No real sites, uploads, authentication or recording.
2. Firefox is a distinct test flow (Mozilla web-ext); do not interpret a Firefox MV3 background script as a Chromium MV3 service_worker.
3. Review broad RPLAY host permissions `https://*/*` and requested APIs before any production release, without restricting legitimate cross-site recording until functional needs are verified.
4. Only then test synthetic HLS/DASH/media save consistency and separate Windows user-device acceptance.

Official references:
- https://playwright.dev/python/docs/chrome-extensions
- https://playwright.dev/python/docs/browsers
- https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle
- https://extensionworkshop.com/documentation/develop/temporary-installation-in-firefox/
