# Filter Policy

## Stable scope

Stable lists are intentionally conservative supplements. Active rules must remain third-party hostname network blocks in the form `||domain^$third-party`.

Stable lists must not contain broad cosmetic rules, first-party blocking, anti-adblock circumvention, paywall bypass rules, URL rewriting, `$document`, or `$all` rules.

## Candidate lifecycle

New domains start in `experimental/candidates.json` and are not active filters.

A candidate may be promoted only when:

1. the domain is still present in maintained current sources or is reproducibly observed serving the target behavior;
2. classification evidence comes from at least the number of independent source families defined by `candidate_min_independent_source_families` in `manifest.json` (currently 2);
3. an explicit exception review is current and reports no known compatibility exception;
4. the rule is reviewed for site-breakage risk and live breakage testing is completed;
5. the rule fits the conservative third-party hostname policy;
6. evidence remains within the configured freshness window;
7. the stable manifest and expected rule count are updated in the same change;
8. CI passes.

A source family represents an independently maintained filter project, such as EasyList/EasyPrivacy or AdGuard. Multiple files from the same project count as one family.

Any candidate with a known allow/unbreak/CNAME compatibility exception must remain `hold` or become `rejected`; it cannot remain in `candidate` state. High-risk candidates also remain `hold` until the documented blocker is resolved. Bulk copying from another list is not permitted.

## Evidence integrity and freshness

Mutable source links may be kept for navigation, but file-based evidence must also include immutable GitHub blob snapshots. Snapshot URLs must contain the exact 40-character commit SHA recorded in the evidence object.

Each evidence record declares a `role` (`classification` or `exception`) and a `source_family`. Classification evidence used for promotion must be a pinned file snapshot.

Candidate evidence expires after the number of days defined by `candidate_evidence_max_age_days` in `manifest.json`. The current limit is 45 days. Expired evidence fails validation and must be rechecked before promotion.

`verified_at` must match the newest evidence `checked_at` date for each candidate. The queue-level `observed_at` date must match the newest candidate verification date. Exception reviews are subject to the same freshness window.

The weekly GitHub Actions run performs the same evidence and promotion-gate checks even when the filter files themselves have not changed.

## Generated review report

`experimental/CANDIDATES.md` is generated from `experimental/candidates.json`. CI rejects the change if the committed report does not exactly match the JSON source of truth.

## Rollback

If a stable rule causes breakage, remove that rule first rather than weakening the entire list. Keep the stable subscription URL unchanged so subscribers receive the rollback automatically.

## Versioning

List versions use `YYYYMMDD.N`. Metadata-only changes may increment the suffix. Rule changes must also update the manifest count and changelog.
