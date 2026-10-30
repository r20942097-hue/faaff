# Development environment v6 — independent, real-browser OPFS snapshot test

**User-directed fixture choice:** This test uses only synthetic bytes and a temporary loopback page; it does **not** require a particular RPLAY version, an exported ZIP, or any actual product source. This complements, rather than duplicates, the journaled product-derived prototype in Draft PR #25.

## Scope and acceptance
- Playwright 1.64.1; `chromium` and `firefox` run as independent matrix jobs on `ubuntu-24.04`.
- Secure loopback origin `http://127.0.0.1:<ephemeral_port>/fixture`, disposable browser context, deterministic bytes `[7,31,151,2,0,255]`.
- Real browser `navigator.storage.getDirectory()`, OPFS file write and `close()`.
- A second, deliberately uncommitted write is `abort()`ed; previously committed bytes and SHA256 must remain unchanged.
- Page reload verifies persistence across document lifecycle.
- Two pages on the same origin request an exclusive Web Lock; the second must not enter until the first releases.
- `BrowserContext.storage_state(opfs=True)` exports browser-managed OPFS; the captured state is restored into a **fresh isolated** browser context, where the bytes must match again.
- The full snapshot may contain user data on real websites. **Never upload the raw state**, cookies or OPFS bytes; uploaded evidence includes only fixture digest, statuses, versionless browser identifier and NOT_RUN markers. The full storage-state object stays in process memory only.
- The fixture does not test physical quota, actual browser/process crash, browser restart profile, long-term eviction, multi-origin isolation, encryption, the product's segment journal, or real recording. None of these are GO.

## Execution
```bash
python -m pip install -r ai/requirements-browser.txt
python -m playwright install --with-deps chromium firefox
python -m unittest ai.test_opfs_snapshot_fixture -v
python -m ai.opfs_snapshot_fixture --browser chromium --output opfs-snapshot-chromium.json
python -m ai.opfs_snapshot_fixture --browser firefox --output opfs-snapshot-firefox.json
```

## Evidence policy
- `PASS_DISPOSABLE_BROWSER_OPFS` requires every browser-level step. Failure must exit nonzero and be visible in GitHub Actions.
- `real_product_e2e=NOT_RUN`, `real_quota=NOT_RUN`, `real_power_loss=NOT_RUN`, `release_readiness=NO_GO` remain constant.
- Keep this test separate from real Firefox/Chromium extension source integration and source provenance.
- On an unsupported browser, report BLOCKED, never a synthetic PASS.

## Official references
- Playwright Python v1.63+ OPFS storage state: https://playwright.dev/python/docs/api/class-browsercontext#browser-context-storage-state
- MDN OPFS: https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system
- MDN write/close staging: https://developer.mozilla.org/en-US/docs/Web/API/FileSystemFileHandle/createWritable
- MDN Web Locks: https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API
