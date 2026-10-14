"""Read-only readiness checks shared by the workspace management command."""
import importlib.util
import html
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime, timedelta, timezone


from registry import load, load_json, safe_path, input_identity, registered_files, selected_groups

RUN_LABELS = {'passed': '合格', 'failed': '失敗', 'running': '実行中・中断の可能性', 'blocked': '実行不可', 'interrupted': '中断'}


def last_run(root, key, tool=None, registry=None):
    try:
        path = safe_path(root, 'catalog/results/tool-' + key + '.json')
        if not path.is_file():
            return {'label': '未記録', 'time': '—'}
        record = load_json(path)
        if record.get('schema') != 'workspace-tool-run/v1' or record.get('tool') != key:
            return {'label': '旧形式の記録', 'time': '日時未記録'}
        status = record.get('status')
        if status not in RUN_LABELS or record.get('passed') is not (status == 'passed'):
            raise ValueError('inconsistent run status')
        stamp = datetime.fromisoformat(record.get('finished_at_utc') or record['started_at_utc'])
        if stamp.tzinfo is None:
            raise ValueError('missing timestamp timezone')
        result = {'label': RUN_LABELS[status], 'time': stamp.astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S JST')}
        if status == 'passed':
            if tool is None:
                registry = load() if registry is None else registry
                tool = next(item for item in registry['tools'] if item['id'] == key)
            before, after = record.get('inputs_before'), record.get('inputs_after')
            current = input_identity(root, tool, registry)
            if not isinstance(before, dict) or not isinstance(after, dict):
                result['detail'] = '実行時の照合情報なし'
            elif before != after or record.get('inputs_unchanged_during_run') is not True:
                result.update(label='合格記録・再検証が必要', detail='実行中に登録ファイル・設定が変更')
            elif after != current:
                result.update(label='合格記録・再検証が必要', detail='登録ファイル・設定が変更')
                old_files = after.get('files')
                if isinstance(old_files, dict):
                    result['changed_files'] = sorted(name for name in set(old_files) | set(current['files'])
                                                     if name not in old_files or name not in current['files']
                                                     or old_files[name] != current['files'][name])
                result['definition_changed'] = after.get('tool_definition_sha256') != current['tool_definition_sha256']
            elif record.get('python', {}).get('version') != sys.version.split()[0]:
                result.update(label='合格記録・環境が異なる', detail='記録時のPython版が現在と異なる')
            else:
                result['detail'] = '登録ファイル・設定とPython版は同一'
        return result
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {'label': '記録を確認してください', 'time': '—'}



def retest_advice(previous, command, missing):
    """Suggest only registered-tool execution; never declare complete test coverage."""
    if missing or command is None:
        return '不足項目を解消し、doctorを再実行してから検証してください。'
    if previous.get('detail') == '登録ファイル・設定とPython版は同一':
        return '登録入力に変更なし。外部状態や未登録の依存を変更した場合は再検証：' + command
    return '再検証：' + command + '。実行後にdoctorを再実行してください。'


def inspect(root, executable=shutil.which, module=importlib.util.find_spec, registry=None):
    root = Path(root).resolve()
    results = []
    registry = load() if registry is None else registry
    for tool in registry['tools']:
        key, label = tool['id'], tool['name']
        missing = []
        identity = input_identity(root, tool, registry)
        missing.extend('directory: ' + name + ' (' + reason + ')' for name, reason in identity.get('directory_errors', {}).items())
        for relative in identity['files']:
            try:
                present = safe_path(root, relative).is_file()
            except ValueError:
                present = False
            if not present:
                missing.append('file: ' + relative)
        missing.extend('command: ' + name for name in tool['binaries'] if executable(name) is None)
        missing.extend('module: ' + name for name in tool['modules'] if module(name) is None)
        if not tool['commands']:
            missing.append('implementation: 実行入口が未接続')
        command = 'python tools/manage.py run --tool ' + key if tool['commands'] else None
        previous = last_run(root, key, tool, registry)
        previous['retest_advice'] = retest_advice(previous, command, missing)
        results.append({'id': key, 'name': label, 'status': 'blocked' if missing else 'ready',
                        'missing': missing, 'command': command, 'last_run': previous,
                        'directories': identity.get('directories', {}),
                        'input_groups': [{'id': group['id'], 'name': group['name'], 'files': group['files']}
                                         for group in selected_groups(tool, registry)]})
    return {'schema': 'workspace-readiness/v1',
            'python': {'version': sys.version.split()[0], 'executable': sys.executable},
            'scope': '実行前の依存関係診断。ready は動作検証の合格を意味しません。ブラウザー本体・通信・録画E2Eは別途検証が必要です。',
            'tools': results, 'input_groups': registry.get('input_groups', [])}



def retest_detail(previous):
    pieces = []
    if previous.get('changed_files'):
        pieces.append('変更した登録ファイル：' + ', '.join(previous['changed_files']))
    if previous.get('definition_changed'):
        pieces.append('実行設定・登録定義も変更')
    pieces.append(previous.get('retest_advice', ''))
    return ' / '.join(piece for piece in pieces if piece)


def render(report):
    lines = ['# ツール統合・実行状況', '', report['scope'], '',
             '診断時のPython：`' + report['python']['executable'] + '`（' + report['python']['version'] + '）。環境を変更したらdoctorを再実行してください。', '',
             '前回の結果は診断時に読み込んだ記録です。今回の動作や製品完成を保証しません。', '',
             '| ツール | 実行前診断 | 前回の実行結果・日時 | 共通コマンド | 不足項目 |', '|---|---|---|---|---|']
    for item in report['tools']:
        lines.append('| ' + ' | '.join([item['name'], '実行準備あり' if item['status'] == 'ready' else '要準備',
                                      item.get('last_run', {}).get('label', '未記録') + '<br>' + item.get('last_run', {}).get('time', '—') + '<br>' + item.get('last_run', {}).get('detail', '') + '<br>' + html.escape(retest_detail(item.get('last_run', {}))).replace('|', '&#124;'),
                                      '`' + item['command'] + '`' if item['command'] else 'ソース復元後に接続',
                                      '<br>'.join(item['missing']) or 'なし']) + ' |')
    groups = report.get('input_groups', [])
    if groups:
        lines += ['', '## 共通入力の影響範囲', '',
                  '明示登録した共通入力のみを照合します。未登録の間接依存や外部状態を網羅するものではありません。', '',
                  '| 共通入力 | 利用ツール | 登録ファイル |', '|---|---|---|']
        names = {item['id']: item['name'] for item in report['tools']}
        for group in groups:
            values = [group['name'], ' / '.join(names[key] for key in group['tools']), ' / '.join(group['files'])]
            lines.append('| ' + ' | '.join(html.escape(value).replace('|', '&#124;') for value in values) + ' |')
    return '\n'.join(lines) + '\n'


def overview(root, report=None):
    if report is None:
        path = safe_path(root, 'catalog/results/doctor.json')
        report = load_json(path) if path.is_file() else inspect(root)
    rows = []
    for tool in report['tools']:
        state = '要準備' if tool['status'] == 'blocked' else '実行準備あり'
        command = tool['command'] or '本体ソース復元後に接続'
        missing = '<br>'.join(html.escape(value) for value in tool['missing']) or 'なし'
        previous = tool.get('last_run', {'label': '未記録', 'time': '—'})
        rows.append('<tr data-state="' + tool['status'] + '"><td><strong>' + html.escape(tool['name']) +
                    '</strong><br><small>' + html.escape(tool['id']) + '</small></td><td><span class="state">' +
                    state + '</span></td><td>' + html.escape(previous['label']) + '<br><small>' + html.escape(previous['time']) + '</small><br><small class="run-detail">' + html.escape(previous.get('detail', '')) + '</small><details><summary>変更内容・再検証手順</summary><small class="run-detail">' + html.escape(retest_detail(previous)) + '</small></details></td><td><code>' + html.escape(command) + '</code></td><td>' + missing + '</td></tr>')
    ready = sum(item['status'] == 'ready' for item in report['tools'])
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ツール一覧・実行状況</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#18304b;font-family:system-ui,sans-serif;line-height:1.7}main{max-width:1150px;margin:auto;padding:28px 20px}h1{font-size:30px;line-height:1.4}a{color:#075bb5}nav{display:flex;gap:18px;flex-wrap:wrap}.summary{display:flex;gap:16px;flex-wrap:wrap;margin:22px 0}.card{background:white;border:1px solid #d6e1ed;border-radius:12px;padding:16px 24px}.number{font-size:27px;font-weight:700}.note{background:#e8f1ff;padding:18px;border-radius:10px}.table{overflow:auto;background:white;border:1px solid #d6e1ed;border-radius:12px}table{border-collapse:collapse;width:100%}th,td{padding:14px;text-align:left;border-bottom:1px solid #d6e1ed;vertical-align:top}th{background:#edf2f8}td:nth-child(1){min-width:180px}td:nth-child(2){white-space:nowrap}td:nth-child(3){min-width:190px}td:nth-child(3) small{white-space:nowrap}td:nth-child(3) small.run-detail{white-space:normal;display:block;max-width:240px}td:nth-child(4){min-width:260px}td:nth-child(5){min-width:200px}code{white-space:normal;overflow-wrap:anywhere;font-size:13px}.state{background:#e6f5ed;color:#20633d;padding:4px 8px;border-radius:6px}tr[data-state=blocked] .state{background:#fff2d9;color:#7c5100}td details summary{font-size:13px;line-height:1.4;cursor:pointer}small{color:#52657b}input,select{font:inherit;padding:11px;border:1px solid #c9d5e5;border-radius:8px;background:white}.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}input{flex:1;min-width:180px}#empty{display:none}@media(max-width:650px){main{padding:20px 12px}h1{font-size:25px}table{min-width:1050px}.card{padding:12px 18px}}@media print{body{background:white}main{max-width:none}.toolbar{display:none}.table{overflow:visible}}
</style><main><nav><a href="inventory.html">全ファイル一覧</a><a href="libraries.html">ライブラリ</a><a href="../INTEGRATION.md">統合案・完了条件</a><a href="../../tools/registry.json">共通設定</a></nav><h1>ツール一覧・実行状況</h1><p>目的を選び、表示されたコマンドをワークスペースのルートで実行します。スマートフォンでは表を左右にスクロールできます。</p><div class="summary"><div class="card">登録機能<div class="number">__TOTAL__</div></div><div class="card">実行準備あり<div class="number">__READY__</div></div><div class="card">要準備<div class="number">__BLOCKED__</div></div></div><p class="note">__SCOPE__<br>準備が足りない機能は実行前に止めます。統合した監査ツールの合格を、録画・ブラウザー操作など製品本体の完成判定には使いません。</p><div class="toolbar"><input id="query" type="search" aria-label="ツール検索" placeholder="ツール名・目的・不足項目で検索"><select id="state" aria-label="実行状況"><option value="">すべて</option><option value="ready">実行準備あり</option><option value="blocked">要準備</option></select></div><div class="table"><table><thead><tr><th>ツール・目的</th><th>実行前診断</th><th>共通コマンド</th><th>不足項目</th></tr></thead><tbody>__ROWS__</tbody></table></div><p id="empty">一致するツールがありません。</p><p><a href="../TOOLS.md">Markdown一覧</a> · <a href="../results/doctor.json">診断結果</a> · <a href="../results/latest.json">回帰検証</a></p></main><script>
const query=document.querySelector('#query'),state=document.querySelector('#state'),rows=[...document.querySelectorAll('tbody tr')];function render(){let n=0;for(const row of rows){const visible=(!state.value||row.dataset.state===state.value)&&row.textContent.toLocaleLowerCase().includes(query.value.toLocaleLowerCase());row.hidden=!visible;if(visible)n++}document.querySelector('#empty').style.display=n?'none':'block'}query.addEventListener('input',render);state.addEventListener('change',render);
</script></html>'''.replace('__ROWS__', ''.join(rows)).replace('__TOTAL__', str(len(report['tools']))).replace('__READY__', str(ready)).replace('__BLOCKED__', str(len(report['tools'])-ready)).replace('__SCOPE__', html.escape(report['scope'])) + '\n'
    environment = report.get('python', {})
    note = '<p>診断時のPython：<code>' + html.escape(environment.get('executable', '未記録')) + '</code>（' + html.escape(environment.get('version', '未記録')) + '）。環境を変更したらdoctorを再実行してください。</p>'
    page = page.replace('<th>共通コマンド</th>', '<th>前回の実行結果・日時</th><th>共通コマンド</th>')
    note += '<p>前回の結果は診断時の記録です。実行後はdoctorを再実行すると更新されます。</p>'
    directory_tools = [tool for tool in report['tools'] if tool.get('directories')]
    if directory_tools:
        note += '<section><h2>明示登録したテストフォルダ</h2>'
        for tool in directory_tools:
            note += '<details><summary>' + html.escape(tool['name']) + '</summary>'
            for name, files in tool['directories'].items():
                note += '<p><code>' + html.escape(name) + '</code>（Python ' + str(len(files)) + 'ファイル）</p>'
            note += '</details>'
        note += '</section>'
    note += '<p>照合対象は登録ファイル・実行設定・Python版です。外部サービス、実行バイナリ、間接依存すべての同一性は判定しません。</p>'
    groups = report.get('input_groups', [])
    if groups:
        names = {item['id']: item['name'] for item in report['tools']}
        note += '<section><h2>共通入力の影響範囲</h2><p>明示登録した共通入力の一覧です。未登録の間接依存・外部状態を網羅しません。</p>'
        for group in groups:
            note += '<details><summary>' + html.escape(group['name']) + '（' + str(len(group['tools'])) + '機能）</summary><p>' + html.escape(' / '.join(names[key] for key in group['tools'])) + '</p><p><code>' + html.escape(' / '.join(group['files'])) + '</code></p></details>'
        note += '</section>'
    return page.replace('<div class="toolbar">', note + '<div class="toolbar">', 1)


def run(root):
    from configuration import load as load_configuration
    config = load_configuration(root)
    report = inspect(root)
    target = safe_path(root, 'catalog/results/doctor.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='')
    safe_path(root, 'catalog/TOOLS.md').write_text(render(report), encoding='utf-8', newline='')
    generated = safe_path(root, 'catalog/generated')
    generated.mkdir(parents=True, exist_ok=True)
    safe_path(root, 'catalog/generated/tools.html').write_text(overview(root, report), encoding='utf-8', newline='')
    from manage import build
    build(Path(root), config)
    print(render(report))
    return 0
