"""Combine deliverables, source availability, diagnostics and next actions offline."""
import argparse
from datetime import date, datetime, timedelta, timezone
import html
import json
from pathlib import Path

from artifacts import load as load_artifacts, records, RELEASES, STAGES
from doctor import inspect
from projects import load as load_projects
from registry import load_json, safe_path, write_report

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))


def iso_date(value):
    if not isinstance(value, str):
        raise ValueError('date must use YYYY-MM-DD')
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('date must use YYYY-MM-DD')
    return parsed


def candidate_deadlines(root, today):
    """Use the oldest evidence or exception review; a new summary cannot renew it."""
    base = safe_path(root, 'faaff/browser_filter_lists')
    manifest = load_json(safe_path(base, 'manifest.json'))
    if not isinstance(manifest, dict):
        raise ValueError('filter manifest must be an object')
    age = manifest.get('candidate_evidence_max_age_days')
    if type(age) is not int or not 1 <= age <= 365:
        raise ValueError('invalid candidate evidence age')
    queue = load_json(safe_path(base, manifest.get('candidate_queue')))
    if not isinstance(queue, dict) or not isinstance(queue.get('candidates'), list):
        raise ValueError('invalid candidate queue')
    result = []
    for candidate in queue['candidates']:
        if not isinstance(candidate, dict) or not isinstance(candidate.get('domain'), str):
            raise ValueError('invalid candidate')
        evidence = candidate.get('evidence')
        review = candidate.get('exception_review')
        if not isinstance(evidence, list) or not evidence or not isinstance(review, dict):
            raise ValueError('candidate evidence and exception review are required')
        if any(not isinstance(record, dict) for record in evidence):
            raise ValueError('evidence record must be an object')
        dates = [iso_date(record.get('checked_at')) for record in evidence]
        dates.append(iso_date(review.get('checked_at')))
        if any(checked > today for checked in dates):
            raise ValueError('candidate evidence cannot be dated in the future')
        last_valid = min(dates) + timedelta(days=age)
        remaining = (last_valid - today).days
        result.append({'domain': candidate['domain'], 'state': candidate.get('state'),
                       'last_valid_on': last_valid.isoformat(),
                       'stale_from': (last_valid + timedelta(days=1)).isoformat(),
                       'days_remaining': remaining,
                       'status': 'stale' if remaining < 0 else 'due_soon' if remaining <= 7 else 'current'})
    return result


def collect(root, today=None, readiness=None):
    root = Path(root).resolve()
    today = today or datetime.now(JST).date()
    products = load_projects(safe_path(root, 'catalog/projects.json'))['products']
    artifacts = records(load_artifacts(safe_path(root, 'catalog/artifacts.json')), root)
    diagnosis = inspect(root) if readiness is None else readiness
    deadlines = candidate_deadlines(root, today)
    actions = []
    for product in products:
        if product['source_state'] == 'missing':
            actions.append({'id': 'source-' + product['id'], 'priority': 1,
                            'target': product['name'], 'kind': 'source', 'state': 'blocked',
                            'next': product['next'], 'due_on': None,
                            'completion': '正式取得元・版・ハッシュを記録し、本体ソースを取得する'})
    for tool in diagnosis['tools']:
        previous = tool.get('last_run', {})
        if tool['status'] == 'blocked':
            actions.append({'id': 'prepare-' + tool['id'], 'priority': 2,
                            'target': tool['name'], 'kind': 'preparation', 'state': 'blocked',
                            'next': ' / '.join(tool['missing']), 'due_on': None,
                            'completion': '不足項目を解消し、doctorで実行準備を再診断する'})
        elif previous.get('detail') != '登録ファイル・設定とPython版は同一':
            actions.append({'id': 'verify-' + tool['id'], 'priority': 2,
                            'target': tool['name'], 'kind': 'verification', 'state': 'actionable',
                            'next': tool['command'], 'due_on': None,
                            'completion': '登録入力を変更せず検証に成功し、doctorを再実行する'})
    for item in deadlines:
        actions.append({'id': 'evidence-' + item['domain'],
                        'priority': 1 if item['status'] != 'current' else 3,
                        'target': item['domain'], 'kind': 'evidence',
                        'state': 'actionable' if item['status'] != 'current' else 'scheduled',
                        'next': '分類根拠と互換性例外を再確認し、実際の確認日と固定参照を記録する',
                        'due_on': item['last_valid_on'],
                        'completion': '根拠・例外・昇格ゲートの検証が成功する。候補の自動採用は行わない'})
    actions.sort(key=lambda row: (row['priority'], row['due_on'] or '9999-12-31', row['id']))
    return {'schema': 'portfolio-status/v1', 'as_of_jst': today.isoformat(),
            'scope': 'ローカルでの一覧・ソース取得状況・診断・確認期限。通信、製品E2E、公開状態の再検証は実行していません。',
            'counts': {'artifacts': len(artifacts), 'products': len(products),
                       'missing_products': sum(p['source_state'] == 'missing' for p in products),
                       'tools': len(diagnosis['tools']),
                       'ready_tools': sum(t['status'] == 'ready' for t in diagnosis['tools']),
                       'actions': len(actions)},
            'artifacts': artifacts, 'products': products, 'tools': diagnosis['tools'],
            'candidate_deadlines': deadlines, 'actions': actions}


