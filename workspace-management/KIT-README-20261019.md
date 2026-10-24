# 全成果物・改良予定の導入キット 20261019.1

日本時間2026-10-19のローカル開発候補です。公開GitHubへは未送信で、Windows CIは未実施です。製品本体未取得9件は同梱していません。

## 導入

キットZIPの外部SHA256を照合して新しい場所へ展開し、その場所で実行します。

```sh
python apply_catalogue_update.py --base workspace-source-20261011.zip --update catalogue-update-20261019.1.zip --update-sha256 f480132144a2651c6f0be130c19c6ae455f584b1becb0f33a50492ec16f572a5 --output work/integrated-tools
```

基準ソースZIP20261012.2は変更しません。37ファイルのv5更新を全件照合し、新しいwork/integrated-toolsへ適用します。既存出力先は上書きしません。旧v1～v4の固定集合も従来どおり検証します。

## 確認と継続開発

作成したwork/integrated-toolsへ移動し、新しい仮想環境を用意します。

```sh
python -m venv work/verify-env
```

Linuxでは `work/verify-env/bin/python`、Windowsでは `work/verify-env/Scripts/python.exe` を使い、次を実行します。

```sh
python tools/manage.py setup
python tools/manage.py doctor
python tools/manage.py all
python tools/manage.py portfolio
```

上のpythonは新規仮想環境のPythonへ置き換えます。setupは固定版・SHA256を照合して検証依存を導入します。フィルター購読には不要です。

- 全体一覧・次の作業：catalog/PORTFOLIO.md
- 成果物検索：catalog/generated/artifacts.html
- 10製品の取得状況：catalog/generated/projects.html
- 管理18機能の診断：catalog/generated/tools.html
- 期限・改良予定のJSON：catalog/results/portfolio-status.json

集計機能は登録記録・手元ソース・依存診断・確認期限をまとめます。通信や製品の起動検証は実行せず、過去の動作合格・公開状態を更新しません。根拠の有効期限は最も古い資料・例外確認日から算出し、期限当日まで有効です。

フィルター生成の改行・パス衝突、不正な候補の型、診断の照合情報欠落、Firefox検証の準備失敗時の記録を修正しています。配信フィルター本文・版・購読URLは変更していません。

sの修正コミットはローカルに保存しています。公開前のため、その新コミットへのGitHub参照は利用できません。既存の固定公開フィルター・配布物のURLは保持しています。
