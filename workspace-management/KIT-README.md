# ツール統合・導入キット 20261015.2

更新：2026-10-15（日本時間）。基準ソースZIP20261012.2、管理更新ZIP20261015.2、検証ヘルパー4ファイルをまとめた導入キットです。公開済み固定版から構築します。管理17機能の準備用で、未取得の製品本体9件を含みません。

## 準備と導入

公開チェックサムでキットZIPのSHA256を照合し、新しいフォルダへ展開します。Python 3.11・3.14・3.15を使用できます。キットの展開先で実行します。

```sh
python apply_catalogue_update.py --base workspace-source-20261011.zip --update catalogue-update-20261015.2.zip --update-sha256 ad0ecfe2ef803543e111bb2f3fc44b01ff3d06c23c1ead5d69a13b37cd329401 --output work/integrated-tools
```

パス・CRC・全内容ハッシュ・基準版を検査して、新規のwork/integrated-toolsへ26ファイルを適用します。既存の出力先は拒否します。失敗時はこの処理が作った作業先だけを整理します。基準ZIPの公開互換名workspace-source-20261011.zipは、実内容20261012.2を指します。

## 検証

work/integrated-toolsへ移動して、新規仮想環境を作ります。

```sh
python -m venv work/verify-env
```

Linux：

```sh
work/verify-env/bin/python tools/manage.py setup
work/verify-env/bin/python tools/manage.py doctor
work/verify-env/bin/python tools/manage.py all
work/verify-env/bin/python tools/manage.py run --tool workflows
```

Windows：

```powershell
.\work\verify-env\Scripts\python.exe tools/manage.py setup
.\work\verify-env\Scripts\python.exe tools/manage.py doctor
.\work\verify-env\Scripts\python.exe tools/manage.py all
.\work\verify-env\Scripts\python.exe tools/manage.py run --tool workflows
```

setupはネットワークを使用し、版・SHA256を固定した依存を導入します。グローバルPythonへの導入は停止します。doctorのreadyは準備判定です。製品E2E・実エンジン・Firefox実拡張・録画の実機検証は別途必要です。ブラウザー検査には別途Chromiumの準備が必要で、キャッシュは同梱しません。

## 一覧と入力変更

catalog/generated/artifacts.htmlが成果物、tools.htmlが管理機能、projects.htmlが製品本体の取得状況です。HTML・Markdown・CSV・JSONは同じ正本から生成します。配布設定はlink_mode=directで、生成後のカタログ内のシンボリックリンクを検査します。

更新ZIP内の成果物一覧は作成時点31件です。現在の公開一覧は新しい更新ZIP・キットを追加した33件です。固定ZIP内の説明・推奨指定は作成時点の記録として扱い、最新版の導入はこの同梱手順を使います。推奨・現行と履歴の表示は、本文一致・動作検証・main反映とは別です。

共通入力6グループ・フォルダ照合6ツールを維持します。s/testsはfilters、faaff/browser_filter_lists/scriptsはcandidatesへ接続済みです。明示登録した.py集合の追加・変更・削除を再検証へ反映します。生成__pycache__は除外します。symlink・隠しディレクトリ・特殊ファイル・欠落・空集合を拒否し、1利用先32フォルダ、1フォルダ4096項目・深さ32に制限します。

## Pythonモジュール入力

CI設定検証をpython -m tools.check_workflowsで実行します。registryのmodule_inputsでtools/check_workflows.pyを明示登録し、既存modules（インストール済み依存）と区別します。doctorとツール一覧に対応を表示します。

module_inputsは各ツールまたは共通input_groupsへ登録できます。モジュール名と、ワークスペース相対の.pyファイルを指定します。同じ対応は統合し、競合・重複・未使用・cwdに対応する入口ソースの欠落を拒否します。1利用先32対応、1対応128ファイルまでです。ローカル対応では-I/-Pを拒否します。未登録モジュールと標準検査のモジュール実行は除外表示を維持します。

実行前後に対応ソースを照合し、変化した場合は後続を停止して失敗を記録します。欠落・symlinkは準備不可です。これは登録ソースの変更検知であり、環境のsys.path・PYTHONPATH・インストール済みパッケージを含む実行時import先の保証ではありません。全import先や全間接依存を自動追跡しません。読取りと実行をOS上で原子的に固定する保証はありません。

## Suite監査の実行分離

Suite監査もpython -m tools.check_suite_auditで呼び出します。同じ仮想環境のPythonから、管理用tools名前空間を読み込んでいない専用の子プロセスを起動します。pytestのcwd・sys.path・モジュール状態の変更は子プロセス内で扱い、終了コード・標準出力・標準エラーを呼出元へ返します。これは名前空間の分離で、セキュリティサンドボックスではありません。

監査原本・監査テストのハッシュを先に照合し、既存のWindows ZIPパス対策と26テストを維持します。親側の中断は終了コード130です。プロセスツリー全体の停止や、任意の外部状態の同一性を保証しません。

更新形式v4は26ファイルを厳密に列挙します。v1～v3も従来の固定集合で検証し、v3へv4追加ファイルを混ぜた更新や、欠落・改変を拒否します。旧版のヘルパーではv4を適用できないため、同梱の最新版ヘルパーを使います。
