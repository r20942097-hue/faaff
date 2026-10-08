PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL,
  migration_sha256 TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS remote_sources (
  source_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  repository TEXT,
  ref TEXT,
  commit_sha TEXT,
  source_state TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS remote_observations (
  observation_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES remote_sources(source_id),
  object_type TEXT NOT NULL,
  project_id TEXT REFERENCES projects(project_id),
  track_id TEXT REFERENCES tracks(track_id),
  version TEXT,
  artifact_sha256 TEXT,
  status TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  UNIQUE(source_id, object_type, project_id, track_id, version, artifact_sha256, payload_sha256)
);

CREATE TABLE IF NOT EXISTS external_components (
  component_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT,
  artifact_sha256 TEXT,
  verification_state TEXT NOT NULL,
  source_ref TEXT,
  metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dependency_edges (
  edge_id TEXT PRIMARY KEY,
  consumer_release_id TEXT NOT NULL REFERENCES releases(release_id),
  provider_kind TEXT NOT NULL CHECK(provider_kind IN ('PROJECT','EXTERNAL_COMPONENT')),
  provider_project_id TEXT REFERENCES projects(project_id),
  provider_track_id TEXT REFERENCES tracks(track_id),
  provider_component_id TEXT REFERENCES external_components(component_id),
  version_constraint TEXT,
  requirement TEXT NOT NULL,
  propagation_mode TEXT NOT NULL,
  optional INTEGER NOT NULL DEFAULT 0 CHECK(optional IN (0,1)),
  metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dependency_results (
  result_id TEXT PRIMARY KEY,
  consumer_release_id TEXT NOT NULL REFERENCES releases(release_id),
  edge_id TEXT NOT NULL REFERENCES dependency_edges(edge_id),
  status TEXT NOT NULL,
  provider_state TEXT,
  provider_decision TEXT,
  provider_release_id TEXT,
  evaluated_at TEXT NOT NULL,
  input_state_sha256 TEXT NOT NULL,
  reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promotion_eligibility (
  eligibility_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL REFERENCES releases(release_id),
  evaluated_at TEXT NOT NULL,
  input_state_sha256 TEXT NOT NULL,
  candidate_status TEXT NOT NULL,
  stable_status TEXT NOT NULL,
  candidate_reasons_json TEXT NOT NULL,
  stable_reasons_json TEXT NOT NULL,
  dependency_status TEXT,
  UNIQUE(release_id, input_state_sha256)
);

CREATE TABLE IF NOT EXISTS promotion_plans (
  plan_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL REFERENCES releases(release_id),
  target_stage TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  input_state_sha256 TEXT NOT NULL,
  input_eligibility_id TEXT REFERENCES promotion_eligibility(eligibility_id),
  required_approvals_json TEXT NOT NULL,
  preconditions_json TEXT NOT NULL,
  actions_json TEXT NOT NULL,
  plan_sha256 TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS promotion_plan_approvals (
  plan_id TEXT NOT NULL REFERENCES promotion_plans(plan_id),
  role TEXT NOT NULL,
  actor TEXT NOT NULL,
  approved_at TEXT NOT NULL,
  note TEXT,
  PRIMARY KEY(plan_id, role, actor)
);

CREATE TABLE IF NOT EXISTS adapter_plans (
  adapter_plan_id TEXT PRIMARY KEY,
  promotion_plan_id TEXT REFERENCES promotion_plans(plan_id),
  adapter_type TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  preconditions_json TEXT NOT NULL,
  actions_json TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  plan_sha256 TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS reconciliation_proposals (
  proposal_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  from_release_id TEXT REFERENCES releases(release_id),
  to_release_id TEXT REFERENCES releases(release_id),
  status TEXT NOT NULL,
  reason TEXT NOT NULL,
  source_observations_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  applied_at TEXT,
  input_state_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shadow_diffs (
  diff_id TEXT PRIMARY KEY,
  baseline_name TEXT NOT NULL,
  baseline_sha256 TEXT,
  compared_state_sha256 TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  diff_json TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dependency_edge_unique
ON dependency_edges(consumer_release_id, provider_kind,
  COALESCE(provider_project_id,''), COALESCE(provider_track_id,''),
  COALESCE(provider_component_id,''), COALESCE(version_constraint,''), requirement);

CREATE INDEX IF NOT EXISTS idx_remote_obs_project ON remote_observations(project_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_dependency_consumer ON dependency_edges(consumer_release_id);
CREATE INDEX IF NOT EXISTS idx_dependency_result_consumer ON dependency_results(consumer_release_id, evaluated_at);
CREATE INDEX IF NOT EXISTS idx_promotion_release ON promotion_eligibility(release_id, evaluated_at);
