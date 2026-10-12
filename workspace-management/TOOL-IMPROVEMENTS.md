# ツールの改良案と開発状況

2026-10-12。共通15機能の管理ツールを継続改良しています。

| 対象 | 改良・調査結果 | 検証・残課題 |
|---|---|---|
| 依存導入と通常実行 | UTF-8・時間制限・終了コード・部分ログを同じ子プロセス処理へ統合 | 追加6件が合格。起動失敗・中断時も残りを停止 |
| 導入状況の保存 | 処理の起動前にコマンドと未完了状態を記録し、終了後に結果を原子的に保存 | 新規Python 3.15環境で実際の導入・pip check・版照合が合格 |
| 配布と一覧 | 最新ソースZIPは192ソース、515,953バイト。Linux回帰302件 | 二重ビルド一致、展開前のパス・CRC・全ハッシュ、新規環境で管理検証。6環境CIはvalidation.jsonに記録 |
| 依存表3種類 | 正本ZIPとの完全バイト一致、用途・サイズ・SHA256の表示とJSON記録 | ZIP外の照合9件が合格。302件には加算しない |
| PySocksの保守評価 | Selenium 4.51.0→urllib3[socks] 2.8.0→PySocksの間接依存と確認。最新PyPI版1.7.1は2019-09-20公開 | Scorecard 2.4の警告は残る。単独削除や別パッケージへの置換では要求を満たせないため上流・代替構成の調査を継続 |
| typing_extensions | 4.16.0のPyPIメタデータはPSF-2.0とLICENSEを宣言 | GitHubのライセンス未検出は解消した扱いにしない |
| 録画・AI・Windows製品 | 本体未取得のため取得元・版・ハッシュと能力契約の接続が次の段階 | 管理コードのCIを製品の完成や実機E2Eとして扱わない |

## 導入結果の見方

ZIPを新しいフォルダへ展開し、新規仮想環境のPythonで `tools/manage.py setup` を実行します。結果は `catalog/results/python-setup.json` に保存します。`status` が全体の結果、`checks` が実行順の記録です。各行の `argv` で対象、`output` で原因、`exit_code` で終了理由を確認します。

| 表示・終了コード | 意味 |
|---|---|
| running / exit_codeがnull | 起動前・実行中・終了未確認。合格として扱わない |
| passed / 0 | 処理が完了して合格 |
| failed / 124 | 時間切れ。保存した標準出力・標準エラーの部分ログを確認 |
| failed / 127 | 起動失敗。実際の例外型とメッセージを確認 |
| interrupted / 130 | ユーザー中断。実行済み結果を保持し、残りを停止 |
| failed / その他 | 対象コマンドが返した終了コードと出力を確認 |

全子孫プロセスの停止や、中断した処理の部分出力保存まで保証するものではありません。元の管理・監査73ファイルは保持し、共通処理はアダプター・管理側に実装しています。今回の一覧UI実装は変えておらず、35項目は既存の画面検証記録です。

## 次の改善の条件

PySocksの代替を採用する場合は、Seleniumとurllib3の要求を満たす構成を決め、固定ハッシュ・pip check・Firefox実拡張の検証をそろえます。公開が古いことだけで脆弱性があるとは判断しません。既存依存の版と検査条件を維持しています。製品本体を取得した場合は、起動・切断・復旧・中断後の再開を実機で確認する段階へ進めます。

[依存照合とDependency Reviewの記録](DEPENDENCY-READINESS.md)と[最新ZIP検証記録](validation.json)も参照してください。mainは未反映です。

調査根拠：[Selenium](https://pypi.org/pypi/selenium/4.51.0/json)、[urllib3](https://pypi.org/pypi/urllib3/2.8.0/json)、[PySocks](https://pypi.org/pypi/PySocks/json)、[typing_extensions](https://pypi.org/pypi/typing_extensions/4.16.0/json)、[Python TimeoutExpired](https://docs.python.org/3.15/library/subprocess.html#subprocess.TimeoutExpired)。
