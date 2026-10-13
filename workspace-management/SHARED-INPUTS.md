# 共通入力の影響範囲

2026-10-13。registryのinput_groupsから生成。明示登録した範囲のみで、外部状態や全間接依存を網羅しません。

| 共通入力 | 利用機能 | 照合ファイル |
|---|---|---|
| 共通実行・診断・登録設定 | 16機能：成果物・全ファイル・ライブラリ一覧 / 広告リスト生成・同期 / 候補の根拠・昇格判定 / 実エンジン検証 / 画面・DOM検証 / CI設定検証 / 監視・録画ツール / プロジェクト・配布監査 / Control Planeの抽出・整合性 / 依存・検証根拠の確認 / Suite配布監査の回帰検証 / Control Plane Nextの配布・復元検証 / 固定したPython検証環境の照合 / Firefox実拡張の動作検証 / 取得ツール原本の整合性 / 成果物の公開本文・main状況確認 | `tools/registry.py`<br>`tools/doctor.py`<br>`tools/manage.py`<br>`tools/registry.json`<br>`tools/configuration.py`<br>`catalog/config.json` |
| Python検証依存と導入 | 4機能：画面・DOM検証 / CI設定検証 / Suite配布監査の回帰検証 / 固定したPython検証環境の照合 | `tools/check_python_lock.py`<br>`tools/setup_verification.py`<br>`tools/python-lock.json`<br>`tools/requirements-verification.lock.txt`<br>`tools/requirements-build.lock.txt`<br>`tools/python-build-lock.json`<br>`tools/requirements-verification.txt` |
| 共有フィルター正本と生成 | 3機能：広告リスト生成・同期 / 実エンジン検証 / Firefox実拡張の動作検証 | `s/scripts/generate_lists.py`<br>`s/filter-profiles.json` |

変更後は管理ワークスペースで `python tools/manage.py doctor` を実行し、再検証案内を確認します。共通入力の欠落は実行前に停止します。旧合格に共通入力の照合がなければ再実行が必要です。

[最新版の更新方法](ARTIFACTS-GUIDE.md) · [ツール共通登録](registry.json)
