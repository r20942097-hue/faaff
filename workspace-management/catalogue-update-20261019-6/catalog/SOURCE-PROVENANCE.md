# 導入したファイルの取得元と差分

導入済みワークスペースのルートで実行します。基準・更新ZIPは元のキット内の場所を指定します。下記は同梱手順どおりwork/integrated-toolsへ適用した場合です。

```sh
python tools/source_provenance.py --root . --baseline ../../workspace-source-20261011.zip --baseline-sha256 BASE_SHA --update ../../catalogue-update-20261019.6.zip --update-sha256 UPDATE_SHA256 --output work/provenance-20261019
```

BASE_SHAはe2ab70a46e41a2f193f8738b0917a9966c3850056f68d79e0f7b48b3e59208d9です。UPDATE_SHA256はキット内KIT-README.mdに記載した更新ZIPのSHA256を使います。更新ZIPは自己ハッシュを内部へ埋め込まず、外部値を指定します。

生成されたwork/provenance-20261019/index.htmlを開きます。基準一致・更新版一致・想定から変更・現在一覧にない・現在のみ存在を絞り込めます。基準・想定・現在のSHA256、各設定に記録されたGitHub参照先、固定基準と指定更新の履歴を確認できます。

GitHubへ通信・取得する機能ではなく、参照URLとの実内容一致や真正性は保証しません。検査対象のPythonコードはimport・実行しません。現在一覧にない状態は欠落・symlink・設定による選択外を含みます。現在の一覧と設定を2回確認し、変化を検出したら停止しますが、同時点のファイルシステムスナップショットまでは保証しません。既存出力への上書きは拒否します。
