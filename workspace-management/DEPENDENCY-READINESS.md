# Dependency Reviewの確認と残作業

2026-10-12。管理ソースの回帰296件・画面35項目、Linux/Windows × Python 3.11/3.14/3.15の6環境は合格しています。録画等の製品本体の完成判定ではありません。

## 現在の阻害要因

Dependency Reviewだけを再実行しましたが、再び次のエラーになりました。

> Dependency review is not supported on this repository. Please ensure that Dependency graph is enabled.

[再実行した検査](https://github.com/r20942097-hue/faaff/actions/runs/38156840064)。固定したdependency-review-actionの実装では、APIの403に対してこの案内を出します。管理設定を読み書きできる接続ではないため、設定値を直接確認したという意味ではありません。

## リポジトリ管理者が行う操作

1. [faaffの設定](https://github.com/r20942097-hue/faaff/settings/security_analysis)を開きます。
2. Code security / Advanced SecurityのDependency graphで **Enable** を選びます。既に有効なら、有効状態とポリシー・アクセス制限を確認してください。
3. GitHubによる依存解析を待ち、Dependency Reviewの失敗したジョブだけを再実行します。
4. PR #14とPR #15の結果を確認します。APIアクセスが引き続き拒否される場合は、その新しいログに基づいて切り分けます。

管理者権限が必要です。現在の接続にはGitHubリポジトリの管理設定を変更する操作がありません。新しい秘密トークンをチャットへ貼る必要はありません。

## ZIP内の依存を確認しやすくする変更

| 公開する確認用ファイル | 正本となるZIP内ファイル | 用途 |
|---|---|---|
| dependencies/runtime/requirements.txt | tools/requirements-verification.lock.txt | 通常の検証依存 |
| dependencies/build/requirements.txt | tools/requirements-build.lock.txt | Python 3.15のPyYAMLビルド依存 |
| dependencies/extension/requirements.txt | tools/requirements-extension.lock.txt | LinuxのFirefox実拡張用依存 |

requirements.txtはGitHubが対応する依存マニフェスト形式です。ZIPの中だけではなく、リポジトリ上でも版と配布ハッシュを確認できます。Dependency graphでの解析成功は、設定有効化後に別途確認します。

導入の正本は引き続きZIP内のロックです。確認用コピーを単独で編集しません。CIは展開した検証済みZIPと3ファイルをバイト単位で照合し、改変・欠落なら依存導入前に停止します。照合用の回帰テスト5件も実行します。元のZIPとSHA256は変更していません。

## main反映の順序

Dependency Reviewが合格するまでは公開準備が完了した扱いにしません。PR #15はPR #14のブランチをbaseとするdraftです。mainへの反映を行う段階では、PR #14を先に確認し、PR #15のbaseと差分・CIを再確認してから進めます。日本語表示のs PR #5は別リポジトリでの更新です。

## 参照

- [Dependency graphの有効化](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/enable-dependency-graph)
- [対応する依存マニフェスト](https://docs.github.com/en/code-security/reference/supply-chain-security/dependency-graph-supported-package-ecosystems)
- [固定actionの403処理](https://github.com/actions/dependency-review-action/blob/a1d282b36b6f3519aa1f3fc636f609c47dddb294/src/main.ts#L262)
