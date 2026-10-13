# ツール統合・導入キット 20261014.3

基準ソースZIP20261012.2・最新の管理更新ZIP20261014.3・検証ヘルパー4ファイルをまとめた導入キットです。公開済み固定版のファイルだけを使用します。管理17機能のソースを用意するもので、未取得の録画・AI・Windows等の製品本体は含みません。

## 準備

公開チェックサムとキットZIPのSHA256を照合し、新しいフォルダへ展開します。既存リポジトリへの上書きはしません。Python 3.11・3.14・3.15を使用できます。

展開先のキットフォルダで実行します。

```sh
python apply_catalogue_update.py --base workspace-source-20261011.zip --update catalogue-update-20261014.3.zip --update-sha256 e2a68613c0c855237cc4b713ed8c2cc1ac5bab5bf04a4eeb80fea1582b7cc4de --output work/integrated-tools
```

基準ZIP・更新ZIPのパス・CRC・全内容ハッシュを検証してから、新規のwork/integrated-toolsへ展開・適用します。既存出力先は拒否します。途中で失敗した場合は、この処理が作った作業先だけを整理します。

## 検証して使う

work/integrated-toolsへ移動して、新しい仮想環境を作ります。

```sh
python -m venv work/verify-env
```

Linuxの場合：

```sh
work/verify-env/bin/python tools/manage.py setup
work/verify-env/bin/python tools/manage.py doctor
work/verify-env/bin/python tools/manage.py all
```

Windowsの場合：

```powershell
.\work\verify-env\Scripts\python.exe tools/manage.py setup
.\work\verify-env\Scripts\python.exe tools/manage.py doctor
.\work\verify-env\Scripts\python.exe tools/manage.py all
```

setupはネットワークを使用してハッシュ固定依存を導入します。グローバルPythonへの導入は停止します。doctorのreadyは準備の判定で、製品本体の動作合格ではありません。エンジン・ブラウザー実体・録画等のE2Eは別途必要です。

## 内容と一覧

基準ZIPの192ソースへ、管理更新24ファイルを適用します。共有コードと直接登録した依存の変更を検知し、再検証を案内します。更新ZIP内の成果物一覧は作成時点19件です。現在の公開一覧は更新ZIPやこの導入キットを追加した状態で、作成時点の記録とは区別します。

catalog/generated/artifacts.htmlが成果物、tools.htmlが管理機能、projects.htmlが製品本体の取得状況です。一覧はPython標準ライブラリで生成でき、ブラウザーで閲覧します。ローカルの生成結果は閲覧端末の診断結果とは異なります。

## 設定検査と直接リンク

`tools/manage.py run --tool settings-consistency` で登録漏れ・重複・時間制限の不整合を検査できます。共通入口で設定エラーが出る場合は `tools/check_settings.py` を実行します。配布設定はlink_mode=directで、一覧生成後にカタログ内のシンボリックリンクがないことを検証します。旧版のlayout設定とは区別します。

## フラグ付き実行の検査

Pythonの-B/-I/-W/-XやNodeの--no-warningsなど、対応するフラグの後のスクリプトも登録入力と照合します。未対応オプションはエラーにします。モジュール・インライン・標準入力・情報表示・Node inspectは除外種別として記録し、本文や引数値は記録しません。全CLI文法やオプション値の妥当性、実行成功の保証ではありません。

## 本文更新候補のレビュー

制作物の版・本文を変更する場合は、入力候補をwork/へ用意し、check_artifact_publication.pyの--review/--candidate/--previewで比較・本文確認します。新規や変更対象はpendingで用意し、古いpassedを引き継ぎません。実行後も正本は変更されません。詳細は公開ARTIFACTS-GUIDE.mdを参照してください。
