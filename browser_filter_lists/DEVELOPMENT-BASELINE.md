# Browser Filter Lists — Development Baseline

Updated: 2026-10-02

## Product state

- Recommended output is the uBlock Origin default delta list. It intentionally has 0 active rules because the reviewed legacy rules are already covered by current defaults or too broad for this profile.
- Optional legacy compatibility lists remain available with 17 ad and 9 tracking rules. They are not recommended with current uBO defaults.
- Canary is empty. Five research domains remain inactive. The candidate queue has four `hold` entries and one `rejected` entry.
- Current source inventory pins EasyList, uAssets, and AdGuard snapshots. Peter Lowe is represented only by the pinned uAssets mirror; direct retrieval is unverified. The Japanese list is stale and excluded from current promotion evidence.
- CI covers filter syntax, candidate evidence, promotion gates, delta overlap, and generated report freshness. There is no claim of live browser breakage testing or a public subscription endpoint.

## Verified baseline and current work

- Development baseline: `browser-filter-delta-v4` at `e894b0215100dd740a7bcdb35c250a049b69a19a`.
- Working change: PR #9, `codex/delta-v4-canary-empty-test-fix`, targeting that baseline.
- PR #9 fixes an empty-canary test assumption, records the current source inventory, hardens snapshot validation, and checks that pinned candidate evidence matches the inventory.
- Local tests and GitHub CI/filter validation pass. GitHub Dependency Review is unsupported in the repository settings; this leaves dependency/vulnerability posture unknown and is not a vulnerability finding.

## Next design: evidence synchronization

Keep one authoritative chain:

1. `upstream/current-source-snapshot-inventory.json` pins reviewed source repositories, commits, paths, blob SHAs, and sizes.
2. Candidate evidence records must reference the same pinned commit and an inventoried path for any source family represented there.
3. Candidate status and canary status stay separate. A research item cannot silently become a canary or stable rule through documentation edits.
4. `CANDIDATES.md` remains generated from `candidates.json`; README claims describe the actual canary and queue state.
5. Any source refresh invalidates mismatched evidence until the cited rules and exceptions are checked again at the new pinned revisions.

The first operational tool for this design is `scripts/refresh_source_snapshot_proposal.py`. It queries GitHub for the latest immutable commits and file blob metadata, then prints or atomically writes a separate proposal. It never updates the authoritative inventory, candidate statuses, stable rules, or canary. Human review must refresh overlap and candidate evidence before adopting the proposal.

## Completion gates

- All local tests, validators, and generated-report checks pass.
- GitHub CI and filter validation pass on the proposed head.
- Candidate pins match the current inventory; all active rules pass overlap, evidence, exception, and soak gates.
- Browser breakage tests are recorded before any candidate is promoted.
- Public distribution is a separate release step and requires an accessible public host.
- Dependency Review remains reported as unsupported/unknown until repository capabilities are enabled and a scan actually runs.
