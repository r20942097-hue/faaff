# GPT1 v3.0 | Offline MV3 extension control gate (CANDIDATE / NO_GO)

2026-10-30 JST. This is a proposed hardening of v2.9.1, **not** a release gate.

## Verified background

- GitHub Actions synthetic-extension-sandbox run `40938571378`, job `123675548997` succeeded with Node Playwright 1.62.1 + Chromium 156.0.8078.0, including worker/popup exchange and restart storage, in a Linux network namespace.
- Python Playwright 1.57.0 + system Chromium 144.0.7559.96 on the isolated container **did not observe a synthetic extension worker**. The same outcome occurred when a RPLAY candidate was supplied. This is **harness BLOCKED**, not evidence of a RPLAY defect.
- Official Playwright docs: extension support is documented for a **persistent Chromium context**, the **`chromium` channel**, and preferably bundled Chromium; branded Google Chrome/Edge no longer support the command-line sideload flags. See https://playwright.dev/python/docs/chrome-extensions and https://playwright.dev/python/docs/browsers .
- Firefox uses a distinct pipeline: temporary installation through Mozilla `web-ext` or about:debugging. A Chromium PASS does not establish Firefox compatibility. See https://extensionworkshop.com/documentation/develop/getting-started-with-web-ext/ .

## New fail-closed controls

1. **Network:** only a non-root Linux network namespace may run the product browser. Reject missing namespace receipts, matching parent namespaces, default routes, and **any non-loopback IPv4/IPv6 route**. Receipt is environment evidence, not cryptographic proof of an isolated wrapper.
2. **Provenance:** caller must supply a trusted expected SHA256; mismatch blocks. `extension_source_preflight` delegates ZIP CRC/traversal checks to `artifact_gate`. A SHA256 computed from the archive alone does not authenticate a publisher.
3. **MV3 only:** only PASS manifests with `manifest_version: 3` and an explicitly selected ZIP root can enter the Service Worker gate. MV2 needs a different browser test.
4. **Synthetic positive control:** the throwaway MV3 worker accepts a ping, asynchronously writes `chrome.storage.local`, and replies. The popup JavaScript verifies the reply and stored value, then changes a marker from PENDING to a **specific success string**. The harness waits for the dynamic marker. The static HTML alone cannot pass.
5. **Real extension (later):** launch using a fresh profile with sandbox enabled and external network isolated; check registration/worker manifest and declared popup only. Does not visit sites, authenticate, record, or download. If synthetic control fails, product never executes.
6. **Traceability:** report Python Playwright version and whether the Chromium binary is Playwright-managed or an explicitly overridden system executable. Only the former follows the preferred documented path.
7. **Playwright API contract:** Python `Worker.evaluate()` has no `timeout=` parameter. The previous v2.9 argument was invalid and is removed; an offline regression test guards this behavior.
8. **Release policy:** output cannot imply GO. Even a browser pass remains `PASS_OFFLINE_ONLY` and `CANDIDATE_NO_GO`. User Windows and real streaming sites remain NOT_RUN.

## Automated checks

```
python -m unittest discover -s ai/tests -p test_isolated_extension_e2e.py -v
```

27 offline unit tests pass locally on Python 3.13.5. The GitHub PR preflight runs the suite on Ubuntu and Windows with Python 3.11 and 3.14. The Windows suite uses mocks and never attempts Linux namespaces.

## Separate execution decision

The code does **not** automatically run user products in public CI. To verify a real product, first establish the trusted ZIP provenance and source commit, then use an isolated approved runner with Playwright-matched Chromium and an explicit, externally verified network isolation wrapper. The initial synthetic test must pass. Do not disable the sandbox, pass authenticated URLs, or reuse user profiles to evade the gate.

## Remaining acceptance gates

- Python Playwright 1.62.1 + Chromium 156 synthetic positive control on the successful GitHub runner: NOT_RUN for this Python harness.
- RPLAY, StreamHarbor, YouTube Optimizer actual worker/popup: NOT_RUN under the v3.0 harness.
- Firefox temporary install, real-site E2E, HLS/DASH/MP4 completeness, long-session recovery, Windows user device: NOT_RUN.
- Main merge, external release, runtime deployment: NO_GO / PUBLICATION_HOLD.