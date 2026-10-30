# GPT1 v4.0 — OPFS journal + cross-instance locks research (CANDIDATE / NO_GO)

Date: 2026-10-30 JST. Product source is **not published or merged**. All results below are from synthetic in-memory OPFS.

## P0 root causes
1. Original RPLAY v2.67 can evict a good segment *before* a new write fails (Issue #31).
2. v3.9.1 candidate delays eviction but an incomplete deletion after a committed new segment can leave overbudget state.
3. In-process queues do not serialize independent store instances.
4. MV3 service workers can be stopped unexpectedly; heap-only progress state is not durable.

## Local v4.0 development-only prototype
- A cooperative **exclusive** lock per origin + namespace wraps put, get, has, list, stats, recovery; no lock manager means BLOCKED, never silent fallback.
- A separate `rsp_txn_v40/<namespace>/<id>.json` journal records the staged ID, content SHA256/length and intended eviction victims **before** writing a new pair.
- Replay: if the new pair matches size and SHA256, resume idempotent victim removal; if the new pair is incomplete and all victims are intact, remove only the new staging leftovers; if either case cannot be proven, retain the journal and require manual recovery.
- A post-write deletion failure that is subsequently recovered is reported as **COMMITTED_RECOVERED_AFTER_ERROR**, not falsely categorized as data never saved.
- Unknown journals, corrupt metadata, tampered existing victims and unmatched IDs fail closed.
- No data is deleted for quota *before* attempting a new write; if there is no physical staging space, fail without deleting old data.

## Evidence
- RPLAY v3.9.1 derived candidate modules + journal/locks wrapper: **62 / 62** synthetic OPFS tests PASS, in a nonroot, separate Linux network namespace, Node 22.16 with file-read permissions limited to source/test files.
- Self-contained synthetic store test containing **no RPLAY code**: **39 / 39** PASS in local Node.
- Local evidence-gate Python unit tests: **12 / 12** PASS.
- Source ZIP SHA256, journal/source SHA256 and test logs are preserved with the local candidate. Archive and its tests are not uploaded to public GitHub.
- The code and fixture are provided as an **offline ZIP candidate** through ChatGPT, not as a production extension.

## Explicit non-go findings
- **Real Chromium / Firefox OPFS has not been tested**, nor power loss, actual storage quota, real Web Locks in MV3 Worker, cross-origin storage sharing, signed provenance, HLS/DASH recording or MP4 decode.
- Cooperative Web Locks work only if *all* writers agree on the origin/lock name. Any unwrapped call to the original store invalidates coordination. Deadlock/lock-wait timeout and worker cancellation policy are not implemented.
- Journal file close is not a proven all-file atomic transaction or durability barrier. Damaged records intentionally cause BLOCKED/manual recovery; journal tamper authentication is not implemented.
- Staging requires **temporary physical capacity** for new data, metadata and journal. Refusing writes under tight physical quota is preferable to destructive precommit eviction.
- Remain Issue #31 OPEN, PUBLICATION_HOLD and CANDIDATE_NO_GO. No main push, merge, deletion, release, or product ZIP upload.

## Further work (highest priority)
1. Port the synthetic coordinator into an offline extension fixture using browser-provided OPFS and Web Locks, testing forced termination and restart with isolated profiles.
2. Enumerate all RPLAY storage mutation entrypoints and require the same lock protocol.
3. Add bounded per-fragment retry/ledger contracts as seen in hls.js `fragLoadPolicy` and yt-dlp's `--fragment-retries`, keeping network fetch separate from durable commit.
4. Verify full stream reconstruction, HLS/DASH discontinuities and FFmpeg decoded MP4 + audio.

Primary references:
- https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API
- https://developer.mozilla.org/en-US/docs/Web/API/FileSystemSyncAccessHandle/flush
- https://developer.mozilla.org/en-US/docs/Web/API/FileSystemWritableFileStream/write
- https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle
- https://github.com/video-dev/hls.js/blob/master/src/config.ts
- https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/options.py
