import json
import os
D = os.path.dirname(os.path.abspath(__file__)) + '/'
body = open(D + 'body_v10.html').read()
body = body.replace('<li>평소 가격 목표 4개 모두 미달.</li>', '<li>평소 가격 목표(rMAE·MAE·MAPE·편의) 미달.</li>')
js = open(D + 'script_v9.js').read()
def rep(a, b, n=1):
    global js
    assert js.count(a) == n, (a[:70], js.count(a)); js = js.replace(a, b)
rep(".call(d3.axisBottom(x).tickValues(months.map(r => r.date))",
    ".call(d3.axisBottom(x).tickValues(months.reduce((a, r) => { if (!a.length || x(r.date) - x(a[a.length - 1]) >= 30) a.push(r.date); return a; }, []))", 2)
rep(".attr('fill', 'var(--color-fg-muted)').attr('font-size', 11).text('경보 문턱 ' + tW + '%');",
    ".attr('fill', 'var(--color-fg-muted)').attr('font-size', 11).attr('class', 'halo').text('경보 문턱 ' + tW + '%');", 2)
a = js.index("    document.getElementById('fan-note').textContent ="); b = js.index("\n", js.index("평균 폭", a))
js = js[:a] + "    document.getElementById('fan-note').textContent = `이 기간 범위 안 ${f1(cov * 100)}% · 평균 폭 ${f1(d3.mean(rows, r => r.hi - r.lo))}원`;" + js[b:]
rep("sub.textContent = (p >= 75 && p <= 85 ? '목표 범위 안 · ' : '목표 범위 밖 · ') + '시험 구간 2026.1.1~9.30';",
    "sub.textContent = p >= 75 && p <= 85 ? '목표 75~85% 안' : '목표 75~85% 밖';")
rep("const go = (id) => { const el = document.getElementById(id); if (!el) return false; el.scrollIntoView({ behavior: 'smooth', block: 'start' }); mark(id); return true; };",
    "const go = (id) => { const el = document.getElementById(id); if (!el) return false; if (el.tagName === 'DETAILS') el.open = true; el.scrollIntoView({ behavior: 'smooth', block: 'start' }); const sec = el.closest('.pi-tab'); mark(sec ? sec.id : id); return true; };")
rep("    fillTable('#price-regimes', 'price_regimes');", "    fillTable('#price-regimes', 'price_regimes');\n    fillTable('#price-exp', 'price_experiments', (c, v) => c === '결과' ? (v === '2026 나빠짐' ? 'miss' : (v === '편의만 달성' ? 'hit' : null)) : null);\n    document.querySelectorAll('#price-exp tbody tr').forEach(tr => { if (tr.firstChild && tr.firstChild.textContent === '기존 최종 모델') tr.className = 'final'; });")
rep("    fillTable('#price-regimes', 'price_regimes');\n", "    fillTable('#price-regimes', 'price_regimes');\n    fillTable('#fuel-tests', 'fuel_tests', (c, v) => c === '판정' ? (v === '나빠짐' ? 'miss' : null) : null);\n    document.querySelectorAll('#fuel-tests tbody tr').forEach(tr => { if (tr.lastChild && tr.lastChild.textContent === '기준') tr.className = 'final'; });\n")
rep("    fillTable('#price-regimes', 'price_regimes');\n", "    fillTable('#price-regimes', 'price_regimes');\n    fillTable('#common-period', 'common_period');\n    document.querySelectorAll('#common-period tbody tr').forEach(tr => { if (tr.firstChild && tr.firstChild.textContent.indexOf('최종') === 0) tr.className = 'final'; });\n    fillTable('#drop-weekday', 'drop_weekday', null, r => String(r['기간']) === '2026');\n    fillTable('#drop-weekday-25', 'drop_weekday', null, r => String(r['기간']) === '2025');\n    document.querySelectorAll('#drop-weekday tbody tr, #drop-weekday-25 tbody tr').forEach(tr => { if (tr.children[1] && tr.children[1].textContent.indexOf('경보 모델 +') === 0) tr.className = 'final'; });\n")
rep("['실제 최저가', r.min === '' ? '—' : r.min + '원']", "['한낮 최저가', r.min === '' ? '—' : r.min + '원']")
s = body + '\n' + js
assert 'pi-tabs' not in s
open(D + 'page_v10.html', 'w').write(s)
json.dump({"text": s}, open(D + 'index_v10.json', 'w'), ensure_ascii=False)
print(len(s.encode()))
