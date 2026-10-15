# ツール統合・導入キット 20261015.4

更新：2026-10-15（日本時間）。基準ソースZIP20261012.2・管理更新26ファイル・検証ヘルパーをまとめたキットです。管理17機能を準備します。未取得の製品本体9件は含みません。

## 準備と導入

公開チェックサムでキットZIPを照合し、新しいフォルダへ展開します。Python 3.11・3.14・3.15を使用できます。キットの展開先で実行します。

```sh
python apply_catalogue_update.py --base workspace-source-20261011.zip --update catalogue-update-20261015.4.zip --update-sha256 c340b7ac8c229707c38f931eac661997e542685c050fa92be361de0fffdf30ea --output work/integrated-tools
```

パス・CRC・全内容ハッシュ・基準版を検査し、新規work/integrated-toolsへ26ファイルを適用します。既存出力先は拒否します。失敗時はこの処理が作った作業先だけを整理します。基準ZIPの公開互換名workspace-source-20261011.zipは実内容20261012.2を指します。

## 仮想環境と検証

work/integrated-toolsへ移動して仮想環境を作ります。

```sh
python -m venv work/verify-env
```

Linux：

```sh
work/verify-env/bin/python tools/manage.py setup
work/verify-env/bin/python tools/manage.py doctor
work/verify-env/bin/python tools/manage.py all
work/verify-env/bin/python tools/manage.py run --tool suite-audit
```

Windows：

```powershell
.\work\verify-env\Scripts\python.exe tools/manage.py setup
.\work\verify-env\Scripts\python.exe tools/manage.py doctor
.\work\verify-env\Scripts\python.exe tools/manage.py all
.\work\verify-env\Scripts\python.exe tools/manage.py run --tool suite-audit
```

setupはネットワークで版・SHA256固定の依存を導入します。グローバルPythonへの導入は停止します。doctorのreadyは準備判定で、製品の動作合格ではありません。ブラウザー検査にはChromiumを別途準備します。

## Suiteの停止と記録

Suiteのpytestは専用の子Pythonで実行します。監査開始前にstdinの起動ゲートを使い、POSIXでは新しいプロセスグループ、WindowsではJob Objectへ登録します。管理対象へ登録できなければ監査を開始しません。

内部タイムアウトは90秒、CLI指定は1～100秒です。共通入口は120秒の上限を維持し、Suiteには8秒の中断猶予を明示設定しています。中断を転送した後にコントローラーの停止処理を待ち、途中出力を回収します。通常終了時も残った管理対象の子孫を停止します。未指定の他ツールの実行方法は維持します。

| 終了コード | 意味 |
|---|---|
| 0 | 検査合格と停止処理完了 |
| 124 | 時間切れ |
| 130 | 中断 |
| 125 | 停止処理を完了できなかった |
| 127 | 起動・管理対象への登録失敗 |

catalog/results/suite-worker.jsonに実行中・結果・期限・終了コード・停止処理の状態を保存します。共通入口からの実行では途中出力もtool-suite-audit.jsonへ残します。前の合格は開始時に未完了へ置き換えます。停止処理が未完了なら合格を付与しません。

POSIXの対象は同じプロセスグループ、WindowsはJobへ割り当てた子孫です。別セッションへ離れたプロセス、コントローラーのSIGKILLやOS停止を含む全条件の回復を保証しません。セキュリティサンドボックスではありません。

## 一覧と入力照合

成果物はcatalog/generated/artifacts.html、管理機能はtools.html、製品の取得状況はprojects.htmlです。更新ZIP内の一覧は作成時点33件、キット登録後の公開一覧は37件です。固定ZIP内の説明は作成時点の記録で、最新版の導入は同梱の手順を使います。

共通入力6グループ・フォルダ照合6ツール、モジュール対応2入口を維持します。Suiteの監査原本・テスト・SOURCE-ORIGIN.jsonも明示入力へ含めました。module_inputsは.pyソースの変更検知で、既存modulesはインストール済み依存の確認用です。全import先の解決や原子的な読取り固定ではありません。

v4は26ファイルの厳密な集合です。旧v1～v3も従来の固定集合で検査し、不正混在・欠落・改変を拒否します。同梱の最新版ヘルパーを使います。配布設定はlink_mode=directで、生成後のカタログ内のシンボリックリンクを検査します。

Suite監査原本のハッシュ確認、既存のZIPパス検査、監査26テストは維持します。製品E2E・実エンジン・Firefox実拡張・録画の実機検証は別途必要です。

## Windows起動順の修正

WindowsではCREATE_SUSPENDEDで起動し、Jobへ登録してから初期スレッドを再開します。仮想環境の起動プログラムがPython本体を先に作る競合を防ぎます。登録・再開失敗時は監査を始めず、停止状態を記録します。旧版20261015.3は停止試験で不合格を検出したため推奨しません。
