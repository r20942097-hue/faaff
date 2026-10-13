# 共通入力の影響範囲

2026-10-14。registryのinput_groupsから生成。明示登録した範囲のみで、全間接依存・外部状態を網羅しません。

| 共通入力 | 利用機能 | 登録ファイル |
|---|---|---|
| 共通実行・診断・登録設定 | 17機能：成果物・全ファイル・ライブラリ一覧 / 広告リスト生成・同期 / 候補の根拠・昇格判定 / 実エンジン検証 / 画面・DOM検証 / CI設定検証 / 監視・録画ツール / プロジェクト・配布監査 / Control Planeの抽出・整合性 / 依存・検証根拠の確認 / Suite配布監査の回帰検証 / Control Plane Nextの配布・復元検証 / 固定したPython検証環境の照合 / Firefox実拡張の動作検証 / 取得ツール原本の整合性 / 成果物の公開本文・main状況確認 / 設定・実行入口の重複と整合性 | `tools/registry.py`<br>`tools/doctor.py`<br>`tools/manage.py`<br>`tools/registry.json`<br>`tools/configuration.py`<br>`catalog/config.json`<br>`tools/check_settings.py` |
| Python検証依存と導入 | 4機能：画面・DOM検証 / CI設定検証 / Suite配布監査の回帰検証 / 固定したPython検証環境の照合 | `tools/check_python_lock.py`<br>`tools/setup_verification.py`<br>`tools/python-lock.json`<br>`tools/requirements-verification.lock.txt`<br>`tools/requirements-build.lock.txt`<br>`tools/python-build-lock.json`<br>`tools/requirements-verification.txt` |
| 共有フィルター正本と生成 | 3機能：広告リスト生成・同期 / 実エンジン検証 / Firefox実拡張の動作検証 | `s/scripts/generate_lists.py`<br>`s/filter-profiles.json` |

`python tools/manage.py doctor` で変更と不足を確認します。共通入力に変更があれば前回の合格は再検証待ちになります。設定が壊れた場合は `python tools/check_settings.py` で検査します。

[設定の役割](TOOL-IMPROVEMENTS.md) · [初回導入](KIT-README.md)
