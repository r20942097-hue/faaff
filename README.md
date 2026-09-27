# Universal Live Watcher v6.9.0

Windows向けのRPLAY LIVE監視・録画基盤です。RPLAY API、Browser Bridge、yt-dlp Providerを分離し、HLS/DASH manifestの観測、FFmpeg録画、録画復旧、通知、SQLite履歴、Dashboard、Watchdogを統合します。SSRF/DNS-rebinding対策、ストリーム健全性監視、動的録画同時実行制御、MV3 alarmsによるBridge保守も含みます。

## v6.9 hardening

Manifest probing now rejects response bodies over the configured byte limit, including chunked/unknown-length responses. yt-dlp child processes use bounded stdout/stderr readers and terminate on oversized extractor output. HLS fallback observes LL-HLS PART/PRELOAD-HINT/SKIP metadata plus GAP/DISCONTINUITY telemetry without independently reconstructing partial segments. Release verification rejects symlink entries and runtime/local-state contamination.

The segmented fallback remains deliberately conservative: encrypted HLS, fMP4 initialization segments, byte-range reconstruction, and independent DASH downloading are not implemented. FFmpeg remains authoritative for complex live formats.

## v6.8 unified recorder core

HLS can use a conservative MPEG-TS segment fallback after repeated FFmpeg failures, with per-session variant state, quality preference, live-edge control, initial-take limiting, crash-safe journaling, retry/backoff, variant failover, and time/byte limits.

The Browser Extension receives opaque quality IDs. Signed manifest URLs stay inside the watcher process, and the HLS master manifest is retained internally for safe variant failover.

## Security and production boundary

Manifest and segmented recording redirect handling rejects HTTPS-to-HTTP downgrade and revalidates redirect targets. Authentication, subscription, ticket, DRM, signed-access, Cookie, password, localStorage, and Authorization bypasses are not implemented.

The tested local release is validated with the full test suite, clean extraction, compileall, extension JavaScript syntax checks, CLI smoke tests, release verification, and deterministic rebuild. Real Windows + real RPLAY production E2E remains a separate validation boundary and is not inferred from local tests.

## GitHub / engineering

GitHub is currently the engineering/bootstrap surface rather than the complete runtime source of truth. Active automation includes CI, Dependency Review, Dependabot, deterministic release packaging, SHA-256, and artifact-attestation preparation. CodeQL is retained as a ready-to-enable template because the current private-repository plan does not provide active scanning.

Do not commit runtime SQLite databases, recordings, diagnostics, credentials, tokens, or local caches.
