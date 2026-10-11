# 共通ツール・整理済みソーススナップショット

s・faaffをまたぐ15機能の生成・診断・検証を共通入口へまとめました。保存用ソースZIPであり、フィルター配信の正本とGit履歴は既存リポジトリを維持します。

## 見方

1. `workspace-source-20261011.zip`と`.zip.sha256`を取得し、SHA256を照合します。
2. 新しいフォルダへ展開し、`README.md`から目的を選びます。

| 一覧 | 内容 |
|---|---|
| catalog/generated/tools.html | 15機能の準備状況・前回の結果・登録入力とPython版の照合 |
| catalog/generated/inventory.html | 全ファイルの検索、分類、原本リンク |
| catalog/generated/libraries.html | ビルド依存を含む41件、重複を統合 |
| catalog/generated/projects.html | 10製品の本体ソース・状態・次の統合案 |
| catalog/PYTHON.md | Python 3.15対応、導入、改善案と調査根拠 |

実行準備と動作合格は別列です。合格時の登録ファイル・実行設定・Python版が変わった場合は再検証を表示します。外部サービスや全ての間接入力まで同一と保証する意味ではありません。実行後はdoctorで一覧を更新してください。

## 実行とPython 3.15対応

Python 3.11以上で新規仮想環境を作り、仮想環境のPythonで`tools/manage.py setup`を実行します。通常11依存の版・配布SHA256を固定し、pip checkと実行版の照合まで共通実行します。

Python 3.15ではPyYAML 6.0.3の配布バイナリがないため、固定ソースと固定ビルド依存から標準Python版を導入します。Cコンパイラー不要です。グローバルPythonでの導入は停止します。詳しいOS別コマンドはZIP内のcatalog/README.mdにあります。

```sh
python tools/manage.py doctor
python tools/manage.py all
python tools/manage.py run --tool suite-audit
```

## 検証

正式版Python 3.15.0で標準17検査・回帰296件・一覧UI35項目を確認しました。LinuxのWindows junction 1件はskipとして別集計します。ワークフロー検査は標準Python版のPyYAMLでも通過しています。最新ZIPのLinux/Windows × Python 3.11/3.14/3.15の6環境CI結果はvalidation.jsonで確認できます。

固定入力の二重ビルドがバイト一致し、ZIP全ファイルのハッシュ・パスを展開前に検証します。最新内容はworkspace-source-20261012.1.zip、192ソースファイル、509,757バイトです。ZIP内の公開記録は作成時点の履歴です。最新ZIPのSHA256・実行コミット・CIはZIP外のvalidation.jsonで照合してください。

不正UTF-8を含む子プロセス出力でも終了コードを保持します。各コマンドの結果を順次保存し、中断時は終了コード130と中断状態を記録して残りを停止します。実際のSIGINTで確認しました。タイムアウトは標準出力・標準エラーの部分ログを保存します。全ての子孫プロセスまで停止できる保証ではありません。元の管理・監査ソース73ファイルは保持し、Nextの圧縮差やSuiteのWindows ZIPパス差は明示したアダプターで検査します。

## 公開範囲と残課題

録画・AI・Windows操作・Browser Bridge等の製品本体は未取得です。管理ソースのCIを製品E2Eや録画完成判定へ転用しません。署名付きuBOのFirefox実拡張12項目は同一フィルター版で以前に確認済みで、Python 3.15の実拡張合格を意味しません。

sの広告更新はPR #3でmain反映済み。日本語表示はPR #5でCI成功、main未反映。faaffのDependency ReviewはDependency graph無効で失敗しており、設定の有効化後に再検証が必要です。検査を弱めていません。

CIはPR更新と手動実行を入口とし、pushとの二重実行を除いています。ZIP・Python bootstrap・チェックサム・CI定義の変更時に6環境で検証します。GitHubのPRパス条件はPR全体の変更を評価するため、このPRではREADMEや検証記録のみの追記でも再実行されます。ライセンス・出典・取得コミットを保持しています。

2026-10-12追補：導入をmanage.py setupから実行できるようにしました。CI設定のpermissions・jobs・steps・uses・checkoutのwithに不正な型がある場合は検査エラーとして表示します。ローカル方針チェックであり、Actions全仕様を代替するものではありません。ツール一覧では診断したPythonの版も確認できます。
