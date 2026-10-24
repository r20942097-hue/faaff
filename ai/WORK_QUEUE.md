# Integration queue (observed 2026-10-25)

1. [IN_THIS_PR] Add AI navigation, pinned `s/main` import and scoped offline CI without changing subscription URLs or existing `browser_filter_lists/`.
2. [PENDING] Review stacked graph and PR base refs: #1 -> #2 -> #8; #12 -> #13; #14 -> #15 -> #16. Review and merge only with evidence and preserved dependencies.
3. [PENDING] Decide publication ownership. Keep `s` as distributor until two-repository publishing is validated or a deliberately approved cutover exists.
4. [PENDING] Reconcile `filter-profiles.json` mirror outputs against `faaff/browser_filter_lists/` policy and regression tests; copied source is not proof of generated-output parity.
5. [BLOCKED_BY_SOURCE] PR #16 lists missing product runtimes. Verify real source, ZIP provenance, immutable SHA-256 and product-specific E2E before claiming integrated runtime readiness.
6. [PENDING] Track source/build/CI/real-device/release status separately for each actual imported product. Add entries only with verifiable source locations.

No production migration, ZIP overwrite, PR merge, repository deletion or subscription change is performed by this staging PR.
