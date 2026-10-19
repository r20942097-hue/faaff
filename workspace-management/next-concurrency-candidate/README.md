# Windowsロック取得の派生候補

原本の並行書込み失敗を再現し、ロックの排他的作成に限定した修正を作成しました。[原本の観測記録](../next-concurrency-observation-20261020.json)、[由来とハッシュ](PROVENANCE.json)、[検証・残件](../CONTROL-PLANE-NEXT-FOLLOWUP.md)を参照してください。

Windowsでロック作成がPermissionErrorになった場合、従来の2秒期限内で再試行します。権限拒否が続く場合は元の例外を返します。書込み・ファイル置換・削除のエラーを再試行しません。作成後のwrite/fsync失敗でもロックとfdを解放します。

リポジトリのルートで実行します。原本ZIPを検証した一時コピーだけを変更し、既存の配布ZIPや作業データを上書きしません。派生コピーのファイル一覧・チェックサムも更新し、原本の過去のPASS表示は引き継ぎません。

```sh
python -m unittest discover -s workspace-management -p test_next_lock_candidate.py
python workspace-management/diagnose_next_concurrency.py --iterations 300 --regressions --candidate-io workspace-management/next-concurrency-candidate/ucs_control_plane/io.py --candidate-sha256 26da2b8b4f7a480c2b3e132b4cf36e7f09592e49ec7af8946ea491925313231e --output work/next-lock-candidate.json
```

このフォルダは管理コンポーネントのソース候補です。実キット20261019.7への修正適用、新しいキットの導入検証、未取得9製品の受入は別の作業です。既存キットの未合格記録は維持します。
