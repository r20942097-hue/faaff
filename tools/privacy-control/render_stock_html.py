"""Self-contained, noninteractive HTML for synthetic stock-fragment evidence."""
from html import escape


def render_stock(report):
    counts = report["counts"]
    template_complete = report.get("template_source_components_complete") is True
    scope_label = ("公式EasyPrivacyテンプレートに記載された全39ソース（公開配布版との同一性は未検証）"
                   if template_complete else "固定したEasyPrivacyソース5ファイル（部分ベースライン）")

    def e(x):
        return escape(str(x), quote=True)
    metrics = [
        ("候補ホスト", counts["candidates"]),
        ("上流ソースファイル", counts["source_components"]),
        ("通信シナリオ", counts["cases"]),
        ("エンジン観測", counts["engine_observations"]),
        ("既存ソース遮断（uBO）", counts["selected_source_baseline_blocked"]["ubo"]),
        ("追加の合成遮断（uBO）", counts["additional_synthetic_blocks"]["ubo"]),
        ("追加の合成遮断（Ghostery）", counts["additional_synthetic_blocks"]["ghostery"]),
        ("判定不一致（変更後）", counts["engine_disagreements"]["combined"]),
    ]
    info = "\n".join(
        "<div class='metric'><dt>" + e(name) + "</dt><dd>" + e(value) + "</dd></div>"
        for name, value in metrics)
    rows = []
    for item in report["per_host"]:
        c = item["selected_fragment_coverage"]
        d = item["additional_synthetic_cases"]
        rows.append("<tr><th scope='row'><code>" + e(item["host"]) + "</code></th>"
                    "<td>" + e(", ".join(c["ubo"]) or "—") + "</td>"
                    "<td>" + e(", ".join(d["ubo"]) or "—") + "</td>"
                    "<td>" + e(", ".join(d["ghostery"]) or "—") + "</td>"
                    "<td>NOT_ESTABLISHED</td></tr>")
    return """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src 'none'; base-uri 'none'; form-action 'none'">
<title>UPC — 上流フィルター比較（合成通信）</title>
<style>
:root{color-scheme:light dark;font:15px/1.65 system-ui,Meiryo,sans-serif}
body{max-width:1250px;margin:0 auto;padding:clamp(12px,3vw,40px)}
header{border-bottom:1px solid #9996;padding-bottom:15px}
h1{font-size:clamp(1.45rem,3vw,2rem)}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.metric{border:1px solid #8886;padding:12px;border-radius:9px;min-width:0}
dt{font-size:.84rem;opacity:.76}dd{font-size:1.16rem;font-weight:650;margin:4px 0 0}
table{border-collapse:collapse;min-width:850px;width:100%;font-size:.87rem}
th,td{padding:9px 11px;text-align:left;border-bottom:1px solid #8885;vertical-align:top}
thead{background:light-dark(#eff1f5,#272b32)}
th[scope=row]{font-weight:550}
.table-scroll{overflow-x:auto;border:1px solid #8885;border-radius:10px}
code{overflow-wrap:anywhere}small,.muted{opacity:.75}
.note{border-left:3px solid #a78336;background:light-dark(#f9f5eb,#28251a);padding:14px}
footer{margin-top:24px;border-top:1px solid #8885;padding-top:12px;font-size:.85rem}
</style></head><body>
<header><small>Unified Privacy Control / Phase 2 / READ-ONLY</small>
<h1>上流の追跡防止フィルターとの比較</h1>
<p class="muted">""" + e(scope_label) + """と候補38件を、実際の遮断エンジンが合成通信で比較した結果</p>
</header><section><h2>観測の概要</h2><dl class="metrics">
""" + info + """
</dl></section><section><h2>解釈上の制約</h2>
<p class="note"><strong>公開不可（NO_GO）。</strong>
固定ソースの比較であり、公開済み配布リストや実際のブラウザーの有効リストとの同等性は未検証です。
利用中ブラウザーの購読状態、実サイトの追加追跡防止効果、ログイン・署名URLの安全性は確認されていません。
遮断した広告数・実利用者の追跡数を表すものでもありません。</p>
</section><section><h2>候補別の比較</h2><div class="table-scroll"><table>
<thead><tr><th>候補ドメイン</th><th>既存ソース（uBO）</th>
<th>候補による追加一致（uBO）</th><th>候補による追加一致（Ghostery）</th>
<th>実サイトの効果</th></tr></thead><tbody>
""" + "\n".join(rows) + """
</tbody></table></div></section>
<footer>Source: pinned upstream EasyPrivacy components; 0 newly published rules; all rule additions remain review-only.</footer>
</body></html>
"""
