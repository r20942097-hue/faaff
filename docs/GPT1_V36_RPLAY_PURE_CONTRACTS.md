# GPT1 v3.6 — Isolated RPLAY pure-module contract evidence (NOT a product GO)

Date: 2026-10-30 JST. This document is an audit receipt. The actual user product archive is deliberately **not** committed to the public repository.

## Evidence / explicit limits
- RPLAY v2.67 Chromium 67-file source candidate ZIP was read-only checked against previously recorded SHA-256 `7bfdc92cc8c5cee421548f5a86a03b4dd4bdd097c088d09c58b4becf6c2cce35`. SHA match is *not* signed provenance or Git commit binding.
- Bounded ZIP inspection: 67 entries, including CRC, Windows-safe names, collision checks, max size and symlink checks. Only `hls_window.js`, `hls_ledger.js` and `http_resume.js` were staged as test inputs.
- Real pure product JS executed using **synthetic metadata only**, inside Linux user/network namespaces without external routes, non-root UID and Node 22.16.0 `--permission` filesystem/child-process restrictions.
- **417/417 PASS**: 256 deterministic HTTP Range properties, 128 deterministic HLS/ledger gap properties, 30 basic/negative cases, 3 security controls (nonroot UID, denied arbitrary file read, denied child-process spawn).
- **17/17 PASS**: synthetic Python security/quality gate tests for wrong digest, malformed ZIP, missing source, symlinks, traversal, Windows path collisions, incomplete isolation receipt and no-release invariant.
- Observation is classified `PASS_OFFLINE_CONTRACT_ONLY`. Browser install: `NOT_RUN`; recording, MP4, Firefox and Windows device: `NOT_RUN`; release decision: `CANDIDATE_NO_GO`; source provenance: `NOT_VERIFIED`.
- Test harness and sanitized receipt distributed separately as a user-downloadable candidate bundle, not as a public GitHub Actions artifact. The CI cannot claim that the candidate ZIP was tested without independently receiving the same exact bytes and verified provenance.

## Existing-tool comparison (public reference only)
- [Chrome MV3 SW lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle): worker global state can disappear on idle termination; persist state and test restart.
- [yt-dlp documented options](https://github.com/yt-dlp/yt-dlp/blob/master/README.md): bounded per-fragment retries, concurrent fragments and retry delays; do not mix acquisition success with verified output.
- [cat-catch release notes](https://github.com/xifangczy/cat-catch/releases): HLS BYTERANGE support, duplicate-fragment fixes, retries and Firefox behavior. These are known failure-case ideas, not imported code.
- [Playwright extension harness](https://playwright.dev/python/docs/chrome-extensions): persistent bundled Chromium for synthetic MV3 browser checks. A passing synthetic control is not real RPLAY recording approval.

## Next gates, in order
1. Independent original source/build provenance; ensure the archive matches pinned source commit.
2. Full isolated, offline RPLAY Worker + Popup registration using a known-good Playwright/Chromium stack. Do not upload the user archive into a public PR run.
3. Restart/crash recovery of segment ledgers, OPFS, 200/206/416 Range resumes and *verified files* from locally generated HLS/DASH samples.
4. Full MP4 output integrity/ffprobe or decode testing, Firefox MV3, Windows device and longer recordings.
5. Keep publication hold until each evidence-backed product-specific gate is explicitly passed.

Protected `main` and user original archives remain unchanged. No code copied from external downloader projects.
