# GPT1 v3.7 — RPLAY offline product-code contract checks

Date: 2026-10-30 JST. **CANDIDATE / NO_GO**. This is a development harness, not a release artifact.

## Design and evidence boundary

The local optional CLI tests three actual RPLAY v2.67 pure JS modules `hls_window.js`, `hls_ledger.js`, and `http_resume.js` using synthetic HLS playlists, sequence-ledger numbers and HTTP Range metadata. The local controlled Linux run completed **417/417** product-function contract cases. No browser loads, real media segments, actual recording or MP4 output were verified.

The verifier's own synthetic regression suite has **31 tests**. GitHub Actions runs those 31 Python tests on Ubuntu and Windows, Node `--check` for the JS test suite, and Linux Bash `-n` for the sandbox launcher. CI does **not** execute RPLAY JavaScript or accept a product ZIP from a public PR. A passing CI preflight must not be presented as product contract E2E.

## Security improvements

1. Verify a caller-supplied expected SHA256 for the exact candidate archive, without treating that self-contained hash as authentic publisher provenance.
2. Bound and CRC-check the ZIP. Reject unsafe paths, symlinks, device/special file types, Windows filename collisions and unexpected Manifest targets.
3. Pin SHA256 of the reviewed 417-case test suite (`875ada3ea10b862b251299d6fff6efbc91e5e1235dedeb8c2e7da67ff89cbfab`) and the isolation wrapper (`a71dba8f85418c0d8dd9cc4f4511d51ecc84dfe67d0da20697b4d5306ab76ea6`). No alternate scripts are permitted without an explicit reviewed update.
4. Linux local runner requires user/network namespaces, non-root execution, no external routes, Node `--permission` file read restrictions, a fixed receipt and **exact** result count 417, scope string, and isolation flags. If any check fails, return BLOCKED.
5. The Node permission model is not a substitute for system sandboxing. Do not use `--no-sandbox` or run arbitrary candidate code in a normal user account.
6. Preserve `product_browser=NOT_RUN`, `real_site=NOT_RUN`, `recording=NOT_RUN`, `mp4_output=NOT_RUN`, `windows_device=NOT_RUN`, and `release_decision=CANDIDATE_NO_GO`.

## Local reproduction (only authorized, independently checked archives)

```bash
python -m unittest discover -s ai/tests -p test_offline_product_contract_probe.py -v
node --check ai/tests/product_contracts.js
bash -n ai/tests/isolate_node.sh
python ai/offline_product_contract_probe.py /private/RPLAY_v267_CHROMIUM_67FILES_LOCAL_ONLY.zip --sha256 7bfdc92cc8c5cee421548f5a86a03b4dd4bdd097c088d09c58b4becf6c2cce35
```

The example SHA256 was observed from a supplied local candidate; Git commit linkage and publisher provenance remain **NOT_VERIFIED**. Do not commit the ZIP or extracted product JS to this public repository. Only the independent test harness and documentation are committed.

## Sources examined

- Chrome MV3 Service Worker lifecycle: https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle (event-driven worker, memory state lost on idle stop).
- RFC 9110 ranges: https://www.rfc-editor.org/rfc/rfc9110.html (206, 416, partial representation and validators).
- Node permissions: https://nodejs.org/api/permissions.html (defense in depth, not full sandbox).
- yt-dlp: https://github.com/yt-dlp/yt-dlp/blob/master/README.md (fragment retries and concurrency controls).
- Playwright: https://playwright.dev/python/docs/chrome-extensions (persistent Chromium context for real MV3 extension E2E).
- Firefox background: https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background (MV3 background scripts differ from Chromium).

## Next engineering gates

Signed or independently verifiable ZIP-to-Git source lineage; isolation-hardened real RPLAY Worker and Popup; crash/restart ledger atomicity; synthetic 206/416 and HLS/DASH media pipeline; output TS/MP4 decode and hash; Firefox and Windows real-device acceptance. Release stays PUBLICATION_HOLD.
