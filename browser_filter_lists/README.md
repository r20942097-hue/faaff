# Browser Filter Lists

Small supplementary filter lists for general web browsing.

## Lists

### Universal Web Ad Filter
Conservative supplementary ad-network list. Network blocking only; third-party requests only.

Subscription URL after merge to `main`:

`https://raw.githubusercontent.com/r20942097-hue/faaff/main/browser_filter_lists/filters/universal-web-ad-filter.txt`

### Universal Web Tracking Filter
Optional analytics/session-measurement blocking. May affect analytics, feedback widgets, or embedded features.

Subscription URL after merge to `main`:

`https://raw.githubusercontent.com/r20942097-hue/faaff/main/browser_filter_lists/filters/universal-web-tracking-filter.txt`

## Recommended use

Use the ad list together with one maintained general-purpose base list. Do not treat this repository as a replacement for a maintained base list.

The tracking list is optional. If a site breaks after enabling it, disable the tracking list first.

## Scope

These lists intentionally avoid:
- broad cosmetic filtering
- cookie-banner hiding
- anti-adblock circumvention
- paywall rules
- URL rewriting

## Validation

Run:

```bash
python browser_filter_lists/scripts/validate_filters.py
```

GitHub Actions runs the same validation on pushes and pull requests.
