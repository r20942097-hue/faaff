# GPT1 v3.8.2 — OPFS and local HTTP contract follow-up

**Status: CANDIDATE_NO_GO / PUBLICATION_HOLD.** This report records local, isolated tests; it is not evidence of GitHub CI executing these suites.

## Real user-supplied source examined (not committed)
- RPLAY v2.67 Chromium candidate ZIP SHA256: `7bfdc92cc8c5cee421548f5a86a03b4dd4bdd097c088d09c58b4becf6c2cce35`. This digest is a byte identity only, not an origin signature.
- Actual JS modules: `segment_store.js`, `segment_assemble.js`, `recovery_core.js`, `sha256.js`; alongside `http_resume.js`, `hls_window.js`, `hls_ledger.js`.
- Separate local in-memory OPFS test harness (74 tests) and Python fail-closed ZIP/sandbox verifier (31 tests) PASS. A **known bad** eviction-before-write loss is explicitly reproduced, tracked as [P0 #31](https://github.com/r20942097-hue/faaff/issues/31).
- Experimental patch proposal moves eviction from pre-write to post-write. Under 75 synthetic cases, an injected candidate write/metadata failure leaves previous valid segments intact. **This is NOT a complete atomic transaction**. Physical quota, post-commit victim deletion failures, process crash and multi-context races remain unverified.
- A separate synthetic localhost HTTP server test executed 18 checks against the actual RPLAY pure `http_resume` and HLS window/ledger modules in a Linux network namespace with only loopback enabled. Verified 200/206/416 semantics, Content-Range, If-Range, ETag changes, short bodies, wrong range, and HLS loss reconciliation. This does **not** exercise full recording/download scheduling or DASH.
- External network route unavailable; Node process unprivileged with filesystem/process permission restrictions. No credentials, signatures, media streams, product ZIPs or source modules copied into this repository.

## Evidence semantics / no false GO
- These are local results, **not** the CI's verified 417-case prior suite and not browser OPFS tests.
- `segment_assemble.js` concatenates bytes, it does not decode or remux; TS sync bytes are not full demux or audiovisual correctness.
- Browser extension E2E, real browser OPFS, Windows end-device, crash/power failure, HLS/DASH recording and MP4 full decode: `NOT_RUN`.
- Product release: `CANDIDATE_NO_GO`; this document neither alters `product_quality.json` nor certifies an artifact.

## Next gates (priority)
1. Design a crash-recoverable, journaled commit for segment write and bounded-budget eviction, with concurrency locking and no old committed data deletion before safe commit.
2. Inject failures before/after every phase on disposable real Chromium/Firefox OPFS, and verify byte hashes and restart inventory.
3. Load the exact product archive inside the verified sandbox only after trusted provenance + source integrity; keep sensitive URLs out of test fixtures.
4. Extend localhost HLS/DASH acquisition end-to-end and full FFmpeg/ffprobe media decode.

Official sources:
- Chrome MV3 lifecycle: https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle
- MDN OPFS: https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system
- MDN writable close semantics: https://developer.mozilla.org/en-US/docs/Web/API/FileSystemFileHandle/createWritable
- HTTP Range RFC 9110: https://www.rfc-editor.org/rfc/rfc9110.html
- HLS RFC 8216: https://www.rfc-editor.org/rfc/rfc8216.html
