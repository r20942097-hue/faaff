# Integration queue (observed 2026-10-30)

> This is a **review queue**, not a live PR register or release ledger. For current branch/PR/CI status, inspect GitHub. Code and tests at the exact ref are authoritative; `ai/PROJECT_STATE.json` records observed state, `ai/HANDOFF.md` records handoff, and `AGENTS.md` holds durable rules. Private ChatGPT memory must not be copied into this public repository or treated as evidence of GitHub state.

**Live review entry points:** [faaff open PRs](https://github.com/r20942097-hue/faaff/pulls?q=is%3Apr+is%3Aopen), [s open PRs](https://github.com/r20942097-hue/s/pulls?q=is%3Apr+is%3Aopen). Before any merge, check exact PR base/head, changed files, CI, dependencies and approvals.


1. [DONE_ON_MAIN] AI navigation, pinned `s/main` import and scoped offline CI exist on `main`. Preserve the existing subscription URLs and `browser_filter_lists/` paths.
2. [HISTORY_ONLY] Earlier stacked graph: #1 -> #2 -> #8; #12 -> #13; #14 (merged) -> #15 -> #16 (both closed unmerged 2026-10-28 because they contained ZIPs). Do not treat closed branches as open merge candidates; the owner retains history/backups.
3. [PENDING_DECISION] `s` remains the live filter distributor. Any two-repository publishing workflow or cutover needs verified equivalence, review and explicit owner approval.
4. [PENDING] Reconcile `filter-profiles.json` mirror outputs against `faaff/browser_filter_lists/` policy and regression tests; copied source is not proof of generated-output parity.
5. [BLOCKED_BY_SOURCE] Closed PR #16 listed missing product runtimes. Verify real source, ZIP provenance, immutable SHA-256 and product-specific E2E before claiming integrated runtime readiness.
6. [PENDING] Track source/build/CI/real-device/release status separately for each actual imported product. Add entries only with verifiable source locations.
7. [PENDING] Open PR review (snapshot 2026-10-30): #21–#30 in `faaff` and #11 in `s` were open at observation. #25 is stacked on #23 (`proposal/gpt1-workspace-preflight-20261029`), not `main`; reassess base after #23. #27 and #29 both edit `ai/WORK_QUEUE.md`; reconcile after either merge. Recheck live PR state; never infer safe merge order from this snapshot.
8. [PENDING] Secondary engine pin refresh (prior investigation, 2026-10-30): `s` pinned `@ghostery/adblocker` 2.20.1 (`verification/ghostery/package.json`, `package-lock.json`, `engine-lock.json`); npm `latest` was reported as 2.20.3 (published 2026-10-28), with the same external dependencies. A parse/match smoke test on both versions in an isolated install behaved identically; the full `check_engine.mjs` run is NOT_RUN. Update in `s` first, then re-import here as described in `ai/README.md`.
9. [UNVERIFIED] The uBlock engine commit pinned in `s` `verification/engine-lock.json` was not compared with upstream (no access in the observing session). Commit-SHA pins are not covered by Dependabot, so freshness needs a manual check.
10. [NEEDS_HUMAN] `SECURITY.md` names no private reporting channel and describes Watcher runtime behavior that is not on `main`. Decide the reporting channel and whether to keep or reword the Watcher text. Other owner decisions (LICENSE, stale Actions workflows, Watcher source location) are tracked in `ai/PROJECT_STATE.json` `open_items`.

No production migration, ZIP overwrite, PR merge, repository deletion or subscription change is performed by this staging PR.
