# Experimental Candidate Review

> Generated from `experimental/candidates.json`. These entries are inactive and are not subscription rules.

Last verified: `2026-10-01`\
Evidence freshness limit: `45 days`\
Queue: `0 candidate`, `4 hold`, `1 rejected`

| Domain | Category | State | Risk | Verified | Reason |
| --- | --- | --- | --- | --- | --- |
| bidswitch.net | tracking | rejected | medium | 2026-10-01 | Rejected from the recommended delta profile because current EasyPrivacy already covers bidswitch.net; adding it would duplicate uBlock Origin default coverage. |
| bluekai.com | tracking | hold | medium | 2026-10-01 | Confirmed in EasyPrivacy and AdGuard tracking lists, but current compatibility allow/unbreak rules show that broad blocking can break specific sites. |
| agkn.com | tracking | hold | medium | 2026-10-01 | Confirmed in EasyPrivacy and AdGuard tracking lists, but AdGuard contains a site-specific compatibility allow rule for an agkn.com resource. |
| bounceexchange.com | tracking | hold | medium | 2026-10-01 | Confirmed in EasyPrivacy and AdGuard tracking lists, but uAssets contains an explicit site-specific unbreak exception for bounceexchange.com. |
| amazon-adsystem.com | ads | hold | high | 2026-10-01 | Advertising domain with documented exception handling in AdGuard; broad promotion remains blocked pending targeted breakage testing. |

## Evidence snapshots

### `bidswitch.net`

- `github_file_snapshot` checked `2026-10-01`: https://github.com/easylist/easylist/blob/f1f8051be490ba07b5c2214298ad04026f4e7663/easyprivacy/easyprivacy_trackingservers_general.txt
- `github_file_snapshot` checked `2026-10-01`: https://github.com/AdguardTeam/AdguardFilters/blob/1ad282a5134fde60e6943e777b74ea9ec5abd161/SpywareFilter/sections/tracking_servers.txt

### `bluekai.com`

- `github_file_snapshot` checked `2026-10-01`: https://github.com/easylist/easylist/blob/f1f8051be490ba07b5c2214298ad04026f4e7663/easyprivacy/easyprivacy_trackingservers_general.txt
- `github_file_snapshot` checked `2026-10-01`: https://github.com/AdguardTeam/AdguardFilters/blob/1ad282a5134fde60e6943e777b74ea9ec5abd161/SpywareFilter/sections/tracking_servers.txt
- `github_file_snapshot` checked `2026-10-01`: https://github.com/AdguardTeam/AdguardFilters/blob/1ad282a5134fde60e6943e777b74ea9ec5abd161/SpywareFilter/sections/allowlist.txt
- `github_file_snapshot` checked `2026-10-01`: https://github.com/uBlockOrigin/uAssets/blob/6d71f53af6fcbee8c36e89ba705b7e9a24badfae/filters/unbreak.txt
- Promotion blocker: Known site-specific allow/unbreak exceptions must be resolved or explicitly scoped before stable promotion.

### `agkn.com`

- `github_file_snapshot` checked `2026-10-01`: https://github.com/easylist/easylist/blob/f1f8051be490ba07b5c2214298ad04026f4e7663/easyprivacy/easyprivacy_trackingservers_general.txt
- `github_file_snapshot` checked `2026-10-01`: https://github.com/AdguardTeam/AdguardFilters/blob/1ad282a5134fde60e6943e777b74ea9ec5abd161/SpywareFilter/sections/tracking_servers.txt
- `github_file_snapshot` checked `2026-10-01`: https://github.com/AdguardTeam/AdguardFilters/blob/1ad282a5134fde60e6943e777b74ea9ec5abd161/SpywareFilter/sections/allowlist.txt
- Promotion blocker: Known site-specific allow exception requires breakage analysis before stable promotion.

### `bounceexchange.com`

- `github_file_snapshot` checked `2026-10-01`: https://github.com/easylist/easylist/blob/f1f8051be490ba07b5c2214298ad04026f4e7663/easyprivacy/easyprivacy_trackingservers_general.txt
- `github_file_snapshot` checked `2026-10-01`: https://github.com/AdguardTeam/AdguardFilters/blob/1ad282a5134fde60e6943e777b74ea9ec5abd161/SpywareFilter/sections/tracking_servers.txt
- `github_file_snapshot` checked `2026-10-01`: https://github.com/uBlockOrigin/uAssets/blob/6d71f53af6fcbee8c36e89ba705b7e9a24badfae/filters/unbreak.txt
- Promotion blocker: Known uAssets unbreak exception requires site-breakage analysis before stable promotion.

### `amazon-adsystem.com`

- `github_file_snapshot` checked `2026-10-01`: https://github.com/AdguardTeam/AdGuardSDNSFilter/blob/4a991ef85f9ae63c38f8f32f7996fa85e9d5cfb2/Filters/exceptions.txt
- `github_issue` checked `2026-10-01`: https://github.com/uBlockOrigin/uAssets/issues/17437
- Promotion blocker: Documented CNAME-related exception indicates broad blocking can affect legitimate requests.
