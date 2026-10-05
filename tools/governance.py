"""Strict validation for the bundled JSON Schema subset; no external dependencies.
Evidence integrity and binding are checked. A local record is not a signed attestation.
"""
import hashlib
import json
import re
import stat
import zipfile
from datetime import date
from pathlib import Path, PurePosixPath
ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT/'project_registry.json' if (ROOT/'project_registry.json').is_file() else ROOT/'docs/project_registry.json'
class Invalid(ValueError): pass

def load(path):
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d: raise Invalid('duplicate JSON key: ' + k)
            d[k] = v
        return d
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda v: (_ for _ in ()).throw(Invalid('invalid number: ' + v)))
    except (OSError, ValueError) as e: raise Invalid(str(e)) from e

def validate(value, schema, path='$'):
    if 'anyOf' in schema:
        for choice in schema['anyOf']:
            try: validate(value, choice, path); return
            except Invalid: pass
        raise Invalid(path + ': no allowed type matches')
    if 'const' in schema and (type(value) is not type(schema['const']) or value != schema['const']):
        raise Invalid(path + ': invalid constant')
    if 'enum' in schema and not any(type(value) is type(v) and value == v for v in schema['enum']):
        raise Invalid(path + ': invalid enum')
    types = {'object':dict,'array':list,'string':str,'integer':int,'boolean':bool,'null':type(None)}
    if 'type' in schema and type(value) is not types[schema['type']]: raise Invalid(path + ': invalid type')
    if isinstance(value, dict):
        missing = set(schema.get('required', [])) - value.keys()
        if missing: raise Invalid(path + ': missing ' + ', '.join(sorted(missing)))
        props = schema.get('properties', {})
        if schema.get('additionalProperties') is False and value.keys() - props.keys():
            raise Invalid(path + ': unknown keys ' + ', '.join(sorted(value.keys() - props.keys())))
        for key in value.keys() & props.keys(): validate(value[key], props[key], path + '.' + key)
    elif isinstance(value, list):
        if len(value) < schema.get('minItems', 0): raise Invalid(path + ': empty array')
        for i, item in enumerate(value):
            if 'items' in schema: validate(item, schema['items'], f'{path}[{i}]')
    elif isinstance(value, str):
        if len(value) < schema.get('minLength', 0): raise Invalid(path + ': empty string')
        if 'pattern' in schema and not re.fullmatch(schema['pattern'], value): raise Invalid(path + ': invalid format')
    elif type(value) is int and value < schema.get('minimum', value): raise Invalid(path + ': below minimum')

def schema_check(value, name): validate(value, load(ROOT / 'schemas' / name))

def validate_registry(d):
    schema_check(d, 'project-registry.schema.json')
    try: date.fromisoformat(d['updated'])
    except ValueError: raise Invalid('invalid updated date')
    seen = set()
    for p in d['projects']:
        if p['id'] in seen: raise Invalid('duplicate project: ' + p['id'])
        seen.add(p['id'])
        if p['state'] == 'STABLE' and (p['stable'] is None or p['decision'] != 'GO'):
            raise Invalid(p['id'] + ': STABLE requires stable reference and GO')
    return d

SEMVER = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?')
def validate_manifest(d):
    schema_check(d, 'release-manifest.schema.json')
    m = SEMVER.fullmatch(d['version'])
    if not m or (m[4] and any(x.isdigit() and len(x)>1 and x[0]=='0' for x in m[4].split('.'))):
        raise Invalid('version must be SemVer 2.0.0')
    if not d['example'] and any(d[x]['sha256'] == '0'*64 for x in ['source','artifact']):
        raise Invalid('placeholder hash forbidden')
    if d['state']=='STABLE' and (m[4] or d['blockers'] or d['release_decision']!='GO'):
        raise Invalid('STABLE claim conflicts with prerelease, blockers or decision')
    return d

