# Integration work queue — 2026-10-30 observed snapshot

This is an execution queue, **not** a release registry. Re-read actual Git branches, PR heads, CI and source hashes before acting. `ai/PROJECT_STATE.json` remains the machine-readable baseline, `ai/HANDOFF.md` is the session handoff, `AGENTS.md` controls permissions. All PR links below are **proposals**, not merged features on `main`.

## Now — unblock Codex without adding tools

1. **[NEEDS_HUMAN / CLOUD_UNVERIFIED]** In the intended ChatGPT workspace, create or select a Codex Cloud environment containing `r20942097-hue/faaff`, prepare/test and publish it; run the read-only task in [CODEX_SETUP.md](CODEX_SETUP.md). A successful ChatGPT GitHub connector call or GitHub Actions run does **not** verify this.
2. **[PENDING / OPTIONAL]** If write capability needs confirmation after the read test, prove a proposal-branch-only push and a **Draft PR** from the actual Codex task. Avoid gratuitous test commits when a real change can serve as the proof. Never push/merge to `main` without the owner gate.
3. **[BLOCKED_BY_SOURCE]** Validate complete authoritative source/version/hash and safe test fixtures for RPLAY and the three browser add-ons. Source candidate observations live in Draft PR [#39](https://github.com/r20942097-hue/faaff/pull/39), **not** in `main`. Do not select a newer release from uninspected archives or claim real Firefox/Windows/HLS/DASH E2E from static ZIP integrity.
4. **[PENDING / PRODUCT]** Once source is verified and reviewed, reuse existing product-appropriate fixtures and browser harness proposals; keep static/synthetic/real-browser/real-site/real-device gates distinct. Native Windows Firefox, real YouTube and real streaming-site behavior remain **NOT_RUN** unless independently observed.

## Reuse, do not duplicate

- **Main-present:** Source synchronization guard, CodeQL, Dependency Review, Dependabot, AI hub/pinned filter source validator, conservative filter-list checks. Main is an **engineering/bootstrap** tree and lacks complete RPLAY/three-addon runtimes. A CI result with a skipped product test is **not** product PASS.
- **Open Draft PRs as of this snapshot:** [#35](https://github.com/r20942097-hue/faaff/pull/35) agent-tool isolated checks; [#36](https://github.com/r20942097-hue/faaff/pull/36) workflow security; [#37](https://github.com/r20942097-hue/faaff/pull/37) MCP synthetic harness; [#38](https://github.com/r20942097-hue/faaff/pull/38) Playwright/Mozilla synthetic browser harness; [#39](https://github.com/r20942097-hue/faaff/pull/39) tool/source inventory; [#40](https://github.com/r20942097-hue/faaff/pull/40) Codex setup and this queue. Their status must be refreshed at execution time.
- **Acceptance order:** source provenance → scoped dependency/install validation → targeted static/synthetic checks → actual extension/site/device testing → explicit approval → release. Do not repeatedly install a new generic agent or CI scanner to compensate for missing product source.
- **Boundaries:** `faaff` is the engineering hub; `r20942097-hue/s` owns live filter subscriptions. Keep pinned import and published URLs stable. No main push, automatic merge, ZIP/binary upload to the public repo, publication, or irreversible deletion under this staging task.

## Parallel work not blocked by Codex authentication

5. **[PENDING / FILTER]** Keep `s` the distributor unless an explicitly approved migration passes parity tests. Reconcile `filter-profiles.json` output and the existing `faaff/browser_filter_lists/` policy before changing any generated path or subscription URL.
6. **[PENDING / STATE]** On the next authenticated development task, report exact repo/branch/HEAD, changed paths, test commands/results and observed blockers. Update `ai/PROJECT_STATE.json` and `ai/HANDOFF.md` *in the same reviewed PR* if the authoritative state materially changes. Do not create an additional project-state copy.

## Preserved earlier context (2026-10-25 to 2026-10-28)

- Initial AI index and pinned `s` import were integrated; the old `[IN_THIS_PR]` record is historical, not current work.
- Historical stacked PR graph: `#1 -> #2 -> #8`; `#12 -> #13`; `#14` merged; `#15/#16` closed unmerged on 2026-10-28 due to ZIP contents, with backups recorded in `ai/HANDOFF.md`.
- The original `s` pinned source and product-hub limitations are recorded in `ai/projects.json` and `ai/PROJECT_STATE.json`; avoid interpreting those snapshots as live branch status.
