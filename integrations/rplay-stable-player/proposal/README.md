# RPLAY Stable Player — 3ジャンル提案（proposal, 2026-10-28）

**PROPOSAL ONLY / NOT A RELEASE / CANDIDATE_NO_GO**。ゲート P0 / PUBLICATION_HOLD / NO_NEW_INTERNAL_PUSH。

- 設計書: [`DESIGN_3GENRE_2026-10-28.md`](DESIGN_3GENRE_2026-10-28.md)
- プロトタイプ（独立した MV3 拡張・依存なし）: [`prototype/`](prototype/)
- base: `r20942097-hue/faaff` main `479a15e4cfe43ad487081b0bb0d87a812bb0a24a`
- 正本候補（推奨、決定は NEEDS_HUMAN）: Drive `RPLAY_Stable_Player_v2.50.0_UNIFIED_CANDIDATE.zip`
  SHA-256 `e79eea624539fce0715b2f422163f1e3102eca589bc0f1521893bcfd2ed28347`（ZIP はコミットしていない）
- 公開実装（参考のみ・コード非流用・ライセンス無し）: https://github.com/0xddy/rplay-downloader @ `4c07560e742aa6e637584665987325e336a36f28`（manifest version 2.0.0、タグ無し）

## 置き場所の理由
`integrations/` は外部系統の取り込み・統合用（既存: `integrations/browser-filters/`、kebab-case）。RPLAY は `ai/projects.json` に未登録の系統で、`main` に実体が無いため、既存ファイルや `ai/` レジストリを変更せず、独立サブツリー `integrations/rplay-stable-player/proposal/` に置いた。`integrations/browser-filters/source/s/` の固定写しは変更していない。

## 検証（2026-10-28, Linux, Node v20.19.2, Python 3）
| 検証 | コマンド | 結果 |
|---|---|---|
| AI hub | `python3 ai/check_hub.py` | PASS |
| JSON 構文 | `python3 -m json.tool prototype/manifest.json`, `package.json` | PASS |
| JS 構文 | `node --check`（全 .js） | PASS |
| 単体テスト | `cd prototype && node --test tests/` | PASS（34/34） |
| manifest 静的確認 | `tests/manifest_static.test.js`（MV3・権限 allowlist・禁止権限・API と権限の対応・参照ファイル） | PASS |
| 既存オフライン検査 | `python3 -m unittest discover -s integrations/browser-filters/source/s/tests -p 'test_*.py'`（50件）, `browser_filter_lists/scripts/test_validator.py` | PASS（変更対象外の回帰確認） |
| 空白 | `git diff --cached --check` | PASS |
| ZIP 混入 | `git ls-files | grep -iE '\.(zip|7z)$'` | PASS（0件） |
| 実ブラウザ読み込み・SW 停止/復旧 | — | NOT_RUN |
| 実 RPLAY / 実 YouTube E2E | — | NOT_RUN |
| Firefox / Windows | — | NOT_RUN |
| CI（GitHub Actions） | push していないため | NOT_RUN |

ユニットテストは合成データのみ。実製品の動作を示すものではない。
