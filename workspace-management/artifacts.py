"""Generate a curated deliverable catalogue independently of the full file inventory."""
import csv
from datetime import date
import hashlib
import html
import io
import json
from pathlib import Path
import re
from urllib.parse import quote, urlsplit

from registry import load_json, relative_path, safe_path

STAGES = {'main': 'main反映済み', 'pr': 'PR公開・main未反映', 'local': 'ローカル保存'}
KINDS = {'snapshot': 'ソースZIP', 'filter': '広告・追跡', 'font': '日本語表示', 'candidate': '候補', 'optional': '追加設定用'}
LOCAL = {'match': '記録と一致', 'changed': '内容変更・要再確認', 'missing': '未保存・公開先から取得', 'unchecked': '手元は未照合', 'blocked': '原本を参照できません'}
VERIFIED = {'passed': '検証合格', 'matched': '公開版の本文一致', 'pending': '未確認'}


def public_url(value, optional=False):
    if optional and value == '':
        return value
    if not isinstance(value, str):
        raise ValueError('URL must be a string')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.netloc not in {'github.com', 'raw.githubusercontent.com'}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not parsed.path.startswith('/') or any(ord(c) < 33 for c in value)):
        raise ValueError('invalid public artifact URL')
    return value


def digest(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid artifact SHA256')


def validate(data):
    if not isinstance(data, dict) or data.get('schema') != 'deliverable-catalog/v1':
        raise ValueError('invalid deliverable schema')
    if not isinstance(data.get('scope'), str) or not data['scope']:
        raise ValueError('deliverable scope is required')
    rows = data.get('artifacts')
    if not isinstance(rows, list) or not rows:
        raise ValueError('artifacts must be a nonempty array')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not re.fullmatch('[a-z][a-z0-9-]*', row['id']) or row['id'] in seen:
            raise ValueError('invalid or duplicate artifact id')
        seen.add(row['id'])
        if any(not isinstance(row.get(k), str) or not row[k] for k in ('name', 'version', 'purpose', 'notes')):
            raise ValueError('artifact descriptions are required')
        if not isinstance(row.get('kind'), str) or row['kind'] not in KINDS:
            raise ValueError('invalid artifact kind')
        relative_path(row.get('local_path'))
        digest(row.get('sha256'))
        if type(row.get('bytes')) is not int or row['bytes'] < 0:
            raise ValueError('invalid artifact size')
        publication, verification = row.get('publication'), row.get('verification')
        if not isinstance(publication, dict) or not isinstance(publication.get('stage'), str) or publication['stage'] not in STAGES:
            raise ValueError('invalid artifact publication')
        public_url(publication.get('url'), optional=publication['stage'] == 'local')
        public_url(publication.get('pr_url'), optional=publication['stage'] != 'pr')
        commit = publication.get('commit')
        if publication['stage'] != 'local' and (not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}', commit)):
            raise ValueError('published artifact requires a fixed commit')
        if publication['stage'] != 'local' and ('/' + commit + '/') not in publication['url']:
            raise ValueError('artifact URL must reference its fixed commit')
        if not isinstance(verification, dict) or not isinstance(verification.get('status'), str) or verification['status'] not in VERIFIED:
            raise ValueError('invalid artifact verification')
        if not isinstance(verification.get('summary'), str) or not verification['summary']:
            raise ValueError('verification scope is required')
        if not isinstance(verification.get('checked_on'), str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', verification['checked_on']):
            raise ValueError('verification date is required')
        try:
            date.fromisoformat(verification['checked_on'])
        except ValueError as error:
            raise ValueError('invalid verification date') from error
        public_url(verification.get('evidence_url'), optional=True)
        if verification['status'] != 'pending' and verification.get('sha256') != row['sha256']:
            raise ValueError('verification refers to a different artifact')
    baseline = data.get('baseline')
    if baseline is not None:
        if not isinstance(baseline, dict) or not isinstance(baseline.get('label'), str) or not baseline['label'] or not isinstance(baseline.get('items'), list):
            raise ValueError('invalid artifact baseline')
        ids = set()
        for item in baseline['items']:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not re.fullmatch('[a-z][a-z0-9-]*', item['id']) or item['id'] in ids:
                raise ValueError('invalid or duplicate baseline id')
            ids.add(item['id'])
            if any(not isinstance(item.get(k), str) or not item[k] for k in ('name', 'version')):
                raise ValueError('invalid baseline description')
            digest(item.get('sha256'))
    return data


def load(path):
    return validate(load_json(path))


def changes(data):
    validate(data)
    baseline = data.get('baseline')
    if baseline is None:
        return {'baseline': '比較対象未登録', 'added': [], 'changed': [], 'removed': []}
    old = {r['id']: r for r in baseline['items']}
    new = {r['id']: r for r in data['artifacts']}
    return {'baseline': baseline['label'],
            'added': [new[k]['name'] for k in sorted(new.keys() - old.keys())],
            'removed': [old[k]['name'] for k in sorted(old.keys() - new.keys())],
            'changed': [{'id': k, 'name': new[k]['name'], 'before': old[k]['version'], 'after': new[k]['version']}
                        for k in sorted(old.keys() & new.keys())
                        if any(old[k][field] != new[k][field] for field in ('version', 'sha256'))]}


def records(data, root=None):
    validate(data)
    result = []
    for original in data['artifacts']:
        row = dict(original, local_state='unchecked', actual_sha256=None)
        if root is not None:
            try:
                path = safe_path(root, row['local_path'])
                row['local_state'] = 'missing'
                if path.is_file():
                    with path.open('rb') as stream:
                        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
                    row['actual_sha256'] = actual
                    row['local_state'] = 'match' if actual == row['sha256'] and path.stat().st_size == row['bytes'] else 'changed'
                elif path.exists():
                    row['local_state'] = 'blocked'
            except (OSError, ValueError):
                row['local_state'] = 'blocked'
        result.append(row)
    return result


def spreadsheet(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


def views(data, root=None, standalone=False):
    rows = records(data, root)
    delta = changes(data)
    headers = ['成果物', '用途', '版', '公開状況', '公開版の検証', '確認日', '生成時の手元確認', '公開先', 'SHA256', 'サイズ']
    cells = [[r['name'], r['purpose'], r['version'], STAGES[r['publication']['stage']],
              r['verification']['summary'], r['verification']['checked_on'], LOCAL[r['local_state']],
              r['publication']['url'], r['sha256'], str(r['bytes'])] for r in rows]
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows([spreadsheet(v) for v in row] for row in cells)
    def md(value):
        return html.escape(str(value)).replace('|', '&#124;').replace('\n', '<br>')
    md_headers = ['成果物・用途', '版', '公開状況', '公開版の検証・確認日', '生成時の手元', '取得先']
    markdown = ['# 成果物一覧', '', md(data['scope']), '', '| ' + ' | '.join(md_headers) + ' |', '| ' + ' | '.join(['---'] * len(md_headers)) + ' |']
    for row in rows:
        download = '[公開版](' + row['publication']['url'] + ')' if row['publication']['url'] else '—'
        markdown.append('| ' + ' | '.join([md(row['name']) + '<br>' + md(row['purpose']), md(row['version']),
                         md(STAGES[row['publication']['stage']]), md(row['verification']['summary']) + '<br>' + row['verification']['checked_on'],
                         md(LOCAL[row['local_state']]), download]) + ' |')
    markdown += ['', '## 前回からの変更', '', md(delta['baseline']), '',
                 '追加 ' + str(len(delta['added'])) + '件・変更 ' + str(len(delta['changed'])) + '件・登録解除 ' + str(len(delta['removed'])) + '件。登録解除は原本の削除を意味しません。']
    markdown += ['- ' + md(c['name']) + '：' + md(c['before']) + ' → ' + md(c['after']) for c in delta['changed']]
    markdown += ['', '## サイズ・SHA256', '']
    for row in rows:
        markdown += ['<details><summary>' + md(row['name']) + '</summary>', '',
                     format(row['bytes'], ',') + ' bytes', '', '`' + row['sha256'] + '`', '',
                     md(row['notes']), '', '</details>', '']
    cards = []
    esc = html.escape
    for row in rows:
        publication, verification = row['publication'], row['verification']
        links = '<a href="' + esc(publication['url'], quote=True) + '">公開版を取得</a>' if publication['url'] else ''
        if publication['pr_url']:
            links += ' <a href="' + esc(publication['pr_url'], quote=True) + '">公開PR</a>'
        if verification['evidence_url']:
            links += ' <a href="' + esc(verification['evidence_url'], quote=True) + '">検証記録</a>'
        if root is not None and row['local_state'] == 'match' and not standalone:
            links += ' <a href="../../' + quote(row['local_path']) + '">手元の原本</a>'
        cards.append('<article data-stage="' + publication['stage'] + '" data-kind="' + row['kind'] + '" data-local="' + row['local_state'] + '"><p class="badges"><span>' + esc(KINDS[row['kind']]) + '</span><span>' + esc(STAGES[publication['stage']]) + '</span></p><h2>' + esc(row['name']) + '</h2><p>' + esc(row['purpose']) + '</p><dl><dt>版</dt><dd>' + esc(row['version']) + '</dd><dt>公開版の検証</dt><dd>' + esc(VERIFIED[verification['status']]) + '<br>' + esc(verification['summary']) + '</dd><dt>確認日</dt><dd>' + verification['checked_on'] + '</dd><dt>生成時の手元</dt><dd>' + esc(LOCAL[row['local_state']]) + '</dd></dl><p class="notes">' + esc(row['notes']) + '</p><p class="actions">' + links + '</p><details><summary>サイズ・SHA256・原本パス</summary><p>' + format(row['bytes'], ',') + ' bytes</p><code>' + row['sha256'] + '</code><p><code>' + esc(row['local_path']) + '</code></p></details></article>')
    nav = '<a href="inventory.html">全ファイル</a><a href="tools.html">ツール</a><a href="projects.html">製品</a><a href="../INTEGRATION.md">統合・更新案</a>' if not standalone else '<a href="README.md">使い方</a><a href="TOOL-IMPROVEMENTS.md">統合・更新案</a>'
    source = 'artifacts-source.json' if standalone else '../artifacts.json'
    counts = '<span>成果物 <strong>' + str(len(rows)) + '</strong></span>' + ''.join('<span>' + esc(label) + ' <strong>' + str(sum(r['publication']['stage'] == key for r in rows)) + '</strong></span>' for key, label in STAGES.items())
    delta_html = '<p>' + esc(delta['baseline']) + '：追加 ' + str(len(delta['added'])) + '件・変更 ' + str(len(delta['changed'])) + '件・登録解除 ' + str(len(delta['removed'])) + '件</p><ul>' + ''.join('<li>' + esc(c['name']) + '：' + esc(c['before']) + ' → ' + esc(c['after']) + '</li>' for c in delta['changed']) + '</ul>'
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>成果物一覧</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#18304b;font-family:system-ui,sans-serif;line-height:1.7}main{max-width:1240px;margin:auto;padding:28px 20px}a{color:#075bb5}nav,.summary,.toolbar,.actions{display:flex;gap:12px;flex-wrap:wrap}h1{font-size:30px}h2{font-size:21px;line-height:1.5}.summary{margin:22px 0}.summary span,article,.change{background:white;border:1px solid #d6e1ed;border-radius:12px;padding:18px}.note{background:#e8f1ff;border-radius:12px;padding:18px}.toolbar{margin:20px 0}input,select,button{font:inherit;padding:10px;border:1px solid #c9d5e5;border-radius:8px;background:white}input{flex:1;min-width:180px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:16px}.grid article[hidden]{display:none}article{min-width:0;overflow-wrap:anywhere}.badges{display:flex;gap:8px;flex-wrap:wrap}.badges span{background:#edf2f8;border-radius:6px;padding:3px 8px;font-size:13px}article[data-stage=main] .badges span:last-child{background:#e6f5ed;color:#20633d}article[data-stage=pr] .badges span:last-child{background:#fff2d9;color:#7c5100}dl{display:grid;grid-template-columns:110px 1fr;gap:8px}dt{color:#52657b}dd{margin:0}.notes{font-size:14px;color:#52657b}code{font-size:12px;overflow-wrap:anywhere}summary{cursor:pointer}.change{margin-top:24px}#empty{display:none}@media(max-width:600px){main{padding:20px 12px}.toolbar>*{max-width:100%}h1{font-size:26px}dl{grid-template-columns:96px 1fr}.summary span{padding:10px}}@media print{nav,.toolbar,.actions{display:none}body{background:white}main{max-width:none}.grid{display:block}article{break-inside:avoid;margin-bottom:14px}}</style><main><nav>__NAV__<a href="artifacts.csv" download>CSV保存</a></nav><h1>成果物一覧</h1><p class="note">__SCOPE__</p><div class="summary">__COUNTS__</div><p>確認日は記録時点の日付です。「生成時の手元」は一覧を作成したワークスペースの照合結果で、閲覧端末の診断ではありません。</p><div class="toolbar"><input id="query" type="search" aria-label="成果物検索" placeholder="名前・用途・版・SHA256で検索"><select id="stage" aria-label="公開状況"><option value="">公開状況すべて</option value="main">main反映済み</option><option value="pr">PR公開・main未反映</option><option value="local">ローカル保存</option></select><select id="kind" aria-label="成果物の種類"><option value="">種類すべて</option>__KINDS__</select><button id="reset">条件を解除</button></div><p id="count" aria-live="polite"></p><p id="empty">一致する成果物がありません。</p><div class="grid">__CARDS__</div><section class="change"><h2>前回からの変更</h2>__DELTA__<p>版・本文のSHA256を固定した比較対象と照合しています。登録解除は原本の削除を意味しません。</p></section><p><a href="artifacts.md">Markdown一覧</a> · <a href="__SOURCE__">一覧の正本</a></p></main><script>
const query=document.querySelector('#query'),stage=document.querySelector('#stage'),kind=document.querySelector('#kind'),rows=[...document.querySelectorAll('article')];function render(){let count=0;for(const row of rows){const show=(!stage.value||row.dataset.stage===stage.value)&&(!kind.value||row.dataset.kind===kind.value)&&row.textContent.toLocaleLowerCase().includes(query.value.toLocaleLowerCase());row.hidden=!show;if(show)count++}document.querySelector('#count').textContent=count+'件 / 全'+rows.length+'件';document.querySelector('#empty').style.display=count?'none':'block'}query.addEventListener('input',render);stage.addEventListener('change',render);kind.addEventListener('change',render);document.querySelector('#reset').addEventListener('click',()=>{query.value='';stage.value='';kind.value='';render()});render();
</script></html>'''
    substitutions = {'__NAV__': nav, '__SCOPE__': esc(data['scope']), '__COUNTS__': counts, '__CARDS__': ''.join(cards), '__DELTA__': delta_html,
                     '__SOURCE__': source, '__KINDS__': ''.join('<option value="' + key + '">' + esc(label) + '</option>' for key, label in KINDS.items())}
    page = re.sub(r'__(?:NAV|SCOPE|COUNTS|CARDS|DELTA|SOURCE|KINDS)__', lambda match: substitutions[match.group(0)], page)
    return {'artifacts.html': page + '\n', 'artifacts.md': '\n'.join(markdown) + '\n', 'artifacts.csv': '\ufeff' + stream.getvalue(),
            'artifacts.json': json.dumps({'schema': 'deliverable-catalog-view/v1', 'scope': data['scope'], 'artifacts': rows, 'changes': delta}, ensure_ascii=False, indent=2) + '\n'}
