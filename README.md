# Universal Live Watcher

Windows向けのRPLAY LIVE監視・録画基盤。Discovery、Browser Bridge、yt-dlp、manifest検証、FFmpeg録画、Recovery、SQLite履歴、Diagnostics、Adaptive Learningを統合します。

## Current verified release

v6.8.1

Verified local release ZIP SHA-256:
`94d30d1ec57a2a195a79df1095196341618ce41fb76b4418c93b88d65b0c37e9`

## Unified recorder core

Browser Extensionは検出転送だけでなく、LIVE状態、HLS品質候補、録画状態、進捗、録画履歴を扱う操作面です。

HLS録画はFFmpegを主経路とし、連続失敗時にMPEG-TS segment fallbackへ切り替えられます。fallbackはper-session variant state、preferred quality、live-edge、initial take count、retry/backoff、two-phase journal、time/byte limits、variant failoverを備えます。

拡張機能はopaqueな `quality_id` のみを送信し、署名manifest URLはブラウザUIへ返しません。HLS master URLもwatcher内部でだけ保持してvariant failoverに利用します。

## Security

Manifest probingとsegment recordingではHTTPSからHTTPへのredirect downgradeを拒否し、redirect先も再検証します。認証、購読、チケット、DRM、署名アクセス、Cookie、password、localStorage、Authorization headerの回避機能はありません。

## Verification boundary

ローカルでは425 tests、clean release extraction 425 tests、compileall、Extension JavaScript syntax、CLI version、dry-run、release verifier、deterministic rebuildを確認済みです。

実Windows + 実RPLAY本番E2Eは別検証境界であり、この開発環境から成功率や網羅性を推定していません。

## GitHub security

このprivate GitHub repositoryではCodeQL code scanningは現行プランではactiveにしていません。再有効化用templateとstatus文書を残しています。

## Repository synchronization

GitHub側はengineering/bootstrap surfaceです。完全な検証済みruntime source checkoutとは主張せず、完全なv6.8.1 runtimeは上記の決定論的release ZIPを基準にしています。

## Engineering

CI、Dependency Review、Dependabot、deterministic release packaging、SHA-256、artifact provenance準備を利用します。第三者Actionsはfull commit SHAで固定しています。
