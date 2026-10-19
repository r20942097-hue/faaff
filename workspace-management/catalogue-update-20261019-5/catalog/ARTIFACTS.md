# 20261019.5更新の案内

作成時点の成果物44件・製品10件・管理19機能・標準20検査です。[取得元と差分](SOURCE-PROVENANCE.md)、[一時ログを作らない回収](PROCESS-LOGS.md)、[新しい作業先の手順](../README.md)を参照してください。以下は以前の説明・履歴です。

---

# 成果物一覧の見方・統合更新

更新：2026-10-15（日本時間）。[成果物一覧](generated/artifacts.html)は33件です。管理17機能・標準18検査・製品10件の取得状況を確認できます。製品本体9件は未取得です。

## 最初に選ぶもの

| 状況 | 選択 | 内容 |
|---|---|---|
| 初回導入 | ツール統合・導入キット20261015.2 | 基準ZIP・26ファイル更新・ヘルパー4ファイル・手順書 |
| 基準ZIPと最新版ヘルパーがある | 管理更新ZIP20261015.2 | 26ファイル、109,873bytes |
| 過去の状態を再現する | 履歴版の固定ZIP | 作成時点の本文・検証範囲を保持 |

キットは610,683bytesです。版・SHA256・固定公開先を一覧で照合し、[KIT-README.md](https://github.com/r20942097-hue/faaff/blob/codex/workspace-management-20261011/workspace-management/KIT-README.md)の手順で新規作業先へ導入します。基準ZIPの実内容は20261012.2で、公開互換名workspace-source-20261011.zipとは区別します。更新ZIP内の一覧は作成時点31件、現在の公開一覧は33件です。固定ZIP内の推奨指定・説明は作成時点の記録で、最新版の導入は同梱KIT-READMEを使います。

## 一覧の見方

1. 「版の選び方」で推奨・現行対象、履歴版、全ての版を選びます。現在は現行対象12件・推奨2件・履歴19件です。
2. 名前・用途・版で検索し、種類と公開状況を組み合わせます。条件解除で全件・登録順へ戻ります。
3. main反映済みか、PR公開・main未反映かを確認します。共通管理の改良は[PR #15](https://github.com/r20942097-hue/faaff/pull/15)で公開中です。
4. 公開版の検証範囲・確認日・固定コミットを読み、サイズ・SHA256を照合します。本文一致だけの確認を動作合格とは扱いません。
5. 生成時の手元確認は一覧作成時点の状態です。閲覧端末の診断ではありません。

| 表示 | 意味 |
|---|---|
| 推奨版 | 用途系列ごとに正本へ明示した導入対象。公開・動作検証・main反映とは別 |
| 現行対象 | 系列別の版選択がない独立した対象 |
| 履歴版 | 本文・固定公開先・当時の検証を保持した過去の対象 |
| 公開版の本文一致 | 固定公開ファイルのサイズ・SHA256が一致 |
| 検証合格 | 表示した版の、記載した範囲の検証が合格 |
| 内容変更・要再確認 | 手元の本文が公開・検証記録と異なる |
| 手元は未照合 | 独立公開一覧など、手元を診断していない |

HTML・Markdown・CSV・JSONは同じ正本から生成します。確認日・版文字列から推奨を自動判定せず、同じ系列への複数推奨を拒否します。登録解除は原本削除ではありません。基準比較は固定公開ZIP20261012.1を保持し、再生成で移動しません。

## 共通ツールと設定

```sh
python tools/manage.py build
python tools/manage.py check
python tools/manage.py doctor
python tools/manage.py run --tool settings-consistency
python tools/manage.py run --tool workflows
python tools/manage.py run --tool suite-audit
```

設定が壊れた場合はpython tools/check_settings.pyで診断します。registryが入力・コマンド・依存・時間制限を管理し、catalog/config.jsonが一覧設定を管理します。配布設定はlink_mode=directです。Python依存は別の版・SHA256ロックで固定します。

共通入力6グループ・フォルダ照合6ツールを維持し、s/testsはfilters、faaffの検証ソースはcandidatesへ接続済みです。新しいmodule_inputsはローカルの-mと.py入力を明示対応させ、CI設定検証とSuite監査に導入しました。既存modulesはインストール済み依存の確認用で、用途が異なります。[共有入力](https://github.com/r20942097-hue/faaff/blob/codex/workspace-management-20261011/workspace-management/SHARED-INPUTS.md)で範囲を確認できます。

## 更新候補を比較する

正本をwork/へ複製し、本文・版・サイズ・SHA256・固定公開先を編集します。新規・本文変更対象の動作検証はpendingへ戻します。

```sh
python tools/check_artifact_publication.py --review work/artifacts-proposed.json --candidate work/artifacts-checked.json --preview work/artifacts-review.md
```

固定公開本文を新規取得し、比較表と確認済み候補を新規ファイルへ出力します。正本・入力候補は上書きしません。本文確認で動作合格は付与せず、古い合格を新しい本文へ引き継ぐ候補を拒否します。推奨指定だけを変更する場合も比較表へ表示され、本文の検証記録とは区別します。

不完全な通信、正本・候補の処理中の変更、15分より古い観測、不正な未来時刻は拒否します。scope・baseline・共有ルール根拠の変更はこのレビューでは扱いません。公開状況だけの観測には--reviewを付けずに--candidate/--previewを使います。採用前に差分と必要な動作検証を確認します。

[統合・改良案](https://github.com/r20942097-hue/faaff/blob/codex/workspace-management-20261011/workspace-management/TOOL-IMPROVEMENTS.md) · [実ファイルの比較例（未採用）](https://github.com/r20942097-hue/faaff/blob/codex/workspace-management-20261011/workspace-management/ARTIFACT-REVIEW-EXAMPLE.md)

## Suite監査の実行分離

-m呼出しから同じPythonの専用子プロセスを起動し、pytestと固定監査ソースのtools名前空間を扱います。cwd・sys.pathの変更を子へ分け、監査原本のハッシュ確認・26テスト・Windows ZIPパス対策を維持します。v4の26ファイル更新には同梱の最新版ヘルパーを使います。旧v1～v3の固定集合も維持し、不正な混在を拒否します。
