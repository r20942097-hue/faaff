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

## 状態とプロベナンス（観測 2026-10-28T02:18:43Z）

値の正本は [`PROJECT_STATE.json`](PROJECT_STATE.json)（`observed_at`・`repositories`・`gate`・`open_items`・`related_bots`）。ここは人間向けの要約。事実には出典と観測時刻を付け、取得できない値は推測で埋めず「未取得（理由）」と書く。行動前に Git の実値を再確認すること。

| 項目 | 値 | 出典・取得方法 | 観測 (UTC) |
|---|---|---|---|
| faaff default branch / HEAD | `main` / `479a15e4cfe43ad487081b0bb0d87a812bb0a24a`（PR #20 の merge commit） | `gh repo clone` 後の `git rev-parse HEAD`、`git ls-remote origin HEAD`、`gh api repos/r20942097-hue/faaff/commits/main`（3方法一致） | 2026-10-28T02:18:43Z |
| s default branch / HEAD | `main` / `20a26610db8970abef1bd7016f5f641ce25b7063`（s#10 の merge commit。`ai/imports/s.json` の `source_commit` と一致） | `gh api repos/r20942097-hue/s/commits/main`、`git ls-remote https://github.com/r20942097-hue/s HEAD`（一致） | 2026-10-28T02:18:43Z |
| ゲート | P0 / PUBLICATION_HOLD / NO_NEW_INTERNAL_PUSH | [AGENTS.md@479a15e](https://github.com/r20942097-hue/faaff/blob/479a15e4cfe43ad487081b0bb0d87a812bb0a24a/AGENTS.md) | 2026-10-28T02:18:43Z |
| faaff / s の open PR | なし | `gh pr list --state open`（両 repo） | 2026-10-28T02:18:43Z |

faaff の HEAD は「このファイルを含むコミットの親」。自己参照のため、このファイル自身のコミット SHA は記録できない。

### 未解決（詳細は `open_items`）
- NEEDS_HUMAN: `NO_NEW_INTERNAL_PUSH` の再定義（全 push/PR 禁止 → main 直接 push 禁止のみ）を所有者が承認した記録の確認。
- NEEDS_HUMAN: 2026-10-28 のゲート下での main merge 3件（faaff#10、s#10、faaff#20）の承認記録の確認。
- NEEDS_HUMAN: Drive 上の「01_MASTER_LEDGER」の名前が、AGENTS.md の Master ledger（v27 台帳）と一致するかの確認。
- PARTIAL: `projects.json` の faaff `observed_head` は自己参照のため常に1コミット遅れる。`WORK_QUEUE.md` の見出しが「observed 2026-10-25」のまま。

### 関係ボット（役割名は依頼文の記載。ボット台帳との照合は未実施）
開発担当 / 進捗管理担当 / 公開・リリース判定担当 / デプロイ担当 / ゲーム移行担当 / デザイン担当 / リサーチ・資料担当
