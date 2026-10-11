# Production E2E Checklist

1. Confirm version 6.10.0 against the release archive and SHA256-v6.10.0.txt. The runtime source/archive is not present in this checkout; obtain and verify it before running the following checks.
2. Run `--doctor-json`.
3. Run `--recovery-learning 50` and inspect the evidence policy.
4. Start on the target Windows machine.
5. Open one authorized RPLAY LIVE.
6. Verify discovery and/or Browser Bridge observation.
7. For an authorized recording, verify FFmpeg -> TS -> MP4 finalization.
8. Observe manifest refresh/re-resolution.
9. Verify one recovery context produces exactly one effectiveness observation.
10. Restart during pending attribution and verify reconciliation.
11. Inspect `/api/coverage` and `/metrics`.
