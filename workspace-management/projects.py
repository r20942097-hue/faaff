"""Render the current product integration inventory without promoting historical claims."""
import csv
from datetime import date
import html
import io
import re

from registry import load_json


FIELDS = ['name', 'current_source', 'current_product_e2e', 'available_management',
          'next', 'historical_reference', 'historical_record_date']
HEADERS = ['製品・ツール', '現在の本体ソース', '製品E2E', '今あるもの', '次の統合・改良', '履歴の参照版', '履歴の日付']


def validate(data):
    if not isinstance(data, dict) or data.get('schema') != 'product-integration-availability/v1' or not isinstance(data.get('scope'), str):
        raise ValueError('invalid product inventory schema')
    products = data.get('products')
    if not isinstance(products, list) or not products:
        raise ValueError('product inventory must be a nonempty array')
    seen = set()
    for product in products:
        if not isinstance(product, dict) or not isinstance(product.get('id'), str) or not re.fullmatch('[a-z][a-z0-9-]*', product['id']) or product['id'] in seen:
            raise ValueError('invalid or duplicate product id')
        seen.add(product['id'])
        if any(not isinstance(product.get(key), str) or not product[key] for key in FIELDS):
            raise ValueError('product fields must be nonempty strings')
        try:
            date.fromisoformat(product['historical_record_date'])
        except ValueError as error:
            raise ValueError('invalid historical record date') from error
        if product.get('source_state') not in ('available', 'missing'):
            raise ValueError('invalid product source state')
        if product['source_state'] == 'missing' and product['current_product_e2e'] != '未完了':
            raise ValueError('missing product source cannot claim current E2E success')
    return data


def load(path):
    return validate(load_json(path))


def views(data):
    validate(data)
    products = data['products']
    rows = []
    for product in products:
        cells = ''.join('<td>' + html.escape(product[key]) + '</td>' for key in FIELDS)
        rows.append('<tr data-source="' + product['source_state'] + '">' + cells + '</tr>')
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>製品の現状・統合案</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#18304b;font-family:system-ui,sans-serif;line-height:1.7}main{max-width:1400px;margin:auto;padding:28px 20px}a{color:#075bb5}nav,.toolbar{display:flex;gap:14px;flex-wrap:wrap}.note{padding:18px;background:#e8f1ff;border-radius:10px}.summary{display:flex;gap:16px;flex-wrap:wrap;margin:20px 0}.summary div{background:white;padding:14px 20px;border-radius:10px;border:1px solid #d6e1ed}.toolbar{margin:20px 0}input,select,button{font:inherit;padding:10px;border:1px solid #c9d5e5;border-radius:8px;background:white}input{flex:1;min-width:170px}.table{overflow:auto;background:white;border:1px solid #d6e1ed;border-radius:12px}table{border-collapse:collapse;width:100%;min-width:1100px}th,td{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #d6e1ed;overflow-wrap:anywhere}th{background:#edf2f8}td:first-child{font-weight:600;min-width:150px}td:nth-child(2){min-width:180px;max-width:230px}td:nth-child(4){min-width:200px}td:nth-child(5){min-width:240px}td:last-child{white-space:nowrap}#empty{display:none}@media(max-width:650px){main{padding:20px 12px}h1{font-size:25px}}@media print{.toolbar,nav{display:none}.table{overflow:visible}main{padding:0}body{background:white}}</style>
<main><nav><a href="tools.html">実行できる管理ツール</a><a href="inventory.html">全ファイル</a><a href="../INTEGRATION.md">統合の実施表</a><a href="projects.csv" download>CSV保存</a></nav><h1>製品の現状・統合案</h1><p class="note">__SCOPE__</p><div class="summary"><div>登録製品 <strong>__TOTAL__</strong></div><div>本体ソースあり <strong>__AVAILABLE__</strong></div><div>本体ソース未取得 <strong>__MISSING__</strong></div></div><p>名称・今あるもの・次の改良を検索できます。スマートフォンでは表を左右にスクロールしてください。</p><div class="toolbar"><input id="query" type="search" aria-label="製品検索" placeholder="名前・今あるもの・次の改良で検索"><select id="source" aria-label="本体ソースの状態"><option value="">すべて</option><option value="available">本体ソースあり</option><option value="missing">本体ソース未取得</option></select><button id="reset">条件を解除</button></div><p id="count" aria-live="polite"></p><div class="table"><table><thead><tr>__HEADERS__</tr></thead><tbody>__ROWS__</tbody></table></div><p id="empty">一致する製品がありません。</p><p><a href="projects.md">Markdown一覧</a> · <a href="../projects.json">一覧の原本</a> · <a href="../BRANCHES.md">取得ブランチの根拠</a></p></main><script>
const query=document.querySelector('#query'),source=document.querySelector('#source'),rows=[...document.querySelectorAll('tbody tr')];function render(){let n=0;for(const row of rows){const show=(!source.value||row.dataset.source===source.value)&&row.textContent.toLocaleLowerCase().includes(query.value.toLocaleLowerCase());row.hidden=!show;if(show)n++}document.querySelector('#count').textContent=n+'件 / 全'+rows.length+'件';document.querySelector('#empty').style.display=n?'none':'block'}query.addEventListener('input',render);source.addEventListener('change',render);document.querySelector('#reset').addEventListener('click',()=>{query.value='';source.value='';render()});render();
</script></html>'''
    available = sum(product['source_state'] == 'available' for product in products)
    substitutions = {'__SCOPE__': html.escape(data['scope']), '__TOTAL__': str(len(products)),
                     '__AVAILABLE__': str(available), '__MISSING__': str(len(products)-available),
                     '__HEADERS__': ''.join('<th>' + header + '</th>' for header in HEADERS), '__ROWS__': ''.join(rows)}
    for key, value in substitutions.items():
        page = page.replace(key, value)
    csv_file = io.StringIO(newline='')
    writer = csv.writer(csv_file)
    writer.writerow(HEADERS)
    writer.writerows([[product[key] for key in FIELDS] for product in products])
    def markdown_cell(value):
        return html.escape(value).replace('|', '&#124;').replace('\n', '<br>')
    markdown = ['# 製品の現状・統合案', '', data['scope'], '', '| ' + ' | '.join(HEADERS) + ' |', '| ' + ' | '.join(['---']*len(HEADERS)) + ' |']
    markdown += ['| ' + ' | '.join(markdown_cell(product[key]) for key in FIELDS) + ' |' for product in products]
    return {'projects.html': page + '\n', 'projects.csv': '\ufeff' + csv_file.getvalue(), 'projects.md': '\n'.join(markdown) + '\n'}
