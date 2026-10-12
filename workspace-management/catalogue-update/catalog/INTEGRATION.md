# 統合・改良の実施表

2026-10-11。目的から選ぶ場合は[ツール一覧](generated/tools.html)、原本を探す場合は[全ファイル一覧](generated/inventory.html)を開きます。

| 対象 | 今回の統合・改良 | 検証・完了条件 | 現状 |
|---|---|---|---|
| 全ツール | 登録・実行・診断・時間制限をmanage.pyとregistry.jsonへ統合 | 同じ設定で依存診断と実行、不足時は停止 | 実装・回帰検証済み |
| 広告・追跡 | 共通JSONから既存7配信ファイルを生成 | 原本・ミラー一致、2エンジン検証 | sのmain公開済み。faaffはPR #14でDependency Reviewを含むCI合格、main未反映 |
| 日本語表示 | uBO既定設定でスタイルが有効になる明示的全ホスト指定 | 標準・Deep、アイコン・行高を実拡張で検証 | 修正PR #5、CI成功 |
| 候補管理 | 厳格JSON・期限・独立根拠・昇格条件を共通化 | 不正入力を拒否、保留を自動採用しない | ローカル検証済み |
| プロジェクト監査 | 別ブランチの管理ソースを固定して登録 | 原本73ファイルのハッシュ・欠落・追加を検出 | 取得・回帰検証済み |
| Control Plane | v9の抽出とNextのZIP復元・整合性を共通実行 | 固定ソースのテストと配布検証 | 管理レイヤー検証済み。製品本体の合格判定には使わない |
| Suite監査 | 配布監査を個別実行に接続 | 独立した26テスト | 検証済み |
| Python設定 | 通常依存と3.15用ビルド依存を版・SHA256で固定、導入入口を共通化 | 新規仮想環境、pip check、実行中の版・PyYAMLプロファイル照合 | 正式版3.15.0で確認、[互換性一覧](PYTHON.md) |
| Firefox実拡張 | 署名付きuBO・Geckodriver・Docker image・Python依存を固定 | 対象通信、表示、フォントの12項目 | 制御したローカルfixtureで通過 |
| 配布・一覧 | 原本・設定・一覧・検証記録をシンボリックリンク不要のZIPへ | 二重ビルド一致、新規展開前のパス・全ハッシュ確認 | ソーススナップショットとして検証。録画完成品とは別 |
| 録画・AI・Windows等 | 製品本体を能力契約と共通診断へ接続 | 正式ソース、依存、起動・復旧・実機テスト | 本体未取得。公開2repo・16ブランチの調査では見つからず |

## 操作の順序

```sh
python tools/manage.py doctor
python tools/manage.py filters --check
python tools/manage.py all
python tools/manage.py run --tool source-integrity
```

任意検証用の仮想環境とハッシュ固定依存の導入は[使い方](README.md)を参照してください。実エンジン・画面・CI設定の追加検証は[広告更新表](ADBLOCK-UPDATE.md)に記載しています。

```sh
# Dockerと初回取得用ネットワークがある環境
python tools/manage.py run --tool firefox-extension

# 新しいファイル名を指定。既存ZIPやチェックサムは上書きしない
python tools/manage.py release --output work/releases/workspace-source.zip
```

ソースZIPは新規展開先で一覧・標準検証を実行できます。ブラウザー・エンジンの取得キャッシュ、仮想環境、Git管理データ、認証情報は含めません。

## 次の統合案

[10製品の一覧](PROJECTS.md)に本体の有無と次の改良を分けて記載しました。既存の履歴資料は参照として保持します。新しい本体を取得したら、まず取得元・バージョン・ハッシュを固定し、設定・イベント・ジョブ結果の契約を管理レイヤーへ接続します。その後、起動・切断・再接続・中断復旧を検証します。

録画はFFmpeg診断、録画終了、MP4確定、再起動後の復旧まで実機確認が必要です。AI・Windows操作・Browser Bridgeは現在の本体ソースがなく、管理ツールの合格をこれらの完成扱いにはしません。

実行結果の合格表示は、登録ファイルと実行設定の照合情報を保存して再判定します。Pythonの版も別途照合します。外部サービス・全ての間接入力まで検証した扱いにはしません。

中断時は実行済みの検査を保持し、残りを停止して中断状態を保存します。タイムアウト時も部分ログから原因を調べられます。依存名はドット・ハイフン・アンダースコアの別表記を統一してビルド依存との版競合を検出します。

2026-10-12：依存導入をmanage.py setupへ接続。CI設定の型不正をエラーとして報告し、一覧にPython版を表示します。管理コードと製品本体の検証範囲は維持します。

## 2026-10-12：改良案と実施状況

| 優先 | 対象・問題 | 改良内容・方針 | 完了条件・現状 |
|---|---|---|---|
| 1 | 依存導入の失敗時にコマンドと部分ログが欠落 | 通常実行と子プロセス処理を共通化し、起動前・終了後の結果を保存 | 実装済み。時間切れ・起動失敗・中断等の追加6件と新規環境で検証 |
| 2 | 依存表と配布ZIPの内容を追いにくい | ZIP外の3依存表と原本をバイト照合し、用途・サイズ・SHA256を表示 | PR #15で照合9件と6環境CI合格。Dependency ReviewもPR #14・#15で合格 |
| 3 | Firefox用PySocksの保守評価警告 | Selenium→urllib3[socks]→PySocksの依存経路を確認。単独削除せず、上流の要求変更や代替構成を調査 | 最新PyPI版は1.7.1、2019-09-20公開。警告は未解消。変更時はpip checkとFirefox実拡張の再検証が必要 |
| 4 | typing_extensionsのライセンスをGitHubが未検出 | 4.16.0の配布メタデータではPSF-2.0とLICENSEを確認。検出元の差を記録 | PyPI確認済み、GitHubの検出成功は未確認。判定条件を緩和しない |
| 5 | 本体未取得の録画・AI・Windows等 | 正式ソースを固定取得した後、設定・イベント・結果の契約へ接続 | 本体が必要。管理ソースのCIを製品完成として扱わない |

調査根拠：[Selenium 4.51.0](https://pypi.org/pypi/selenium/4.51.0/json)、[urllib3 2.8.0](https://pypi.org/pypi/urllib3/2.8.0/json)、[PySocks公開版](https://pypi.org/pypi/PySocks/json)、[typing_extensions 4.16.0](https://pypi.org/pypi/typing_extensions/4.16.0/json)、[TimeoutExpiredの出力仕様](https://docs.python.org/3.15/library/subprocess.html#subprocess.TimeoutExpired)。公開が古いことだけで脆弱性があるとは判定しません。現在の固定版とハッシュは維持します。

2026-10-12：配布・購読の12成果物を[成果物一覧](generated/artifacts.html)へ整理。正本 `catalog/artifacts.json` から4形式を既存build/checkで生成し、版・固定公開先・検証範囲・確認日・生成時の手元照合を分けます。前の公開ZIP 20261012.1と版・本文を比較します。[更新案と完了条件](ARTIFACTS.md)を参照してください。新しい生成コードは開発側の更新であり、公開ZIP 20261012.2への取り込みとは別に検証します。

成果物の公開確認を共通registryのartifact-publicationへ登録しました。固定版と固定mainの本文、PR状態を確認し、結果を保存します。正本は自動変更せず、通信失敗・main本文変化・別の正本への古い確認結果から公開昇格を行いません。更新案は新規work JSONへ出します。
