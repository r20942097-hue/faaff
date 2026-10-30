# Changelog

## 2026-10-30 — 現状の注記（履歴は変更なし）

- このファイルは Universal Live Watcher の旧記録（v5.10.0）を含みます。main に現在あるのは、ブラウザー用フィルターの検証基盤と AI 作業ハブです。
- Watcher のランタイム（`rplay_watcher/`）は main に存在しません。下記の v5.10.0 の項目は、過去のリリースの記録であり、現在の main の機能を示すものではありません。
- 現在の状態と未解決の判断事項は `ai/WORK_QUEUE.md` と `ai/PROJECT_STATE.json`（`ai/` 配下）を参照してください。

## v5.10.0 — 2026-09-27

- Persist recovery attribution across process restarts.
- Make recovery-effectiveness learning idempotent by context ID.
- Add recency decay, stale-evidence limits, effective-trial minimums, and conservative Wilson-style selection.
- Add Python package metadata and CLI entry point.
- Add Ubuntu/Windows CI across Python 3.11–3.14.
- Add CodeQL, Dependency Review, Dependabot, deterministic release packaging, and artifact attestation.
- Pin third-party GitHub Actions to full commit SHAs.
- Harden protected remote Bridge health/readiness endpoints.
