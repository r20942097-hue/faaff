# Development environment v7 — source-independent OPFS journal restart gate

Test data is **synthetic bytes**. No actual RPLAY release, product archive, real service, account, or authentication token is required.

## Scope
Playwright 1.64.1 drives both Chromium and Firefox with unique temporary persistent browser profiles and localhost origins. The test:
1. Closes an immutable A blob and its generation-1 manifest.
2. Writes B, **aborts** a generation-2 manifest write to simulate application-level pre-commit interruption.
3. Closes the browser context (graceful browser shutdown), then relaunches the same persistent profile in a new browser process and verifies A is intact and B is uncommitted.
4. Detects and deletes the orphaned B, re-writes B and commits its generation-2 manifest **after** the blob closes.
5. Closes the browser again, relaunches the same profile, and verifies B's SHA256 and bytes.
6. Accesses a different localhost port to assert cross-origin OPFS isolation.
The comparison includes manifest-declared SHA-256, recomputed SHA-256 and original byte arrays, not just file existence.

## CI
- `ai/opfs_restart_fixture.py`: real-browser test runner and JSON-only result.
- `ai/test_opfs_restart_fixture.py`: eight unit tests for journal ordering, data validation, error redaction and NO_GO.
- `.github/workflows/opfs-journal-restart-fixture.yml`: Chromium and Firefox on isolated Ubuntu 24.04 agents; artifacts retained for 14 days.
- `.github/workflows/environment-readiness.yml`: unit tests on Windows Server 2025 and Ubuntu 24.04 (these jobs do not launch browsers).
- Execute `python -m ai.opfs_restart_fixture --browser chromium --output chromium.json` or `--browser firefox`.

## Critical limits
- **Normal shutdown/restart only**, not SIGKILL, browser crash, machine power loss, real quota exhaustion, persistent storage eviction, or filesystem failure.
- The intentionally minimal journal is **reference test code**, not a patch to the RPLAY implementation; no production data is exercised.
- A fixture PASS does not clear known product P0 Issue #31. Actual RPLAY integration, Firefox/Chrome product E2E, HLS/DASH capture, media integrity and rollout remain NOT_RUN / NO_GO.
- Uploaded artifacts include **only** result labels, non-secret test SHA-256 and browser name. The full browser profile and captured OPFS content stay in a temporary directory and are destroyed automatically.
- Keep PR #34 Draft; leave PR #25 research separate; do not merge, release or modify live filter URLs.

## First-party verification references
- https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context
- https://developer.mozilla.org/en-US/docs/Web/API/FileSystemFileHandle/createWritable
- https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system
- https://playwright.dev/python/docs/api/class-browsercontext#browser-context-storage-state
