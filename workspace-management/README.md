# 全成果物と継続開発 — 2026-10-19

成果物50件・製品10件・管理19機能を整理しました。[全体と改良予定](PORTFOLIO.md)、[検索一覧](artifacts.html)、[Markdown](artifacts.md)、[CSV](artifacts.csv)で確認できます。

追加候補は20261019.7です。[48ファイルの導入手順](KIT-README-20261019-7.md)、[改良・検証・残る作業](DEVELOPMENT-20261019.md)を参照してください。[取得元・差分診断](SOURCE-PROVENANCE.md)、[一時ログを作らない回収と連続中断の対応](PROCESS-LOGS.md)を含みます。

連続中断を含む修正元ソースはWindows/Linux × Python3.11・3.14・3.15の全6環境で成功しました。実キットのLinux/Python3.12で48ファイル照合・新規venv導入・標準21検査・Suite26件・取得元214ファイル診断が成功しています。候補20261019.7の実キット6環境CIを確認中です。[段階6記録](verification-20261019-stage7.json)・[ドラフトPR #16](https://github.com/r20942097-hue/faaff/pull/16)に保存しています。外部50件の最終照合も進めています。

20261019.5は追加Windows CIで連続中断の不具合が見つかった履歴版です。以前の固定ZIPと当時の記録、既存の推奨選択は保持します。本体未取得9製品は、取得後の着手内容を一覧へ残しています。

以下は2026-10-15以前の履歴です。件数と版指定は当時の状態です。

候補20261019.7は、登録APIから戻る前の中断でも復元処理が実行されるよう修正しました。修正元311テストとWindows/Linux全6環境が成功しています。候補20261019.6以前の固定ZIPは履歴として保持しています。

---

# 共通管理ツールと成果物一覧

更新：2026-10-15（日本時間）。管理17機能・標準18検査を共通入口へ統合しています。成果物33件は現行対象12件・推奨2件・履歴19件に整理しました。製品10件のうち本体9件は未取得で、管理テストの合格と製品完成は区別します。PR #15で公開中、main未反映です。

## 最初に開くもの

| 目的 | 一覧・手順 |
|---|---|
| 最新版の導入 | [導入キット20261015.2](tool-integration-kit-20261015.2.zip)と[導入手順](KIT-README.md) |
| 成果物の比較 | [一覧表](artifacts.md)・[検索付きHTML](artifacts.html)・[CSV](artifacts.csv) |
| 版・検証・公開状態の見方 | [成果物ガイド](ARTIFACTS-GUIDE.md) |
| 統合と次の開発案 | [改良・開発状況](TOOL-IMPROVEMENTS.md) |
| 変更後の確認範囲 | [共通入力とモジュール対応](SHARED-INPUTS.md) |

初回導入は基準ZIPだけを展開せず、基準ZIP・更新26ファイル・検証ヘルパーをまとめた導入キットを使います。公開SHA256を照合し、新しい作業先へ適用します。基準ZIPの実内容は20261012.2で、公開互換名workspace-source-20261011.zipは維持しています。

今回の改良はSuite監査の実行分離です。-m呼出しから専用の子Pythonでpytestを実行し、管理用と固定監査用のtools名前空間の衝突を避けます。監査原本・既存ZIPパス検査を維持し、module_inputsはCI設定検証とSuite監査へ接続しました。

管理210件・公開支援183件（重複158件は合算しない）、現行一覧と適用先の画面64項目が合格しました。キットの実CLI適用・新規仮想環境のsetup/allはローカルで確認済みです。新キットの実導入はLinux/Windows×Python3.11/3.14/3.15の全6環境で合格しました。[実導入CI](https://github.com/r20942097-hue/faaff/actions/runs/38652955604)。通常CI・CodeQL・Dependency Reviewも合格しています。製品E2Eと今回のFirefox実拡張再実行は対象外です。

更新ZIP内の一覧は作成時点31件、現在の公開一覧は33件です。旧版の本文・版・検証範囲を保持し、最新版の導入は上記の手順を使います。広告リストの本文・版20261011.1は今回変更していません。

---

## 以前のソーススナップショットと開発記録

以下は前の公開READMEです。15機能・検証302件などの数値と導入手順は当時の対象で、現行17機能・新版キットの結果とは区別します。

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

今回の成果物一覧・共通生成更新は、公開ZIP20261012.2の内容を変更するものではありません。17の候補ファイルを固定ハッシュで検証し、検証済み基準ZIPの新規展開先へ適用して管理コードを別途検査します。詳細・実行結果は [成果物一覧の検証記録](artifact-catalogue-validation.json) を参照してください。

## 新しい管理コードを使う

基準ZIPと[管理コード更新ZIP](catalogue-update-20261012.1.zip)・[SHA256](catalogue-update-20261012.1.zip.sha256)を使い、新規作業先を作成します。リポジトリのルートから実行してください。

```sh
python workspace-management/apply_catalogue_update.py --base workspace-management/workspace-source-20261011.zip --update workspace-management/catalogue-update-20261012.1.zip --update-sha256 010c64b23b6c8a66adadf9c43c8711f293d7ea4c2fe3f336c951682b37ec0fde --output work/updated-tools
```

作成したwork/updated-toolsで新規仮想環境を用意し、仮想環境のPythonでtools/manage.py setupとallを実行します。既存の作業先は上書きしません。基準ZIPのSHA256を固定し、更新ZIPの全ファイルを照合してから適用します。新しい16機能の管理コードは更新ZIP側、基準ZIPは以前の15機能です。製品本体の完成判定とは別です。
