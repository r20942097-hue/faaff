"""Optional Chromium checks for the local catalogue (requires Playwright)."""
import json
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(ROOT / 'work/browsers'))
from playwright.sync_api import sync_playwright


def main():
    rows = json.loads((ROOT / 'catalog/generated/inventory.json').read_text(encoding='utf-8'))
    output = ROOT / 'work/browser-check'
    output.mkdir(parents=True, exist_ok=True)
    errors, checks = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto((ROOT / 'catalog/generated/inventory.html').as_uri())
        assert page.locator('#rows tr').count() == len(rows)
        checks.append('all inventory rows render')
        for href in page.locator('#rows td.file a').evaluate_all('(links) => links.map(link => link.href)'):
            assert Path(unquote(urlparse(href).path)).is_file(), href
        checks.append('all local artifact links resolve')
        page.select_option('#source', 's')
        assert page.locator('#rows tr').count() == sum(row['source'] == 's' for row in rows)
        checks.append('source filter')
        page.select_option('#category', 'フィルター')
        assert page.locator('#rows tr').count() == sum(row['source'] == 's' and row['category'] == 'フィルター' for row in rows)
        checks.append('combined source/category filter')
        page.fill('#query', 'japanese-text-softener')
        assert page.locator('#rows tr').count() == 2
        checks.append('text search')
        page.fill('#query', 'no-matching-file-123456')
        assert '一致するファイルがありません' in page.locator('#rows').inner_text()
        checks.append('empty-state message')
        page.click('#reset')
        assert page.locator('#rows tr').count() == len(rows)
        checks.append('reset restores full list')
        page.select_option('#state', '候補')
        assert page.locator('#rows tr').count() == 3
        checks.append('candidate filter')
        page.click('#reset')
        page.screenshot(path=str(output / 'desktop.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(output / 'mobile.png'), full_page=True)
        checks.append('mobile layout fits viewport')
        page.emulate_media(media='print')
        assert not page.locator('.toolbar').is_visible()
        checks.append('print layout hides controls')
        page.emulate_media(media='screen')
        page.goto((ROOT / 'catalog/generated/filters.html').as_uri())
        profiles = json.loads((ROOT / 's/filter-profiles.json').read_text(encoding='utf-8'))
        assert page.locator('table').first.locator('tbody tr').count() == len(profiles['outputs'])
        checks.append('profile overview matches canonical output count')
        for index, profile in enumerate(profiles['outputs']):
            expected = sum(len(profiles['rule_sets'][key]['rules']) for key in profile['rule_sets'])
            assert page.locator('table').first.locator('tbody tr').nth(index).locator('.number').inner_text() == str(expected)
        checks.append('profile rule counts match canonical data')
        for href in page.locator('a').evaluate_all('(links) => links.map(link => link.href)'):
            assert Path(unquote(urlparse(href).path)).is_file(), href
        checks.append('profile overview links resolve')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(output / 'profiles-mobile.png'), full_page=True)
        for cell in page.locator('.number').all():
            bounds = cell.bounding_box()
            assert bounds['x'] + bounds['width'] <= 390, bounds
        checks.append('profile overview and rule counts fit mobile viewport')
        page.goto((ROOT / 'catalog/generated/libraries.html').as_uri())
        from manage import dependency_rows
        dependencies = dependency_rows(ROOT)
        assert page.locator('tbody tr').count() == len(dependencies)
        checks.append('library overview matches pinned dependencies')
        for href in page.locator('a').evaluate_all('(links) => links.map(link => link.href)'):
            assert Path(unquote(urlparse(href).path)).is_file(), href
        checks.append('library overview links resolve')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(output / 'libraries-mobile.png'), full_page=True)
        checks.append('library overview fits mobile viewport')
        page.goto((ROOT / 'catalog/generated/tools.html').as_uri())
        from registry import load
        tools = load()['tools']
        diagnosis = json.loads((ROOT / 'catalog/results/doctor.json').read_text(encoding='utf-8'))
        assert page.locator('tbody tr').count() == len(tools)
        checks.append('tool overview matches shared registry')
        assert diagnosis['python']['version'] in page.locator('main').inner_text()
        checks.append('tool overview shows the diagnosed Python version')
        assert '前回の実行結果・日時' in page.locator('thead').inner_text()
        for index, item in enumerate(diagnosis['tools']):
            previous = item.get('last_run', {'label': '未記録', 'time': '—'})
            cell = page.locator('tbody tr').nth(index).locator('td').nth(2).inner_text()
            assert previous['label'] in cell and previous['time'] in cell
        checks.append('tool readiness and previous execution records render separately')
        for index, item in enumerate(diagnosis['tools']):
            detail = item.get('last_run', {}).get('detail')
            if detail:
                assert detail in page.locator('tbody tr').nth(index).locator('td').nth(2).inner_text()
        checks.append('tool result input and Python compatibility details render')
        for index in range(len(tools)):
            assert page.locator('tbody tr').nth(index).bounding_box()['height'] < 180
        checks.append('mobile tool rows remain readable without character-by-character wrapping')
        page.select_option('#state', 'blocked')
        assert page.locator('tbody tr:visible').count() == sum(tool['status'] == 'blocked' for tool in diagnosis['tools'])
        checks.append('tool overview filters missing prerequisites')
        page.select_option('#state', '')
        page.fill('#query', 'Control Plane')
        assert page.locator('tbody tr:visible').count() == 2
        checks.append('tool overview searches recovered control-plane tools')
        page.fill('#query', 'no-matching-tool-123456')
        assert page.locator('#empty').is_visible()
        checks.append('tool overview empty-state message')
        page.fill('#query', '')
        for href in page.locator('a').evaluate_all('(links) => links.map(link => link.href)'):
            assert Path(unquote(urlparse(href).path)).is_file(), href
        checks.append('tool overview links resolve')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(output / 'tools-mobile.png'), full_page=True)
        checks.append('tool overview fits mobile viewport')
        page.goto((ROOT / 'catalog/generated/projects.html').as_uri())
        from projects import load as load_projects
        products = load_projects(ROOT / 'catalog/projects.json')['products']
        assert page.locator('tbody tr').count() == len(products)
        checks.append('product overview matches current inventory')
        page.select_option('#source', 'missing')
        assert page.locator('tbody tr:visible').count() == sum(product['source_state'] == 'missing' for product in products)
        checks.append('product overview filters missing source')
        page.fill('#query', 'AI Orchestrator')
        assert page.locator('tbody tr:visible').count() == 1
        checks.append('product overview combines source and text filters')
        page.fill('#query', 'no-matching-product-123456')
        assert page.locator('#empty').is_visible()
        checks.append('product overview empty-state message')
        page.click('#reset')
        assert page.locator('tbody tr:visible').count() == len(products)
        checks.append('product overview resets filters')
        for href in page.locator('a').evaluate_all('(links) => links.map(link => link.href)'):
            assert Path(unquote(urlparse(href).path)).is_file(), href
        checks.append('product overview links resolve')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(output / 'projects-mobile.png'), full_page=True)
        checks.append('product overview fits mobile viewport')
        page.goto((ROOT / 'catalog/generated/artifacts.html').as_uri())
        from artifacts import load as load_artifacts, changes
        artifact_data = load_artifacts(ROOT / 'catalog/artifacts.json')
        artifacts = artifact_data['artifacts']
        assert page.locator('article').count() == len(artifacts)
        checks.append('artifact overview matches canonical deliverables')
        assert '生成時の手元' in page.locator('main').inner_text()
        assert '公開版の検証' in page.locator('main').inner_text()
        checks.append('artifact publication and local verification are distinct')
        page.select_option('#stage', 'pr')
        assert page.locator('article:visible').count() == sum(a['publication']['stage'] == 'pr' for a in artifacts)
        checks.append('artifact overview filters PR publications')
        page.select_option('#kind', 'snapshot')
        assert page.locator('article:visible').count() == 1
        checks.append('artifact overview combines stage and kind filters')
        page.fill('#query', 'no-matching-artifact-123456')
        assert page.locator('#empty').is_visible()
        checks.append('artifact overview empty-state message')
        page.click('#reset')
        page.fill('#query', 'Deep')
        assert page.locator('article:visible').count() == 1
        checks.append('artifact overview searches deliverable names')
        page.click('#reset')
        assert page.locator('article:visible').count() == len(artifacts)
        checks.append('artifact overview resets all filters')
        for href in page.locator('a').evaluate_all('(links) => links.map(link => link.href)'):
            if urlparse(href).scheme == 'file':
                assert Path(unquote(urlparse(href).path)).is_file(), href
        checks.append('artifact overview local navigation resolves')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.locator('article').first.locator('summary').click()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(output / 'artifacts-mobile.png'), full_page=True)
        checks.append('artifact cards and expanded hashes fit mobile viewport')
        delta = changes(artifact_data)
        assert len(delta['changed']) == 1
        assert '20261012.1 → 20261012.2' in page.locator('.change').first.inner_text()
        checks.append('artifact overview shows fixed release comparison')
        assert '追跡ブロックの共有ルール' in page.locator('#relations').inner_text()
        assert '9行' in page.locator('#relations').inner_text()
        checks.append('artifact overview shows shared rules while keeping both sources')
        page.fill('#query', 'Deep')
        page.locator('#relations a').last.click()
        assert page.locator('article:visible').count() == len(artifacts)
        assert page.locator('#query').input_value() == ''
        checks.append('shared-rule navigation clears filters and reveals target artifact')
        original_ids = page.locator('article').evaluate_all('(rows)=>rows.map(r=>r.id)')
        page.select_option('#sort', 'size')
        sizes = page.locator('article').evaluate_all('(rows)=>rows.map(r=>Number(r.dataset.size))')
        assert sizes == sorted(sizes)
        page.select_option('#stage', 'pr')
        assert page.locator('article:visible').count() == sum(a['publication']['stage'] == 'pr' for a in artifacts)
        page.click('#reset')
        assert page.locator('#sort').input_value() == 'original'
        assert page.locator('article').evaluate_all('(rows)=>rows.map(r=>r.id)') == original_ids
        checks.append('artifact sorting combines filters and resets registration order')
        page.emulate_media(media='print')
        assert not page.locator('.toolbar').is_visible()
        checks.append('artifact print layout hides controls')
        page.emulate_media(media='screen')
        # Deliberately shuffled fixtures distinguish natural sorting, ties and dates.
        import copy
        from artifacts import views
        fixture = {'schema': 'deliverable-catalog/v1', 'scope': 'sorting fixture', 'artifacts': []}
        for index, (name, day, size) in enumerate([
                ('item10', '2026-01-01', 90), ('item2', '2026-10-12', 3),
                ('item2', '2026-10-12', 1), ('item1', '2026-02-01', 3)]):
            row = copy.deepcopy(artifacts[0])
            row.update(id='sort-' + str(index), name=name, bytes=size)
            row['verification']['checked_on'] = day
            fixture['artifacts'].append(row)
        page.goto('about:blank')
        page.set_content(views(fixture, standalone=True)['artifacts.html'])
        def order():
            return page.locator('article').evaluate_all('(rows)=>rows.map(r=>Number(r.dataset.order))')
        page.select_option('#sort', 'name')
        assert order() == [3, 1, 2, 0]
        checks.append('artifact names sort naturally and retain tie order')
        page.select_option('#sort', 'date')
        assert order() == [1, 2, 3, 0]
        checks.append('artifact verification dates sort newest first with stable ties')
        page.select_option('#sort', 'size')
        assert order() == [2, 1, 3, 0]
        checks.append('artifact sizes sort numerically with stable ties')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.fill('#query', 'item2')
        assert page.locator('article:visible').count() == 2
        page.click('#reset')
        assert order() == [0, 1, 2, 3]
        assert page.locator('article:visible').count() == 4
        checks.append('artifact sorting fixture fits mobile and resets search')
        assert not errors, errors
        checks.append('no JavaScript page errors')
        browser.close()
    result = {'passed': True, 'checks': checks, 'inventory_count': len(rows),
              'scope': 'Catalogue and profile-selection UI only; not uBlock filter-engine or recording E2E'}
    (ROOT / 'catalog/results/browser.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='')
    print(f'BROWSER CHECK PASSED: {len(checks)} checks')


if __name__ == '__main__':
    main()
