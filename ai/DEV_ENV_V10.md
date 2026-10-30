# 開発環境 v10：隔離ブラウザーのOSプロセス強制終了・OPFS復旧

日付：2026-10-30。**製品リリース判定：NO_GO。**

## 目的と試験材料

特定のRPLAY版、実際の録画、認証情報、URL、ユーザープロファイルに依存せず、確定済みデータの保存耐性を合成データで調べる。v9の「ブラウザー正常終了」「Chromiumレンダラーのみのクラッシュ」より厳しい条件として、テスト専用ブラウザーのOSプロセスを強制終了する。

## 改善した技術

- Playwright 1.64.1の`launch_persistent_context()`で、システムの既定プロファイルとは異なる一時プロファイルを作る。
- 独立したPython子プロセスを新規セッションで生成し、その子がPlaywrightブラウザーを起動する。
- 合成セグメントAのバイト列と世代1の台帳を書き込み、確定後のSHA-256を確認する。
- 合成セグメントBを書き込むが、世代2の台帳の`createWritable()`を閉じず、更新を未確定に保つ。
- Python子プロセスから準備完了の単一マーカーを受け取り、親側でその子の実際のOS子孫プロセスを`psutil`で特定する。ブラウザー実行ファイルを持つ子孫の存在確認が必須。
- プロセスグループの一致を仮定しない。Playwrightの起動したブラウザーが別グループでも、親子関係とPID生成時刻を追跡できる`psutil.Process`からテスト専用の子孫のみ停止する。
- 停止後に同じ一時プロファイルを再起動し、Aの台帳、実バイト、SHA-256を照合する。孤立したBがあれば回収する。
- 一時HTTPサーバーは親プロセスに維持するため、再起動の前後で`http://127.0.0.1:<port>`のオリジンは一致する。
- PythonやOSの任意の実行ファイルを停止しない。既定のPC環境や利用者のブラウザーは操作しない。

## 実装ファイル

- `ai/opfs_process_kill_fixture.py`：隔離プロセス／実ブラウザー／OPFS実データの検証。
- `ai/test_opfs_process_kill_fixture.py`：8件のfail-closed単体テスト（プロセス所有、SHA256、秘密情報非表示、NO_GO）。
- `ai/requirements-process.txt`：`psutil==7.2.2`を固定。PID再利用による他プロセスへの誤信号を防ぐ実装を使用。
- `.github/workflows/opfs-process-kill.yml`：Ubuntu 24.04のChromium／Firefoxジョブ。機密情報・生のプロファイルはアップロードしない。
- `.github/workflows/environment-readiness.yml`：Windows Server 2025とUbuntu 24.04では、ブラウザー実行を必要としない単体テストのみ追加。

## コマンド

```bash
python -m pip install -r ai/requirements-browser.txt -r ai/requirements-process.txt
python -m playwright install --with-deps chromium firefox
python -m unittest ai.test_opfs_process_kill_fixture -v
python -m ai.opfs_process_kill_fixture --browser chromium --output chromium-oskill.json
python -m ai.opfs_process_kill_fixture --browser firefox --output firefox-oskill.json
```

### 失敗を隠さない判定

子プロセスのOS実行ファイルが確認できない、SIGKILLに失敗した、再起動不能、確定済みAが不一致、未確定Bの扱いが不整合、いずれも`BLOCKED`と非ゼロ終了。生の例外スタックやユーザーデータはアップロードせず、許可リスト内の診断コードだけを記録する。

## 限界と製品の次工程

- `SIGKILL`は実プロセスの強制終了であり、突然の電源断、OSカーネルクラッシュ、物理ストレージの書き込みキャッシュ消失を直接再現しない。
- Firefoxの結果はChromiumと別々に検証し、両者を自動的に同一合格として扱わない。
- 合成FixtureのPASSでは、RPLAY Issue #31の早期セグメント削除問題が修正されたことにはならない。実製品コードの回帰テストと媒体デコード試験はNOT_RUN。
- 作業ブランチとDraft PR #34の変更に限定する。main、既存の安定配布、購読URL、GitHub Releaseは更新しない。

## 一次資料

- [Playwright browserType.launch_persistent_context()](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
- [psutil Process.children と安全なkill](https://psutil.readthedocs.io/en/latest/#psutil.Process.children)
- [psutil PID reuse](https://psutil.io/faq/)
- [MDN OPFS](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system)
- [MDN storage quotas / eviction](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)
