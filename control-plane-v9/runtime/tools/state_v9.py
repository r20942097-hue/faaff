import sqlite3,json,hashlib
AUTHORITATIVE_TABLES=[
 "projects","tracks","releases","project_heads","artifacts","artifact_locations","release_artifacts",
 "evidence_sources","evidence","gate_definitions","gate_results","blockers","operations","operation_items",
 "invalidation_rules","schema_migrations","policy_documents","remote_sources","remote_observations",
 "external_components","dependency_edges"
]
def canonical_state(con):
    con.row_factory=sqlite3.Row
    out={}
    for t in AUTHORITATIVE_TABLES:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone():continue
        cols=[x[1] for x in con.execute(f"PRAGMA table_info({t})")]
        out[t]=[dict(x) for x in con.execute(f"SELECT * FROM {t} ORDER BY {','.join(cols)}")]
    return out
def state_sha256(con):
    raw=json.dumps(canonical_state(con),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()
