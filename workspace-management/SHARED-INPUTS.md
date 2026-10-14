# 現行の共通入力（20261015.1）

共通入力は6グループです。フォルダ照合の利用先は6ツールです。取得済みのs/faaffテスト・検証ソースを登録し、登録した利用先の再検証へ接続しました。

| グループ | 対象 | 利用先 |
|---|---|---|
| common-runner | 共通実行7ファイル | 17機能 |
| python-verification | 依存・環境検証7ファイル | 4機能 |
| filter-shared-source | 正本2ファイル | 3機能 |
| management-tests | tools/testsの.pyソース集合 | catalogue、settings-consistency |
| s-tests | s/testsの.pyソース集合（現在5ファイル） | filters |
| faaff-scripts | faaff/browser_filter_lists/scriptsの.pyソース集合（現在9ファイル） | candidates |

faaff-scriptsにはテストと検証実装の両方を含みます。個別登録と共通登録の同じフォルダは1回だけ列挙します。監査2ツールの個別登録も維持しています。追加・変更・削除は利用先の入力照合とdoctorへ反映します。

欠落・空集合・symlinkは実行前に停止し、変更時は後続を止めて理由を表示します。1利用ツールで合算32フォルダ、1フォルダ4096項目・深さ32までです。生成__pycache__は除外します。全import先や外部状態の自動追跡ではなく、OS上で読取りと実行を原子的に固定する保証はありません。

## 以前の3グループの実施記録

# 共通入力の影響範囲

2026-10-14。registryのinput_groupsから生成。明示登録した範囲のみで、全間接依存・外部状態を網羅しません。

| 共通入力 | 利用機能 | 登録ファイル |
|---|---|---|
| 共通実行・診断・登録設定 | 17機能：成果物・全ファイル・ライブラリ一覧 / 広告リスト生成・同期 / 候補の根拠・昇格判定 / 実エンジン検証 / 画面・DOM検証 / CI設定検証 / 監視・録画ツール / プロジェクト・配布監査 / Control Planeの抽出・整合性 / 依存・検証根拠の確認 / Suite配布監査の回帰検証 / Control Plane Nextの配布・復元検証 / 固定したPython検証環境の照合 / Firefox実拡張の動作検証 / 取得ツール原本の整合性 / 成果物の公開本文・main状況確認 / 設定・実行入口の重複と整合性 | `tools/registry.py`<br>`tools/doctor.py`<br>`tools/manage.py`<br>`tools/registry.json`<br>`tools/configuration.py`<br>`catalog/config.json`<br>`tools/check_settings.py` |
| Python検証依存と導入 | 4機能：画面・DOM検証 / CI設定検証 / Suite配布監査の回帰検証 / 固定したPython検証環境の照合 | `tools/check_python_lock.py`<br>`tools/setup_verification.py`<br>`tools/python-lock.json`<br>`tools/requirements-verification.lock.txt`<br>`tools/requirements-build.lock.txt`<br>`tools/python-build-lock.json`<br>`tools/requirements-verification.txt` |
| 共有フィルター正本と生成 | 3機能：広告リスト生成・同期 / 実エンジン検証 / Firefox実拡張の動作検証 | `s/scripts/generate_lists.py`<br>`s/filter-profiles.json` |

`python tools/manage.py doctor` で変更と不足を確認します。共通入力に変更があれば前回の合格は再検証待ちになります。設定が壊れた場合は `python tools/check_settings.py` で検査します。

[設定の役割](TOOL-IMPROVEMENTS.md) · [初回導入](KIT-README.md)

## モジュール入力の明示対応（20261015.1）

既存6グループは維持します。モジュール対応を導入した利用先は現在1件、workflowsです。

| 利用先 | -mの対象 | 登録ソース |
|---|---|---|
| workflows | tools.check_workflows | tools/check_workflows.py |

各ツール、またはinput_groupsへ次を指定できます。filesはワークスペース相対の.pyファイルです。

```json
"module_inputs": [
  {"module": "tools.check_workflows", "files": ["tools/check_workflows.py"]}
]
```

共通グループはtoolsで利用先を明示し、通常のfilesを空配列にしてモジュール対応だけを登録することもできます。同じ対応は統合し、同じ利用先の同一モジュールに異なるファイル集合がある場合は拒否します。1利用先32対応、1対応128ファイルまでです。モジュール名はASCII識別子のドット区切り、ソースは隠しパスを除いた相対.pyパスです。

cwdに対応するmodule.pyまたはmodule/__main__.pyを含め、利用ツールの-m実行から参照される対応だけを登録します。未使用・競合・-I/-Pのローカル対応を拒否します。通常のmodulesはインストール済み依存の確認用で維持します。

実行前後と後続コマンドの前にソースを照合し、変化時は後続を停止して失敗を記録します。欠落・symlinkは準備不可です。doctorとツール一覧に対応・変更ファイル・再実行コマンドを表示します。実行時import先の保証、未登録importの追跡、原子的な読取り固定ではありません。
