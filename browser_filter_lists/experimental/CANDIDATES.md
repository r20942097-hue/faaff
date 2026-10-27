# Experimental Candidate Review

> Generated from `experimental/candidates.json`. These entries are inactive and are not subscription rules.

Last verified: `2026-10-11`

Evidence freshness limit: `45 days`

Queue: `1 candidate`, `4 hold`, `0 rejected`

| Domain | Category | State | Risk | Verified | Reason |
| --- | --- | --- | --- | --- | --- |
| bidswitch.net | tracking | candidate | medium | 2026-10-11 | Confirmed in current EasyPrivacy and AdGuard tracking-server lists; no exact allow/unbreak exception was found in the reviewed sources. |
| bluekai.com | tracking | hold | medium | 2026-10-11 | Confirmed in EasyPrivacy and AdGuard tracking lists, but current compatibility allow/unbreak rules show that broad blocking can break specific sites. |
| agkn.com | tracking | hold | medium | 2026-10-11 | Confirmed in EasyPrivacy and AdGuard tracking lists, but AdGuard contains a site-specific compatibility allow rule for an agkn.com resource. |
| bounceexchange.com | tracking | hold | medium | 2026-10-11 | Confirmed in EasyPrivacy and AdGuard tracking lists, but uAssets contains an explicit site-specific unbreak exception for bounceexchange.com. |
| amazon-adsystem.com | ads | hold | high | 2026-10-11 | Current EasyList and AdGuard classify the domain as advertising, but maintained allow/redirect exceptions in AdGuard and uAssets show compatibility risk. |

## Evidence snapshots

### `bidswitch.net`

- `github_file_snapshot` checked `2026-10-11`: https://github.com/easylist/easylist/blob/cb852423c6371c789f2b2ea855f6dbb56a49f7a9/easyprivacy/easyprivacy_trackingservers_general.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/AdguardTeam/AdguardFilters/blob/93e2053f5aa91f07225aeadcb9a7da33cfa347f4/SpywareFilter/sections/tracking_servers.txt

### `bluekai.com`

- `github_file_snapshot` checked `2026-10-11`: https://github.com/easylist/easylist/blob/cb852423c6371c789f2b2ea855f6dbb56a49f7a9/easyprivacy/easyprivacy_trackingservers_general.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/AdguardTeam/AdguardFilters/blob/93e2053f5aa91f07225aeadcb9a7da33cfa347f4/SpywareFilter/sections/tracking_servers.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/AdguardTeam/AdguardFilters/blob/93e2053f5aa91f07225aeadcb9a7da33cfa347f4/SpywareFilter/sections/allowlist.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/uBlockOrigin/uAssets/blob/ecaadbee6a35c60b597121330ef002391c0e28f0/filters/unbreak.txt
- Promotion blocker: Known site-specific allow/unbreak exceptions must be resolved or explicitly scoped before stable promotion.

### `agkn.com`

- `github_file_snapshot` checked `2026-10-11`: https://github.com/easylist/easylist/blob/cb852423c6371c789f2b2ea855f6dbb56a49f7a9/easyprivacy/easyprivacy_trackingservers_general.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/AdguardTeam/AdguardFilters/blob/93e2053f5aa91f07225aeadcb9a7da33cfa347f4/SpywareFilter/sections/tracking_servers.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/AdguardTeam/AdguardFilters/blob/93e2053f5aa91f07225aeadcb9a7da33cfa347f4/SpywareFilter/sections/allowlist.txt
- Promotion blocker: Known site-specific allow exception requires breakage analysis before stable promotion.

### `bounceexchange.com`

- `github_file_snapshot` checked `2026-10-11`: https://github.com/easylist/easylist/blob/cb852423c6371c789f2b2ea855f6dbb56a49f7a9/easyprivacy/easyprivacy_trackingservers_general.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/AdguardTeam/AdguardFilters/blob/93e2053f5aa91f07225aeadcb9a7da33cfa347f4/SpywareFilter/sections/tracking_servers.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/uBlockOrigin/uAssets/blob/ecaadbee6a35c60b597121330ef002391c0e28f0/filters/unbreak.txt
- Promotion blocker: Known uAssets unbreak exception requires site-breakage analysis before stable promotion.

### `amazon-adsystem.com`

- `github_file_snapshot` checked `2026-10-11`: https://github.com/easylist/easylist/blob/cb852423c6371c789f2b2ea855f6dbb56a49f7a9/easylist/easylist_adservers.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/AdguardTeam/AdguardFilters/blob/93e2053f5aa91f07225aeadcb9a7da33cfa347f4/BaseFilter/sections/adservers.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/AdguardTeam/AdguardFilters/blob/93e2053f5aa91f07225aeadcb9a7da33cfa347f4/BaseFilter/sections/allowlist.txt
- `github_file_snapshot` checked `2026-10-11`: https://github.com/uBlockOrigin/uAssets/blob/ecaadbee6a35c60b597121330ef002391c0e28f0/filters/unbreak.txt
- Promotion blocker: Maintained site-specific allow and redirect exceptions require scoped breakage testing; broad stable promotion is blocked.
