# Security Scan Status

> 2026-10-27 注記: このリポジトリは現在 **public** です。public リポジトリでは CodeQL を有効化できるため、下記の「private / current plan」の前提は現状と一致しません（有効化は所有者判断）。記載のローカル検証結果はこのリポジトリの CI では再現されていません。

The active private GitHub repository does not run CodeQL code scanning under the current plan. A ready-to-enable template is retained at `.github/workflows/codeql.yml.template`.

Local v6.10.0 verification includes 441 tests covering manifest/network security, Bridge authentication, subprocess isolation, Recovery, recording, extension control, HLS variant failover, cross-scheme redirect handling, toolchain diagnostics, crash-safe segment journaling, session isolation, LL-HLS/GAP/DISCONTINUITY observation, bounded yt-dlp subprocess output, manifest-size limits, bounded FFmpeg diagnostics, and release integrity.

Local tests are not equivalent to GitHub-hosted CodeQL scanning.
