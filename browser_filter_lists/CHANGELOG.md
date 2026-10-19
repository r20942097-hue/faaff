# Changelog

## 2026-10-19 — Candidate type validation

- Report invalid candidate category/state/risk types as validation errors instead of uncaught exceptions.
- Add regression tests for malformed JSON enum values; stable rules and candidate decisions are unchanged.

## 2026-10-11 — shared profiles and refreshed evidence (local)

- Refreshed candidate evidence from pinned current EasyList, AdGuard and uAssets snapshots.
- Kept one candidate and four holds; no automatic promotions.
- Kept stable active rules at 17 advertising and 9 tracking rules; generated metadata version 20261011.1.
- Exported common rule sets from s/filter-profiles.json while retaining existing subscription paths and licenses.
- Raised registry policy to version 4 and bound each source family to known repositories.
- Rejected duplicate JSON keys, unsafe paths, spoofed independent families and expired promotion evidence.
- CI discovers all regression tests, including shared JSON/path helpers.
- These changes have not been pushed or published.

## 2026-10-01 — cross-source promotion gates

- Raised candidate policy to version 3.
- Required at least two independent classification source families before an entry can remain a promotion candidate.
- Added explicit exception review metadata and CI enforcement.
- Added evidence roles (`classification` / `exception`) and source-family identities.
- Rechecked current EasyPrivacy, AdGuard, and uAssets evidence using immutable snapshots.
- Kept `bidswitch.net` as the only candidate after cross-source confirmation.
- Moved `bluekai.com`, `agkn.com`, and `bounceexchange.com` to `hold` because maintained allow/unbreak evidence exists.
- Kept `amazon-adsystem.com` on `hold` because of documented compatibility exceptions.
- Added a dedicated promotion-gate validator and regression tests.
- Kept stable active rules unchanged at 17 ad rules and 9 optional tracking rules.

## 2026-10-01 — candidate evidence hardening

- Added a 45-day candidate evidence freshness policy to `manifest.json`.
- Added per-candidate verification dates and immutable GitHub evidence snapshots.
- Pinned EasyPrivacy evidence to repository snapshot `de1806065e53df5732bd048688a9b2800fa69a73`.
- Pinned the AdGuard exception evidence to snapshot `4a991ef85f9ae63c38f8f32f7996fa85e9d5cfb2`.
- Added a dedicated evidence validator for dates, snapshot URL integrity, commit/path matching, and stale evidence.
- Added evidence-validator regression tests.
- Added generated `experimental/CANDIDATES.md` and CI synchronization checks.
- Added a weekly scheduled evidence freshness check.
- Kept stable active rules unchanged at 17 ad rules and 9 optional tracking rules.

## 2026-10-01 — validation and staging hardening

- Added `manifest.json` as the canonical stable-list registry.
- Added explicit expected rule counts and safety caps.
- Added `experimental/candidates.json` for inactive evidence-backed candidates.
- Added stable promotion, high-risk hold, and rollback policy.
- Hardened hostname, path, metadata, duplicate, cross-list, and candidate validation.
- Added validator regression tests and CI execution.
- Kept stable active rules unchanged at 17 ad rules and 9 optional tracking rules.

## 2026-10-01 — publication polish

- Added stable Homepage and Subscription metadata.
- Added HTTPS one-click subscription links.
- Added CI checks for published metadata and stable Raw URLs.

## 2026-10-01 — initial publication

- Published the conservative ad supplement.
- Published the optional tracking supplement.
- Added initial validation workflow and subscription documentation.
