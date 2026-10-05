# Production Management Pack v5

v3を実行監査し、誤昇格・入力検証・保管漏れを修正した管理基盤です。Python 3.11以上、標準ライブラリのみで動作します。今回の動作確認はLinux/Python 3.12.14です。

## 使い方

パックを展開し、そのフォルダで実行してください。

```bash
python tools/validate_registry.py project_registry.json
python tools/validate_release_manifest.py templates/RELEASE_MANIFEST.example.json
python tools/promotion_decision.py templates/RELEASE_MANIFEST.example.json --json
python tools/retention_plan.py project_registry.json
python -m unittest discover -s tests -v
python tools/verify_pack.py .
```

サンプルの正しい判定は `DEV_OR_NO_GO`。実リリースではManifestと同じフォルダに実ソース、成果物、証拠JSON、SBOM、provenanceを配置して `python tools/verify_release.py RELEASE_MANIFEST.json` を実行します。証拠JSONは `schemas/evidence.schema.json` の形式で作成し、Manifestに相対パスとSHA-256を記録します。`passed` はJSON booleanの `true` のみ許可します。

`verify_release` はDEV_OR_NO_GOで終了コード1、構造・入力不正で2、それ以外は0です。CANDIDATE_ELIGIBLEも0になるため、STABLEを必要とする呼び出し元はdecisionを明示確認してください。`promotion_decision` は判定報告用なので、DEV_OR_NO_GOでも終了コード0です。

## 今回確認した範囲

管理コード、異常入力、証拠のハッシュ・同一性、ZIP安全性、台帳からの一覧生成、保持参照、管理パック再現ビルド。製品の実ゲーム・Windows・ブラウザ受入は今回実施していません。v3継承台帳を基準に、WP10 0.38.0の407テストとSuite 0.51.0の366テストを再実行し、YouTube dev70の配布物・検証記録を照合しました。その他の参照は引継ぎ値です。未知の復旧版を推測で登録しません。

## 限界

ローカル証拠は記録内容と対象の一致を検査します。記録が主張するテストの実行や成功、署名者の真正性を自動証明するものではありません。SBOMは1.7識別子・対象・components型、provenanceはin-toto/SLSA識別子・subjectを検査し、公式スキーマ全文の検証や署名検証は行いません。署名付きattestationの検証は別の受入工程です。

実装したJSON Schema検証は同梱スキーマで使用する `type/const/enum/anyOf/required/properties/additionalProperties/minItems/items/minLength/pattern/minimum` に対応します。汎用JSON Schemaエンジンではありません。

ZIP検査上限は展開後512 MiB・10,000エントリです。パストラバーサル、暗号化、シンボリックリンク、重複名、大小文字衝突を拒否します。検査中に他プロセスがファイルを書き換えない隔離ディレクトリで実行してください。

## 版移行

Registry schema 3→4、Manifest schema 1→2。v3形式の曖昧なbooleanフラグは自動移行せず、証拠ファイルが揃った時に新Manifestを作ります。旧版を保持し、v5は別パックとして保存します。旧成果物のarchive/削除、製品昇格、公開、mergeはこのコードの操作範囲に含みません。


## v5製品監査

`python tools/audit_product_archives.py /path/to/saved-zips` で同じフォルダのSHA256一覧とZIPをread-only照合します。6 ZIP / 997内部ハッシュ確認結果、WP10同梱旧記録との差異はPORTFOLIO_AUDIT.mdとevidence/portfolio-audit-2026-10-05を参照してください。管理基盤はPRの更新済み40テスト版を取り込み、監査ツール4テストを加えています。
