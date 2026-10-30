# HANDOFF — 次のAIへ（2026-10-31 更新）

## 2026-10-31 確認済みの最新判断

- **正本:** `AGENTS.md` が最優先。自律調査・多言語検索・仕様化・検証を許可された範囲で実施し、人の通常確認を増やさない。
- **正式反映:** PR #42（`AGENTS.md`のみ）が `main` に squash merge。マージコミット `d1989e657001f8de054a8d168c9601692c0c8d43`。変更前後の証拠は `PROJECT_STATE.json` の `governance` を参照する。最新 HEAD は必ず再取得する。
- **検証:** PRの必須CI成功、merge後の `main` の CI・AI hub/pinned import・CodeQL Python は SUCCESS。Watcherランタイムは `main` にないため実ランタイム/実ブラウザーの検証を PASS としない。
- **権限:** RulesetはPR・必須CI・force-push/削除禁止を技術的に強制。ただしレビュー承認0はAIへのマージ無制限許可ではない。明示の所有者承認が必要な操作は `AGENTS.md` を守る。
- **固定取り込み:** `s` PR #15 は `AGENTS.md` のみ。 `ai/imports/s.json` の `excluded_paths` に該当するため、取り込み元コード/フィルターの再インポートは不要。実際にインポート対象ファイルに差分があるときだけ別PRで更新する。
- **次に優先:** 定期ニュース監視のAI更新 → 実務影響評価 → 提案ブランチ最小差分 → CI/監査 → 明示的な適用履歴、の一連の完走証拠を得る。メモリ直接同期は未実証。従来のP0/公開HOLDを解除したとは扱わない。

## 2026-10-28 の履歴（参照用）

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