def markdown(report):
    def cell(value):
        return html.escape(str(value)).replace('|', '&#124;').replace('\r', '').replace('\n', '<br>')
    counts = report['counts']
    lines = ['# 全成果物・改良予定', '', '確認基準日：' + report['as_of_jst'] + '（日本時間）', '',
             report['scope'], '',
             f"成果物 {counts['artifacts']}件、製品 {counts['products']}件（本体未取得 {counts['missing_products']}件）、管理機能 {counts['tools']}件。", '',
             '## 成果物一覧', '',
             '公開・検証の表示は元の登録記録です。今回の集計だけでは更新しません。', '',
             '| 成果物 | 版 | 選び方 | 公開状況 | 記録の確認日 | 公開先 |', '|---|---|---|---|---|---|']
    for artifact in report['artifacts']:
        values = [artifact['name'], artifact['version'], RELEASES[artifact['release_state']],
                  STAGES[artifact['publication']['stage']], artifact['verification']['checked_on']]
        url = artifact['publication']['url']
        link = '[固定公開先](<' + url + '>)' if url else '未公開'
        lines.append('| ' + ' | '.join(cell(value) for value in values) + ' | ' + link + ' |')
    lines += ['', '## 製品と次の開発', '', '| 製品 | 本体ソース | 次の作業 |', '|---|---|---|']
    for product in report['products']:
        lines.append('| ' + ' | '.join(cell(product[key]) for key in ('name', 'current_source', 'next')) + ' |')
    lines += ['', '## フィルター根拠の確認期限', '',
              '期限当日は有効、翌日から期限切れです。最も古い根拠・例外確認日を使います。', '',
              '| 対象 | 有効期限 | 期限切れ開始 | 状態 |', '|---|---|---|---|']
    labels = {'current': '期間内', 'due_soon': '7日以内に再確認', 'stale': '期限切れ'}
    for row in report['candidate_deadlines']:
        lines.append('| ' + ' | '.join(cell(value) for value in [row['domain'], row['last_valid_on'], row['stale_from'], labels[row['status']]]) + ' |')
    lines += ['', '## 継続する改良予定', '',
              '優先度1から着手します。blockedは前提条件待ち、scheduledは期限に合わせる項目です。', '',
              '| 優先 | 対象 | 状態 | 次の作業 | 完了条件 |', '|---|---|---|---|---|']
    for row in report['actions']:
        lines.append('| ' + ' | '.join(cell(row[key]) for key in ('priority', 'target', 'state', 'next', 'completion')) + ' |')
    return '\n'.join(lines) + '\n'


def run(root, today=None):
    root = Path(root).resolve()
    target = safe_path(root, 'catalog/results/portfolio-status.json')
    write_report(target, {'schema': 'portfolio-status/v1', 'status': 'running'})
    document = safe_path(root, 'catalog/PORTFOLIO.md')
    try:
        document.write_text('# 全成果物・改良予定\n\n状態：再集計中。完了した記録ではありません。\n', encoding='utf-8')
        report = collect(root, today)
        report['status'] = 'completed'
        rendered = markdown(report)
        document.write_text(rendered, encoding='utf-8', newline='')
        write_report(target, report)
    except (OSError, ValueError, TypeError) as error:
        write_report(target, {'schema': 'portfolio-status/v1', 'status': 'failed',
                              'error': type(error).__name__ + ': ' + str(error)})
        raise
    counts = report['counts']
    print(f"PORTFOLIO REPORT GENERATED: {counts['artifacts']} artifacts, {counts['products']} products, {counts['actions']} next actions")
    print('catalog/PORTFOLIO.md; catalog/results/portfolio-status.json')
    return 0


def main(root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', type=iso_date, help='YYYY-MM-DD in Japan; defaults to today')
    parser.add_argument('--root', type=Path, default=Path(root), help='integrated workspace to inspect')
    args = parser.parse_args()
    try:
        return run(args.root, args.as_of)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, 'PORTFOLIO REPORT FAILED: ' + str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
