# Changelog

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