def safe_file(base, name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or not p.parts:
        raise Invalid('unsafe relative path: ' + name)
    base = Path(base).resolve()
    target = base.joinpath(*p.parts)
    for part in [target, *target.parents]:
        if part == base: break
        if part.is_symlink(): raise Invalid('symlink forbidden: ' + name)
    if not target.resolve().is_relative_to(base) or not target.is_file(): raise Invalid('missing/unsafe file: ' + name)
    return target

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def zip_check(path):
    with zipfile.ZipFile(path) as z:
        seen=set(); folded=set(); total=0
        for i in z.infolist():
            name=i.filename; p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or not p.parts:
                raise Invalid('unsafe ZIP entry: ' + name)
            key=str(p)
            if key in seen or key.casefold() in folded: raise Invalid('duplicate/case-collision ZIP entry: '+name)
            seen.add(key);folded.add(key.casefold())
            if stat.S_ISLNK(i.external_attr >> 16) or i.flag_bits & 1: raise Invalid('symlink/encrypted ZIP entry: '+name)
            total+=i.file_size
            if total>512*1024*1024 or len(seen)>10000: raise Invalid('ZIP resource limit exceeded')
        bad=z.testzip()
        if bad: raise Invalid('ZIP CRC failure: '+bad)

def verify_identity(d, base):
    for label, name in [('source',d['source']['path']),('artifact',d['artifact']['filename'])]:
        p=safe_file(base,name)
        if digest(p)!=d[label]['sha256']: raise Invalid(label + ': SHA-256 mismatch')
        if label=='artifact' and p.stat().st_size!=d[label]['size_bytes']: raise Invalid('artifact: size mismatch')
        if p.suffix.lower()=='.zip': zip_check(p)

def verify_gate(d, base, gate):
    ref=d['evidence'][gate]
    if ref is None: raise Invalid(gate + ': evidence missing')
    path=safe_file(base,ref['path'])
    if digest(path)!=ref['sha256']: raise Invalid(gate+': record SHA-256 mismatch')
    rec=load(path);schema_check(rec,'evidence.schema.json')
    for k,v in [('product_id',d['product_id']),('version',d['version']),('artifact_sha256',d['artifact']['sha256']),('source_sha256',d['source']['sha256']),('gate',gate)]:
        if rec[k]!=v: raise Invalid(gate+': evidence binding mismatch: '+k)
    if gate in {'sbom','provenance'}:
        payload=rec['payload']
        if payload is None: raise Invalid(gate+': payload required')
        data_path=safe_file(base,payload['path'])
        if digest(data_path)!=payload['sha256']: raise Invalid(gate+': payload digest mismatch')
        data=load(data_path)
        if type(data) is not dict: raise Invalid(gate+': payload must be object')
        if gate=='sbom':
            metadata=data.get('metadata')
            if type(metadata) is not dict or type(metadata.get('component')) is not dict: raise Invalid('SBOM metadata invalid')
            component=metadata['component']
            if data.get('bomFormat')!='CycloneDX' or data.get('specVersion')!='1.7' or component.get('name')!=d['product_id'] or component.get('version')!=d['version'] or type(data.get('components')) is not list:
                raise Invalid('SBOM format/product binding mismatch')
        else:
            if data.get('_type')!='https://in-toto.io/Statement/v1' or data.get('predicateType')!='https://slsa.dev/provenance/v1' or type(data.get('predicate')) is not dict:
                raise Invalid('provenance format mismatch')
            subjects=data.get('subject')
            if type(subjects) is not list or not any(type(x) is dict and x.get('name')==d['artifact']['filename'] and type(x.get('digest')) is dict and x['digest'].get('sha256')==d['artifact']['sha256'] for x in subjects):
                raise Invalid('provenance subject mismatch')

POLICY_KEYS={'schema_version','candidate_gates','risk_classes'}
def policy_check(p):
    gates=set(load(ROOT/'schemas/evidence.schema.json')['properties']['gate']['enum'])
    if type(p) is not dict or set(p)!=POLICY_KEYS or type(p['schema_version']) is not int or p['schema_version']!=1:
        raise Invalid('invalid promotion policy')
    if type(p['candidate_gates']) is not list or any(type(g) is not str for g in p['candidate_gates']) or set(p['candidate_gates'])!=gates-{'real_environment','rollback'}:
        raise Invalid('candidate policy gates incomplete')
    if type(p['risk_classes']) is not dict or not p['risk_classes']: raise Invalid('risk policy missing')
    for r,c in p['risk_classes'].items():
        if type(c) is not dict or set(c)!={'stable_gates'} or type(c['stable_gates']) is not list or any(type(g) is not str or g not in gates for g in c['stable_gates']):
            raise Invalid('invalid risk policy: '+r)
    return p

def promotion(d, base, policy):
    validate_manifest(d);policy_check(policy)
    if d['risk_class'] not in policy['risk_classes']: raise Invalid('unknown risk class')
    failures=[]
    if d['example']: failures.append('example manifest cannot qualify')
    try: verify_identity(d,base)
    except (Invalid, zipfile.BadZipFile, OSError) as e: failures.append(str(e))
    for gate in policy['candidate_gates']:
        try: verify_gate(d,base,gate)
        except Invalid as e: failures.append(str(e))
    failures += [b['reason'] for b in d['blockers'] if b['scope']=='candidate']
    if failures: return {'decision':'DEV_OR_NO_GO','reasons':failures}
    stable_failures=[b['reason'] for b in d['blockers'] if b['scope']=='stable']
    if d['release_decision']!='GO': stable_failures.append('release_decision must be GO')
    if SEMVER.fullmatch(d['version'])[4]: stable_failures.append('prerelease cannot qualify as STABLE')
    for gate in policy['risk_classes'][d['risk_class']]['stable_gates']:
        try: verify_gate(d,base,gate)
        except Invalid as e: stable_failures.append(str(e))
    return {'decision':'CANDIDATE_ELIGIBLE' if stable_failures else 'STABLE_ELIGIBLE','reasons':stable_failures}

def retention(d):
    validate_registry(d)
    keys=['latest_observed','product_verified','integration_verified','stable','previous_known_good']
    return {'mode':'plan_only','projects':[{'id':p['id'],'keep_refs':sorted({p[k] for k in keys if p[k]}),'archive_candidates':[], 'unresolved':'Artifact inventory and unique evidence checks required before archive.'} for p in d['projects']]}

def render_index(d):
    validate_registry(d)
    lines=['# PROJECT_INDEX','', 'Updated: '+d['updated']+' | Policy: '+d['policy_version'], '', 'Baseline imported from v3. Selective product revalidation: WP10 0.38.0 and Suite 0.51.0; YouTube dev70 integrity/report audit. Other references remain inherited. See PORTFOLIO_AUDIT.md.', '', '| Project | Observed | Product verified | Integration verified | Stable | Previous known-good | State | Decision |','|---|---|---|---|---|---|---|---|']
    keys=['id','latest_observed','product_verified','integration_verified','stable','previous_known_good','state','decision']
    for p in d['projects']: lines.append('| '+' | '.join(str(p[k] or '—').replace('|','\\|').replace('\n',' ') for k in keys)+' |')
    return '\n'.join(lines)+'\n'

