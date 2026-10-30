# Development environment v13.1 — RPLAY source fingerprint inspection

Read-only evidence (2026-10-30); no product files in GitHub.

Both locally inspected RPLAY ZIPs passed full CRC and bounded archive intake. All four extension/root/src copies of `segment_store.js` are byte-identical to GitHub P0 Issue #31's SHA256 `3f1a00b89207f8cb783f59152db6ff230c300569f79b1e1eb691353b70218b9e`.

- v2.67.0 LEDGER_ASSEMBLY_AUTO archive SHA256: `ac9ae88db808408baf6c52099bfccc84399a4eb52381ef6780e9f12873717444`, 5307 entries, CRC PASS.
- v2.68.0 LEDGER_SELF_CROSS archive SHA256: `e2dba6dbe4fd18efc934f78ab4768fcf66ca5b22cf0d85da7495f4d1f5f7767e`, 5425 entries, CRC PASS.

The known-bad module evicts valid older segments before writing a candidate. A later quota/write failure can destroy already committed data (Issue #31). The new read-only `ai/source_segment_fingerprint.py` uses existing strict bounded `ai.archive_intake.scan` and SHA256 checks on four expected paths, never extracts or uploads ZIP bytes. A changed digest is **not** automatically classified as fixed, and all outcomes explicitly retain `release_readiness=NO_GO`. Exit 2 indicates a completed inspection still requiring review; 3 indicates input blocked. CI unit fixtures are synthetic only.

Use: `python -m ai.source_segment_fingerprint CANDIDATE.zip --output inspection.json`

This does NOT test native RPLAY browser playback, OPFS failure handling, disk quota, concurrent mutations, power-loss durability or source provenance. PR stays Draft/unmerged and Issue #31 remains OPEN.
