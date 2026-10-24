# ファイル別の取得元参照の実測

5ファイルについて、固定GitHub参照先のバイトを8件取得し、現在のSHA256と比較しました。検査対象のコードは実行していません。リポジトリ全体や未取得9製品の取得元を証明するものではありません。

| ファイル | 現在の設定にある参照先 | 更新元候補との一致 |
|---|---|---|
| faaff/browser_filter_lists/CHANGELOG.md | [基準版の内容で、現在とは異なる](https://raw.githubusercontent.com/r20942097-hue/faaff/c00d72829bdb772ba4db18cded78c1838ec0f254/browser_filter_lists/CHANGELOG.md) | [7dc49b3の固定参照で一致](https://raw.githubusercontent.com/r20942097-hue/faaff/7dc49b37d98c694d000c0154d269dc0304cb8581/browser_filter_lists/CHANGELOG.md) |
| faaff/browser_filter_lists/scripts/test_validator.py | [基準版の内容で、現在とは異なる](https://raw.githubusercontent.com/r20942097-hue/faaff/c00d72829bdb772ba4db18cded78c1838ec0f254/browser_filter_lists/scripts/test_validator.py) | [7dc49b3の固定参照で一致](https://raw.githubusercontent.com/r20942097-hue/faaff/7dc49b37d98c694d000c0154d269dc0304cb8581/browser_filter_lists/scripts/test_validator.py) |
| faaff/browser_filter_lists/scripts/validate_filters.py | [基準版の内容で、現在とは異なる](https://raw.githubusercontent.com/r20942097-hue/faaff/c00d72829bdb772ba4db18cded78c1838ec0f254/browser_filter_lists/scripts/validate_filters.py) | [7dc49b3の固定参照で一致](https://raw.githubusercontent.com/r20942097-hue/faaff/7dc49b37d98c694d000c0154d269dc0304cb8581/browser_filter_lists/scripts/validate_filters.py) |
| s/scripts/generate_lists.py | [現在の内容と一致](https://raw.githubusercontent.com/r20942097-hue/s/93e39a8b351b6b1519b56d2a8d36b093735a4281/scripts/generate_lists.py) | 同じ固定参照で一致 |
| s/tests/test_generation.py | [現在の内容と一致](https://raw.githubusercontent.com/r20942097-hue/s/93e39a8b351b6b1519b56d2a8d36b093735a4281/tests/test_generation.py) | 同じ固定参照で一致 |

sの生成処理とテストは設定済みの93e39a8と一致しました。faaffの変更した3ファイルは、取得時点のc00d728参照と異なり、更新元7dc49b3の固定参照と一致しました。現在の診断が「設定の参照先は現在内容の証明ではない」と明示する理由を、実際のバイトで確認できています。

## 次の改良

基準ソースの固定参照を保持したまま、ファイルごとの更新元参照と期待SHA256を別に記録する案です。faaff全体の参照を一括で新しいコミットへ変更せず、取得時点と変更ファイルの由来を区別します。

完了条件は、変更3ファイルの基準・更新元・現在を分けて表示し、明示的な通信検証で一致・不一致・取得失敗を区別できることです。未取得・未検証の参照を合格にしません。ネットワーク無効時は静的な観測を維持し、取得失敗で前回合格を残さない設計にします。

今回の候補20261019.6と過去のZIPは変更していません。次に配布が必要になった時点で、新しい候補として実装・検証します。[全ハッシュと固定URL](source-reference-observation-20261019.json)を保存しています。
