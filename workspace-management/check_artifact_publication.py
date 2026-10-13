"""Observe public artifact bytes and main without silently adopting new releases."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from datetime import datetime, timezone, timedelta
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from artifacts import load, validate
from registry import safe_path, unique_object, write_report

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 128 * 1024 * 1024


def download(url, maximum=MAX_BYTES):
    with urlopen(Request(url, headers={'User-Agent': 'workspace-artifact-publication-check'}), timeout=15) as response:
        body = response.read(maximum + 1)
    if len(body) > maximum:
        raise ValueError('public response exceeds size limit')
    return body


def metadata(url):
    return json.loads(download(url, 1024 * 1024), object_pairs_hook=unique_object)


def location(row):
    parsed = urlsplit(row['publication']['url'])
    parts = parsed.path.lstrip('/').split('/')
    if parsed.netloc != 'raw.githubusercontent.com' or len(parts) < 4 or parts[2] != row['publication']['commit']:
        raise ValueError('public byte check requires a fixed raw GitHub file')
    return '/'.join(parts[:2]), '/'.join(parts[3:])


def catalogue_identity(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def observe(data, fetch=download, fetch_metadata=metadata, progress=None):
    validate(data)
    repositories = sorted({location(row)[0] for row in data['artifacts'] if row['publication']['stage'] != 'local'})
    heads = {}
    for repo in repositories:
        answer = fetch_metadata('https://api.github.com/repos/' + repo + '/commits/main')
        if not isinstance(answer, dict) or not isinstance(answer.get('sha'), str) or not re.fullmatch('[0-9a-f]{40}', answer['sha']):
            raise ValueError('invalid observed main commit')
        heads[repo] = answer['sha']
    prs = {}
    for row in data['artifacts']:
        pr = row['publication']['pr_url']
        if pr and pr not in prs:
            matched = re.fullmatch(r'https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(\d+)', pr)
            if not matched:
                raise ValueError('invalid PR observation URL')
            answer = fetch_metadata('https://api.github.com/repos/' + matched[1] + '/pulls/' + matched[2])
            if not isinstance(answer, dict) or type(answer.get('merged')) is not bool or not isinstance(answer.get('state'), str) or answer['state'] not in {'open', 'closed'} or not isinstance(answer.get('base'), dict) or not isinstance(answer['base'].get('ref'), str):
                raise ValueError('invalid observed PR state')
            prs[pr] = {'merged': answer['merged'], 'state': answer.get('state'), 'base': answer['base']['ref']}

    def check(row):
        result = {'id': row['id'], 'passed': False, 'public_bytes_match': False, 'main_bytes_match': False,
                  'stage': row['publication']['stage'], 'proposal': None}
        if row['publication']['stage'] == 'local':
            result['reason'] = 'local artifact has no public byte verification'
            return result
        try:
            if row['bytes'] > MAX_BYTES:
                raise ValueError('registered artifact exceeds download limit')
            body = fetch(row['publication']['url'], MAX_BYTES)
            result['public_bytes_match'] = len(body) == row['bytes'] and hashlib.sha256(body).hexdigest() == row['sha256']
            repo, path = location(row)
            result['observed_main_commit'] = heads[repo]
            main_url = 'https://raw.githubusercontent.com/' + repo + '/' + heads[repo] + '/' + path
            result['main_url'] = main_url
            try:
                main = fetch(main_url, MAX_BYTES)
                result['main_bytes_match'] = len(main) == row['bytes'] and hashlib.sha256(main).hexdigest() == row['sha256']
                result['main_state'] = 'match' if result['main_bytes_match'] else 'different'
            except HTTPError as error:
                if error.code != 404:
                    raise
                result['main_state'] = 'missing'
            if row['publication']['pr_url']:
                result['pr_observation'] = prs[row['publication']['pr_url']]
            result['passed'] = result['public_bytes_match'] and (row['publication']['stage'] != 'main' or result['main_bytes_match'])
            if result['public_bytes_match'] and result['main_bytes_match'] and row['publication']['stage'] == 'pr':
                result['proposal'] = {'stage': 'main', 'commit': heads[repo], 'url': main_url}
            if not result['public_bytes_match']:
                result['reason'] = 'fixed public bytes differ from the registered identity'
            elif row['publication']['stage'] == 'main' and not result['main_bytes_match']:
                result['reason'] = 'current main differs from the registered release; review required'
        except (OSError, ValueError) as error:
            result['error'] = type(error).__name__
            result['reason'] = str(error)
        return result

    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(check, row): row['id'] for row in data['artifacts']}
        for future in as_completed(futures):
            result = future.result()
            results[result['id']] = result
            if progress:
                progress([results[row['id']] for row in data['artifacts'] if row['id'] in results])
    checks = [results[row['id']] for row in data['artifacts']]
    return {'schema': 'artifact-publication-observation/v1', 'passed': all(r['passed'] for r in checks),
            'catalogue_identity': catalogue_identity(data),
            'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'main_commits': heads, 'checks': checks,
            'scope': 'Public file identity and observed main/PR state only. No product runtime tests or automatic catalogue adoption.'}


def candidate(data, report):
    validate(data)
    if not isinstance(report, dict) or report.get('schema') != 'artifact-publication-observation/v1' or report.get('passed') is not True or not isinstance(report.get('checks'), list):
        raise ValueError('cannot propose an update from incomplete or failed observations')
    if any(not isinstance(result, dict) or not isinstance(result.get('id'), str) for result in report['checks']):
        raise ValueError('invalid observation result')
    if report.get('catalogue_identity') != catalogue_identity(data):
        raise ValueError('observation refers to a different catalogue')
    source = {row['id']: row for row in data['artifacts']}
    if {r.get('id') for r in report['checks']} != set(source) or len(report['checks']) != len(source):
        raise ValueError('observation does not cover the catalogue')
    updated = copy.deepcopy(data)
    by_id = {row['id']: row for row in updated['artifacts']}
    for result in report['checks']:
        if result.get('passed') is not True or result.get('public_bytes_match') is not True:
            raise ValueError('cannot adopt an unverified observation')
        proposal = result.get('proposal')
        if proposal:
            if not isinstance(proposal, dict) or result.get('main_bytes_match') is not True or proposal.get('stage') != 'main' or proposal.get('commit') != result.get('observed_main_commit') or proposal.get('url') != result.get('main_url'):
                raise ValueError('proposal has no matching observed main identity')
            by_id[result['id']]['publication'].update(proposal)
    return validate(updated)



def preview(data, report):
    """Compare a validated publication proposal without adopting it."""
    proposed = candidate(data, report)
    def cell(value):
        text = html.escape(str(value)).replace('\\', '\\\\')
        for character in ('*', '_', '[', ']', '`'):
            text = text.replace(character, '\\' + character)
        return text.replace('|', '&#124;').replace('\r', '').replace('\n', '<br>')
    lines = ['# 成果物の公開状態・更新候補', '',
             '公開本文とmainの観測に基づく提案です。正本は未変更です。観測後の公開状態は再確認が必要です。', '',
             '観測日時（UTC）：' + cell(report.get('checked_at_utc', '未記録')), '',
             '| 成果物 | 項目 | 現在 | 更新候補 |', '|---|---|---|---|']
    changed = 0
    fields = [('stage', '公開段階'), ('commit', '固定コミット'), ('url', '取得先'), ('pr_url', 'PR参照')]
    for before, after in zip(data['artifacts'], proposed['artifacts']):
        differences = [(key, label) for key, label in fields if before['publication'].get(key) != after['publication'].get(key)]
        if differences:
            changed += 1
            for key, label in differences:
                lines.append('| ' + ' | '.join(cell(v) for v in [before['name'], label,
                             before['publication'].get(key, ''), after['publication'].get(key, '')]) + ' |')
    lines += ['', '公開記録の変更候補：' + str(changed) + '件 / 全' + str(len(data['artifacts'])) + '件。', '',
              '本文のSHA256・サイズ・版・動作検証の範囲・確認日は変更しません。公開本文の一致は新しい動作検証の合格ではありません。', '',
              '採用前に公開段階・固定コミット・取得先を確認し、更新候補JSONを正本と比較してください。観測が古い場合は再確認します。']
    if not changed:
        lines += ['', '公開記録の変更候補はありません。製品動作が新たに検証されたという意味ではありません。']
    return '\n'.join(lines) + '\n'


def review_candidate(current, proposed, report):
    """Review new content using fresh bytes; never infer new runtime verification."""
    validate(current)
    validate(proposed)
    if not isinstance(report, dict) or report.get('base_catalogue_identity') != catalogue_identity(current):
        raise ValueError('review refers to a different base catalogue')
    try:
        checked = datetime.fromisoformat(report['checked_at_utc'])
        if checked.tzinfo is None:
            raise ValueError('observation must have a timezone')
        age = (datetime.now(timezone.utc) - checked).total_seconds()
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('invalid review observation time') from error
    if not -60 <= age <= 900:
        raise ValueError('review requires a fresh observation within 15 minutes')
    updated = candidate(proposed, report)
    old = {row['id']: row for row in current['artifacts']}
    sensitive = ('sha256', 'bytes', 'version', 'kind', 'local_path')
    for row in updated['artifacts']:
        previous = old.get(row['id'])
        needs_verification = (previous is None
                              or any(row[key] != previous[key] for key in sensitive)
                              or row['verification'] != previous['verification'])
        if needs_verification:
            if row['verification']['status'] == 'passed':
                raise ValueError('new or changed content cannot inherit runtime verification: ' + row['id'])
            row['verification'] = {
                'status': 'matched', 'sha256': row['sha256'],
                'checked_on': checked.astimezone(timezone(timedelta(hours=9))).date().isoformat(),
                'summary': '固定公開版のサイズ・SHA256を新規照合。本文・版等の更新後の動作検証は未確認。',
                'evidence_url': '',
            }
    # Do not silently replace the comparison baseline or shared-rule evidence.
    for key in ('scope', 'baseline', 'rule_groups'):
        if current.get(key) != proposed.get(key):
            raise ValueError('review cannot change catalogue context: ' + key)
    return validate(updated)


def review_preview(current, proposed, report):
    reviewed = review_candidate(current, proposed, report)
    def cell(value):
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        text = html.escape(value).replace('\\', '\\\\')
        for character in ('*', '_', '[', ']', '`'):
            text = text.replace(character, '\\' + character)
        return text.replace('|', '&#124;').replace('\r', '').replace('\n', '<br>')
    lines = ['# 制作物の本文更新・比較レビュー', '',
             '正本は未変更です。固定公開本文の一致を確認した候補です。動作検証の合格は新たに付与しません。', '',
             '| 制作物ID | 項目 | 現在 | 確認済み候補 |', '|---|---|---|---|']
    before = {row['id']: row for row in current['artifacts']}
    after = {row['id']: row for row in reviewed['artifacts']}
    changed = 0
    for key in dict.fromkeys([*before, *after]):
        left, right = before.get(key), after.get(key)
        if left == right:
            continue
        changed += 1
        if left is None or right is None:
            lines.append('| ' + ' | '.join(cell(v) for v in [key, '追加' if left is None else '一覧から解除', left, right]) + ' |')
            continue
        for field in dict.fromkeys([*left, *right]):
            if left.get(field) != right.get(field):
                lines.append('| ' + ' | '.join(cell(v) for v in [key, field, left.get(field), right.get(field)]) + ' |')
    if [row['id'] for row in current['artifacts']] != [row['id'] for row in reviewed['artifacts']]:
        lines += ['', '登録順の変更：' + cell([row['id'] for row in current['artifacts']]) + ' → ' + cell([row['id'] for row in reviewed['artifacts']])]
    lines += ['', '変更対象：' + str(changed) + '件。追加・一覧から解除は原本の作成・削除ではありません。', '',
              '本文・版等が変わる候補は公開本文一致までの確認です。新しい動作検証・製品完成を保証しません。',
              '採用前に候補JSONと正本を比較し、公開本文と正本の変更を再確認してください。']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', help='Write a proposed catalogue under work/; never replace the canonical catalogue.')
    parser.add_argument('--preview', help='Write a comparison table to a new Markdown file under work/.')
    parser.add_argument('--review', help='Review a proposed catalogue JSON under work/ against current canonical data.')
    args = parser.parse_args()
    review_input = None
    if args.review:
        if not args.preview:
            parser.error('review requires a new Markdown preview')
        if not args.review.startswith('work/'):
            parser.error('review must be a JSON file under work/')
        try:
            review_input = safe_path(ROOT, args.review)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        if review_input.suffix != '.json' or not review_input.is_file():
            parser.error('review must be an existing JSON file')
    output = None
    if args.candidate:
        if not args.candidate.startswith('work/'):
            parser.error('candidate must be a new JSON file under work/')
        try:
            output = safe_path(ROOT, args.candidate)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        if output.suffix != '.json' or output.exists():
            parser.error('candidate must be a new JSON file')
    preview_output = None
    if args.preview:
        if not args.preview.startswith('work/'):
            parser.error('preview must be a new Markdown file under work/')
        try:
            preview_output = safe_path(ROOT, args.preview)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        if preview_output.suffix != '.md' or preview_output.exists():
            parser.error('preview must be a new Markdown file')
    destination = ROOT / 'catalog/results/artifact-publication.json'
    running = {'schema': 'artifact-publication-observation/v1', 'status': 'running', 'passed': False, 'checks': []}
    write_report(destination, running)
    try:
        base = load(ROOT / 'catalog/artifacts.json')
        data = load(review_input) if review_input is not None else base
        def progress(checks):
            running['checks'] = checks
            write_report(destination, running)
            print('Observed', len(checks), '/', len(data['artifacts']), flush=True)
        report = observe(data, progress=progress)
        if review_input is not None:
            report['base_catalogue_identity'] = catalogue_identity(base)
            report['review_input'] = args.review
            if report['passed']:
                # Re-read both inputs after the network operation to detect concurrent edits.
                if catalogue_identity(load(ROOT / 'catalog/artifacts.json')) != catalogue_identity(base):
                    raise ValueError('base catalogue changed during review')
                if catalogue_identity(load(review_input)) != catalogue_identity(data):
                    raise ValueError('review input changed during observation')
                proposal = review_candidate(base, data, report)
                report['reviewed_catalogue_identity'] = catalogue_identity(proposal)
                comparison = review_preview(base, data, report)
        report['status'] = 'passed' if report['passed'] else 'failed'
        if output is not None and report['passed']:
            if review_input is None:
                proposal = candidate(data, report)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('x', encoding='utf-8', newline='') as stream:
                json.dump(proposal, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            report['candidate'] = args.candidate
        if preview_output is not None and report['passed']:
            if review_input is None:
                comparison = preview(data, report)
            preview_output.parent.mkdir(parents=True, exist_ok=True)
            with preview_output.open('x', encoding='utf-8', newline='') as stream:
                stream.write(comparison)
            report['preview'] = args.preview
    except (OSError, ValueError, KeyboardInterrupt) as error:
        running.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=type(error).__name__, finished_at_utc=datetime.now(timezone.utc).isoformat())
        write_report(destination, running)
        print('PUBLICATION CHECK FAILED:', type(error).__name__, str(error), flush=True)
        return 130 if isinstance(error, KeyboardInterrupt) else 1
    write_report(destination, report)
    print('PUBLICATION CHECK', 'PASSED' if report['passed'] else 'FAILED', flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
