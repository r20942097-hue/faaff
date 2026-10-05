# Retention Policy

## Durable evidence

- STABLE artifact and evidence: retain while supported.
- CURRENT candidate and evidence: retain until superseded.
- PREVIOUS_KNOWN_GOOD and evidence: retain while it remains the rollback point.
- Superseded DEV artifacts: archive first; delete only after uniqueness and reference checks.
- CI logs are not the authoritative long-term evidence store.

GitHub's default retention for checks, workflow runs, commit statuses, Actions artifacts, and logs is 90 days. Evidence required to prove a current, stable, or rollback release must therefore be copied into durable release or Library evidence rather than existing only in CI.

## Archive eligibility

Archive an item only when:

1. it is not CURRENT, STABLE, or PREVIOUS_KNOWN_GOOD;
2. unique failure/recovery evidence has been preserved;
3. no current release manifest or provenance record depends only on that copy;
4. a later verified version supersedes its functional purpose.

Deletion is a separate decision from archival.
