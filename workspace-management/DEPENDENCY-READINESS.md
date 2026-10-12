# Dependency Reviewの確認と残作業

2026-10-12。管理ソースの回帰296件・画面35項目、Linux/Windows × Python 3.11/3.14/3.15の6環境は合格しています。録画等の製品本体の完成判定ではありません。

## 前回のエラーと今回の結果

前回、Dependency Reviewだけを再実行した時点では次のエラーになりました。

> Dependency review is not supported on this repository. Please ensure that Dependency graph is enabled.

[再実行した検査](https://github.com/r20942097-hue/faaff/actions/runs/38156840064)。固定したdependency-review-actionの実装では、APIの403に対してこの案内を出します。管理設定を読み書きできる接続ではないため、設定値を直接確認したという意味ではありません。

今回のソースコミット `75d584993ffaf4b14f121e2f5f68d3f0522775f1` では[Dependency Reviewが合格](https://github.com/r20942097-hue/faaff/actions/runs/38164196557)しました。3種類のrequirements.txtが依存変更として解析され、high以上の脆弱性と拒否対象パッケージは検出されませんでした。固定action・権限・判定条件を緩和していません。API403は今回再現していません。管理設定値や、設定を誰が変更したかを直接確認したという意味ではありません。

ログにはtyping_extensions 4.16.0のライセンスを取得できない旨と、PySocksのOpenSSF Scorecard 2.4（警告閾値3未満）が残っています。前者について[PyPIの4.16.0メタデータ](https://pypi.org/pypi/typing_extensions/4.16.0/json)では `license_expression: PSF-2.0` と `license_files: [LICENSE]` を確認しました。これをGitHub上でのライセンス検出成功とは扱いません。PySocksの低スコアも解消した扱いにせず、Firefox用依存の保守状況と代替可否の次回調査対象にします。今回、依存の版や検査条件は変更していません。

## 同じAPI拒否が再発した場合の操作

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

requirements.txtはGitHubが対応する依存マニフェスト形式です。ZIPの中だけではなく、リポジトリ上でも版と配布ハッシュを確認できます。今回、Dependency Reviewのログで3種類すべての依存解析を確認しました。

導入の正本は引き続きZIP内のロックです。確認用コピーを単独で編集しません。CIは展開した検証済みZIPと3ファイルをバイト単位で照合し、改変・欠落なら依存導入前に停止します。初版では照合用の回帰テスト5件を実行し、今回9件へ拡充しました。元のZIPとSHA256は変更していません。Windowsでも照合できるよう確認用ファイルの改行をLFに固定しています。初版の依存照合・5テスト・共通管理検証はLinux/Windows × Python 3.11/3.14/3.15の6環境で合格しました。[検証実行](https://github.com/r20942097-hue/faaff/actions/runs/38161658501)を参照してください。

## main反映の順序

PR #15のDependency Reviewは今回合格しました。PR #14も失敗したジョブだけを再実行し、[Dependency Reviewの合格](https://github.com/r20942097-hue/faaff/actions/runs/38125486938)を確認しました。PR #15はPR #14のブランチをbaseとするdraftです。mainへの反映を行う段階では、PR #14を先に確認し、PR #15のbaseと差分・CIを再確認してから進めます。日本語表示のs PR #5は別リポジトリでの更新です。

## 参照

- [Dependency graphの有効化](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/enable-dependency-graph)
- [対応する依存マニフェスト](https://docs.github.com/en/code-security/reference/supply-chain-security/dependency-graph-supported-package-ecosystems)
- [固定actionの403処理](https://github.com/actions/dependency-review-action/blob/a1d282b36b6f3519aa1f3fc636f609c47dddb294/src/main.ts#L262)

## 照合結果の見方

`verify_dependencies.py --snapshot 展開先 --json` で、3種類すべてが一致した場合にJSONを表示します。`profile` は用途、`mirror` は公開依存表、`snapshot_source` はZIP内の正本、`bytes` はファイルのサイズ、`sha256` はその内容のハッシュです。通常表示でも用途・サイズ・ハッシュを1行ずつ確認できます。不一致の場合は用途と両方の実測ハッシュをエラーに表示し、合格の一覧を出しません。

| 用途 | サイズ | 確認対象 |
|---|---:|---|
| runtime | 15,237 bytes | 通常の検証依存 |
| build | 628 bytes | PyYAMLビルド依存 |
| extension | 2,968 bytes | Firefox実拡張用依存 |

CIは導入前に照合結果をログと展開先の `dependency-mirror-check.json` に保存します。これはジョブ内の検証記録で、ダウンロード用Actions artifactとして公開する設定ではありません。既存5件に、全ファイルのハッシュ・サイズ・対応先、不一致時の実測ハッシュ、改行差、ディレクトリ誤指定の4件を追加し、ローカルの9件が合格しました。今回の変更でもZIPの内容とSHA256は同じです。

改良後の9テスト・3表の照合・既存管理検証は、Linux/Windows × Python 3.11/3.14/3.15の6環境すべてで合格しました。[今回のCI](https://github.com/r20942097-hue/faaff/actions/runs/38164196425)はソースコミット `75d584993ffaf4b14f121e2f5f68d3f0522775f1` の実行です。ZIP内の回帰296件と、ZIP外の照合9件は別集計です。

## 最新ZIPとの対応

2026-10-12の更新ZIPは `workspace-source-20261012.2.zip` です。導入処理を共通化したためZIPの内容とSHA256を更新しています。本文中の75d584...と6環境CIは前回の依存表照合改良の記録です。今回のZIP、Linux回帰302件、照合9件と6環境CIは [validation.json](validation.json) と [最新改良一覧](TOOL-IMPROVEMENTS.md) を参照してください。導入依存の版と3表の内容は同じです。
