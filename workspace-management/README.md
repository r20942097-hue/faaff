# 共通ツール・整理済みソーススナップショット

既存の2リポジトリをまたぐ生成・診断・検証を、共通入口と一覧にまとめました。ZIPは2026-10-11時点の保存用ソースです。フィルター配信の正本とGit履歴は既存のs・faaffを使い続けます。

## 見方

1. `workspace-source-20261011.zip`とチェックサムを取得します。
2. チェックサムとZIPのSHA256を照合し、新しいフォルダへ展開します。
3. 展開先の`README.md`から目的を選びます。
4. `catalog/generated/tools.html`：ツールの目的・実行準備・不足項目。
5. `catalog/generated/inventory.html`：全ファイルの検索表。
6. `catalog/generated/libraries.html`：直接・間接依存39件。
7. `catalog/generated/projects.html`：10製品の現状と次の統合案、検索と本体ソースの状態で絞り込み。

「実行準備あり」は依存診断です。テスト合格は`catalog/results/`で確認してください。配布ZIPのリンクは原本を直接開くためsymlink不要です。

## 検証したこと

- 共通17標準＋4追加検査が通過。
- 回帰281件通過、LinuxではWindows junction 1件をskip。Windows CIでは製品E2Eとは別に管理コードを検証。
- 署名付きuBOのFirefox実拡張12項目、一覧UI33項目、合成DOM12項目通過。
- 固定入力の二重ビルドがバイト一致、ZIP全ファイルのハッシュとパスを展開前に確認。
- 2,149,235バイトの非圧縮ZIPを485,487バイトへ圧縮（約78%削減）。

追加のLinux/Windows・Python 3.11/3.14 CIはこのブランチの「Workspace snapshot checks」で確認します。管理ソースの検証であり、Windows製品の実機合格ではありません。

## 実行

展開先でPython 3.11以上を使います。

```sh
python tools/manage.py doctor
python tools/manage.py all
python tools/manage.py run --tool source-integrity
```

追加依存は仮想環境で`tools/requirements-verification.lock.txt`からハッシュ検証付きで導入します。詳細は展開先の`catalog/README.md`を参照してください。Firefox実拡張の再実行はLinux Docker用です。

## 制約と更新

録画・AI・Windows操作・Browser Bridge等の製品本体は未取得です。既存履歴の合格記録は今回の合格数に含めません。ZIPを録画完成品として扱いません。

sの広告リストはPR #3をmainへ反映済み。日本語表示の追補はs PR #5でCI成功、main未反映。faaff PR #14はDependency graph無効によりDependency Reviewが失敗しています。設定を有効化して再検証が必要です。

`s/`、`faaff/`、取得した管理ソースに含まれるライセンス・出典・取得コミットを保持しています。ZIP、仮想環境、キャッシュ、Git管理データはそれぞれ分離して扱います。

最新版はworkspace-source-20261011.9.zipの内容です。Windows CIで見つかったリンク整理を修正し、Nextの元ソースを保持したまま圧縮差を許容する検証アダプターを追加しました。内部ハッシュ・メタデータ一致と同一環境の二重ビルド一致は必須です。最新版ZIPはLinux/Windows × Python 3.11/3.14の4環境すべて合格しました。モバイル表の折り返しと共通展開ツールの元パス検査を含みます。実行結果は開始時に過去の合格を無効化し、途中経過と終了状態を原子的に保存します。

Suiteの検証では、Windowsで変換される前のZIPパス表記も検査します。元の監査実装とテストを変更せず、共通入口から明示したアダプターで実行します。ツール一覧には、診断時に読み込んだ前回の結果と日時（JST）を別列で表示します。実行後はdoctorで更新してください。

CI結果：[最新ソースコミットの4環境検証](https://github.com/r20942097-hue/faaff/actions/runs/38139542746)。実行対象のコミットとZIP SHA256はvalidation.jsonで確認できます。

共通ZIP展開も、読み込み時に変換された名前を拒否します。NULで隠された接尾辞を含む回帰テストを追加しました。モバイル表は日時・コマンドの列幅を確保し、一文字ずつの折り返しを防ぎます。ZIP内のpublication等の記録は作成時点の履歴です。最新のZIP identityとCIはZIP外のvalidation.jsonで照合してください。

公開ZIPとローカル検証ZIPのSHA256一致も確認済みです。CIはPR更新と手動実行を入口とし、pushとの二重実行を除きました。READMEや検証記録だけの更新ではソース検証を再実行しません。ソースZIP・Python bootstrap・チェックサム・CI定義が変わった場合に4環境で検証します。
