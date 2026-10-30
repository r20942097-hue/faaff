# Development environment v13 — Windows native browser termination, synthetic OPFS

Date: 2026-10-30. Independent Windows Server 2025 testing only, product NO_GO.

## Why v13 is necessary

Prior v10/v12 full browser-process termination tests ran only on Linux. Windows 2025 passed pure Python readiness but did not terminate an actual browser. v13 launches Playwright's Chromium/Firefox into distinct temporary persistent profiles from a child Python process in a new Windows process group. It requires actual browser OS process descendants of that child, force-terminates only those owned descendants with psutil (Windows TerminateProcess), terminates the leader, waits for process exit, and reopens the exact disposable profile in a new browser.

The v12 child fixture commits a synthetic blob B and closes the generation-2 manifest while retaining old A; it reports READY only after an exact-byte/hash readback. After forced termination v13 validates B and the manifest, cleans old A, repeats cleanup idempotently, and verifies B again after a second restart.

Windows uses a background thread and Queue to await stdout; using select.select() on Windows pipe is invalid. Failures use bounded sanitized codes, never raw profile paths or credentials. Only loopback localhost and synthetic bytes are used. This is not POSIX SIGKILL.

## Test and release boundaries

- A successful job establishes only a Windows hosted CI observation for the supplied synthetic inputs.
- Not a native installed Firefox 159/Chrome user profile, not real product store code, authenticated recording, HLS/DASH/MP4, real-site capture, Firefox physical quota, power failure or disk corruption.
- Windows process termination via psutil is not proof of resilience against kernel crash, sudden power loss, or multi-file atomicity.
- PR #34 stays Draft/unmerged, main and live distribution untouched. P0 RPLAY Issue #31 stays OPEN, products NO_GO.

## Standalone commands (Windows only)

python -m unittest ai.test_opfs_windows_terminate_fixture -v
python -m playwright install chromium firefox
python -m ai.opfs_windows_terminate_fixture --browser chromium --output chromium-result.json
python -m ai.opfs_windows_terminate_fixture --browser firefox --output firefox-result.json

Official sources:
- https://playwright.dev/python/docs/browsers
- https://playwright.dev/python/docs/api/class-browsertype
- https://developer.mozilla.org/en-US/docs/Web/API/FileSystemFileHandle/createWritable
- https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria
