# Universal Live Watcher

Windows向けのRPLAY LIVE監視・録画基盤。Discovery、Browser Bridge、yt-dlp、manifest検証、FFmpeg録画、Recovery、SQLite履歴、Diagnostics、Adaptive Learningを統合します。

## Current verified release

v6.1.0

Verified local release ZIP SHA-256:
`78dc39c027aa771635d9715ef5af4f72b495913544cdbaebcafd466a0c0de895`

## Unified Stream UX

Browser Extensionを検出転送だけの層から操作面へ拡張しています。検出LIVEの状態、HLS品質候補、録画状態、進捗を表示し、Record / StopをローカルBridge経由で実行できます。

HLS品質選択では、拡張機能から署名manifest URLを送信せず、opaqueな `quality_id` だけを送ります。実URLはWatcherプロセス内の直近Probe結果から解決されます。

## Safety

認証、購読、チケット、DRM、署名アクセス、Cookie、password、localStorage、Authorization headerの回避機能はありません。使用するRPLAYアカウントと配信は正規にアクセス・録画可能な範囲に限定してください。

## Verification boundary

ローカルでは390 tests、clean release extraction 390 tests、compileall、Extension JavaScript syntax、CLI version、dry-run、release verifier、deterministic rebuildを確認済みです。

実Windows + 実RPLAY本番E2Eは別検証境界であり、この開発環境から成功率や網羅性を推定していません。

## Repository sync

接続中のGitHub操作APIには個別ファイル書き込みはありますが、ローカルの全ソースツリーを一括同期する操作がありません。そのためこのprivate repositoryはGitHub engineering/bootstrap layerとして扱い、完全な検証済みruntime source checkoutであるとは主張しません。

## Engineering

CI、CodeQL、Dependency Review、Dependabot、deterministic release packaging、SHA-256、artifact attestationを利用します。第三者Actionsはfull commit SHAで固定しています。
