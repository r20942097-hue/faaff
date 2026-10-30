"""Read-only static HTML report. No JavaScript, network or external assets."""
from html import escape


def render(report: dict) -> str:
    counts = report["coverage"]["counts"]
    findings = report["coverage"]["findings"]
    fields = [
        ("固定元コミット", report["source"]["source_commit"]),
        ("安定版追跡ルール", str(report["stable_rules"])),
        ("候補版追跡ルール", str(report["candidate_rules"])),
        ("安定版との完全一致", str(counts.get("EXACT_OVERLAP_WITH_PINNED_STABLE", 0))),
        ("完全一致なし・効果未証明", str(counts.get("NO_EXACT_STABLE_OVERLAP_NOT_VERIFIED", 0))),
        ("未対応構文", str(counts.get("UNSUPPORTED_NOT_VERIFIED", 0))),
        ("既定ブラウザールールとの照合", report["browser_stock_coverage"]),
        ("実エンジン・実サイト互換性", report["real_engine_efficacy"]
         + " / " + report["live_site_compatibility"]),
        ("公開", report["release"]),
    ]
    metric = "\n".join(
        "<div class='metric'><dt>" + escape(k) + "</dt><dd>" + escape(v) + "</dd></div>"
        for k, v in fields
    )
    items = "\n".join(
        "<tr><td><code>" + escape(str(item["rule"]), quote=True) + "</code></td>"
        "<td>" + escape(str(item["status"]), quote=True) + "</td>"
        "<td>" + escape(str(item["parser_reason"]), quote=True) + "</td></tr>"
        for item in findings
    )
    return """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
 content="default-src 'none'; style-src 'unsafe-inline'; script-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'">
<title>Unified Privacy Control — read-only coverage</title>
<style>
:root{color-scheme:light dark;font:16px/1.6 system-ui,-apple-system,Meiryo,sans-serif}
body{max-width:1120px;margin:0 auto;padding:clamp(12px,3vw,36px)}
header{border-bottom:1px solid #8885;padding-bottom:18px}
h1{font-size:clamp(1.5rem,3vw,2.1rem);line-height:1.35}
small,.muted{opacity:.76}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
.metric{border:1px solid #8886;border-radius:9px;padding:12px;min-width:0}
dt{font-size:.82rem;opacity:.75}dd{font-size:1.02rem;font-weight:650;margin:4px 0 0;overflow-wrap:anywhere}
.table-scroll{overflow-x:auto;border:1px solid #8886;border-radius:9px}
table{border-collapse:collapse;width:100%;font-size:.89rem}
th,td{padding:10px 12px;border-bottom:1px solid #8884;text-align:left;vertical-align:top}
thead{background:light-dark(#f0f2f5,#22272b)}
code{overflow-wrap:anywhere;font-size:.88em}
.warning{border-left:3px solid #a48234;padding:10px 14px;background:light-dark(#f6f4ea,#28251c)}
a{color:inherit}footer{margin-top:28px;border-top:1px solid #8885;padding-top:14px;font-size:.85rem}
</style></head><body>
<header><small>UPC / Phase 1 / OFFLINE SNAPSHOT</small>
<h1>広告・追跡防止ルール評価</h1>
<p class="muted">公開フィルターを変更しない固定スナップショットの診断レポート</p></header>
<section aria-labelledby="stats"><h2 id="stats">検証情報</h2><dl class="metrics">
""" + metric + """
</dl></section>
<section aria-labelledby="risk"><h2 id="risk">判定の限界</h2>
<p class="warning"><strong>NO_GO：</strong>完全一致なしは追加の広告・追跡遮断を保証しません。
既定ブロッカーの購読状況、実サイト、署名付きURL、ログイン、決済、動画再生の安全性は未検証です。
このレポートはブラウザーやOSの設定を変更しません。</p></section>
<section aria-labelledby="rules"><h2 id="rules">候補ルールの分類</h2>
<div class="table-scroll"><table><thead><tr>
<th scope="col">元のルール</th><th scope="col">分類</th><th scope="col">構文判定</th>
</tr></thead><tbody>
""" + items + """
</tbody></table></div></section>
<footer>Fixed source only · No live traffic · No automatic promotion · Publication NO_GO</footer>
</body></html>
"""
