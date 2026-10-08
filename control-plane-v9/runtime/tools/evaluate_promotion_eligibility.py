#!/usr/bin/env python3
from pathlib import Path
from contextlib import closing
import argparse, sqlite3, json, hashlib, datetime
from state_v9 import state_sha256


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def deadline_status(value, now):
    if value is None:
        return None
    try:
        deadline = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if deadline.tzinfo is None:
            return 'INVALID_EXPIRY'
        return 'EXPIRED' if deadline <= now else None
    except (ValueError, TypeError, AttributeError):
        return 'INVALID_EXPIRY'


def active_policy(con, raw=None):
    row = con.execute("SELECT policy_sha256,content_json FROM policy_documents WHERE policy_kind='promotion' AND active=1").fetchone()
    if not row or (raw is not None and hashlib.sha256(raw).hexdigest() != row[0]):
        raise ValueError('active promotion policy does not match supplied policy')
    policy = json.loads(raw if raw is not None else row[1])
    for target in ('CANDIDATE', 'STABLE'):
        roles = policy.get('approval_policy', {}).get(target)
        if not isinstance(roles, list) or not roles or not all(isinstance(x, str) and x for x in roles) or len(set(roles)) != len(roles):
            raise ValueError('invalid approval policy: ' + target)
    return policy


def profile_for(con, pol, rid):
    row = con.execute("SELECT r.project_id,r.track_id,p.policy_profile FROM releases r JOIN projects p ON p.project_id=r.project_id WHERE r.release_id=?", (rid,)).fetchone()
    if not row:
        raise ValueError('release not found')
    return pol.get('track_policy', {}).get(row[1]) or pol.get('project_policy', {}).get(row[0]) or row[2] or 'context_only'


def gate_status(con, rid, gate, now=None):
    now = now or utc_now()
    row = con.execute("""SELECT g.status,g.evidence_id,g.valid_until,e.status,e.subject_type,e.subject_id,e.evidence_type,e.valid_until
                         FROM gate_results g LEFT JOIN evidence e ON e.evidence_id=g.evidence_id
                         WHERE g.release_id=? AND g.gate_id=? ORDER BY g.assessed_at DESC,g.gate_result_id DESC LIMIT 1""", (rid, gate)).fetchone()
    if not row:
        return 'NOT_RUN', None
    status, eid = row[0], row[1]
    if status != 'PASS':
        return status, eid
    if not eid or row[3] != 'PASS' or row[4] != 'release' or row[5] != rid or row[6] != 'gate:' + gate:
        return 'INVALID_EVIDENCE', eid
    for value in (row[2], row[7]):
        invalid = deadline_status(value, now)
        if invalid:
            return invalid, eid
    return 'PASS', eid


def reasons_for(con, rid, gates, now=None):
    out = []
    for gate in gates:
        status, evidence = gate_status(con, rid, gate, now)
        if status != 'PASS':
            out.append({'gate': gate, 'status': status, 'evidence_id': evidence})
    return out


def eligibility_for(con, pol, rid, now=None):
    now = now or utc_now()
    profile = profile_for(con, pol, rid)
    if profile == 'context_only':
        return {'profile': profile, 'candidate_status': 'CONTEXT_ONLY', 'stable_status': 'CONTEXT_ONLY', 'candidate_reasons': [], 'stable_reasons': []}
    cfg = pol.get('profiles', {}).get(profile)
    groups = [cfg.get('candidate_gates'), cfg.get('stable_gates'), pol.get('global_stable_gates')] if isinstance(cfg, dict) else []
    if not groups or not all(isinstance(g, list) and g and all(isinstance(x, str) and x for x in g) for g in groups):
        reason = {'gate': 'policy_profile', 'status': 'INVALID_PROFILE', 'detail': profile}
        return {'profile': profile, 'candidate_status': 'NOT_ELIGIBLE', 'stable_status': 'NOT_ELIGIBLE', 'candidate_reasons': [reason], 'stable_reasons': [reason]}
    candidate = reasons_for(con, rid, cfg['candidate_gates'], now)
    stable = reasons_for(con, rid, cfg['candidate_gates'] + cfg['stable_gates'] + pol['global_stable_gates'], now)
    state = state_sha256(con)
    for d in con.execute("""SELECT dr.status,dr.reason,de.propagation_mode FROM dependency_results dr JOIN dependency_edges de ON de.edge_id=dr.edge_id
                            WHERE dr.consumer_release_id=? AND dr.input_state_sha256=? ORDER BY dr.edge_id""", (rid, state)):
        reason = {'gate': 'dependency_graph', 'status': d[0], 'detail': d[1]}
        if d[0] == 'BLOCKED_CANDIDATE' and d[2] in ('BLOCK_CANDIDATE', 'BLOCK_STABLE'):
            if d[2] == 'BLOCK_CANDIDATE':
                candidate.append(reason)
            stable.append(reason)
        elif d[0] == 'CANDIDATE_OK_STABLE_BLOCKED' and d[2] == 'BLOCK_STABLE':
            stable.append(reason)
    blockers = [x[0] for x in con.execute("SELECT code FROM blockers WHERE release_id=? AND status='ACTIVE'", (rid,))]
    if blockers:
        stable.append({'gate': 'active_blockers', 'status': 'BLOCKED', 'detail': blockers})
    return {'profile': profile, 'candidate_status': 'ELIGIBLE' if not candidate else 'NOT_ELIGIBLE', 'stable_status': 'ELIGIBLE' if not stable else 'NOT_ELIGIBLE', 'candidate_reasons': candidate, 'stable_reasons': stable}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('db'); ap.add_argument('--policy', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    raw = Path(a.policy).read_bytes(); policy_sha = hashlib.sha256(raw).hexdigest()
    with closing(sqlite3.connect(a.db)) as con:
        con.execute('PRAGMA foreign_keys=ON'); con.row_factory = sqlite3.Row
        pol = active_policy(con, raw)
        state = state_sha256(con); now = utc_now(); report = []
        for r in con.execute('SELECT * FROM releases ORDER BY project_id,track_id,version'):
            result = eligibility_for(con, pol, r['release_id'], now)
            payload = {'release_id': r['release_id'], 'policy_sha256': policy_sha, **result, 'state': state}
            eid = 'elig:' + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            dep_status = 'BLOCKED' if any(x.get('gate') == 'dependency_graph' for x in result['stable_reasons']) else 'CLEAR'
            con.execute("""INSERT OR IGNORE INTO promotion_eligibility(eligibility_id,release_id,evaluated_at,input_state_sha256,candidate_status,stable_status,
                           candidate_reasons_json,stable_reasons_json,dependency_status) VALUES(?,?,?,?,?,?,?,?,?)""",
                        (eid, r['release_id'], now.isoformat(), state, result['candidate_status'], result['stable_status'], json.dumps(result['candidate_reasons'], sort_keys=True), json.dumps(result['stable_reasons'], sort_keys=True), dep_status))
            report.append(payload)
        con.commit()
        Path(a.out).write_text(json.dumps({'schema_version': 1, 'policy_sha256': policy_sha, 'input_state_sha256': state, 'releases': report}, indent=2), encoding='utf-8')
        print('evaluated', len(report), 'candidate_eligible', sum(x['candidate_status'] == 'ELIGIBLE' for x in report), 'stable_eligible', sum(x['stable_status'] == 'ELIGIBLE' for x in report))


if __name__ == '__main__':
    main()
