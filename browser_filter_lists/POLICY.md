# Filter Policy

## Recommended stable scope

The recommended profile is `ubo-default-delta`. Its purpose is not to replicate EasyList, EasyPrivacy, Peter Lowe, or uBO default filters. Stable delta rules must provide verified coverage that is absent from the reviewed default set.

The reference uBO default profile includes uBlock filters, EasyList, EasyPrivacy, Online Malicious URL Blocklist, and Peter Lowe's list, with regional lists enabled according to locale. Because adding more lists increases false-positive and interaction risk, the preferred delta is the smallest justified one, including zero active rules when the defaults already cover all vetted cases.

Active stable delta rules must remain narrowly scoped network rules. Prefer the smallest hostname, path, request type, or source-domain scope that solves the verified gap. Do not add a broad root-domain rule when maintained upstream lists use narrower subdomain/path rules or compatibility exceptions.

The recommended stable list must not contain broad cosmetic rules, first-party blanket blocking, anti-adblock circumvention, paywall bypass rules, unsafe URL rewriting, `$document`, or `$all` rules. Avoid regex when a simpler rule is sufficient.

Legacy compatibility lists may retain previously published rules, but they are not the recommended profile and must not be used as evidence that a rule belongs in delta stable.

## Upstream-first principle

If a missed ad/tracker can be fixed cleanly in EasyList/EasyPrivacy, prefer reporting or fixing it upstream. uAssets explicitly prefers EasyList/EasyPrivacy for EasyList-compatible fixes and uses uBO-specific lists primarily for uBO-specific syntax and targeted exceptions.

AdGuard Base also incorporates EasyList and its contributor guidance says not to duplicate rules already present there. This project applies the same principle to the full uBO default profile.

A local delta rule is justified only when it fills a verified current gap, acts as a temporary bridge while upstream is pending, or intentionally targets behavior outside the default profile while still meeting this project's conservative scope.

## Upstream overlap gate

The current default-set audit is recorded in `upstream/default-overlap-audit.json`.

A rule cannot enter or remain in the recommended delta stable list when the audited uBO default sources already cover the same hostname or an equivalent broader/narrower effective rule.

The upstream audit expires after `upstream_audit_max_age_days` from `manifest.json` (currently 7 days). A stale audit fails CI. This keeps delta decisions tied to current upstream state instead of historical assumptions.

## Candidate lifecycle

New domains start as research, not active filters. A domain may progress only when:

1. current reviewed uBO default sources do not already cover it;
2. classification evidence comes from at least the configured number of independent source families;
3. the evidence establishes actual ad/tracking behavior, not merely that the service calls itself "analytics";
4. an explicit exception review is current and reports no known compatibility exception;
5. evidence remains within the configured freshness window;
6. the proposed rule is the narrowest practical rule;
7. it enters canary rather than stable directly;
8. it completes at least `canary_min_soak_days` (currently 14 days);
9. live breakage testing is completed;
10. the stable manifest and expected rule count are updated in the same change;
11. CI passes.

A source family represents an independently maintained project. Multiple files from the same project count as one family.

A first-party marketing or product page may corroborate what a service does, but it is not sufficient by itself to establish privacy-invasive tracking. Low-authority domain-description, reputation, or AI-summary sites are research hints only and cannot authorize canary/stable promotion.

Any candidate already covered by the reviewed uBO defaults is rejected from the delta profile even if several other lists classify it as advertising or tracking.

Any candidate with a known allow/unbreak/CNAME compatibility exception must remain `hold` or become `rejected`. High-risk candidates also remain `hold` until their blocker is resolved.

Bulk copying from another filter list is not permitted.

## Canary

Canary rules live in `experimental/universal-web-canary-filter.txt` and `experimental/canary.json`. They are explicitly non-stable.

Canary admission requires a verified upstream gap, strong independent classification evidence, the narrowest practical rule, and a no-known-exception review. Canary and stable delta hosts must remain disjoint.

The earliest promotion date must be at least the configured soak period after `started_at`. Completing the calendar soak does not itself authorize promotion; evidence, breakage review, upstream overlap, and CI must still pass.

An empty canary is valid and preferable to admitting weak candidates.

## Evidence integrity and freshness

Mutable source links may be kept for navigation, but file-based evidence used for promotion should use immutable commit-pinned snapshots where possible.

Evidence should distinguish:
- `classification`: supports what the request/domain does;
- `exception`: documents compatibility or unbreak concerns;
- `overlap`: proves current default-profile coverage;
- `observation`: reproducible behavior from a real site or test case.

Candidate evidence expires after `candidate_evidence_max_age_days` (currently 45 days). Exception reviews use the same freshness window. The upstream overlap audit uses a much shorter limit because EasyList, EasyPrivacy, Peter Lowe, and uAssets change frequently.

Evidence quality and independence matter more than the raw number of links.

## Provenance and licensing

Do not bulk-copy third-party filter content. Upstream lists use different licenses, including GPL and Creative Commons terms. Exact copied rules must not be relicensed as CC0 without a compatible legal basis.

Recommended delta rules should be independently authored from observed behavior and documented evidence. Upstream lists may be used to verify coverage, classification, and compatibility, with attribution retained in audit/evidence records.

If a rule is materially derived from licensed upstream content rather than independently authored, its provenance and compatible licensing must be recorded before publication.

## Generated reports

`experimental/CANDIDATES.md` is generated from `experimental/candidates.json`. CI rejects a stale report.

## Rollback

If a stable delta rule causes breakage, remove or narrow that rule first rather than weakening the entire list. Keep the eventual public stable subscription path unchanged so subscribers receive the rollback automatically.

## Distribution boundary

The development repository may be private. A private GitHub Raw URL is not a general public subscription endpoint. Public distribution should be generated from validated artifacts into a dedicated public repository with stable paths.

## Versioning

List versions use `YYYYMMDD.N`. Metadata-only changes may increment the suffix. Rule changes must also update the manifest count, overlap audit, and changelog.
