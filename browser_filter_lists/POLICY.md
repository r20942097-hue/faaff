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
5. the stable manifest and expected rule count are updated in the same change;
6. CI passes.

High-risk candidates remain `hold` until the documented blocker is resolved. Bulk copying from another list is not permitted.

## Rollback

If a stable rule causes breakage, remove that rule first rather than weakening the entire list. Keep the stable subscription URL unchanged so subscribers receive the rollback automatically.

## Versioning

List versions use `YYYYMMDD.N`. Metadata-only changes may increment the suffix. Rule changes must also update the manifest count and changelog.
