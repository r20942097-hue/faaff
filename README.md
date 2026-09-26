# Universal Live Watcher

Windows向けのRPLAY LIVE監視・録画基盤。Discovery、Browser Bridge、yt-dlp、manifest検証、FFmpeg録画、Recovery、SQLite履歴、Diagnostics、Adaptive Learningを分離して統合します。

## Current release

v5.10.0

完全な配布スナップショット: `release/Universal-Live-Watcher-v5.10.0.zip`

SHA-256: `5da12dc0dd46aa51b6fd0b1ca1ac32ece2821b1eca3d4e035cb1655179eea723`

## Safety

認証、購読、チケット、DRM、署名アクセス、Cookie、password、localStorage、Authorization headerの回避機能はありません。使用するRPLAYアカウントと配信は正規にアクセス・録画可能な範囲に限定してください。

## v5.10

- Recovery attributionをSQLiteへ永続化
- context_idによる冪等learning記録
- recency decay / stale evidence / effective trials / conservative Wilson guard
- Provider capability / health / incidents / SLO / forensics
- yt-dlp / HTTP probe / manifest / FFmpegのSSRF・DNS-rebinding対策
- Ubuntu / Windows × Python 3.11〜3.14 CI
- CodeQL / Dependency Review / Dependabot
- deterministic release build + SHA-256 + artifact attestation

## Development

`python -m pytest -q`

`python -m compileall -q rplay_watcher`

`python -m rplay_watcher --version`

`python -m rplay_watcher --doctor-json`

実Windows + 実RPLAYの本番E2Eは自動テストとは別の検証境界です。
