PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  name TEXT,
  priority INTEGER,
  lifecycle TEXT NOT NULL,
  risk_class TEXT,
  policy_profile TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tracks (
  track_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  name TEXT NOT NULL,
  purpose TEXT,
  UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS releases (
  release_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  track_id TEXT NOT NULL REFERENCES tracks(track_id),
  version TEXT NOT NULL,
  stage TEXT NOT NULL,
  decision TEXT NOT NULL,
  observed_at TEXT,
  UNIQUE(track_id, version)
);

CREATE TABLE IF NOT EXISTS project_heads (
  project_id TEXT PRIMARY KEY REFERENCES projects(project_id),
  observed_release_id TEXT REFERENCES releases(release_id),
  product_verified_release_id TEXT REFERENCES releases(release_id),
  integration_verified_release_id TEXT REFERENCES releases(release_id),
  stable_release_id TEXT REFERENCES releases(release_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,
  size_bytes INTEGER,
  media_type TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact_locations (
  location_id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
  backend TEXT NOT NULL,
  backend_object_id TEXT,
  locator TEXT NOT NULL,
  location_state TEXT NOT NULL,
  canonical INTEGER NOT NULL DEFAULT 0 CHECK(canonical IN (0,1)),
  observed_at TEXT NOT NULL,
  UNIQUE(backend, locator)
);

CREATE TABLE IF NOT EXISTS release_artifacts (
  release_id TEXT NOT NULL REFERENCES releases(release_id),
  artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
  role TEXT NOT NULL,
  PRIMARY KEY(release_id, artifact_id, role)
);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  evidence_type TEXT NOT NULL,
  status TEXT NOT NULL,
  collected_at TEXT NOT NULL,
  issuer TEXT,
  environment_json TEXT,
  payload_sha256 TEXT,
  source_ref TEXT,
  valid_until TEXT,
  supersedes_evidence_id TEXT REFERENCES evidence(evidence_id)
);

CREATE TABLE IF NOT EXISTS gate_definitions (
  policy_profile TEXT NOT NULL,
  gate_id TEXT NOT NULL,
  mandatory_for_stable INTEGER NOT NULL DEFAULT 1 CHECK(mandatory_for_stable IN (0,1)),
  freshness_rule TEXT,
  PRIMARY KEY(policy_profile, gate_id)
);

CREATE TABLE IF NOT EXISTS gate_results (
  gate_result_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL REFERENCES releases(release_id),
  gate_id TEXT NOT NULL,
  status TEXT NOT NULL,
  evidence_id TEXT REFERENCES evidence(evidence_id),
  environment_fingerprint TEXT,
  assessed_at TEXT NOT NULL,
  valid_until TEXT
);

CREATE TABLE IF NOT EXISTS blockers (
  blocker_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL REFERENCES releases(release_id),
  code TEXT NOT NULL,
  status TEXT NOT NULL,
  detail TEXT
);

CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL REFERENCES releases(release_id),
  approval_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  approved_at TEXT NOT NULL,
  note TEXT
);

CREATE TABLE IF NOT EXISTS operations (
  operation_id TEXT PRIMARY KEY,
  operation_type TEXT NOT NULL,
  status TEXT NOT NULL,
  planned_at TEXT NOT NULL,
  applied_at TEXT,
  completed_at TEXT,
  actor TEXT,
  source_snapshot_id TEXT,
  plan_sha256 TEXT,
  reversible INTEGER NOT NULL DEFAULT 1 CHECK(reversible IN (0,1))
);

CREATE TABLE IF NOT EXISTS operation_items (
  operation_item_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL REFERENCES operations(operation_id),
  action TEXT NOT NULL,
  artifact_id TEXT REFERENCES artifacts(artifact_id),
  source_backend TEXT,
  source_locator TEXT,
  destination_backend TEXT,
  destination_locator TEXT,
  expected_sha256 TEXT,
  expected_size INTEGER,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  previous_event_hash TEXT,
  event_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  policy_version TEXT NOT NULL,
  event_head_hash TEXT,
  snapshot_sha256 TEXT NOT NULL UNIQUE,
  export_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_releases_project ON releases(project_id);
CREATE INDEX IF NOT EXISTS idx_locations_artifact ON artifact_locations(artifact_id);
CREATE INDEX IF NOT EXISTS idx_evidence_subject ON evidence(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_gate_results_release ON gate_results(release_id);
CREATE INDEX IF NOT EXISTS idx_blockers_release ON blockers(release_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_canonical_per_artifact_backend
ON artifact_locations(artifact_id, backend)
WHERE canonical=1 AND location_state='ACTIVE';

CREATE TABLE IF NOT EXISTS evidence_sources (
  evidence_source_id TEXT PRIMARY KEY,
  source_name TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  source_size INTEGER NOT NULL,
  parser_id TEXT NOT NULL,
  source_origin TEXT,
  ingested_at TEXT NOT NULL,
  UNIQUE(source_sha256, parser_id)
);

CREATE TABLE IF NOT EXISTS policy_evaluations (
  evaluation_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL REFERENCES releases(release_id),
  policy_profile TEXT NOT NULL,
  evaluated_at TEXT NOT NULL,
  decision TEXT NOT NULL,
  required_gate_count INTEGER NOT NULL,
  pass_count INTEGER NOT NULL,
  blocking_count INTEGER NOT NULL,
  state_sha256 TEXT NOT NULL,
  details_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invalidation_rules (
  policy_profile TEXT NOT NULL,
  gate_id TEXT NOT NULL,
  dimension TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  PRIMARY KEY(policy_profile, gate_id, dimension)
);

CREATE TRIGGER IF NOT EXISTS evidence_no_update
BEFORE UPDATE ON evidence
BEGIN
  SELECT RAISE(ABORT, 'evidence rows are immutable; insert superseding evidence instead');
END;

CREATE TRIGGER IF NOT EXISTS evidence_no_delete
BEFORE DELETE ON evidence
BEGIN
  SELECT RAISE(ABORT, 'evidence rows are append-only');
END;

CREATE TRIGGER IF NOT EXISTS events_no_update
BEFORE UPDATE ON events
BEGIN
  SELECT RAISE(ABORT, 'event rows are append-only');
END;

CREATE TRIGGER IF NOT EXISTS events_no_delete
BEFORE DELETE ON events
BEGIN
  SELECT RAISE(ABORT, 'event rows are append-only');
END;

CREATE TRIGGER IF NOT EXISTS artifact_digest_no_update
BEFORE UPDATE OF sha256 ON artifacts
WHEN NEW.sha256 <> OLD.sha256
BEGIN
  SELECT RAISE(ABORT, 'artifact digest is identity and cannot change');
END;

CREATE INDEX IF NOT EXISTS idx_policy_eval_release ON policy_evaluations(release_id, evaluated_at);
CREATE INDEX IF NOT EXISTS idx_evidence_source_sha ON evidence_sources(source_sha256);
