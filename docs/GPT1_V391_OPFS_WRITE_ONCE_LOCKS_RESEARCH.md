# GPT1 v3.9.1 | RPLAY OPFS write-once and cross-instance contention

**2026-10-30 JST — CANDIDATE / NO_GO, public issue #31 remains OPEN.** 
Only a developer-side offline patch and tests were produced; no production addon files, credentialed URLs or source ZIP were committed to the public repository.

## Primary evidence

The actual RPLAY v2.67 `segment_store.js` bytes from three locations in the full multisite ZIP are identical: SHA256 `3f1a00b89207f8cb783f59152db6ff230c300569f79b1e1eb691353b70218b9e` (Chromium, Firefox and source folders). The single Chromium ZIP SHA256 is `7bfdc92cc8c5cee421548f5a86a03b4dd4bdd097c088d09c58b4becf6c2cce35`; the full multisite bundle ZIP SHA256 is **different**, `e991a98c41a4ed752132fbab523ba2ee68bfa06f6b6babfd5406d8ecbbe64add`. These are different archives with a matching module; file hashes alone do not establish origin or reproducible build provenance.

- Original isolated product-module OPFS mock contract: **74/74** tests executed successfully; included a known-bad precommit eviction/data loss reproducer.
- Isolated localhost HTTP Range + HLS function test: **18/18**.
- Python ZIP/sandbox gate mock tests: **31/31**.
- v3.9.1 isolated **candidate** (v3.8.1 eviction-after-write plus write-once ID guard, cleanup and same-instance put queue) and optional injected Web Locks adapter: **92/92** checks executed successfully.
- The v3.8.1 candidate **failed as expected** under a new test requiring an existing segment ID to reject replacement. The new v3.9.1 candidate passed.
- All tests are offline, Node 22.16.0, synthetic bytes and in-memory OPFS; no browser filesystem, actual streaming/MP4 output, crash/power-loss or Windows hardware acceptance.

## Confirmed unresolved behaviors

1. The existing RPLAY original can delete a valid old segment before a replacement write fails (issue #31).
2. The simple v3.8.1 patch prevents that specific precommit deletion, but can still overwrite an existing ID or leave an incomplete pair after failure.
3. v3.9.1 has an explicit write-once-ID guard, new-file cleanup and same-store `put` queue. **Not production-ready**: the guard refuses orphan repair, and callers will need an intentional migration/recovery policy.
4. **Cross-instance race reproduced:** two independently created store objects sharing a synthetic namespace, `maxBytes=4`, each writing three bytes concurrently, successfully store six bytes in total. A per-instance queue is insufficient.
5. An optional shared mock Web Locks adapter brought the cross-instance total to three bytes in this fixture, but availability, crash releasing locks, MV3/Firefox behavior and integration into all entry points are unverified. The adapter is NOT integrated into production.
6. A failure deleting an eviction victim after new data commits can leave both old and new segments and a temporary **overbudget** condition. This requires a recoverable journal rather than just moving the deletion call after writes.
7. OPFS write/close alone is not a fully verified durable multi-file transaction. Explicit manifest/ledger commit, replayable recovery and corruption verification are still required.

## Acceptance gates before changing real product

- Quota-pressure strategy that does not destroy committed data if new writes fail; journal, staged-byte verification and interrupted-deletion replay.
- One origin-scoped lock protocol for **all** store instances and mutating operations, with fail-closed behavior when lock API is unavailable. Verify Web Locks on real Chromium/Firefox extension backgrounds.
- Real OPFS tests in disposable profiles: same-ID rewrite, orphan/crash cleanup, concurrent Worker instances, `QuotaExceededError`, partial failure, browser restart, power-loss surrogate.
- HLS/DASH pipeline and MP4 file decode, long recording and Windows acceptance tested separately.
- Keep Issue #31 OPEN, `PUBLICATION_HOLD` and `CANDIDATE_NO_GO`. Do not merge/publicly release patch candidates.

Sources: [MDN OPFS](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system), [MDN Web Locks](https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API), [W3C Web Locks](https://www.w3.org/TR/web-locks/), [Chrome MV3 worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle).
