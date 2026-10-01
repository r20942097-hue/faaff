# Filter Policy

## Recommended stable scope

The recommended profile is `ubo-default-delta`. Its purpose is not to replicate EasyList, EasyPrivacy, Peter Lowe, or uBO default filters. Stable delta rules must provide verified coverage that is absent from the reviewed default set.

Active stable delta rules must remain third-party hostname network blocks in the form `||domain^$third-party`.

The recommended stable list must not contain broad cosmetic rules, first-party blocking, anti-adblock circumvention, paywall bypass rules, URL rewriting, `$document`, or `$all` rules.

Legacy compatibility lists may retain previously published rules, but they are not the recommended profile and must not be used as evidence that a rule belongs in delta stable.

## Upstream overlap gate

The current default-set audit is recorded in `upstream/default-overlap-audit.json`.

A rule cannot enter or remain in the recommended delta stable list when the audited uBO default sources already cover the same hostname or an equivalent broader rule.

The upstream audit expires after `upstream_audit_max_age_days` from `manifest.json` (currently 7 days). A stale audit fails CI. This keeps delta decisions tied to current upstream state instead of historical assumptions.

## Candidate lifecycle

New domains start as research or inactive candidates. A domain may progress only when:

1. current reviewed uBO default sources do not already cover it;
2. classification evidence comes from at least the number of independent source families defined by `candidate_min_independent_source_families` (currently 2);
3. an explicit exception review is current and reports no known compatibility exception;
4. evidence remains within the configured freshness window;
5. the proposed rule fits the conservative third-party hostname policy;
6. it enters canary rather than stable directly;
7. it completes at least `canary_min_soak_days` (currently 14 days);
8. live breakage testing is completed;
9. the stable manifest and expected rule count are updated in the same change;
10. CI passes.

A source family represents an independently maintained project. Multiple files from the same project count as one family.

Any candidate already covered by the reviewed uBO defaults is rejected from the delta profile even if several other lists classify it as advertising or tracking.

Any candidate with a known allow/unbreak/CNAME compatibility exception must remain `hold` or become `rejected`. High-risk candidates also remain `hold` until their blocker is resolved.

Bulk copying from another filter list is not permitted.

## Canary

Canary rules live in `experimental/universal-web-canary-filter.txt` and `experimental/canary.json`. They are explicitly non-stable.

Canary admission requires an upstream gap audit and a no-known-exception review. Canary and stable delta hosts must remain disjoint.

The earliest promotion date must be at least the configured soak period after `started_at`. Completing the calendar soak does not itself authorize promotion; evidence, breakage review, upstream overlap, and CI must still pass.

## Evidence integrity and freshness

Mutable source links may be kept for navigation, but file-based evidence used for promotion must also include immutable GitHub blob snapshots. Snapshot URLs must contain the exact 40-character commit SHA recorded in the evidence object.

Each candidate evidence record declares a `role` (`classification` or `exception`) and a `source_family`. Classification evidence used for promotion must be reviewable and independently maintained.

Candidate evidence expires after `candidate_evidence_max_age_days` (currently 45 days). Exception reviews use the same freshness window.

The upstream overlap audit uses a much shorter freshness limit because EasyList, EasyPrivacy and uAssets change frequently.

## Generated reports

`experimental/CANDIDATES.md` is generated from `experimental/candidates.json`. CI rejects a stale report.

## Rollback

If a stable delta rule causes breakage, remove that rule first rather than weakening the entire list. Keep the stable subscription URL unchanged so subscribers receive the rollback automatically.

## Versioning

List versions use `YYYYMMDD.N`. Metadata-only changes may increment the suffix. Rule changes must also update the manifest count, overlap audit, and changelog.
