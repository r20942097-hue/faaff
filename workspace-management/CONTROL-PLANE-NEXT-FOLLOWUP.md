# Windows同時書込みの未合格と次の修正

候補20261019.7の実キットCIは6環境中5環境が成功し、Windows/Python3.14で固定Control Plane Nextの `test_concurrent_write_serializes` が `PermissionError(13, 'Permission denied')` を返しました。[CI記録](verification-20261019-stage7-ci.json)、[該当ジョブ](https://github.com/r20942097-hue/faaff/actions/runs/39273845578/job/118132905096)に失敗を残しています。全体は17/18ジョブ成功で、導入合格にはしていません。

失敗ジョブでも管理回帰検査は成功しています。中断・登録中断の修正元は全6環境で成功しました。今回の失敗は、変更していない管理コンポーネントの並行I/O試験で観測されたものです。原因が今回の変更と無関係だと断定するものではありません。

固定原本は `ucs-control-plane-phase2-source.zip`、SHA256は `e0ab7fc8b7b03f5403a96856996b40d6049f639164b7b4fd71bb78ed7645a499` です。ZIPとその検証器・原本ピンは上書きしていません。

## 追加した再現検査

`diagnose_next_concurrency.py` は基準ZIPと内包するNext原本の両方の固定SHA256を検証し、一時ディレクトリに原本を展開して同じ `test_concurrent_write_serializes` を繰り返します。ファイル操作を置換せず、スレッドの例外トレースから発生行・操作・errno・winerror・対象ファイル・呼出し履歴を記録します。各回の後にチェックサム、4件の能力、スナップショット、ロック解放を確認し、失敗時も状態を保存します。

Linuxの初回10回は失敗を観測せず、記録機能2テストを含む管理回帰313件は308成功・5件OS依存スキップでした。Windows/Linux × Python3.11・3.14・3.15で各100回の[再現CI](https://github.com/r20942097-hue/faaff/actions/runs/39324508886)を追加しています。トレースは実行順序に影響するため、失敗が観測されなくても修正完了にはしません。候補20261019.7の未合格記録は維持します。

```sh
python workspace-management/diagnose_next_concurrency.py --iterations 100 --output work/next-concurrency.json
```

## 再現できた失敗点と修正候補

追加した原本CIではWindows/Python3.11の100回中1回、3.14の100回中1回で失敗しました。どちらも `io.py:80` の `os.open(lock_path, O_CREAT | O_EXCL | O_WRONLY)` が `.write.lock` に対してPermissionErrorを返しています。失敗後はチェックサムと残る3件の能力・5件のスナップショットが有効で、ロックは解放されていました。Windows3.15とLinuxの3環境では各100回で失敗を観測しませんでした。[全6環境の記録](next-concurrency-observation-20261020.json)に保存しています。

winerrorは例外に含まれずnullでした。Windows内部の削除待ちや共有状態までは確定していませんが、失敗操作をロックの排他的作成まで特定できました。

`next-concurrency-candidate/ucs_control_plane/io.py` に別候補を作りました。Windowsのロック作成時のPermissionErrorだけを従来の2秒期限内で再試行し、期限を超える権限拒否は元の例外で返します。書込み・置換・削除の権限エラーは再試行しません。またロック作成後のwrite/fsync失敗でもファイルとfdを解放します。原本ZIPは変更せず、隔離コピーのI/Oファイルと派生一覧・チェックサムのみ更新します。原本の古いPASS記録を派生版へ引き継ぎません。

派生ソースはWindows/Linux×Python3.11・3.14・3.15の全6環境で、原本由来の回帰46件と各300回の並行検査に成功しました。OS・権限によりjunction検査のスキップがある環境があります。恒久権限拒否、Windows一過性拒否、POSIX権限拒否、準備失敗、既存ロックのタイムアウト、本体例外の6テストも全環境で成功しています。[CI](https://github.com/r20942097-hue/faaff/actions/runs/39324989910)・[環境別の完全な結果](next-lock-candidate-verification-20261020.json)を保存しました。

Windows3.11・3.14では、並行検査中に再び発生したロック作成の権限エラーが再試行で回復しました。全体1800回で失敗・能力欠落・状態不整合を観測していません。トレースは実行順序に影響するため、すべての競合がない保証ではありません。これは実キットへの統合前のソース候補検証です。管理回帰はローカル319件が314成功・5件スキップでした。

## 当初の情報不足

試験は4スレッドから同じRegistryStoreへ能力を登録し、例外がないことと4件の保存を確認します。原本の `ucs_control_plane/io.py` には、排他ロックファイルの作成・削除、fsync、os.replaceによる置換があります。ロック取得はFileExistsErrorを待ちますが、PermissionErrorの扱いはありません。

当初の試験は例外オブジェクトだけを収集し、発生操作・ファイル名・winerror・スレッド側のトレースを報告していませんでした。追加観測によってロック取得での発生を確認しました。

## 次の作業と完了条件

1. 原本の検証と再ビルド比較を保持するアダプターへ派生I/Oを接続する。原本と派生版の検証結果・ハッシュを分け、原本の不安定なテストを成功と偽って表示しない。
2. 新バージョンの更新ZIP・導入キットを作る。既存.1～.7を上書きせず、厳密なファイル集合、内容manifest、由来、二重ビルド一致、SHA256を検証する。
3. 新規venvでsetup・doctor・all・suite-audit・portfolio・checkをWindows/Linux×Python3.11・3.14・3.15の全6環境で検証する。恒久権限拒否、部分書込み、中断、ロック解放の結果も保持する。
4. 実キットの全6環境が成功してから、新バージョンの導入合格を記録する。.7の当時の未合格は履歴として残す。

残件の解決前は候補20261019.7を導入推奨にしません。成果物の公開サイズ・SHA256一致と機能検証の合格は区別します。
