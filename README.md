# Universal Live Watcher

Windows向けのRPLAY LIVE監視・録画基盤。Discovery、Browser Bridge、yt-dlp、manifest検証、FFmpeg録画、Recovery、SQLite履歴、Diagnostics、Adaptive Learningを分離して統合します。

## Current verified release

v5.11.0

The verified source snapshot and deterministic release ZIP are built from the local release pipeline. Release SHA-256: `6e051ce31d84a8c4d3ff5346a89037effaf4b71baa83bf158a99fb8f12c54b94`

## Safety

認証、購読、チケット、DRM、署名アクセス、Cookie、password、localStorage、Authorization headerの回避機能はありません。使用するRPLAYアカウントと配信は正規にアクセス・録画可能な範囲に限定してください。

## v5.11

- Atomic SQLite recovery claim prevents duplicate concurrent Recovery starts for one `live_key`.
- Persisted recovery guard history and context-based idempotent learning.
- Recency decay, stale-evidence limits, effective-trial minimums, and conservative Wilson-style selection.
- SSRF/DNS-rebinding hardening, Bridge token/origin gates, diagnostics, SLO, forensics.
- GitHub CI, CodeQL, Dependency Review, Dependabot, deterministic packaging, and artifact attestation.

## Repository sync

The connected GitHub interface currently provides repository file writes but not a bulk local-tree upload operation. Therefore the private repository contains the GitHub engineering/bootstrap layer, while the complete 5.11.0 source snapshot is preserved and verified as the local release artifact. No incomplete source tree is presented as a complete CI source checkout.
