# Universal Live Watcher

Windows向けのRPLAY LIVE監視・録画基盤。Discovery、Browser Bridge、yt-dlp、manifest検証、FFmpeg録画、Recovery、SQLite履歴、Diagnostics、Adaptive Learningを統合します。

## Current verified release

v6.6.0

Verified local release ZIP SHA-256:
`6e6be97ec426dd9d9a816da42bee6278677a35d23337773de35d739b416c890e`

## Unified Stream UX

Browser Extensionを検出転送だけの層から操作面へ拡張しています。検出LIVEの状態、HLS品質候補、録画状態、進捗、最近の録画履歴を表示し、Record / StopをローカルBridge経由で実行できます。

HLS品質選択では、拡張機能から署名manifest URLを送信せず、opaqueな `quality_id` だけを送ります。実URLはWatcherプロセス内の直近Probe結果から解決されます。

設定画面では追加hostへのサイト権限を明示的に要求できます。デフォルト監視対象はRPLAYだけで、他サイトはopt-inです。

## Resilient HLS recording

v6.5 adds a conservative MPEG-TS segment fallback after repeated FFmpeg failures. It retries individual segments, starts near the live edge, persists downloaded segment identities, and remuxes the collected TS through the existing finalization path.

## Crash-safe segment journal

v6.6 makes the segment journal two-phase. Before a segment is appended, the expected file offset, byte count, and SHA-256 are persisted as a prepared record. After the bytes are flushed and synced, the record is committed.

On startup, a fully appended prepared segment is committed without downloading it again. A partial append is truncated back to its recorded offset before retry. Playlist reloads follow roughly half the HLS target duration with bounded exponential backoff on transient failures.

The fallback deliberately rejects encrypted HLS, fMP4 initialization segments, and byte-range playlists rather than attempting decryption or complex reconstruction.

## Recording UX

録画ファイル名はWindowsで問題になりやすい文字・予約名を正規化したタイトルと、衝突防止用のlive-key fingerprintを組み合わせます。拡張機能の履歴には完成ファイルのサイズ、録画時間、part数、attempt数を表示します。絶対パスは拡張機能へ送信しません。

## Safety

認証、購読、チケット、DRM、署名アクセス、Cookie、password、localStorage、Authorization headerの回避機能はありません。使用するRPLAYアカウントと配信は正規にアクセス・録画可能な範囲に限定してください。

## Verification boundary

ローカルでは406 tests、clean release extraction 406 tests、compileall、Extension JavaScript syntax、CLI version、dry-run、release verifier、deterministic rebuildを確認済みです。

実Windows + 実RPLAY本番E2Eは別検証境界であり、この開発環境から成功率や網羅性を推定していません。

## GitHub security

このprivate GitHub repositoryでは、現行プランではCodeQL code scanningを実行できないためactive workflowからは外し、`.github/workflows/codeql.yml.template` と `SECURITY-SCAN-STATUS.md` を残しています。

## Repository synchronization

GitHub側はengineering/bootstrap surfaceとして扱っています。完全な検証済みruntime source checkoutとは主張せず、完全なv6.6.0 runtimeは上記の決定論的release ZIPを基準にしています。

## Engineering

CI、Dependency Review、Dependabot、deterministic release packaging、SHA-256、artifact provenance準備を利用します。第三者Actionsはfull commit SHAで固定しています。
