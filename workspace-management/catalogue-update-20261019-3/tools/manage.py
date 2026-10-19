"""Build and verify the workspace catalogue using only Python's standard library."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".aws", ".codex", ".agents", "__pycache__", ".pytest_cache", ".venv", ".cache", "node_modules"}


def category(path):
    parts = path.parts
    if path.suffix == ".txt" and ("filters" in parts or len(parts) == 1 or parts[0] == "v2") and not path.name.startswith("requirements") and path.name != "SHA256-v6.10.0.txt":
        return "フィルター"
    if "experimental" in parts:
        return "実験候補"
    if ".github" in parts:
        return "CI・保守"
    if "scripts" in parts or "tests" in parts or path.suffix == ".py":
        return "検証・管理コード"
    if (path.name.startswith("requirements") and path.suffix == ".txt") or path.name in {"pyproject.toml", "requirements.txt", "requirements-verification.txt", "requirements-verification.lock.txt", "python-lock.json", "selenium-lock.json", "extension-lock.json", "package.json", "package-lock.json"}:
        return "ライブラリ設定"
    if path.suffix == ".html":
        return "案内ページ"
    return "資料"


def scan(root, config):
    from configuration import validate
    validate(root, config)
    rows = []
    for source in config["sources"]:
        base = root / source["path"]
        if not base.is_dir() or base.is_symlink() or not base.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"invalid source directory: {source['path']}")
        for directory, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not (Path(directory) / d).is_symlink())
            if 'include' in source:
                dirs[:] = []
            for name in sorted(files):
                path = Path(directory) / name
                if (name in EXCLUDED or path.is_symlink() or not path.is_file()
                        or name.startswith('.env') or path.suffix in {'.pyc', '.pyo'}):
                    continue
                relative = path.relative_to(base)
                if 'include' in source and relative.as_posix() not in source['include']:
                    continue
                with path.open('rb') as handle:
                    digest = hashlib.file_digest(handle, 'sha256').hexdigest()
                # Library archives may be large; hash in chunks and inspect only headers.
                text = ''
                if path.suffix == '.txt':
                    with path.open('rb') as handle:
                        text = handle.read(65536).decode('utf-8', errors='replace')
                version = re.search(r'(?:^|[\r\n])! Version:[ \t]*([^\r\n]*)', text)
                license_match = re.search(r'(?:^|[\r\n])! License:[ \t]*([^\r\n]*)', text)
                cls = 'ライブラリ・資料' if source.get('kind') == 'library' else category(relative)
                state = '候補' if cls == 'フィルター' and relative.parts[0] == 'v2' else ('実験候補' if cls == '実験候補' else '現行' if cls == 'フィルター' else '資料・設定')
                if cls == 'フィルター' and re.search(r'(?:^|[\r\n])! Status:[ \t]*optional-external[ \t]*(?=[\r\n]|$)', text):
                    state = '追加設定が必要'
                row = {'source': source['name'], 'path': relative.as_posix(), 'category': cls,
                       'state': state, 'version': version.group(1).strip(' \t') if version else '',
                       'license': license_match.group(1).strip(' \t') if license_match else '',
                       'bytes': path.stat().st_size, 'sha256': digest,
                       'original': path.relative_to(root).as_posix(),
                       'url': f"{source['repository']}/blob/{source.get('repository_ref', 'main')}/{quote(relative.as_posix())}" if source.get('repository') else ''}
                row['catalogue_path'] = link_path(row)
                rows.append(row)
    return sorted(rows, key=lambda row: (row['source'], row['path']))


def group(row):
    cls = row['category']
    if cls == 'フィルター':
        if row['state'] == '候補':
            return 'artifacts/filters/candidates'
        if row['state'] == '追加設定が必要':
            return 'artifacts/filters/optional'
        return 'artifacts/filters/current'
    return {'実験候補': 'artifacts/experimental', '案内ページ': 'artifacts/pages',
            'ライブラリ設定': 'libraries/configuration', '検証・管理コード': 'verification',
            'CI・保守': 'automation'}.get(cls, 'documentation')


def link_path(row):
    return f"{group(row)}/{row['source']}/{row['path']}"


def csv_text(rows, direct=False):
    from artifacts import spreadsheet
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['出典', '分類', 'ファイル', '状態', 'バージョン', 'ライセンス', 'バイト数', 'SHA256', '整理先', 'GitHub参照URL'])
    for row in rows:
        values = [row[k] for k in ('source', 'category', 'path', 'state', 'version', 'license', 'bytes', 'sha256')] + [row['original'] if direct else link_path(row), row['url']]
        writer.writerow([spreadsheet(value) for value in values])
    return '\ufeff' + stream.getvalue()


def markdown(rows, direct=False):
    def cell(value):
        text = html.escape(str(value)).replace('\r\n', '\n').replace('\r', '\n')
        for character, entity in [('|', '&#124;'), ('[', '&#91;'), (']', '&#93;'), ('`', '&#96;')]:
            text = text.replace(character, entity)
        return text.replace('\n', '<br>')
    lines = ['# ライブラリ・成果物カタログ', '', f'登録ファイル：**{len(rows)}件**。`python tools/manage.py build` で更新します。', '',
             '録画ツールの実行ソース・ZIP、Windows実機テストは未確認。状態はローカル確認に基づきます。', '',
             '| 出典 | ファイル数 |', '|---|---:|']
    for source in sorted({r['source'] for r in rows}):
        lines.append(f"| {source} | {sum(r['source'] == source for r in rows)} |")
    for source in sorted({r['source'] for r in rows}):
        lines += ['', f'## {source}', '', '| 分類 | ファイル | 状態 | バージョン |', '|---|---|---|---|']
        for row in rows:
            if row['source'] == source:
                target = '../../' + quote(row['original']) if direct else '../' + quote(link_path(row))
                lines.append(f"| {cell(row['category'])} | [{cell(row['path'])}]({target}) | {cell(row['state'])} | {cell(row['version'] or '—')} |")
    return '\n'.join(lines) + '\n'


def html_page(rows, direct=False, show_artifacts=False):
    # Escaping < also prevents an uploaded filename from closing the script element.
    data = json.dumps(rows, ensure_ascii=False).replace('<', '\\u003c')
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>統合カタログ</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#18304b;font-family:system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:32px 20px}h1{font-size:32px}h2{font-size:21px;margin-top:30px}.muted{color:#52657b;line-height:1.8}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card,.note{background:white;border:1px solid #d8e2ee;border-radius:14px;padding:20px}.num{font-size:30px;font-weight:bold}.note{margin-top:18px;line-height:1.8}.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}input,select,button{font:inherit;padding:12px;border:1px solid #c9d5e5;border-radius:8px;background:white}input{flex:1;min-width:220px}button{cursor:pointer}.table{overflow:auto;background:white;border:1px solid #d8e2ee;border-radius:12px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:12px;border-bottom:1px solid #e4eaf2}th{background:#eaf0f7;white-space:nowrap}td.file{min-width:240px;overflow-wrap:anywhere}a{color:#225eba}tr:hover{background:#f6faff}.pill{white-space:nowrap;background:#eef2fa;border-radius:6px;padding:3px 7px}.links{display:flex;gap:18px;flex-wrap:wrap} @media(max-width:600px){.cards{grid-template-columns:1fr}.card{display:flex;justify-content:space-between;align-items:center}.num{font-size:25px}h1{font-size:26px}}@media print{.toolbar,button{display:none}body{background:white}.table{overflow:visible}main{padding:0}}
</style><main><p class="muted">WORKSPACE CATALOG · ローカル管理</p><h1>ライブラリ・成果物・設定一覧</h1><p class="muted">sはフィルター中心、faaffは録画ツールの管理資料とフィルター。ライブラリ保存先と共通管理ツールも一覧に含めます。</p><div class="cards"><div class="card">リポジトリ<div class="num">2</div></div><div class="card">登録ファイル<div class="num">__COUNT__</div></div><div class="card">フィルター<div class="num">__FILTERS__</div></div></div>
<div class="note"><strong>完成状況</strong><br>一覧の自動生成とローカル検証を整備しました。録画ツールの実行ソース・ZIPとWindows実機検証は未確認です。候補フィルターは現行版と区別してください。<br><a href="tools.html">ツール一覧・実行状況</a> · <a href="libraries.html">ライブラリ一覧</a> · <a href="filters.html">フィルターの選び方・一覧表</a> · <a href="../ADBLOCK-UPDATE.md">広告ブロック更新・比較表</a> · <a href="../REPORT.md">統合案・改良内容・残課題</a> · <a href="../results/latest.json">最新のテスト結果</a></div>
<h2>ファイルを探す</h2><div class="toolbar"><input id="query" type="search" aria-label="ファイル検索" placeholder="名前・バージョン・ライセンスで検索"><select id="source" aria-label="出典"><option value="">すべての出典</option></select><select id="category" aria-label="分類"><option value="">すべての分類</option></select><select id="state" aria-label="状態"><option value="">すべての状態</option></select><button id="reset">条件を解除</button></div><p id="count" class="muted" aria-live="polite"></p><div class="table"><table><thead><tr><th>出典</th><th>分類</th><th>ファイル</th><th>状態</th><th>バージョン</th><th>ライセンス</th><th>参照</th></tr></thead><tbody id="rows"></tbody></table></div><p class="muted">ファイル名はローカル原本を開きます。GitHubリンクは公開mainの参照です。sの更新は公開済みです。faaffはPR反映中で、mainとは内容差がある場合があります。リンク経由の編集は原本に反映されます。</p><div class="links"><a href="inventory.csv" download>CSV一覧</a><a href="inventory.md">Markdown一覧</a><a href="../README.md">使い方</a><button id="print">印刷</button></div></main><script>
const data=__DATA__;const query=document.querySelector('#query'),body=document.querySelector('#rows');const selects=['source','category','state'].map(k=>{const el=document.querySelector('#'+k);for(const value of [...new Set(data.map(r=>r[k]))].sort()){const option=document.createElement('option');option.value=value;option.textContent=value;el.append(option)}return [k,el]});
function localPath(r){return '../'+r.catalogue_path.split('/').map(encodeURIComponent).join('/')}
function render(){const q=query.value.toLocaleLowerCase();const selected=data.filter(r=>selects.every(([k,e])=>!e.value||r[k]===e.value)&&[r.source,r.category,r.path,r.state,r.version,r.license].join(' ').toLocaleLowerCase().includes(q));body.replaceChildren();for(const row of selected){const tr=document.createElement('tr');for(const k of ['source','category','path','state','version','license','url']){const td=document.createElement('td');if(k==='path'||k==='url'){if(k==='url'&&!row.url){td.textContent='—'}else{const a=document.createElement('a');a.href=k==='path'?localPath(row):row.url;a.textContent=k==='path'?row.path:'GitHub ↗';td.append(a);if(k==='path')td.className='file'}}else td.textContent=row[k]||'—';tr.append(td)}body.append(tr)}if(!selected.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=7;td.textContent='一致するファイルがありません。検索条件を変更してください。';tr.append(td);body.append(tr)}document.querySelector('#count').textContent=selected.length+' / '+data.length+' 件を表示'}
query.addEventListener('input',render);for(const [,el] of selects)el.addEventListener('change',render);document.querySelector('#reset').addEventListener('click',()=>{query.value='';for(const [,el]of selects)el.value='';render()});document.querySelector('#print').addEventListener('click',()=>window.print());render();
</script></html>'''
    if direct:
        page = page.replace("'../'+r.catalogue_path", "'../../'+r.original")
    if show_artifacts:
        page = page.replace('<a href="tools.html">ツール一覧・実行状況</a>', '<a href="artifacts.html">成果物一覧・公開状況</a> · <a href="tools.html">ツール一覧・実行状況</a>')
    return page.replace('__DATA__', data).replace('__COUNT__', str(len(rows))).replace('__FILTERS__', str(sum(r['category'] == 'フィルター' for r in rows)))


def filter_overview(root):
    data = json.loads((root / 's/filter-profiles.json').read_text(encoding='utf-8'))
    rows = []
    for output in data['outputs']:
        relative = output['scope'] + '/' + output['path']
        count = sum(len(data['rule_sets'][key]['rules']) for key in output['rule_sets'])
        state = 'Strict・任意候補' if output['path'].endswith('strict.txt') else 'v2候補' if output['path'].startswith('v2/') else '現行'
        license_name = data['rule_sets'][output['rule_sets'][0]]['license']
        rows.append('<tr><td>' + html.escape(state) + '</td><td><a href="../../' + quote(relative) + '">' + html.escape(relative) + '</a></td><td class="number">' + str(count) + '</td><td>' + html.escape(license_name) + '</td></tr>')
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>フィルターの選び方・一覧</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#17324d;font-family:system-ui,sans-serif;line-height:1.8}main{max-width:1100px;margin:auto;padding:28px 20px}h1{font-size:30px;line-height:1.4}h2{font-size:22px;margin-top:32px}a{color:#075bb5}.lead{background:#e8f1ff;border-left:5px solid #075bb5;padding:20px;border-radius:8px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.card{background:white;border:1px solid #d6e1ed;border-radius:12px;padding:20px}.card h3{margin-top:0}.table{overflow:auto;border-radius:12px;border:1px solid #d6e1ed}table{border-collapse:collapse;background:white;width:100%}th,td{padding:13px;text-align:left;border-bottom:1px solid #d6e1ed;overflow-wrap:anywhere}th{background:#edf2f8}tbody tr:nth-child(even){background:#fafcff}.number{text-align:right;font-variant-numeric:tabular-nums}.note{color:#455d76}nav{display:flex;flex-wrap:wrap;gap:16px}@media(max-width:650px){.cards{grid-template-columns:1fr}h1{font-size:25px}th,td{padding:9px;font-size:12px}}@media print{body{background:white}main{max-width:none;padding:0}.table{overflow:visible}.cards{display:block}.card{margin-bottom:12px}}
    </style><main><nav><a href="inventory.html">全ファイル一覧</a><a href="../ADBLOCK-UPDATE.md">変更・検証の詳細</a><a href="../results/upstream-audit.csv" download>ドメイン監査CSV</a></nav><h1>フィルターの選び方・一覧</h1><p>バージョン <strong>__VERSION__</strong> ／ 上流確認 __REVIEW__</p><div class="lead"><strong>まずは保守されている基本リスト＋現行広告版から。</strong><br>追跡版は任意追加です。sとfaaffの共通版を両方登録する必要はありません。sの更新は購読先へ反映済みです。faaffの同内容は更新PRにまとめています。</div>
    <h2>目的から選ぶ</h2><div class="cards"><section class="card"><h3>通常の広告ブロック</h3><p>現行広告版を選びます。sは共通17ルール＋a-adsとuBO拡張、faaffは共通17の通信ルールです。</p></section><section class="card"><h3>追跡も抑えたい</h3><p>現行追跡版を任意で追加します。両repoの有効9ルールは同じです。不具合時は追跡版から切り分けます。</p></section><section class="card"><h3>候補を評価したい</h3><p>v2やStrictを選びます。広い対象を含み、サイト機能の確認が必要です。通常版には自動採用していません。</p></section></div>
    <h2>通信フィルター比較</h2><div class="table"><table><thead><tr><th>位置づけ</th><th>ローカル原本</th><th>ルール数</th><th>ライセンス</th></tr></thead><tbody>__ROWS__</tbody></table></div>
    <h2>表示・拡張フィルターの違い</h2><div class="table"><table><thead><tr><th>ファイル</th><th>選び方</th></tr></thead><tbody><tr><td><a href="../../s/ad-ubo.txt">ad-ubo.txt</a></td><td>s広告版に含まれるuBO専用拡張。外部リソースなしの既定版。</td></tr><tr><td><a href="../../s/twitch-custom-optional.txt">twitch-custom-optional.txt</a></td><td>追加設定が必要。既定では無効。ライブ動画の広告除去は保証しません。</td></tr><tr><td><a href="../../s/japanese-text-softener.txt">日本語・標準</a></td><td>本文中心の古いフォントを調整します。</td></tr><tr><td><a href="../../s/japanese-text-softener-deep.txt">日本語・Deep</a></td><td>標準版を含み、子要素まで調べます。標準版で調整されない文字があるときに。</td></tr></tbody></table></div>
    <h2>検証結果を見る</h2><p><a href="../results/latest.json">共通検証</a> · <a href="../results/filter-engine.json">実エンジン</a> · <a href="../results/filter-browser.json">合成画面</a> · <a href="../results/filter-live.json">公開ページ通信</a></p><p class="note">通信・合成画面の検証は、ログイン、フォーム、動画再生、録画の動作保証とは別です。詳しい結果と未完了の項目は更新記録に記載しています。</p></main></html>'''
    return page.replace('__VERSION__', html.escape(data['version'])).replace('__REVIEW__', html.escape(data['reviewed_at'])).replace('__ROWS__', ''.join(rows)) + '\n'


def dependency_rows(root):
    lock = json.loads((root / 's/verification/ghostery/package-lock.json').read_text(encoding='utf-8'))
    rows = []
    for key, entry in lock['packages'].items():
        if not key:
            continue
        name = key.removeprefix('node_modules/')
        rows.append({'name': name, 'version': entry['version'],
                     'role': '任意検証・直接依存' if name == '@ghostery/adblocker' else '任意検証・間接依存',
                     'license': entry.get('license', '未確認'), 'state': 'npm lock固定',
                     'source': 's/verification/ghostery/package-lock.json'})
    python_lock = root / 'tools/python-lock.json'
    if python_lock.is_file():
        for entry in json.loads(python_lock.read_text(encoding='utf-8'))['packages']:
            role = '任意Python検証・直接依存' if entry['role'] == 'direct' else '任意Python検証・間接依存'
            if entry['marker']:
                role += '（Windowsのみ）'
            rows.append({'name': entry['name'], 'version': entry['version'], 'role': role,
                         'license': entry['license'], 'state': '版・配布SHA256固定', 'source': 'tools/python-lock.json'})
    else:
        for line in (root / 'tools/requirements-verification.txt').read_text(encoding='utf-8').splitlines():
            if not line or line.startswith('#'):
                continue
            name, version = line.split('==')
            rows.append({'name': name, 'version': version, 'role': '任意画面・設定検証',
                         'license': {'playwright': 'Apache-2.0', 'PyYAML': 'MIT', 'pytest': 'MIT'}.get(name, '各配布元を確認'), 'state': '動作確認版を固定', 'source': 'tools/requirements-verification.txt'})
    build_lock = root / 'tools/python-build-lock.json'
    if build_lock.is_file():
        for entry in json.loads(build_lock.read_text(encoding='utf-8'))['packages']:
            existing = next((row for row in rows if row['name'].replace('_', '-').lower() == entry['name'].replace('_', '-').lower() and row['version'] == entry['version']), None)
            role = 'Python 3.15のPyYAML標準Python版・ビルド依存'
            if existing:
                existing['role'] += ' / ' + role
            else:
                rows.append({'name': entry['name'], 'version': entry['version'], 'role': role,
                             'license': entry['license'], 'state': '版・配布SHA256固定', 'source': 'tools/python-build-lock.json'})
    selenium_lock = root / 'tools/selenium-lock.json'
    if selenium_lock.is_file():
        for entry in json.loads(selenium_lock.read_text(encoding='utf-8'))['packages']:
            existing = next((row for row in rows if row['name'].replace('_','-').lower() == entry['name'].replace('_','-').lower() and row['version'] == entry['version']), None)
            role = '任意実拡張検証・Linux Docker内の' + ('直接依存' if entry['role'] == 'direct' else '間接依存')
            if existing:
                existing['role'] += ' / ' + role
            else:
                rows.append({'name': entry['name'], 'version': entry['version'], 'role': role,
                             'license': entry['license'], 'state': '版・配布SHA256固定', 'source': 'tools/selenium-lock.json'})
    engine = json.loads((root / 's/verification/engine-lock.json').read_text(encoding='utf-8'))
    rows += [{'name': 'uBlock Origin', 'version': engine['ublock']['commit'], 'role': '任意検証エンジン',
              'license': '同梱LICENSE・各ソース参照', 'state': 'commit・SHA256固定', 'source': 's/verification/engine-lock.json'},
             {'name': 'Public Suffix List', 'version': engine['public_suffix']['commit'], 'role': '第三者ドメイン判定資料',
              'license': 'MPL-2.0', 'state': 'commit・SHA256固定', 'source': 's/verification/engine-lock.json'}]
    return rows


def dependency_overview(rows, inventory_rows=()):
    table = []
    for row in rows:
        values = [html.escape(row[key]) for key in ('name', 'version', 'role', 'license', 'state')]
        table.append('<tr>' + ''.join('<td>' + value + '</td>' for value in values) + '<td><a href="../../' + quote(row['source']) + '">設定原本</a></td></tr>')
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ライブラリ・検証依存一覧</title><style>*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#17324d;font-family:system-ui,sans-serif;line-height:1.8}main{max-width:1200px;margin:auto;padding:28px 20px}a{color:#075bb5}.table{overflow:auto;border:1px solid #d6e1ed;border-radius:12px}table{width:100%;border-collapse:collapse;background:white}td,th{padding:12px;border-bottom:1px solid #d6e1ed;text-align:left;overflow-wrap:anywhere}th{background:#edf2f8}tr:nth-child(even){background:#fafcff}.note{background:#e8f1ff;padding:20px;border-radius:10px}nav{display:flex;gap:16px;flex-wrap:wrap}@media(max-width:650px){main{padding:20px 12px}h1{font-size:25px}td,th{padding:8px}table{min-width:850px}}@media print{body{background:white}main{max-width:none;padding:0}.table{overflow:visible}}</style><main><nav><a href="inventory.html">全ファイル一覧</a><a href="filters.html">フィルター比較</a><a href="libraries.csv" download>ライブラリCSV</a></nav><h1>ライブラリ・検証依存一覧</h1><p>スマートフォンでは表を左右にスクロールできます。CSVは表計算ソフトで開けます。</p><p class="note">一覧生成と標準フィルター検査はPython標準ライブラリのみです。下の依存は実エンジン・画面・設定の任意検証用で、フィルターの購読には不要です。正本の設定から自動生成しています。</p><div class="table"><table><thead><tr><th>ライブラリ・資料</th><th>固定バージョン</th><th>用途</th><th>ライセンス情報</th><th>状態</th><th>原本</th></tr></thead><tbody>__ROWS__</tbody></table></div><h2>録画ツールの依存</h2><p>faaffのpyproject.tomlではPython 3.11以上、実行時の必須外部依存なし、ビルド時はsetuptools&gt;=76とwheelを宣言しています。本体ソースがないため、実行時・パッケージ化の再検証は未完了です。宣言とインストール実績を混同しないでください。</p><p><a href="../../faaff/pyproject.toml">faaffのライブラリ設定</a> · <a href="../../faaff/requirements.txt">実行依存宣言</a></p><p>ライブラリ保存先library-filesは__LIBRARYCOUNT__件、shared/downloadsは__DOWNLOADCOUNT__件を一覧に登録しています。環境全体のインストール済みパッケージではなく、このワークスペースで管理する検証依存の一覧です。</p></main></html>'''
    return page.replace('__ROWS__', ''.join(table)).replace('__LIBRARYCOUNT__', str(sum(row['source'] == 'library-files' for row in inventory_rows))).replace('__DOWNLOADCOUNT__', str(sum(row['source'] == 'downloads' for row in inventory_rows))) + '\n'


def expected_files(rows, root=None, direct=False):
    files = {'inventory.json': json.dumps(rows, ensure_ascii=False, indent=2) + '\n',
            'inventory.csv': csv_text(rows, direct), 'inventory.md': markdown(rows, direct),
            'inventory.html': html_page(rows, direct, root is not None and (root / 'catalog/artifacts.json').is_file())}
    if root is not None and (root / 's/filter-profiles.json').is_file():
        files['filters.html'] = filter_overview(root)
    if root is not None and (root / 'tools/registry.json').is_file():
        from doctor import overview
        files['tools.html'] = overview(root)
    if root is not None and (root / 'catalog/projects.json').is_file():
        from projects import load as load_projects, views
        files.update(views(load_projects(root / 'catalog/projects.json')))
    if root is not None and (root / 'catalog/artifacts.json').is_file():
        from artifacts import load as load_artifacts, views as artifact_views
        files.update(artifact_views(load_artifacts(root / 'catalog/artifacts.json'), root))
    if root is not None and (root / 's/verification/ghostery/package-lock.json').is_file():
        dependencies = dependency_rows(root)
        files['libraries.html'] = dependency_overview(dependencies, rows)
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(['名前', 'バージョン', '用途', 'ライセンス情報', '状態', '原本'])
        writer.writerows([row[key] for key in ('name', 'version', 'role', 'license', 'state', 'source')] for row in dependencies)
        files['libraries.csv'] = '\ufeff' + stream.getvalue()
    return files


def ensure_link(path, target, root):
    if path.is_symlink():
        if path.resolve() == target.resolve():
            return
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"refusing to replace external link: {path}")
        path.unlink()
    elif path.exists():
        raise ValueError(f"refusing to replace regular file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(os.path.relpath(target, path.parent), target_is_directory=target.is_dir())


def build(root, config):
    rows = scan(root, config)
    generated = root / 'catalog' / 'generated'
    generated.mkdir(parents=True, exist_ok=True)
    prior = generated / 'inventory.json'
    previous = json.loads(prior.read_text(encoding='utf-8')) if prior.is_file() else []
    desired = {link_path(row) for row in rows}
    for row in previous:
        old_path = row.get('catalogue_path', link_path(row))
        if Path(old_path).is_absolute() or '..' in Path(old_path).parts:
            raise ValueError('unsafe old catalogue path')
        if old_path not in desired:
            obsolete = root / 'catalog' / old_path
            # Prune only an old generated link pointing at its recorded source.
            if obsolete.is_symlink():
                # Missing-target resolution differs across platforms. Compare the
                # recorded link itself without following a dangling target.
                target = os.path.normcase(os.path.abspath(obsolete.parent / os.readlink(obsolete)))
                recorded = os.path.normcase(os.path.abspath(root / row['original']))
                if target == recorded:
                    obsolete.unlink()
    for name, content in expected_files(rows, root, config.get('link_mode') == 'direct').items():
        (generated / name).write_text(content, encoding='utf-8', newline='')
    if config.get('link_mode') != 'direct':
        for row in rows:
            ensure_link(root / 'catalog' / link_path(row), root / row['original'], root)
        for source in config['sources']:
            if source.get('kind') == 'repository':
                ensure_link(root / 'catalog/repositories' / source['name'], root / source['path'], root)
        for name in ('inventory.html', 'inventory.csv', 'inventory.md'):
            ensure_link(root / 'catalog/lists' / name, generated / name, root)
    print(f'BUILD PASSED: {len(rows)} files')


def check(root, config):
    rows = scan(root, config)
    errors = []
    for name, content in expected_files(rows, root, config.get('link_mode') == 'direct').items():
        path = root / 'catalog/generated' / name
        if not path.is_file() or path.read_bytes() != content.encode('utf-8'):
            errors.append(f'stale generated file: {name}; run build')
    if config.get('link_mode') != 'direct':
        for row in rows:
            path = root / 'catalog' / link_path(row)
            if not path.is_symlink() or path.resolve() != (root / row['original']).resolve():
                errors.append(f'missing or incorrect catalogue link: {link_path(row)}')
    for path in (root / 'catalog').rglob('*'):
        if path.is_symlink() and not path.exists():
            errors.append(f'broken link: {path.relative_to(root)}')
    for relationship in config.get('filter_relationships', []):
        def rules(relative):
            return {line.strip() for line in (root / relative).read_text(encoding='utf-8').splitlines()
                    if line.strip() and not line.lstrip().startswith(('!', '['))}
        base_rules = rules(relationship['base'])
        target_rules = rules(relationship['target'])
        expected = base_rules | set(relationship['extra_rules'])
        if target_rules != expected:
            errors.append(f"filter relationship drift: {relationship['target']}; missing={sorted(expected-target_rules)}, extra={sorted(target_rules-expected)}")
    return errors


def test(root, extra_commands=()):
    py = sys.executable
    from registry import load, execute, write_report
    commands = [(item['name'], item['cwd'], item['argv'], item['timeout_seconds']) for item in load()['checks']]
    for label, directory, command in extra_commands:
        if command[0] == sys.executable:
            command = ['{python}', *command[1:]]
        commands.append((label, directory, command, 120))
    results = []
    path = root / 'catalog/results/latest.json'
    report = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'running', 'passed': False,
              'scope': 'Local static/regression checks plus explicitly enabled engine, synthetic DOM and configuration checks; no authenticated video or Windows recording E2E', 'checks': results}
    write_report(path, report)
    for label, directory, command, timeout in commands:
        try:
            completed = execute(command, root, directory, timeout)
        except KeyboardInterrupt:
            report.update(status='interrupted', tested_at_utc=datetime.now(timezone.utc).isoformat())
            write_report(path, report)
            print('INTERRUPTED: ' + label, flush=True)
            return 130
        code, output = completed['exit_code'], completed['output']
        results.append({'name': label, 'exit_code': code, 'output': output})
        print(('PASS' if code == 0 else 'FAIL') + ': ' + label, flush=True)
        if code:
            print(output, flush=True)
        write_report(path, report)
    passed = all(r['exit_code'] == 0 for r in results)
    report.update(tested_at_utc=datetime.now(timezone.utc).isoformat(), passed=passed, status='passed' if passed else 'failed')
    write_report(path, report)
    return 0 if report['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'check', 'test', 'filters', 'all', 'doctor', 'run', 'setup', 'release', 'portfolio'])
    parser.add_argument('--output', type=Path, help='new work/*.zip output for a portable source snapshot')
    parser.add_argument('--tool', help='registered tool id for run')
    parser.add_argument('--check', action='store_true', help='check filter generation without writing')
    parser.add_argument('--engine-dir', type=Path, help='add pinned uBO engine checks using a prepared directory')
    parser.add_argument('--ghostery-entry', type=Path, help='optional installed Ghostery ESM entry for a second engine')
    parser.add_argument('--browser', action='store_true', help='add catalogue and synthetic filter DOM checks; requires Playwright')
    parser.add_argument('--workflows', action='store_true', help='add local workflow checks; requires PyYAML')
    args = parser.parse_args()
    if args.output and args.command != 'release':
        parser.error('--output applies only to release')
    if args.command == 'release':
        if not args.output or args.check or args.tool or args.engine_dir or args.ghostery_entry or args.browser or args.workflows:
            parser.error('release requires --output and accepts no verification flags')
        from release import package
        try:
            return package(ROOT, args.output)
        except (ValueError, OSError) as error:
            parser.error(str(error))
    if args.tool and args.command != 'run':
        parser.error('--tool applies only to run')
    if args.command == 'portfolio':
        if args.check or args.engine_dir or args.ghostery_entry or args.browser or args.workflows:
            parser.error('portfolio accepts no verification flags')
        from portfolio_status import run
        return run(ROOT)
    if args.command == 'setup':
        if args.check or args.tool or args.engine_dir or args.ghostery_entry or args.browser or args.workflows:
            parser.error('setup accepts no verification flags')
        from setup_verification import main as setup
        return setup()
    if args.command in {'doctor', 'run'}:
        if args.check or args.engine_dir or args.ghostery_entry or args.browser or args.workflows:
            parser.error('doctor and run do not accept verification flags')
        if args.command == 'run':
            if not args.tool:
                parser.error('run requires --tool')
            from registry import run_tool
            try:
                return run_tool(ROOT, args.tool)
            except ValueError as error:
                parser.error(str(error))
        from doctor import run
        return run(ROOT)
    if (args.browser or args.ghostery_entry) and not args.engine_dir:
        parser.error('--browser and --ghostery-entry require --engine-dir')
    if (args.engine_dir or args.workflows) and args.command not in {'all', 'test'}:
        parser.error('optional verification flags apply to all or test')
    extra = []
    if args.engine_dir:
        command = ['node', 's/scripts/check_engine.mjs', '--engine-dir', str(args.engine_dir.resolve()),
                   '--mirror-root', str(ROOT / 'faaff'), '--report', str(ROOT / 'catalog/results/filter-engine.json')]
        if args.ghostery_entry:
            command += ['--ghostery-entry', str(args.ghostery_entry.resolve())]
        extra.append(('filters: real engine and scriptlet behavior', '.', command))
    if args.browser:
        extra += [('catalogue: browser UI', '.', [sys.executable, 'tools/browser_smoke.py']),
                  ('filters: synthetic browser DOM', '.', [sys.executable, 'tools/filter_browser.py', '--engine-dir',
                   str(args.engine_dir.resolve()), '--report', str(ROOT / 'catalog/results/filter-browser.json')])]
    if args.workflows:
        extra.append(('automation: workflow configuration', '.', [sys.executable, 'tools/check_workflows.py']))
    from configuration import load as load_configuration
    config = load_configuration(ROOT)
    if args.command in {'filters', 'all'}:
        command = [sys.executable, str(ROOT / 's/scripts/generate_lists.py'), '--mirror-root', str(ROOT / 'faaff')]
        if args.check:
            command.append('--check')
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode or args.command == 'filters':
            return result.returncode
        build(ROOT, config)
        return test(ROOT, extra)
    if args.command == 'build':
        build(ROOT, config)
        return 0
    if args.command == 'test':
        return test(ROOT, extra)
    errors = check(ROOT, config)
    for error in errors:
        print('ERROR:', error)
    print('CHECK FAILED' if errors else 'CHECK PASSED: inventory, hashes, generated views and links')
    return bool(errors)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print('ERROR:', error, file=sys.stderr)
        sys.exit(2)
