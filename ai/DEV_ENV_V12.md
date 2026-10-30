# Development environment v12 — post-commit process SIGKILL OPFS recovery

Date: 2026-10-30. Draft PR #34; research/CI fixture only.

## Distinct fault boundary

v10 terminated browser-owned OS processes after staging a candidate blob B but before closing its manifest. v12 tests the complementary interruption: B's blob and manifest writers are closed and read back, the previous generation A deliberately remains, and the entire browser process tree is terminated using SIGKILL before cleanup. The next browser process reopens the *same disposable profile*, proves B's manifest + file SHA-256 + exact bytes, deletes old A, repeats cleanup (must remove nothing), and reopens the profile once more to prove B survived.

Engines: Chromium and Firefox via Playwright. All media bytes are synthetic, origin is localhost, profile is temporary. A real browser process in the owned subprocess ancestry is required. No real RPLAY product module, stream, login, credential, existing browser profile or persistent artifact is used. CI uploads only sanitized JSON evidence; browser profiles and raw OPFS are never uploaded. Each failure exits nonzero. The shell session must be Linux; never SIGKILL processes outside a disposable child tree. Tests in Windows/Ubuntu readiness are pure-unit only.

## Meaning and limits

- If both engines PASS, the observed configuration with close() and an OS process SIGKILL preserves the newly committed generation B and permits idempotent cleanup of old generation A.
- This is NOT a physical power failure, kernel crash, physical disk-cache loss, filesystem corruption, product code test or native quota exhaustion. It does NOT establish power-loss durability.
- The simple synthetic cleanup is deliberately not an implementation of the actual RPLAY segment store. Issue #31 (pre-commit eviction data loss) remains OPEN and product release NO_GO.
- PR remains Draft, unmerged; neither main nor public filter subscription URLs nor releases may be changed by this test.

## Run

python -m unittest ai.test_opfs_postcommit_kill_fixture -v
python -m ai.opfs_postcommit_kill_fixture --browser chromium --output postcommit-chromium.json
python -m ai.opfs_postcommit_kill_fixture --browser firefox --output postcommit-firefox.json

Requirements: ai/requirements-browser.txt, ai/requirements-process.txt, Playwright-installed Chromium/Firefox, Linux.

References:
- https://developer.mozilla.org/en-US/docs/Web/API/FileSystemFileHandle/createWritable
- https://developer.mozilla.org/en-US/docs/Web/API/FileSystemSyncAccessHandle/flush
- https://playwright.dev/python/docs/api/class-browsertype
