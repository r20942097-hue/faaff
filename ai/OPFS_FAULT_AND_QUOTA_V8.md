# Development environment v8 — cross-browser OPFS fault injection + real Chromium quota

No product archive, real account, stream, private browsing profile, or RPLAY runtime is required. Tests use disposable browsers and deterministic synthetic bytes. **This is toolchain verification, not a production repair. Product release remains NO_GO.**

## A. Cross-browser application-fault matrix

`ai/opfs_fault_matrix.py` runs on Chromium and Firefox via Playwright 1.64.1 using real browser OPFS. Six independently initialized scenario directories test:

1. Simulated `QuotaExceededError` injected before B write (not real storage quota).
2. Abort uncommitted binary writer.
3. Interrupt after B binary closes, before manifest changes.
4. Abort manifest writer after B is closed.
5. Interrupt after manifest closes, before old A is cleaned up.
6. Reject a different payload trying to reuse a committed ID.

The test records committed generation, validates actual OPFS data SHA-256, restarts the browser with a temporary persistent profile, reconciles known orphans and proves the active blob has not changed. In two separate tabs of the same origin, Web Locks protects two concurrent commits; generations must serialize 2 then 3, and the last committed bytes survive a browser restart.

`ai/test_opfs_fault_matrix.py` has ten fail-closed unit tests; the browser matrix has its own JSON-only artifacts. No raw profiles, cookies, sources or credentials are uploaded.

## B. Chromium engine-enforced quota (separate experiment)

`ai/chromium_native_quota.py` writes a committed 32 KiB baseline in a fresh localhost origin. The runner calls the Chromium DevTools Protocol (CDP) `Storage.getUsageAndQuota`, then `Storage.overrideQuotaForOrigin` with a bound based on the measured usage. Writing an 8 MiB second file must raise a native browser `QuotaExceededError`; the original bytes and manifest are checked before and after graceful browser restart, with SHA-256 validation. Finally the CDP quota override is cleared.

A successful engine-enforced quota test is not the same as a simulated JavaScript throw. Firefox is not covered by this CDP-only method. No actual physical disk exhaustion or OS power loss occurs.

## Verification, 2026-10-30

- [Chromium + Firefox fault matrix](https://github.com/r20942097-hue/faaff/actions/runs/41018898862): both browser jobs PASS, individual JSON artifacts.
- [Chromium native quota](https://github.com/r20942097-hue/faaff/actions/runs/41019265079): PASS, JSON artifact.
- Windows Server 2025 + Ubuntu 24.04 audit jobs exercise pure-Python unit tests; browser tests run separately in Ubuntu CI.
- Product source integration, real HLS/DASH/MP4 capture, actual product concurrency, arbitrary machine crash and Windows-native browser product E2E remain NOT_RUN.

## Reproduce

```sh
python -m pip install -r ai/requirements-browser.txt
python -m playwright install --with-deps chromium firefox
python -m unittest ai.test_opfs_fault_matrix ai.test_chromium_native_quota -v
python -m ai.opfs_fault_matrix --browser chromium --output chromium-fault-matrix.json
python -m ai.opfs_fault_matrix --browser firefox --output firefox-fault-matrix.json
python -m ai.chromium_native_quota --output chromium-native-quota.json
```

## Limitations and future work

- Add forced-process-crash and physical profile durability checks separately; clean profile restart does not test a sudden power loss.
- Add Firefox-native quota exhaustion using browser-supported mechanisms without assuming CDP is available.
- Test `FileSystemSyncAccessHandle` worker-level flush, lock contention and interruption where supported.
- Reuse these tests when real product candidates have source provenance and have been staged in an isolated test branch. Never conflate this with Issue #31 remediation.
- Maintain Draft PR #34 and separate research PR #25; do not alter `main`, release artifacts, or `s/main` filter URLs.

## Official reference documents
- https://chromedevtools.github.io/devtools-protocol/tot/Storage/#method-overrideQuotaForOrigin
- https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria
- https://developer.mozilla.org/en-US/docs/Web/API/FileSystemFileHandle/createWritable
- https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API
- https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context
