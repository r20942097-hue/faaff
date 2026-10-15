# 作業環境の入口

| 目的 | 開く場所 |
|---|---|
| 最新成果物・公開先・検証結果 | [成果物一覧](catalog/generated/artifacts.html) · [見方](catalog/ARTIFACTS.md) |
| 他のツール・製品の統合 | [10製品の現状・改良案](catalog/generated/projects.html) |
| ブランチ・取得済みツール | [16ブランチの一覧](catalog/BRANCHES.md) |
| 統合・改良の順序 | [統合案・完了条件](catalog/INTEGRATION.md) |
| ツール統合・実行状況 | [見やすい一覧](catalog/generated/tools.html) · [診断一覧](catalog/TOOLS.md) |
| ライブラリ・検証依存 | [ライブラリ一覧](catalog/generated/libraries.html) |
| フィルターの選び方・比較表 | [フィルター一覧](catalog/generated/filters.html) |
| 検索できる全体一覧 | [統合カタログ](catalog/generated/inventory.html) |
| 統合案・改良内容・完成までの残課題 | [調査・改良レポート](catalog/REPORT.md) |
| 広告ブロック更新・プロファイル比較 | [更新一覧表](catalog/ADBLOCK-UPDATE.md) |
| 操作手順 | [カタログの使い方](catalog/README.md) |
| 直近の検証結果 | [テスト記録](catalog/results/latest.json) |
| フィルター原本 | [s](s/) |
| 録画ツール資料・フィルター原本 | [faaff](faaff/) |

## 更新・検証

このフォルダで実行します。Python 3.11以上を使用します。

```sh
python tools/manage.py filters --check
python tools/manage.py all
```

`all`は共通ルール生成・一覧更新・標準検証をまとめて実行します。`filters --check`は生成されたリストの同期を確認します。`build`は一覧と原本へのリンクを更新します。`check`は内容変更・リンク切れ・フィルター間の差異を検出します。`test`は両リポジトリと共通管理の検証をまとめて実行し、結果を保存します。

ライブラリの保存先は`library-files/`、ダウンロード済み資料は`shared/downloads/`です。library-filesには固定した管理・監査ツールのソースを保存しています。shared/downloadsは現在空です。調査用ファイル・ブラウザー・バックアップは`work/`に置き、製品一覧から除外しています。環境管理用の隠しフォルダは変更していません。

`python tools/manage.py doctor` で登録した各機能の実行前診断と不足項目を確認できます。診断は依存関係の確認であり、実機テストの合格とは別です。録画本体が復元されるまでは録画機能を完成扱いにしません。

個別実行は `python tools/manage.py run --tool candidates` の形式です。登録・依存・実行条件は `tools/registry.json` にまとめています。別ブランチから取得した監査ツールは `library-files/tool-sources/` に固定ソースと取得元を保存しています。

Suite監査のテストなど追加検証には仮想環境を使います：`python -m venv work/verification-venv` → 仮想環境のPythonで `tools/manage.py setup`。環境を有効にした後で `python tools/manage.py doctor` を実行してください。

Python 3.11〜3.15に対応する検証手順です。通常の直接・間接11依存を配布SHA256付きで固定し、3.15ではビルド依存も固定してPyYAMLの標準Python版を導入します。新規仮想環境を使用してください。[互換性・改善一覧](catalog/PYTHON.md)で詳細を確認できます。`python tools/manage.py run --tool python-environment` で実行中のPythonとの版一致を確認できます。Windows専用依存はLinuxで合格扱いにしません。
