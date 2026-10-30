# Integration queue (observed 2026-10-25)

1. [IN_THIS_PR] Add AI navigation, pinned `s/main` import and scoped offline CI without changing subscription URLs or existing `browser_filter_lists/`.
2. [PENDING] Review stacked graph and PR base refs: #1 -> #2 -> #8; #12 -> #13; #14 (merged) -> #15 -> #16 (both closed 2026-10-28, contained ZIPs). Review and merge only with evidence and preserved dependencies.
3. [PENDING] Decide publication ownership. Keep `s` as distributor until two-repository publishing is validated or a deliberately approved cutover exists.
4. [PENDING] Reconcile `filter-profiles.json` mirror outputs against `faaff/browser_filter_lists/` policy and regression tests; copied source is not proof of generated-output parity.
5. [BLOCKED_BY_SOURCE] Closed PR #16 listed missing product runtimes. Verify real source, ZIP provenance, immutable SHA-256 and product-specific E2E before claiming integrated runtime readiness.
6. [PENDING] Track source/build/CI/real-device/release status separately for each actual imported product. Add entries only with verifiable source locations.
7. [PENDING] Open draft PR stack (observed 2026-10-30): #21, #22, #23, #24 target `main`; #25 targets `proposal/gpt1-workspace-preflight-20261029` (the #23 branch). Retarget #25 to `main` after #23 merges. Merge order is the owner's decision; a dependency-based candidate is small independent PRs (#21, #24, #22) first, then #23, then #25.
8. [PENDING] Secondary engine pin refresh: `s` pins `@ghostery/adblocker` 2.20.1 (`verification/ghostery/package.json`, `package-lock.json`, `engine-lock.json`); npm `latest` is 2.20.3 (published 2026-10-28) with the same external dependencies. A parse/match smoke test on both versions in an isolated install behaved identically; the full `check_engine.mjs` run is NOT_RUN. Update in `s` first, then re-import here as described in `ai/README.md`.
9. [UNVERIFIED] The uBlock engine commit pinned in `s` `verification/engine-lock.json` was not compared with upstream (no access in the observing session). Commit-SHA pins are not covered by Dependabot, so freshness needs a manual check.
10. [NEEDS_HUMAN] `SECURITY.md` names no private reporting channel and describes Watcher runtime behavior that is not on `main`. Decide the reporting channel and whether to keep or reword the Watcher text. Other owner decisions (LICENSE, stale Actions workflows, Watcher source location) are tracked in `ai/PROJECT_STATE.json` `open_items`.

No production migration, ZIP overwrite, PR merge, repository deletion or subscription change is performed by this staging PR.
