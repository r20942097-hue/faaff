# 成果物一覧の見方・統合更新

更新：2026-10-14（日本時間）。[成果物一覧](artifacts.html)は19件です。管理17機能・標準18検査・10製品の取得状況を、配布物の一覧と分けて確認できます。製品本体は9件未取得です。

## 最初に選ぶもの

| 状況 | 選択 | 含まれるもの |
|---|---|---|
| 初回導入 | ツール統合・導入キット20261014.2 | 基準ZIP・24ファイル更新・検証ヘルパー・手順書 |
| 基準ZIPと最新版ヘルパーがある | 管理更新ZIP20261014.2 | 管理コード24ファイル、91,830bytes |
| 過去の版を再現する | 一覧に残した固定版ZIPと検証記録 | 作成時点の内容。現行コードとは区別 |

キットは590,429bytesです。SHA256と固定公開先は成果物一覧から確認してください。基準ZIPは20261012.2を使用します。ファイル名workspace-source-20261011.zipは公開互換名で、実内容の版は一覧の版・ハッシュで確認します。更新ZIP内の一覧は作成時点17件、現在の一覧は新しい更新ZIPとキットを加えた19件です。

## 一覧の見方

1. 名前・用途・版で検索し、公開状況と種類で絞り込みます。登録順・名前順・確認日順・サイズ順で並べ替えられます。「条件を解除」で登録順へ戻ります。
2. main反映済みか、PR公開でmain未反映かを確認します。現在の共通ツール改良はPR #15で公開中です。
3. 公開版の検証範囲・確認日・固定コミットを読みます。本文一致だけの確認を動作合格とは扱いません。
4. 「サイズ・SHA256・原本パス」で同じ版か照合します。生成時の手元確認は一覧作成時点の状態で、閲覧端末の診断ではありません。
5. 前回からの変更は固定した以前の公開ZIP20261012.1との比較です。一覧の再生成で比較対象は移動しません。

| 表示 | 意味 |
|---|---|
| main反映済み | 固定mainコミットの公開本文を確認済み |
| PR公開・main未反映 | PR側の固定版を公開。mainへの反映はまだ |
| 公開版の本文一致 | 固定公開ファイルとSHA256が一致 |
| 検証合格 | 表示した版の、記載した範囲の検証が合格 |
| 内容変更・要再確認 | 手元が公開・検証記録と違う |
| 手元は未照合 | 独立公開一覧など、手元のファイルを診断していない |

HTML・Markdown・CSV・JSONは同じ正本から生成します。CSVはUTF-8です。登録解除の差分は一覧から外れた意味で、原本削除ではありません。

## 導入と更新

初回導入は[KIT-README.md](KIT-README.md)を参照します。キットZIPと公開チェックサムを照合し、新しいフォルダへ展開して、同梱CLIで新規work/作業先を用意します。既存出力先への上書きは拒否します。途中で失敗した場合は、その処理が作った作業先だけを整理します。

基準ZIPと最新版ヘルパーがある場合は、リポジトリルートで実行します。

```sh
python workspace-management/apply_catalogue_update.py --base workspace-management/workspace-source-20261011.zip --update workspace-management/catalogue-update-20261014.2.zip --update-sha256 1c20be0134eadb09c94bf77acda8030311e1a165ff8ee47936596e5ffb71134d --output work/integrated-tools-20261014-2
```

展開・適用はパス・CRC・全内容ハッシュ・基準版を照合します。その後、新規作業先で仮想環境を作成してsetup/allを実行します。setupはネットワークを使用します。配布設定はlink_mode=directで、生成後にもカタログ内のシンボリックリンクがないことを検査します。旧版ZIPは固定履歴として保持します。

## 共通ツールから使う

```sh
python tools/manage.py build
python tools/manage.py check
python tools/manage.py doctor
python tools/manage.py run --tool settings-consistency
```

正本catalog/artifacts.jsonと生成処理tools/artifacts.pyを、既存build/all/checkへ接続しています。設定検査は重複、同じcwd・argvの時間制限、直接実行ファイルの登録を確認します。Pythonの-B/-I/-W/-X、Nodeの--no-warnings等、対応する先行フラグの後も照合します。未対応フラグと値不足はエラーです。モジュール・インライン・標準入力・情報表示・Node inspectはexcluded_entriesへ除外形式を記録します。全CLI文法・オプション値の妥当性・全間接依存の検査ではありません。

設定が壊れて共通入口から実行できない場合はpython tools/check_settings.pyを使います。検査前に以前の合格を未完了へ置き換え、失敗を保存します。

## 変更後に確認する範囲

| 変更 | 必要な確認 |
|---|---|
| 一覧の説明・公開先・SHA256 | build/checkと固定公開本文照合 |
| 一覧コード・画面 | test、build/check、browser_smoke.py |
| フィルタールール | filters --checkと該当エンジン検査 |
| 依存・Python・共通管理コード | 新規仮想環境のsetup/allと対象Python・OSのCI |
| 配布ZIP | 全内容ハッシュ、新規先への実CLI適用、適用先のsetup/all |

共通入力3グループは、実行7ファイル／17機能、Python検証7ファイル／4機能、フィルター正本2ファイル／3機能です。doctorは変更入力と再実行コマンドを案内します。未登録の間接依存・外部サービスの状態を推論しません。

## 公開状態の更新候補

```sh
python tools/check_artifact_publication.py --candidate work/artifacts-proposal.json --preview work/artifacts-preview.md
```

新規ファイル名を指定します。固定公開本文のサイズ・SHA256、現在のmainとPR状態を観測し、変更前後を表にします。正本は自動変更しません。不完全な通信・古い正本への観測からは提案を作りません。確認後に公開状態が変わるため、採用前に再観測します。本文の版・ハッシュ・動作検証日は別途レビューが必要です。

[統合・改良案](TOOL-IMPROVEMENTS.md) · [共有入力](SHARED-INPUTS.md) · [PR #15](https://github.com/r20942097-hue/faaff/pull/15)
