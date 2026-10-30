# GPT1 v4.1 | Real Chromium OPFS + Web Locks synthetic probe

**2026-10-30 JST — development harness ONLY; CANDIDATE / NO_GO / PUBLICATION_HOLD.**

## Problem addressed

The RPLAY v4.0 journal/locking coordinator completed 62 product-derived and 39 synthetic Node test cases, but its OPFS and Web Locks APIs were emulated. This new probe uses a **separate, synthetic MV3 Chromium extension** with no product source, media URLs, host permissions, external network or ordinary profile. It runs inside the existing, previously demonstrated GitHub-hosted **nonroot isolated network namespace** with a normal Chromium sandbox; no `--no-sandbox` fallback.

## Real browser checks

- Exact synthetic extension `chrome-extension://<id>/worker.js` observed; popup pages report the same runtime ID and origin.
- Create a file via real `navigator.storage.getDirectory()`, `createWritable()`, `write()`, `close()`, then compare readback bytes and SHA256.
- Replace the file content in a second writable stream, call `abort()`, verify original committed bytes survive.
- Open **two independent extension pages** and verify a real `navigator.locks.request()` exclusive lock held in page A blocks page B until release.
- Reopen the browser with the same disposable profile; confirm the bytes and hash still match; confirm a lock held at context close was released on reopening.
- Fail closed on missing browser extension support, absence of any required result, incorrect origin/worker ID, unchanged lock state, missing OPFS or weak evidence.
- Scope does **not** include sudden OS power loss, durability after kernel crash, real RPLAY data, Firefox, HLS/DASH, MP4 output or real sites.

## Verification workflow

- `ai/browser_opfs_runtime_probe.py` — executes only with a trusted parent network namespace receipt and the isolation preflight checks from `ai/isolated_extension_e2e.py`.
- `ai/tests/test_browser_opfs_runtime_probe.py` — synthetic-only evidence checks run on Ubuntu and Windows Python 3.11/3.14, without starting browsers.
- `ci/gpt1_python_synthetic_control.sh` — after the known-good MV3 worker/popup control passes, run this new OPFS probe in the **same isolated network namespace**, using the disposable CI Chromium binary.
- `.github/workflows/gpt1-workspace-preflight.yml` — automatically runs new offline unit tests and the isolated browser job on repository-owned pull requests.
- Test result must explicitly be `PASS_SYNTHETIC_BROWSER_OPFS`; otherwise exit nonzero and report BLOCKED. Neither test result may grant release approval.

## Architectural limitations / next steps

- Web Locks are **origin-scoped and cooperative**; all writers must obey one name and lock protocol. Per-instance queues cannot prevent other extension contexts from writing directly.
- FileSystemWritableFileStream generally writes to a temporary destination; successful `write()` is not a commit. Separate `close()`, readback/hash, and ledger transaction evidence.
- Extension MV3 Service Workers may be terminated and restarted. Prove journal replay and ensure a lock does not persist through real context teardown or crash.
- Browser close/restart is **not** power-loss simulation. The release gate still requires real-product ZIP provenance, actual Chromium/Firefox OPFS, journal fault injection, platform-specific browser behavior and user-device tests.
- Existing product Issue #31 remains open. No RPLAY product code or patch is committed, approved, merged or released by this CI workflow.

## Primary specifications / existing tool research

- MDN Web Locks API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API
- W3C Web Locks spec: https://www.w3.org/TR/web-locks/
- MDN Writable File write/close: https://developer.mozilla.org/en-US/docs/Web/API/FileSystemWritableFileStream/write
- Chrome extension worker lifecycle: https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle
- Playwright Chromium extension testing: https://playwright.dev/python/docs/chrome-extensions
- hls.js fragment and gap handling: https://github.com/video-dev/hls.js/releases
- yt-dlp fragment/file retry controls: https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/options.py

**The CI log, not this proposal, is the source of truth for actual browser PASS or BLOCKED.**
