# Development environment v8: source-independent OPFS failure matrix

**Scope and safety.** Tests use deterministic synthetic byte arrays. Neither a specific RPLAY ZIP nor product sources, external URLs, recorded media, cookies, accounts or downloads are needed. Results from browser fixtures never assert product release safety (`release_readiness=NO_GO`).

## Added verification
- A/B byte arrays, manifest generation, active object and SHA-256 are checked on *actual browser OPFS* in Firefox and Chromium.
- Six deliberately injected application-level fault stages:
  1. `simulated_quota_before_blob`: JavaScript adapter throws named `QuotaExceededError` before creating B. **This is not native browser quota exhaustion.**
  2. `abort_binary_writer`: abort uncommitted B writer.
  3. `interrupt_after_binary_close`: B is closed but manifest remains A; B is orphaned.
  4. `abort_manifest_writer`: B exists but manifest update aborts.
  5. `interrupt_after_manifest_close`: B has committed; old A becomes an orphan.
  6. `reject_same_id_conflict`: reject a conflicting payload for a committed object ID before writing.
- Browser process is *gracefully closed* and restarted using the same dedicated temporary profile, then verifies the same active generation and SHA-256 for each scenario.
- Orphan B or A is removed when necessary, with the committed active entry retained. The fixture verifies that only the active blob and manifest remain.
- Two *real tabs on the same origin* attempt writes through the Web Locks API under an exclusive lock. Each transaction re-reads the manifest within the lock, so observed generations must be 2 and 3, with generation 3 intact after browser restart.
- Unit tests run on both Ubuntu 24.04 and Windows Server 2025. Browser E2E runs separately under Linux in a Chromium/Firefox matrix.

## Reproduce from working tree
```shell
python -m pip install -r ai/requirements-browser.txt
python -m playwright install --with-deps chromium firefox
python -m unittest ai.test_opfs_fault_matrix -v
python -m ai.opfs_fault_matrix --browser chromium --output chromium-fault-matrix.json
python -m ai.opfs_fault_matrix --browser firefox --output firefox-fault-matrix.json
```

The script writes only sanitized scope-limited JSON, never browser profiles. All profiles and local servers are temporary.

## Not tested / NOT_RUN
- Actual OS process force-kill, machine crash, power failure, **physical** quota exhaustion and quota-induced eviction.
- Sync OPFS handles in workers, physical durability, real cross-tab synchronization in RPLAY, actual product bytes, real HLS/DASH/MP4 recording, media decoding or signed URLs.
- Real Windows Firefox/Chromium product extension E2E.
- Therefore synthetic matrix PASS is not a repair of known P0 Issue #31; production status stays **NO_GO**.

## Recommended next stage
- Add kill/relaunch experiment in *separately disposable* CI profiles while preserving explicit no-guarantee semantics for OS sync.
- Test native quota independently in a controlled browser/profile; do not mistake `StorageManager.estimate()` for an enforced per-test quota.
- Validate Dedicated Worker `FileSystemSyncAccessHandle` with controlled flush/close under both engines where supported.
- Integrate real product code only after source provenance and scoped permissions are verified.

## First-party references
- https://developer.mozilla.org/en-US/docs/Web/API/FileSystemFileHandle/createWritable
- https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API
- https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/estimate
- https://developer.mozilla.org/en-US/docs/Web/API/FileSystemSyncAccessHandle
- https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context
