# -*- coding: utf-8 -*-
"""
build_standalone.py — 대시보드를 인터넷·서버 없이 여는 파일 하나(dashboard.html)로 만듦
  python experiments/spike_drop/dashboard/build_standalone.py
  → experiments/spike_drop/dashboard/dashboard.html 을 브라우저로 열면 됨 (더블클릭)
page.html      : claude.ai 대시보드에 올린 페이지 원본 (그대로 사용)
d3.min.js      : d3 7.9.0 (차트 라이브러리, 파일에 넣어 둠)
../dash_export : make_dashboard_data.py 가 만든 데이터셋 20개
아래 SHIM 은 claude.ai 대시보드가 제공하던 dash.data / dash.onData / dash.colors / dash.setLink 와 색상 변수를 흉내 낸다.
"""
import os, json, glob

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'dash_export')

TOKENS = '''
:root { color-scheme: light dark;
  --color-bg:#f7f7f5; --color-panel:#ffffff; --color-fg:#1f1e1d; --color-fg-muted:#6b6a66; --color-border-line:#e6e4df;
  --color-ok:#2f7d4f; --color-bad:#c2410c; --color-warn:#b7791f;
  --cds-chart-muted:#c9c7c1; --cds-chart-status-critical:#d93a2b; --cds-chart-reference:#8a8883; --cds-chart-axis:#cfcdc7; --cds-chart-grid:#ecebe7;
  --cds-surface-popover:#ffffff; --cds-border:#e2e0da; --cds-shadow-popover:0 6px 24px rgba(0,0,0,.12); --cds-text-secondary:#6b6a66;
  --cds-dur-slow:.3s; --font-anthropic-sans: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif; }
@media (prefers-color-scheme: dark) { :root {
  --color-bg:#1c1b1a; --color-panel:#262524; --color-fg:#eceae5; --color-fg-muted:#a3a19b; --color-border-line:#3a3936;
  --color-ok:#5cc489; --color-bad:#f08a5d; --color-warn:#e2b04a;
  --cds-chart-muted:#55534f; --cds-chart-status-critical:#ff6b5b; --cds-chart-reference:#8f8d87; --cds-chart-axis:#4a4945; --cds-chart-grid:#33322f;
  --cds-surface-popover:#2c2b29; --cds-border:#3f3e3a; --cds-text-secondary:#a3a19b; } }
body { margin:0; padding:16px; background:var(--color-bg); color:var(--color-fg); font-family:var(--font-anthropic-sans); }
.dash-skeleton { opacity:.4; }
'''

SHIM = '''
window.dash = (function () {
  const raw = window.__DATA__, cache = {}, subs = [];
  const data = (id) => {
    if (!(id in raw)) return { status: 'error', data: [] };
    if (!cache[id]) cache[id] = d3.csvParse(raw[id].replace(/^\\ufeff/, ''));
    return { status: 'ok', data: cache[id] };
  };
  const fill = () => document.querySelectorAll('[data-source][data-field][data-row]').forEach(el => {
    const s = data(el.dataset.source); const r = s.data[+el.dataset.row]; if (r && el.textContent === '—') el.textContent = r[el.dataset.field];
  });
  const api = { data, colors: ['#5f72ec', '#e8853d', '#2a9d8f', '#b05fc4', '#8a8883'],
    onData: (fn) => { subs.push(fn); requestAnimationFrame(() => { fn(); fill(); }); },
    setLink: (id) => { try { history.replaceState(null, '', '#' + id); } catch (e) {} } };
  let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(() => subs.forEach(f => f()), 150); });
  return api;
})();
'''

def main():
    page = open(os.path.join(HERE, 'page.html'), encoding='utf-8').read()
    d3 = open(os.path.join(HERE, 'd3.min.js'), encoding='utf-8').read()
    files = sorted(glob.glob(os.path.join(DATA, '*.csv')))
    raw = {os.path.splitext(os.path.basename(f))[0]: open(f, encoding='utf-8-sig').read() for f in files}
    html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>SMP 예측 대시보드</title><style>' + TOKENS + '</style>'
            '<script>' + d3 + '</script><script>window.__DATA__=' + json.dumps(raw, ensure_ascii=False) + ';</script>'
            '<script>' + SHIM + '</script></head><body>' + page + '</body></html>')
    out = os.path.join(HERE, 'dashboard.html')
    open(out, 'w', encoding='utf-8').write(html)
    print(f'{out} ({len(html.encode()) / 1e6:.1f}MB, 데이터셋 {len(raw)}개)')

if __name__ == '__main__':
    main()
