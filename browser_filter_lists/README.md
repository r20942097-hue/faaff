# Browser Filter Lists

Conservative supplementary filter lists for general web browsing.

## Universal Web Ad Filter

Third-party ad-network blocking only. This is the recommended stable list.

**One-click subscription:**

https://subscribe.adblockplus.org/?location=https%3A%2F%2Fraw.githubusercontent.com%2Fr20942097-hue%2Ffaaff%2Fmain%2Fbrowser_filter_lists%2Ffilters%2Funiversal-web-ad-filter.txt&title=Universal%20Web%20Ad%20Filter

**Direct subscription URL:**

`https://raw.githubusercontent.com/r20942097-hue/faaff/main/browser_filter_lists/filters/universal-web-ad-filter.txt`

## Universal Web Tracking Filter

Optional third-party analytics/session-measurement blocking. It can affect analytics, feedback widgets, or embedded site features.

**One-click subscription:**

https://subscribe.adblockplus.org/?location=https%3A%2F%2Fraw.githubusercontent.com%2Fr20942097-hue%2Ffaaff%2Fmain%2Fbrowser_filter_lists%2Ffilters%2Funiversal-web-tracking-filter.txt&title=Universal%20Web%20Tracking%20Filter

**Direct subscription URL:**

`https://raw.githubusercontent.com/r20942097-hue/faaff/main/browser_filter_lists/filters/universal-web-tracking-filter.txt`

## Recommended use

Use the ad list together with one maintained general-purpose base list. This repository is a small supplement, not a replacement for EasyList, uBlock filters, AdGuard Base, or another maintained base list.

Enable the tracking list only if you accept a higher chance of site-feature breakage. When troubleshooting, disable the tracking list first.

In uBlock Origin, custom lists can also be added manually from **Dashboard → Filter lists → Custom → Import** by pasting a direct subscription URL.

## Stable policy

Stable rules are intentionally restricted to third-party hostname network blocks in this form:

`||example.com^$third-party`

The stable lists intentionally avoid broad cosmetic filtering, first-party blocking, cookie-banner hiding, anti-adblock circumvention, paywall bypass rules, URL rewriting, `$document`, and `$all` rules.

Canonical list metadata and expected rule counts are defined in `manifest.json`. See `POLICY.md` for promotion and rollback rules.

## Experimental candidates

`experimental/candidates.json` is the canonical review queue, not a subscribable filter list. Entries there are inactive until they are explicitly promoted to a stable list.

Candidates record category, risk, proposed rule, live source links, verification dates, immutable evidence snapshots, and any promotion blocker. File-based evidence is pinned to an exact Git commit so later source changes cannot silently rewrite the historical basis for a candidate.

`experimental/CANDIDATES.md` is a generated human-readable view of the same queue. CI verifies that the report is exactly synchronized with the JSON source of truth.

Candidate evidence currently expires after 45 days. A weekly GitHub Actions run checks freshness even when no filter change is submitted. Stale evidence must be reviewed again before it can be used for promotion.

## Updates

Both stable lists currently declare `Expires: 5 days`. uBlock Origin can automatically refresh subscribed custom lists according to expiration metadata when automatic list updates are enabled.

Keep the `main/browser_filter_lists/filters/...` paths stable so existing subscriptions continue to work.

## Validation

Run:

```bash
python browser_filter_lists/scripts/test_validator.py
python browser_filter_lists/scripts/test_evidence.py
python browser_filter_lists/scripts/validate_filters.py
python browser_filter_lists/scripts/validate_candidate_evidence.py
python browser_filter_lists/scripts/render_candidate_report.py --check
```

GitHub Actions runs compilation, regression tests, stable-list validation, candidate-evidence freshness validation, and generated-report consistency checks on relevant pushes and pull requests, plus a weekly scheduled evidence check.
