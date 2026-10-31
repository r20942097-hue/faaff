# 開発環境 v9 — Dedicated Worker 同期OPFS・レンダラークラッシュ

2026-10-30。テスト用の材料は実製品の特定バージョンに限定しない。今回は決定的な合成データ、閉じた一時ブラウザープロファイル、ローカルHTTPページを使う。

## 今回の実装

### Chromium / Firefox 共通

- `ai/opfs_worker_sync_fixture.py`: HTMLから同一オリジンのDedicated Workerを起動し、`createSyncAccessHandle()`、`truncate()`、`write()`、`flush()`、`read()`、`close()`を実際のOPFSに対して実行する。
- 取得した生バイトとSHA-256を照合し、別Workerが同じファイルの排他ハンドルを同時に取得できないこと、解放後には取得できることを検証する。
- 一時プロファイルのブラウザーを正常に閉じ、同じプロファイルを新しいブラウザープロセスで再開して内容を再検査する。
- `ai/test_opfs_worker_sync_fixture.py`: 9件の回帰テスト。
- `.github/workflows/opfs-worker-sync-fixture.yml`: Ubuntu 24.04、Playwright固定版、Chromium / Firefoxマトリクス。
- [実行例 — Chromium / Firefoxとも成功](https://github.com/r20942097-hue/faaff/actions/runs/41020020647)。

### Chromiumレンダラープロセスの異常終了

- `ai/chromium_renderer_crash_fixture.py`: 事前に確定したAと未確定のBの台帳を用意。Chromiumの内部クラッシュ用ナビゲーションを使ってレンダラーを実際に異常終了させる。
- クラッシュの検出を必須とし、ブラウザーを再起動してAのバイトとSHA-256、Bの孤立状態と回収を検証する。単なるページ再読み込みやJavaScript例外をクラッシュとは数えない。
- `ai/test_chromium_renderer_crash_fixture.py`: 7件の回帰テスト。
- `.github/workflows/chromium-renderer-crash.yml`: 一時Chromium専用ジョブ。
- [判定条件と実行方法を修正した後の成功実行](https://github.com/r20942097-hue/faaff/actions/runs/41020522489)。

## 再現手順

```shell
python -m pip install -r ai/requirements-browser.txt
python -m playwright install --with-deps chromium firefox
python -m unittest ai.test_opfs_worker_sync_fixture ai.test_chromium_renderer_crash_fixture -v
python -m ai.opfs_worker_sync_fixture --browser chromium --output worker-chromium.json
python -m ai.opfs_worker_sync_fixture --browser firefox --output worker-firefox.json
python -m ai.chromium_renderer_crash_fixture --output renderer-crash.json
```

## 未検証の領域

- 実製品のRPLAY / StreamHarborソース、認証サイト、メディア録画、MP4デコード。
- Windows上での実ブラウザー拡張のE2E（WindowsのPython単体テストとは区別）。
- ブラウザー本体やOS全体の強制終了、停電、電源断、物理ディスクの不具合。
- Worker同期ハンドルのflushは永続化操作だが、いかなる電源断でも安全という保証にはならない。
- 既知のRPLAY OPFS削除問題（Issue #31）は**製品側未修正**。`NO_GO`を維持する。

## 検証方法と境界

- 実ブラウザー検証が失敗した場合はCIが失敗する。実行不能もPASSにはしない。
- 外部サービス、認証情報、ユーザーデータ、プロファイル、OPFSの生データは成果物としてアップロードしない。
- エラー報告は型名だけを保存し、絶対パス・例外の詳細・署名付きURLは除外する。
- GitHub PR #34はDraftのまま、PR #25は独立した研究成果として保全。main、配布版、公開購読URLには変更を加えない。

## 一次資料

- [MDN: FileSystemSyncAccessHandle](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemSyncAccessHandle)
- [MDN: flush()](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemSyncAccessHandle/flush)
- [MDN: createSyncAccessHandle()](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemFileHandle/createSyncAccessHandle)
- [Chrome DevTools Protocol Page.crash（参考）](https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-crash)
- [Playwright Python page crash event](https://playwright.dev/python/docs/api/class-page#page-event-crash)
