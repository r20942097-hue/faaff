CREATE TABLE IF NOT EXISTS policy_documents (
  policy_id TEXT PRIMARY KEY,
  policy_kind TEXT NOT NULL,
  policy_sha256 TEXT NOT NULL UNIQUE,
  content_json TEXT NOT NULL,
  active INTEGER NOT NULL CHECK(active IN (0,1)),
  loaded_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_policy_kind
ON policy_documents(policy_kind)
WHERE active=1;
