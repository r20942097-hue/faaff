# HANDOFF — 次のAIへ（2026-10-28 更新）

1. まず [`AGENTS.md`](../AGENTS.md)、次に [`PROJECT_STATE.json`](PROJECT_STATE.json)・[`projects.json`](projects.json)・[`WORK_QUEUE.md`](WORK_QUEUE.md) を読む。
2. 権限は「常に可」「要承認」の2段階。`main` への直接 push は禁止（Ruleset で技術的にも保護）。作業は `proposal/*` 等のブランチ → PR。
3. 2026-10-28 の整理内容:
   - PR #15/#16（ZIP を含む）をクローズし、閉じた/マージ済みPRの古いブランチを削除（全ブランチは git bundle でバックアップ済み）。
   - Dependabot PR #10（setup-python 7.1.0）を merge。脆弱性アラート・自動セキュリティ修正・merge 後のブランチ自動削除を有効化。
   - Watcher v6.10.0 の古い記録（`GITHUB-READY.md`、`SECURITY-SCAN-STATUS.md`、`PRODUCTION-E2E-CHECKLIST.md`、`SOURCE-SYNC.md`、`VERIFICATION.md`、`SHA256-v6.10.0.txt`）を削除。`pyproject.toml` は参照があるため残置。
   - `s` の固定取り込みを `8af3fa3` → `20a2661` に更新（`ai/imports/s.json`、AI指示ファイルは取り込み対象外）。
   - CI に ZIP/7z 混入チェックを追加。AI hub・フィルター検証は PR で常に実行（必須チェック化のため）。
4. 検証: `python ai/check_hub.py` と `ai/README.md` のオフライン検査。実機・実ブラウザ・ログイン系は未実施なら NOT_RUN と報告する。
5. 次の候補: `PROJECT_STATE.json` の `open_items`。`s` を変更したら本リポジトリで取り込み更新PRを作る。
6. Codex 初回利用時は [`CODEX_SETUP.md`](CODEX_SETUP.md) に従って、アカウント/Cloud起動、対象リポジトリの実アクセス、既存オフライン検証、製品実機検証を別々に判定する。GitHub接続やCI成功だけでCodex接続・製品動作をPASSにしない。
