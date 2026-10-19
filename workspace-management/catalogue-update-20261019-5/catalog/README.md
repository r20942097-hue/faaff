# 20261019.5更新の案内

作成時点の成果物44件・製品10件・管理19機能・標準20検査です。[取得元と差分](SOURCE-PROVENANCE.md)、[一時ログを作らない回収](PROCESS-LOGS.md)、[新しい作業先の手順](../README.md)を参照してください。以下は以前の説明・履歴です。

---

# 共通カタログの使い方

最新版を取得するときは **[成果物一覧](generated/artifacts.html)** を開き、用途・版・main/PRの公開状態・検証範囲で選びます。[成果物一覧の見方](ARTIFACTS.md)に詳しい説明があります。

依存関係を調べるときは **[ライブラリ一覧](generated/libraries.html)**、フィルターを選ぶときは **[見やすい比較表](generated/filters.html)**、全ファイルを探すときは **[検索付き一覧](generated/inventory.html)** をブラウザーで開きます。

1. 出典（s / faaff / management等）を選びます。
2. 分類や状態で絞り込みます。通常は現行フィルターから確認してください。
3. 名前・バージョン・ライセンスを検索します。
4. ファイル名はローカル原本、GitHubはリモート参照先を開きます。
5. 「条件を解除」で一覧に戻ります。CSV保存・印刷にも対応します。

## フォルダ一覧

| 見たいもの | フォルダ・ファイル |
|---|---|
| 全体一覧の正本 | generated/ |
| リポジトリ | repositories/s、repositories/faaff |
| 現行フィルター | artifacts/filters/current/ |
| v2候補フィルター | artifacts/filters/candidates/ |
| 外部追加設定が必要なフィルター | artifacts/filters/optional/ |
| 実験候補 | artifacts/experimental/ |
| ライブラリ設定 | libraries/configuration/ |
| 説明・記録 | documentation/ |
| テスト・共通管理コード | verification/ |
| CI・保守 | automation/ |
| 広告ブロック更新・比較 | [ADBLOCK-UPDATE.md](ADBLOCK-UPDATE.md) |
| 調査・統合案 | [REPORT.md](REPORT.md) |
| 検証結果 | results/ |

## 更新方法

ワークスペースのルートで実行します。

```sh
python tools/manage.py filters --check
python tools/manage.py all
```

HTML・Markdown・CSV・JSONは同じ原本から生成します。正本はgenerated/です。lists/とcatalog.csvは互換リンクです。

分類フォルダは相対シンボリックリンクです。重複コピーを作らず、原本への編集・更新を反映します。Git履歴、CI参照、購読URLの元のパスを維持しています。

追加したファイルはbuildで一覧に反映されます。新しい保存先はconfig.jsonのsourcesに追加します。対象は両リポジトリ、ライブラリ保存先、ダウンロード保存先、共通管理コード・資料です。環境用の隠しフォルダ、キャッシュ、調査用workは対象外です。

checkは一覧の内容・SHA256・リンクを照合します。原本を削除した場合はリンク切れを報告します。buildでは前回生成した分類リンクのうち、削除された原本へのリンクを整理します。

## ツールの実行と配布

[ツール一覧](generated/tools.html)では目的・準備状況で絞り込めます。「実行準備あり」は依存が揃う意味です。動作検証はresultsの結果を確認してください。

```sh
python tools/manage.py doctor
python tools/manage.py run --tool source-integrity
python tools/manage.py run --tool governance
```

追加検証は仮想環境で導入します。

```sh
python -m venv work/verification-venv
# Linux/macOS
work/verification-venv/bin/python tools/manage.py setup
# Windows
work/verification-venv/Scripts/python.exe tools/manage.py setup
```

導入は配布SHA256を照合し、pip checkと版照合まで実行します。Python 3.15ではPyYAML 6.0.3の標準Python版を、固定ビルド依存から構築します。Cコンパイラーは不要です。環境の既存パッケージとの混在を避け、新規仮想環境を使ってください。[Python互換性・改善一覧](PYTHON.md)を参照してください。

画面検査にはPlaywrightのChromium、エンジン検査にはprepare_engine.pyによる初回取得が必要です。Firefox実拡張検査はLinux Docker用です。Windows上での実拡張検証済みという意味ではありません。

```sh
python tools/manage.py release --output work/releases/workspace-source.zip
```

配布ZIPはsymlink不要の原本直接リンクです。解凍後のREADME.mdから見られます。録画など不足する製品本体を含む完成版ではありません。

展開前に信頼する場所で確認したSHA256を指定できます。既存の展開先は上書きしません。

```sh
python tools/extract_snapshot.py --archive work/releases/workspace-source.zip --sha256 確認した64桁のSHA256 --output work/unpacked
```

元の作業環境にはGit履歴を残し、ZIPは保存時点のスナップショットとして扱います。Windows等のPython 3.11〜3.15では`PYTHONUTF8=1`と`PYTHONIOENCODING=utf-8`を設定すると、取得した旧ツールの出力も統一できます。

## 製品全体の現状を見る

[製品の検索表](generated/projects.html)で名称・本体ソースの有無・次の統合案を絞り込めます。履歴の参照版は過去の記録です。現在のソース・製品E2Eとは別に読みます。表計算で整理する場合は[製品CSV](generated/projects.csv)を使ってください。

原本は`catalog/projects.json`です。変更後にbuildでHTML・CSV・Markdownを同時更新します。checkは原本と生成表の差異を検出します。

一覧のGitHubリンクはconfig.jsonの`repository_ref`に記録した固定コミットを開きます。更新PRとmainの公開状況は[成果物公開記録](generated/artifacts.json)で確認してください。

前回の合格欄は、登録ファイルのSHA256・実行設定・Python版と照合します。変更があれば再検証を表示します。照合対象は登録された入力であり、外部サービスや全ての間接依存まで同一と保証するものではありません。
