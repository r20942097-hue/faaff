# Browser Filter Lists

Conservative browser-network filter research and distribution.

## Recommended profile: Universal Web Delta Filter

The recommended list is now **delta-only**: it is intended to contain only vetted third-party hostname rules that are absent from the reviewed uBlock Origin default filter set.

**Direct subscription URL:**

`https://raw.githubusercontent.com/r20942097-hue/faaff/main/browser_filter_lists/filters/universal-web-delta-filter.txt`

As of the 2026-10-01 audit, the recommended delta list intentionally contains **0 active rules**. The previous 17 ad and 9 tracking rules are already covered by current uBO defaults or are too broad for this profile. Zero rules is therefore a valid result, not a failure.

The reviewed default baseline includes uBO's own default assets together with EasyList, EasyPrivacy, Peter Lowe, and the relevant compatibility/unbreak sources. `upstream/default-overlap-audit.json` records the exact audit basis and pinned commits.

## Legacy compatibility lists

The older lists remain available for compatibility but are no longer recommended when using current uBlock Origin defaults:

- `filters/universal-web-ad-filter.txt` — 17 legacy ad-network rules
- `filters/universal-web-tracking-filter.txt` — 9 legacy tracking rules

Do not subscribe to the legacy lists merely to increase rule count. Their current value is mainly compatibility/testing, because the audited rules overlap with default coverage or are intentionally narrower upstream.

## Canary

`experimental/universal-web-canary-filter.txt` is experimental and must not be used as the normal stable subscription.

A domain may enter canary only when:

1. it is absent from the reviewed default uBO sources;
2. it has current classification evidence;
3. no reviewed allow/unbreak compatibility exception is known;
4. it is kept separate from stable;
5. it completes the configured soak period before stable promotion is even considered.

The current minimum soak is 14 days. Canary metadata lives in `experimental/canary.json`.

## Candidate and evidence policy

`experimental/candidates.json` is the inactive review queue. A candidate cannot remain promotable when it is already covered by the reviewed uBO defaults.

Stable promotion requires:

- no reviewed default overlap;
- at least two independently maintained classification source families;
- fresh immutable evidence;
- current exception review with no known compatibility exception;
- canary soak;
- live breakage testing;
- CI success.

Known allow/unbreak/CNAME exceptions force an entry to `hold` or `rejected`.

Candidate evidence currently expires after 45 days. The upstream-overlap audit is stricter and expires after 7 days, so weekly CI forces the default-set comparison to be refreshed rather than allowing an old delta decision to persist indefinitely.

## Current research

The first delta-canary domain is `trackhaven.com`. It is not stable. It is being kept in canary because current reviewed default sources did not contain it, while AdGuard tracking data and the service's own description identify analytics/tracking use. Promotion is blocked until the canary soak and stronger pinned independent evidence requirements are satisfied.

Additional domains such as `bidderstack.com`, `targetrtb.com`, `rtbscale.com`, and `northstar.cr` remain research-only; they are not active filters.

## Stable policy

Stable network rules remain restricted to:

`||example.com^$third-party`

The project intentionally avoids broad cosmetic filtering, first-party blocking, cookie-banner hiding, anti-adblock circumvention, paywall bypass, URL rewriting, `$document`, and `$all` in stable lists.

## Validation

Run:

```bash
python browser_filter_lists/scripts/test_validator.py
python browser_filter_lists/scripts/test_evidence.py
python browser_filter_lists/scripts/test_promotion.py
python browser_filter_lists/scripts/test_delta_policy.py
python browser_filter_lists/scripts/validate_filters.py
python browser_filter_lists/scripts/validate_candidate_evidence.py
python browser_filter_lists/scripts/validate_candidate_promotion.py
python browser_filter_lists/scripts/validate_delta_policy.py
python browser_filter_lists/scripts/render_candidate_report.py --check
```

GitHub Actions performs the same checks on relevant pushes and pull requests, plus a weekly scheduled refresh gate.
