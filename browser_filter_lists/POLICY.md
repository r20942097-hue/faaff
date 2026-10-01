# Filter Policy

## Stable scope

Stable lists are intentionally conservative supplements. Active rules must remain third-party hostname network blocks in the form `||domain^$third-party`.

Stable lists must not contain broad cosmetic rules, first-party blocking, anti-adblock circumvention, paywall bypass rules, URL rewriting, `$document`, or `$all` rules.

## Candidate lifecycle

New domains start in `experimental/candidates.json` and are not active filters.

A candidate may be promoted only when:

1. the domain is still present in a maintained current source or is reproducibly observed serving the target behavior;
2. the rule is reviewed for site-breakage risk;
3. any known exception or CNAME evidence is evaluated;
4. the rule fits the conservative third-party hostname policy;
5. evidence includes a recent verification date and at least one reviewable snapshot or issue reference;
6. the stable manifest and expected rule count are updated in the same change;
7. CI passes.

High-risk candidates remain `hold` until the documented blocker is resolved. Bulk copying from another list is not permitted.

## Evidence integrity and freshness

Mutable source links may be kept for navigation, but candidate evidence must also include immutable GitHub blob snapshots when a file is used as evidence. Snapshot URLs must contain the exact 40-character commit SHA recorded in the evidence object.

Candidate evidence expires after the number of days defined by `candidate_evidence_max_age_days` in `manifest.json`. The current limit is 45 days. Expired evidence fails the candidate-evidence validator and must be rechecked before promotion.

`verified_at` must match the newest evidence `checked_at` date for each candidate. The queue-level `observed_at` date must match the newest candidate verification date.

The weekly GitHub Actions run performs the same evidence freshness checks even when the filter files themselves have not changed.

## Generated review report

`experimental/CANDIDATES.md` is generated from `experimental/candidates.json`. CI rejects the change if the committed report does not exactly match the JSON source of truth.

## Rollback

If a stable rule causes breakage, remove that rule first rather than weakening the entire list. Keep the stable subscription URL unchanged so subscribers receive the rollback automatically.

## Versioning

List versions use `YYYYMMDD.N`. Metadata-only changes may increment the suffix. Rule changes must also update the manifest count and changelog.
