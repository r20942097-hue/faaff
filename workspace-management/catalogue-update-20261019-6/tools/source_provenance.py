"""Compare configured local files with pinned base/update ZIPs without running their code."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import zipfile

from configuration import load as load_configuration
from extract_snapshot import extract
from manage import scan
from registry import load_json, safe_path
from verify_catalogue_update import apply_update

LABELS = {'unchanged_base': '基準と一致', 'matches_update': '更新版と一致',
          'modified': '想定版から変更', 'missing': '現在一覧にない', 'added': '現在のみ存在'}
SCOPE = ('指定SHA256とZIP内部の全ファイルを検証し、設定されたローカルファイルを照合しました。'
         'GitHubは取得していません。参照URLは各設定に記録された版で、現在の内容との一致を保証しません。'
         '対象製品の実行・E2E・真正性の保証ではありません。現在一覧にない状態には欠落・symlink・設定による選択外を含みます。除外規則により生成結果・キャッシュ等は対象外です。')


def indexed(root):
    config = load_configuration(root)
    return config, {row['original']: row for row in scan(root, config)}


def compare(baseline, expected, current):
    rows = []
    for name in sorted(set(baseline) | set(expected) | set(current)):
        old, wanted, now = baseline.get(name), expected.get(name), current.get(name)
        old_hash = old['sha256'] if old else None
        wanted_hash = wanted['sha256'] if wanted else None
        current_hash = now['sha256'] if now else None
        if now is None:
            state = 'missing'
        elif wanted is None:
            state = 'added'
        elif current_hash != wanted_hash:
            state = 'modified'
        elif old_hash != wanted_hash:
            state = 'matches_update'
        else:
            state = 'unchanged_base'
        row = now or wanted or old
        rows.append({'path': name, 'source': row['source'], 'state': state,
                     'baseline_sha256': old_hash, 'expected_sha256': wanted_hash,
                     'current_sha256': current_hash, 'current_bytes': now['bytes'] if now else None,
                     'baseline_reference_url': old['url'] if old else '',
                     'expected_reference_url': wanted['url'] if wanted else '',
                     'current_declared_reference_url': now['url'] if now else ''})
    return rows


def collect(root, baseline, baseline_sha256, update=None, update_sha256=None):
    root = Path(root).resolve()
    if (update is None) != (update_sha256 is None):
        raise ValueError('update and update SHA256 must be supplied together')
    initial_config, current = indexed(root)
    # Only this trusted reporter is imported. Extracted Python files are never executed/imported.
    with TemporaryDirectory(prefix='source-provenance-') as directory:
        reference = Path(directory) / 'baseline'
        extract(baseline, baseline_sha256, reference)
        base_config, old = indexed(reference)
        history = [{'kind': 'baseline', 'sha256': baseline_sha256,
                    'file': Path(baseline).name, 'sources': base_config['sources']}]
        if update is not None:
            patch = Path(directory) / 'update'
            extract(update, update_sha256, patch)
            apply_update(patch, reference, baseline_sha256)
            manifest = load_json(patch / 'manifest.json')
            history.append({'kind': 'update', 'sha256': update_sha256,
                            'file': Path(update).name, 'version': manifest.get('version'),
                            'schema': manifest['schema'], 'files': manifest['files']})
        expected_config, expected = indexed(reference)
    final_config, final_current = indexed(root)
    if initial_config != final_config or current != final_current:
        raise ValueError('local inputs changed during observation; rerun the report')
    rows = compare(old, expected, current)
    counts = {state: 0 for state in LABELS}
    counts.update(Counter(row['state'] for row in rows))
    return {'schema': 'source-provenance/v1', 'status': 'observed',
            'observed_at_utc': datetime.now(timezone.utc).isoformat(),
            'scope': SCOPE, 'observation': 'Two scans agreed; concurrent writes between scans cannot be ruled out.',
            'history': history, 'expected_sources': expected_config['sources'],
            'current_declared_sources': initial_config['sources'], 'counts': counts, 'files': rows}


def cell(value):
    return html.escape(str(value if value is not None else '—')).replace('|', '&#124;').replace('[', '&#91;').replace(']', '&#93;').replace('`', '&#96;').replace('\r', '&#13;').replace('\n', '&#10;')


def markdown(report):
    lines = ['# 取得元と更新差分', '', report['scope'], '', '観測時刻：' + report['observed_at_utc'], '',
             '| 状態 | 件数 |', '|---|---:|']
    lines += [f'| {label} | {report["counts"][key]} |' for key, label in LABELS.items()]
    lines += ['', '## 基準・更新履歴', '']
    for item in report['history']:
        lines.append('- ' + cell(item['kind'] + ': ' + item['file']) + ' / SHA256 `' + item['sha256'] + '`')
    lines += ['', '## 差分ファイル', '', '全ファイルのハッシュはJSONとHTMLを参照してください。', '',
              '| ファイル | 状態 | 基準SHA256 | 想定SHA256 | 現在SHA256 |', '|---|---|---|---|---|']
    for row in report['files']:
        if row['state'] != 'unchanged_base':
            lines.append('| ' + ' | '.join(cell(value) for value in [row['path'], LABELS[row['state']], row['baseline_sha256'], row['expected_sha256'], row['current_sha256']]) + ' |')
    return '\n'.join(lines) + '\n'


def html_page(report):
    sections = []
    for row in report['files']:
        references = []
        for key, label in [('baseline_reference_url', '基準版の記録'), ('expected_reference_url', '想定版の記録'),
                           ('current_declared_reference_url', '現在の設定の記録')]:
            if row[key]:
                # URLs originate in validated catalogue configs, never arbitrary HTML.
                references.append('<a href="' + html.escape(row[key], quote=True) + '">' + label + '</a>')
        details = '<br>'.join(cell(label) + ': <code>' + cell(row[key]) + '</code>' for key, label in [
            ('baseline_sha256', '基準SHA256'), ('expected_sha256', '想定SHA256'), ('current_sha256', '現在SHA256')])
        sections.append('<tr data-state="' + row['state'] + '"><td>' + cell(row['path']) + '</td><td>' + LABELS[row['state']] + '</td><td>' + details + '</td><td>' + '<br>'.join(references) + '</td></tr>')
    history = ''.join('<li>' + cell(item['kind'] + ': ' + item['file']) + '<br><code>' + item['sha256'] + '</code></li>' for item in report['history'])
    counts = ' / '.join(label + ' ' + str(report['counts'][key]) + '件' for key, label in LABELS.items())
    return '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>取得元と更新差分</title>
<style>body{font:16px/1.7 system-ui,sans-serif;background:#f4f7fb;color:#18304b;margin:0}main{max-width:1500px;margin:auto;padding:24px}code{font-size:12px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #d8e2ee;padding:12px;text-align:left;vertical-align:top}td:first-child{overflow-wrap:anywhere;min-width:180px}input,select{font:inherit;padding:8px;margin:8px 8px 8px 0;max-width:100%}.table{overflow:auto}a{color:#225eba}.note{background:white;padding:16px;border-radius:12px}</style>
<main><h1>取得元と更新差分</h1><p class="note">''' + cell(report['scope']) + '</p><p>観測時刻: ' + cell(report['observed_at_utc']) + '</p><p>' + counts + '</p><h2>固定基準・更新履歴</h2><ul>' + history + '''</ul><p><a href="source-provenance.json">全記録JSON</a> · <a href="SOURCE-PROVENANCE.md">差分Markdown</a></p>
<label>ファイル検索 <input id="query" type="search"></label><label>状態 <select id="state"><option value="">すべて</option>''' + ''.join('<option value="' + key + '">' + value + '</option>' for key, value in LABELS.items()) + '''</select></label><p id="count" aria-live="polite"></p><div class="table"><table><thead><tr><th>ファイル</th><th>状態</th><th>照合したハッシュ</th><th>設定に記録された参照先</th></tr></thead><tbody>''' + ''.join(sections) + '''</tbody></table></div></main><script>
const query=document.querySelector('#query'),state=document.querySelector('#state'),rows=[...document.querySelectorAll('tbody tr')];function render(){let visible=0;for(const row of rows){row.hidden=Boolean((state.value&&row.dataset.state!==state.value)||!row.cells[0].textContent.toLocaleLowerCase().includes(query.value.toLocaleLowerCase()));if(!row.hidden)visible++}document.querySelector('#count').textContent=visible+' / '+rows.length+' 件を表示'}query.addEventListener('input',render);state.addEventListener('change',render);render();</script></html>\n'''


def run(root, baseline, baseline_sha256, output, update=None, update_sha256=None):
    root = Path(root).resolve()
    if not isinstance(output, str) or not output.startswith('work/'):
        raise ValueError('output must be a new directory under work/')
    target = safe_path(root, output)
    if target.exists():
        raise ValueError('report output already exists; choose a new directory')
    report = collect(root, baseline, baseline_sha256, update, update_sha256)
    rendered = {'source-provenance.json': json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                'SOURCE-PROVENANCE.md': markdown(report), 'index.html': html_page(report)}
    target.mkdir(parents=True, exist_ok=False)
    try:
        for name, body in rendered.items():
            (target / name).write_text(body, encoding='utf-8', newline='')
    except BaseException:
        shutil.rmtree(target)
        raise
    print('SOURCE PROVENANCE OBSERVED:', len(report['files']), 'files;', output + '/index.html')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path, help='integrated workspace to inspect')
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--baseline-sha256', required=True)
    parser.add_argument('--update', type=Path)
    parser.add_argument('--update-sha256')
    parser.add_argument('--output', required=True, help='new work/ directory inside inspected workspace')
    args = parser.parse_args()
    try:
        return run(args.root, args.baseline, args.baseline_sha256, args.output, args.update, args.update_sha256)
    except (OSError, ValueError, TypeError, zipfile.BadZipFile) as error:
        parser.exit(1, 'SOURCE PROVENANCE FAILED: ' + str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
