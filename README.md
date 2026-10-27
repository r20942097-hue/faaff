# faaff — engineering / integration hub

> **現状の要約（2026-10-27 観測）**: この `main` ブランチは、ブラウザー用フィルターの検証基盤と AI 作業ハブを置く **engineering / bootstrap リポジトリ** です。Universal Live Watcher（RPLAY LIVE 監視・録画基盤）の**ランタイムソースは `main` に含まれていません**。リポジトリは **公開（public）** です。

## main に実際にあるもの

| パス | 内容 | 検証 |
|---|---|---|
| `browser_filter_lists/` | 保守的な補助フィルター（Universal Web Ad / Tracking Filter）、候補評価・昇格ゲート、検証スクリプト | `.github/workflows/validate-browser-filter-lists.yml` |
| `integrations/browser-filters/source/s/` | [`r20942097-hue/s`](https://github.com/r20942097-hue/s) の固定コミットの写し（配布はしない） | `ai/check_hub.py`、`.github/workflows/ai-hub.yml` |
| `ai/` | AI 作業ハブ: プロジェクト索引 `projects.json`、取り込み来歴 `imports/s.json`、作業キュー `WORK_QUEUE.md` | `python ai/check_hub.py` |
| `AGENTS.md` | AI コーディングエージェント共通の作業指示（`CLAUDE.md` 等はここを参照） | — |
| Watcher 関連の記録 | `CHANGELOG.md`、`VERIFICATION.md`、`PRODUCTION-E2E-CHECKLIST.md`（v5.10.0 時点）、`SOURCE-SYNC.md`、`GITHUB-READY.md`、`SECURITY*.md`、`SHA256-v6.10.0.txt`、`pyproject.toml` | 下記の注意を参照 |

## 購読 URL（変更しないこと）

- https://raw.githubusercontent.com/r20942097-hue/faaff/main/browser_filter_lists/filters/universal-web-ad-filter.txt
- https://raw.githubusercontent.com/r20942097-hue/faaff/main/browser_filter_lists/filters/universal-web-tracking-filter.txt

詳細は [browser_filter_lists/README.md](browser_filter_lists/README.md)。メインの購読配布元は [`s`](https://github.com/r20942097-hue/s) です。

## オフライン検証（リポジトリ直下で実行、Python 3.11 以上）

```sh
python ai/check_hub.py
python -m unittest discover -s integrations/browser-filters/source/s/tests -p 'test_*.py' -v
python integrations/browser-filters/source/s/scripts/validate_lists.py
python integrations/browser-filters/source/s/scripts/generate_lists.py --check
python browser_filter_lists/scripts/test_validator.py
python browser_filter_lists/scripts/test_evidence.py
python browser_filter_lists/scripts/test_promotion.py
python browser_filter_lists/scripts/validate_filters.py
```

## Universal Live Watcher について（注意）

- 以前の README は Universal Live Watcher v6.10.0（Windows 向け RPLAY LIVE 監視・録画基盤）を説明していましたが、その**ランタイム（`rplay_watcher/` パッケージ、`extension/`、`tests/`）は `main` に存在しません**。完全なソースは外部のローカルリリース ZIP（`SHA256-v6.10.0.txt` に記載のハッシュ）にあるとされ、このリポジトリでは検証していません。
- `pyproject.toml` は `rplay_watcher` パッケージを前提としているため、現状の `main` ではインストールできません。`.github/workflows/ci.yml` は該当ソースが無いことを検出してフル CI をスキップします（意図された動作）。
- 「441 tests passed」などの v6.10.0 の検証結果は**外部のローカル実行の記録**であり、このリポジトリ上の CI では再現されていません（状態: NOT_RUN on GitHub）。`VERIFICATION.md` と `PRODUCTION-E2E-CHECKLIST.md` は v5.10.0 時点のままです。
- 実 Windows + 実 RPLAY での本番 E2E は別の検証境界で、ローカルテストから推定しません。
- Watcher ソースを GitHub に同期するか、別リポジトリに分けるかは所有者の判断待ちです（NEEDS_HUMAN）。

## セキュリティ / 運用

- このリポジトリは **public** です。以前の文書にある「private repository のため CodeQL 無効」という記述は現状と一致しません。public リポジトリでは CodeQL を有効化できるため、`.github/workflows/codeql.yml.template` の有効化を検討してください（所有者判断）。
- 有効な自動化: CI（ソース検出）、AI hub、フィルター検証、Dependency Review、Dependabot。サードパーティ Action はフル SHA で固定します。
- ランタイムの SQLite DB、録画、診断ログ、認証情報、トークン、ローカルキャッシュをコミットしないでください。

## ライセンス

`LICENSE` ファイルは未配置です。`pyproject.toml` には `MIT` と記載されています。取り込んだ `s` のフィルターは各ファイルのヘッダー（CC0-1.0 / GPL-3.0-only）に従います。最終的なライセンスは所有者が決定します。
