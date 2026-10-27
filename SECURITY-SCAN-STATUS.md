# Security Scan Status

GitHub metadata checked on 2026-10-11 reports public visibility. `.github/workflows/codeql.yml` is prepared locally to scan the Python code present in this checkout. It replaces the old template, removes duplicate permission keys, and omits the unavailable runtime JavaScript. Remote execution and results remain unverified.

Local v6.10.0 verification includes 441 tests covering manifest/network security, Bridge authentication, subprocess isolation, Recovery, recording, extension control, HLS variant failover, cross-scheme redirect handling, toolchain diagnostics, crash-safe segment journaling, session isolation, LL-HLS/GAP/DISCONTINUITY observation, bounded yt-dlp subprocess output, manifest-size limits, bounded FFmpeg diagnostics, and release integrity.

Local tests are not equivalent to GitHub-hosted CodeQL scanning.
