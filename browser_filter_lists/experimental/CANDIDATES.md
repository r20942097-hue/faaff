# Experimental Candidate Review

> Generated from `experimental/candidates.json`. These entries are inactive and are not subscription rules.

Last verified: `2026-10-01`  
Evidence freshness limit: `45 days`  
Queue: `4 candidate`, `1 hold`, `0 rejected`

| Domain | Category | State | Risk | Verified | Reason |
| --- | --- | --- | --- | --- | --- |
| bidswitch.net | tracking | candidate | medium | 2026-10-01 | Present in the current EasyPrivacy general tracking-server list. |
| bluekai.com | tracking | candidate | medium | 2026-10-01 | Present in the current EasyPrivacy general tracking-server list. |
| agkn.com | tracking | candidate | medium | 2026-10-01 | Present in the current EasyPrivacy general tracking-server list. |
| bounceexchange.com | tracking | candidate | medium | 2026-10-01 | Present in the current EasyPrivacy general tracking-server list; may affect site engagement widgets, so it is not promoted automatically. |
| amazon-adsystem.com | ads | hold | high | 2026-10-01 | Advertising domain with documented exception handling in AdGuard; broad promotion is held pending site-breakage testing. |

## Evidence snapshots

### `bidswitch.net`

- `github_file_snapshot` checked `2026-10-01`: https://github.com/easylist/easylist/blob/de1806065e53df5732bd048688a9b2800fa69a73/easyprivacy/easyprivacy_trackingservers_general.txt

### `bluekai.com`

- `github_file_snapshot` checked `2026-10-01`: https://github.com/easylist/easylist/blob/de1806065e53df5732bd048688a9b2800fa69a73/easyprivacy/easyprivacy_trackingservers_general.txt

### `agkn.com`

- `github_file_snapshot` checked `2026-10-01`: https://github.com/easylist/easylist/blob/de1806065e53df5732bd048688a9b2800fa69a73/easyprivacy/easyprivacy_trackingservers_general.txt

### `bounceexchange.com`

- `github_file_snapshot` checked `2026-10-01`: https://github.com/easylist/easylist/blob/de1806065e53df5732bd048688a9b2800fa69a73/easyprivacy/easyprivacy_trackingservers_general.txt

### `amazon-adsystem.com`

- `github_file_snapshot` checked `2026-10-01`: https://github.com/AdguardTeam/AdGuardSDNSFilter/blob/4a991ef85f9ae63c38f8f32f7996fa85e9d5cfb2/Filters/exceptions.txt
- `github_issue` checked `2026-10-01`: https://github.com/uBlockOrigin/uAssets/issues/17437
- Promotion blocker: Documented CNAME-related exception indicates broad blocking can affect legitimate requests.
