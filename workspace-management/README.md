# 共通ツール・整理済みソーススナップショット

s・faaffをまたぐ15機能の生成・診断・検証を共通入口へまとめました。保存用ソースZIPであり、フィルター配信の正本とGit履歴は既存リポジトリを維持します。

## 見方

最新版を選ぶときは **[成果物一覧](artifacts.md)** を開きます。用途・版・main/PRの公開状態・検証日を確認できます。検索付きHTML、CSV、JSONも同じ[正本](artifacts-source.json)から生成しています。

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

正式版Python 3.15.0で標準17検査・回帰302件を確認しました。一覧UI35項目は既存の確認結果で、今回一覧の実装は変更していません。LinuxのWindows junction 1件はskipとして別集計します。ワークフロー検査は標準Python版のPyYAMLでも通過しています。更新版は新規Python 3.15環境で導入から管理検証まで通過しました。Linux/Windows × Python 3.11/3.14/3.15の6環境CIすべてで合格しました。[今回のCI](https://github.com/r20942097-hue/faaff/actions/runs/38189090220)とvalidation.jsonで照合できます。

固定入力の二重ビルドがバイト一致し、ZIP全ファイルのハッシュ・パスを展開前に検証します。最新内容はworkspace-source-20261012.2.zip、192ソースファイル、515,953バイトです。ZIP内の公開記録は作成時点の履歴です。最新ZIPのSHA256・実行コミット・CIはZIP外のvalidation.jsonで照合してください。

不正UTF-8を含む子プロセス出力でも終了コードを保持します。各コマンドの結果を順次保存し、中断時は終了コード130と中断状態を記録して残りを停止します。実際のSIGINTで確認しました。タイムアウトは標準出力・標準エラーの部分ログを保存します。全ての子孫プロセスまで停止できる保証ではありません。元の管理・監査ソース73ファイルは保持し、Nextの圧縮差やSuiteのWindows ZIPパス差は明示したアダプターで検査します。

## 公開範囲と残課題

録画・AI・Windows操作・Browser Bridge等の製品本体は未取得です。管理ソースのCIを製品E2Eや録画完成判定へ転用しません。署名付きuBOのFirefox実拡張12項目は同一フィルター版で以前に確認済みで、Python 3.15の実拡張合格を意味しません。

sの広告更新はPR #3でmain反映済み。日本語表示はPR #5でCI成功、main未反映。faaffのDependency Reviewは以前API403で失敗していましたが、今回PR #15で合格し、公開した3依存表の解析を確認しました。high以上の脆弱性は検出されませんでした。検査条件を弱めていません。main未反映です。

CIはPR更新と手動実行を入口とし、pushとの二重実行を除いています。ZIP・Python bootstrap・チェックサム・CI定義の変更時に6環境で検証します。GitHubのPRパス条件はPR全体の変更を評価するため、このPRではREADMEや検証記録のみの追記でも再実行されます。ライセンス・出典・取得コミットを保持しています。

2026-10-12追補：導入をmanage.py setupから実行できるようにしました。CI設定のpermissions・jobs・steps・uses・checkoutのwithに不正な型がある場合は検査エラーとして表示します。ローカル方針チェックであり、Actions全仕様を代替するものではありません。ツール一覧では診断したPythonの版も確認できます。

## Dependency Reviewと依存照合の見方

[残作業と手順](DEPENDENCY-READINESS.md)に管理設定の確認・再実行・main反映の順序をまとめました。検証用依存3プロファイルをdependencies/のrequirements.txtへ確認用に公開し、CIで検証済みZIPとの一致を照合します。導入の正本はZIP内のロックです。照合用9テストはZIP内の回帰302件と別に検証します。用途・サイズ・SHA256は通常表示、または `verify_dependencies.py --snapshot 展開先 --json` で確認できます。3表が一致した場合にだけ合格の一覧を表示し、CIログにも残します。PR #15の解析成功と残る警告はリンク先に記載しました。

## 今回のツール開発

依存導入を通常ツールと同じ子プロセス処理へ統合し、起動前にコマンドを保存します。時間切れの部分ログ、不正UTF-8、起動失敗の理由、中断状態・終了コードを導入結果に残します。前の処理が成功しても次の処理に失敗したら、全体を合格とせず残りを停止します。追加6件のテストと新規仮想環境で確認しました。

[改良案と開発状況](TOOL-IMPROVEMENTS.md)に対象・変更・検証・残課題を一覧で記載しました。

今回の成果物一覧・共通生成更新は、公開ZIP20261012.2の内容を変更するものではありません。15の候補ファイルを固定ハッシュで検証し、検証済み基準ZIPの新規展開先へ適用して管理コードを別途検査します。詳細・実行結果は [成果物一覧の検証記録](artifact-catalogue-validation.json) を参照してください。
