# Browser Filter Lists

Small supplementary filter lists for general web browsing.

## Universal Web Ad Filter

Conservative supplementary ad-network list. Network blocking only; third-party requests only.

**One-click subscription:**

https://subscribe.adblockplus.org/?location=https%3A%2F%2Fraw.githubusercontent.com%2Fr20942097-hue%2Ffaaff%2Fmain%2Fbrowser_filter_lists%2Ffilters%2Funiversal-web-ad-filter.txt&title=Universal%20Web%20Ad%20Filter

**Direct subscription URL:**

`https://raw.githubusercontent.com/r20942097-hue/faaff/main/browser_filter_lists/filters/universal-web-ad-filter.txt`

## Universal Web Tracking Filter

Optional analytics/session-measurement blocking. May affect analytics, feedback widgets, or embedded features.

**One-click subscription:**

https://subscribe.adblockplus.org/?location=https%3A%2F%2Fraw.githubusercontent.com%2Fr20942097-hue%2Ffaaff%2Fmain%2Fbrowser_filter_lists%2Ffilters%2Funiversal-web-tracking-filter.txt&title=Universal%20Web%20Tracking%20Filter

**Direct subscription URL:**

`https://raw.githubusercontent.com/r20942097-hue/faaff/main/browser_filter_lists/filters/universal-web-tracking-filter.txt`

## Recommended use

Use the ad list together with one maintained general-purpose base list. Do not treat this repository as a replacement for a maintained base list.

The tracking list is optional. If a site breaks after enabling it, disable the tracking list first.

In uBlock Origin, custom lists can also be added manually from **Dashboard → Filter lists → Custom → Import** by pasting a direct subscription URL.

## Scope

These lists intentionally avoid:

- broad cosmetic filtering
- cookie-banner hiding
- anti-adblock circumvention
- paywall rules
- URL rewriting

## Updates

Both lists currently declare `Expires: 5 days`. uBlock Origin can automatically refresh subscribed custom lists according to their expiration metadata when automatic list updates are enabled.

Keep the `main/browser_filter_lists/filters/...` paths stable after publication so existing subscriptions continue to work.

## Validation

Run:

```bash
python browser_filter_lists/scripts/validate_filters.py
```

GitHub Actions runs the same validation on pushes and pull requests. Validation checks required metadata, duplicate rules, broad `$all`/`$document` rules, and the project's conservative third-party hostname blocking policy.
