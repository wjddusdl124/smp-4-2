# -*- coding: utf-8 -*-
CSS = r'''
.pi { --pi-brand: #667eea; --pi-brand2: #764ba2;
  --pi-ink: color-mix(in srgb, #667eea 62%, var(--color-fg));
  --pi-soft: color-mix(in srgb, #667eea 9%, var(--color-panel));
  --pi-line: color-mix(in srgb, #667eea 22%, var(--color-border-line));
  --pi-r: 16px;
  display: grid; gap: 40px; font-family: var(--font-anthropic-sans); max-width: 1120px; margin-inline: auto; padding-bottom: 48px; }
.pi .page b, .pi b { font-weight: 600; color: var(--color-fg); }

/* ---------- 위쪽 고정 메뉴 */
.pi-nav { position: sticky; top: 0; z-index: 5; display: flex; align-items: center; gap: 12px; padding: 10px 0;
  background: color-mix(in srgb, var(--color-bg) 88%, transparent); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--color-border-line); margin-bottom: -24px; }
.pi-nav .brand { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; white-space: nowrap; }
.pi-nav .brand i { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(135deg, var(--pi-brand), var(--pi-brand2)); display: inline-block; }
.pi-nav .links { display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none; margin-left: auto; }
.pi-nav .links::-webkit-scrollbar { display: none; }
.pi-nav a { font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); text-decoration: none; padding: 7px 12px; border-radius: 999px; white-space: nowrap; }
.pi-nav a:hover { color: var(--color-fg); background: var(--pi-soft); }
.pi-nav a.on { color: #fff; background: var(--pi-brand); font-weight: var(--cds-font-weight-medium); }

/* ---------- 머리 (히어로) */
.pi-hero { border-radius: 22px; padding: clamp(20px, 4vw, 40px); display: grid; gap: 20px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--pi-brand) 16%, var(--color-panel)), color-mix(in srgb, var(--pi-brand2) 12%, var(--color-panel)));
  border: 1px solid var(--pi-line); }
.pi-hero .eyebrow { font-size: var(--cds-font-size-caption); color: var(--pi-ink); font-weight: 600; letter-spacing: .02em; }
.pi-hero h1 { font-size: clamp(26px, 4.2vw, 40px); line-height: 1.2; font-weight: 700; margin: 4px 0 0; letter-spacing: -0.02em; text-wrap: balance; }
.pi-hero p { margin: 0; color: var(--color-fg-muted); line-height: 1.65; max-width: 68ch; }
.pi-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr)); gap: 12px; }
.pi-stat { background: var(--color-panel); border-radius: 14px; padding: 16px 18px; display: grid; gap: 4px; text-decoration: none; color: inherit; border: 1px solid transparent; transition: border-color .15s; }
.pi-stat:hover { border-color: var(--pi-line); }
.pi-stat .k { font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); display: flex; align-items: center; gap: 6px; }
.pi-stat .k::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--dot, var(--pi-brand)); }
.pi-stat .v { font-size: 30px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; line-height: 1.15; }
.pi-stat .v small { font-size: 15px; font-weight: 500; color: var(--color-fg-muted); margin-left: 3px; }
.pi-stat .s { font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); line-height: 1.5; }

/* ---------- 구역 */
.pi-tab { display: grid; gap: 16px; scroll-margin-top: 64px; }
.pi-shead { display: grid; gap: 6px; padding-top: 8px; }
.pi-shead .num { font-size: var(--cds-font-size-caption); font-weight: 700; color: var(--pi-ink); letter-spacing: .06em; }
.pi-shead h2 { font-size: clamp(21px, 2.8vw, 27px); font-weight: 700; margin: 0; letter-spacing: -0.015em; }
.pi-shead p { margin: 0; color: var(--color-fg-muted); line-height: 1.6; max-width: 72ch; }
.pi-lead { margin: 0; font-size: var(--cds-font-size-body); line-height: 1.65; max-width: 78ch; color: var(--color-fg-muted); }
.pi-h { font-size: var(--cds-font-size-heading); font-weight: 600; margin: 8px 0 0; }

.pi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 24rem), 1fr)); gap: 16px; }
.pi-card { background: var(--color-panel); border: 1px solid var(--color-border-line); box-shadow: 0 1px 2px color-mix(in srgb, var(--color-fg) 6%, transparent); border-radius: var(--pi-r); padding: clamp(16px, 2.4vw, 24px); display: grid; gap: 12px; min-width: 0; align-content: start; }
.pi-card.wide { grid-column: 1 / -1; }
.pi-card h2 { font-size: 17px; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
.pi-card .note { font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); margin: 0; line-height: 1.6; }
.pi-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: space-between; }

/* 큰 숫자 카드 */
.pi-big, .pi-kpis, .pi-alert, .pi-goals { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 14rem), 1fr)); gap: 12px; }
.pi-bigcard, .pi-kpi, .pi-alert > div, .pi-goal { background: var(--color-panel); border: 1px solid var(--color-border-line); box-shadow: 0 1px 2px color-mix(in srgb, var(--color-fg) 6%, transparent); border-radius: 14px; padding: 16px 18px; display: grid; gap: 4px; align-content: start; }
.pi-alert > div { background: var(--pi-soft); border-color: var(--pi-line); }
.pi-bigcard .q, .pi-kpi .lab, .pi-alert .lab, .pi-goal .lab { font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); line-height: 1.45; }
.pi-bigcard .q { font-size: var(--cds-font-size-body); color: var(--color-fg); font-weight: 500; }
.pi-bigcard .a, .pi-kpi .val, .pi-alert .val, .pi-goal .val { font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; line-height: 1.2; }
.pi-bigcard .a small { font-size: 14px; font-weight: 500; color: var(--color-fg-muted); margin-left: 3px; }
.pi-bigcard .was { color: var(--color-fg-muted); font-weight: 500; }
.pi-bigcard .d, .pi-kpi .sub, .pi-alert .sub, .pi-goal .sub { font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); line-height: 1.5; }
.pi-kpi .ok { color: var(--color-ok); }

/* 목표 카드 */
.pi-goal .top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.pi-goal .lab { font-weight: 600; color: var(--color-fg); font-size: var(--cds-font-size-body); }
.pi-chip { font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 999px; background: var(--pi-soft); color: var(--pi-ink); white-space: nowrap; }
.pi-chip.ok { background: color-mix(in srgb, var(--color-ok) 14%, var(--color-panel)); color: var(--color-ok); }
.pi-chip.bad { background: color-mix(in srgb, var(--color-bad) 12%, var(--color-panel)); color: var(--color-bad); }
.pi-goal .goal { font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); }
.pi-bullet { position: relative; height: 10px; border-radius: 999px; background: color-mix(in srgb, var(--color-fg) 7%, var(--color-panel)); margin: 8px 0 6px; }
.pi-bullet .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 999px; background: var(--pi-brand); }
.pi-bullet .tick { position: absolute; top: -5px; bottom: -5px; width: 2px; background: var(--color-fg); border-radius: 1px; }
.pi-bullet .tick span { position: absolute; top: 20px; left: 50%; transform: translateX(-50%); font-size: 11px; color: var(--color-fg-muted); white-space: nowrap; }

/* 오차 비중 막대 */
.pi-share { display: grid; gap: 10px; }
.pi-share .row { display: grid; grid-template-columns: 5.5rem 1fr; gap: 10px; align-items: center; font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); }
.pi-share .bar { display: flex; height: 26px; border-radius: 8px; overflow: hidden; }
.pi-share .bar div { display: flex; align-items: center; justify-content: center; color: #fff; font-size: 11px; font-weight: 600; font-variant-numeric: tabular-nums; min-width: 0; overflow: hidden; white-space: nowrap; }

/* 표 */
.pi-tbl { overflow-x: auto; border: 1px solid var(--color-border-line); border-radius: 12px; }
.pi table { border-collapse: collapse; width: 100%; font-size: var(--cds-font-size-caption); font-variant-numeric: tabular-nums; }
.pi th, .pi td { padding: 9px 12px; text-align: right; border-bottom: 1px solid var(--color-border-line); white-space: nowrap; }
.pi tbody tr:last-child td { border-bottom: 0; }
.pi th:first-child, .pi td:first-child { text-align: left; }
.pi th { color: var(--color-fg-muted); font-weight: 500; background: color-mix(in srgb, var(--color-fg) 3%, var(--color-panel)); }
.pi tbody tr:hover td { background: var(--pi-soft); }
.pi tr.final td { font-weight: 600; background: var(--pi-soft); }
.pi td.in, .pi td.hit { color: var(--color-ok); font-weight: 600; }
.pi td.out { color: var(--color-warn); }
.pi td.miss { color: var(--color-bad); font-weight: 600; }
.pi td.wrap, .pi th.wrap { white-space: normal; text-align: left; min-width: 12rem; }

/* 차트 */
.pi-legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); }
.pi-legend span { display: inline-flex; align-items: center; gap: 6px; }
.pi-legend i { display: inline-block; width: 14px; height: 3px; border-radius: 2px; }
.pi-legend i.band { height: 10px; opacity: .3; }
.pi-legend i.dot { width: 8px; height: 8px; border-radius: 50%; }
.pi select { font: inherit; font-size: var(--cds-font-size-caption); padding: 5px 10px; border-radius: 999px; border: 1px solid var(--color-border-line); background: var(--color-panel); color: var(--color-fg); }
.pi-chart { position: relative; min-height: 300px; }
.pi-chart.short { min-height: 220px; }
.pi-chart svg { display: block; overflow: visible; }
.pi-tip { position: absolute; pointer-events: none; background: var(--cds-surface-popover); border: 1px solid var(--cds-border); border-radius: 10px; box-shadow: var(--cds-shadow-popover); padding: 8px 10px; font-size: var(--cds-font-size-caption); white-space: nowrap; z-index: 2; }
.pi-tip .t { color: var(--cds-text-secondary); margin-bottom: 2px; }
.pi-tip .r { display: flex; gap: 6px; align-items: center; font-variant-numeric: tabular-nums; }
.pi-tip .r i { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.pi .axis text { fill: var(--color-fg-muted); font-size: 11px; }
.pi .axis path, .pi .axis line { stroke: var(--cds-chart-axis); }
.pi .grid line { stroke: var(--cds-chart-grid); }
.pi .grid path { display: none; }

/* 글 */
.pi-steps { margin: 0; padding-left: 1.2em; display: grid; gap: 8px; line-height: 1.6; }
.pi-plain { margin: 0; padding-left: 1.1em; display: grid; gap: 10px; line-height: 1.6; }
.pi-plain li::marker, .pi-steps li::marker { color: var(--pi-brand); }
.pi-terms { margin: 0; display: grid; grid-template-columns: max-content 1fr; gap: 8px 14px; line-height: 1.55; }
.pi-terms dt { font-weight: 600; }
.pi-terms dd { margin: 0; color: var(--color-fg-muted); }
.pi-more summary { cursor: pointer; font-size: var(--cds-font-size-caption); color: var(--pi-ink); font-weight: 500; padding: 4px 0; }
.pi-more[open] { display: grid; gap: 12px; }
.pi-foot { margin: 0; font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); }
.pi-callout { border-left: 3px solid var(--pi-brand); background: var(--pi-soft); border-radius: 0 12px 12px 0; padding: 12px 16px; line-height: 1.6; font-size: var(--cds-font-size-body); }
.pi-callout b { color: var(--pi-ink); }
[data-dash-source-state=empty] { color: transparent; }
[data-dash-source-state=refreshing] { opacity: .5; transition: opacity var(--cds-dur-slow); }
.pi-fail { display: flex; align-items: center; justify-content: center; gap: 6px; min-height: inherit; color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); }
.pi-fail::before { content: ""; width: .375rem; height: .375rem; border-radius: 50%; background: var(--color-bad); }
@media (max-width: 640px) {
  .pi { gap: 32px; }
  .pi-nav .brand span { display: none; }
  .pi-terms { grid-template-columns: 1fr; gap: 2px; }
  .pi-terms dd { margin-bottom: 8px; }
}
'''

PA = 'data-source="price_adjust"'
W0 = 'data-where="기간=2026&amp;방법=최종 모델 (조정 없음)&amp;기준=전체 시간"'

HEAD = f'''  <nav class="pi-nav" aria-label="구역">
    <span class="brand"><i></i><span>SMP 한눈에</span></span>
    <div class="links">
      <a href="#tab-overview" data-to="tab-overview" class="on">한눈에</a>
      <a href="#tab-price" data-to="tab-price">평소 가격</a>
      <a href="#tab-drop" data-to="tab-drop">급락 경보</a>
      <a href="#tab-spike" data-to="tab-spike">급등 대응</a>
      <a href="#tab-model" data-to="tab-model">예측 범위</a>
    </div>
  </nav>

  <header class="pi-hero" id="top">
    <div>
      <div class="eyebrow">육지 SMP 하루 전 예측 · 시험 구간 2026년 1~9월</div>
      <h1>평소 가격, 급락, 급등을<br>각각 다른 모델로 봅니다</h1>
    </div>
    <p id="takeaway">평소 가격은 목표 4개 중 <b {PA} data-field="달성 수" {W0}>—</b>개를 달성해 아직 목표에 못 미칩니다. 급락일은 하루 전 경보로 <b data-source="drop_perf" data-field="2026 잡은 날" data-where="목표=75%25">—</b>일을 알렸고, 급등일 <b data-source="spike_summary" data-field="급등일" data-where="기간=2026">—</b>일 중 <b data-source="spike_summary" data-field="경보 또는 범위로 대비" data-where="기간=2026">—</b>일은 경보나 넓힌 예측 범위로 대비했습니다.</p>
    <div class="pi-stats">
      <a class="pi-stat" href="#tab-price" data-to="tab-price">
        <span class="k">평소 가격 · 평균 오차 (MAE)</span>
        <span class="v"><span data-source="price_targets" data-field="2026 전체 시간" data-where="지표=MAE (원)">—</span><small>원</small></span>
        <span class="s">목표 <span data-source="price_targets" data-field="목표값" data-where="지표=MAE (원)">—</span>원 이하 · 목표 4개 중 <span {PA} data-field="달성 수" {W0}>—</span>개 달성</span>
      </a>
      <a class="pi-stat" href="#tab-drop" data-to="tab-drop" style="--dot: var(--cds-chart-status-critical)">
        <span class="k">급락 경보 · 잡은 급락일</span>
        <span class="v"><span data-source="drop_perf" data-field="2026 잡은 날" data-where="목표=75%25">—</span><small>일</small></span>
        <span class="s">경보 <span data-source="drop_perf" data-field="2026 경보일" data-where="목표=75%25">—</span>일 중 <span data-source="drop_perf" data-field="2026 적중률(%)" data-where="목표=75%25">—</span>% 적중</span>
      </a>
      <a class="pi-stat" href="#tab-spike" data-to="tab-spike" style="--dot: var(--color-warn)">
        <span class="k">급등 대응 · 대비한 급등일</span>
        <span class="v"><span data-source="spike_summary" data-field="경보 또는 범위로 대비" data-where="기간=2026">—</span><small>/ <span data-source="spike_summary" data-field="급등일" data-where="기간=2026">—</span>일</small></span>
        <span class="s">하루 전 경보 <span data-source="spike_summary" data-field="하루 전 경보로 잡음" data-where="기간=2026">—</span>일 · 예측 범위 안 <span data-source="spike_summary" data-field="범위로 담음" data-where="기간=2026">—</span>일</span>
      </a>
    </div>
  </header>
'''

def shead(num, title, desc):
    return f'''    <div class="pi-shead"><span class="num">{num}</span><h2>{title}</h2><p>{desc}</p></div>
'''

def goal(key, name, unit):
    k = key.replace('%', '%25')
    w = f'data-where="지표={k}"'
    return f'''      <div class="pi-goal" data-metric="{key}">
        <div class="top"><span class="lab">{name}</span><span class="pi-chip" data-source="price_targets" data-field="판정" {w}>—</span></div>
        <span class="val"><span data-source="price_targets" data-field="2026 전체 시간" {w}>—</span>{unit}</span>
        <span class="goal">목표(세로선) <span data-source="price_targets" data-field="목표" {w}>—</span> · 차이 <span data-source="price_targets" data-field="차이" {w}>—</span></span>
        <div class="pi-bullet" data-source="price_targets"></div>
        <span class="sub">2025년 <span data-source="price_targets" data-field="2025 전체 시간" {w}>—</span> · 평소 시간만 <span data-source="price_targets" data-field="2026 평소 시간만 (참고)" {w}>—</span></span>
      </div>
'''

RG = lambda g, f: f'data-source="price_regimes" data-field="{f}" data-where="구간={g}"'

PRICE = f'''  <!-- ================= 평소 가격 예측 ================= -->
  <section class="pi-tab" id="tab-price">
{shead('02 · 평소 가격 예측', '평소 가격은 얼마나 정확한가요?', '매일 다음 날 24시간의 가격을 하나의 값(중앙값)으로 예측한 성적입니다. 목표 판정은 급등·급락 시간까지 모두 포함한 <b>전체 시간</b> 기준이고, 평소 시간만 따로 본 값은 참고용입니다.')}
    <div class="pi-goals" id="price-goals">
{goal('rMAE', 'rMAE', '')}{goal('MAE (원)', 'MAE', '<small>원</small>')}{goal('MAPE (%)', 'MAPE', '%')}{goal('편의 (%)', '편의 (치우침)', '%')}    </div>
    <p class="pi-foot">rMAE = 우리 오차 ÷ '어제 같은 시각 가격을 그대로 쓴' 오차 (1보다 작을수록 좋음). 편의 = 평균적으로 실제보다 높게(+)·낮게(−) 예측한 정도. MAPE·편의는 가격이 20원 미만이면 20원으로 나눕니다.</p>

    <div class="pi-grid">
      <section class="pi-card" id="price-share-card">
        <h2>오차는 어디서 나오나요?</h2>
        <p class="note">2026년 시간을 평소·급등·급락으로 나눴습니다(어제 같은 시각보다 2025년 변화폭 상·하위 5% 이상 움직이면 급등·급락). 급락 시간은 전체의 <b {RG('급락', '시간 비중(%)')}>—</b>%뿐이지만 오차의 <b {RG('급락', '오차 비중(%)')}>—</b>%를 차지합니다.</p>
        <div class="pi-legend" id="share-legend"></div>
        <div class="pi-share" id="price-share" data-source="price_regimes"></div>
        <div class="pi-tbl">
          <table id="price-regimes" data-source="price_regimes" data-row-key="구간">
            <thead><tr><th data-field="구간">구간</th><th data-field="시간수">시간</th><th data-field="MAE">MAE(원)</th><th data-field="편의(%)">편의(%)</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <p class="note">급락 시간에는 실제보다 높게(편의 <span {RG('급락', '편의(%)')}>—</span>%), 급등 시간에는 낮게(<span {RG('급등', '편의(%)')}>—</span>%) 예측합니다. 평소 시간만 보면 MAE는 목표 안(<span {RG('평소', 'MAE')}>—</span>원)이지만, rMAE는 <span data-source="price_targets" data-field="2026 평소 시간만 (참고)" data-where="지표=rMAE">—</span>로 오히려 높습니다. 평소에는 어제 가격을 그대로 써도 잘 맞기 때문입니다.</p>
      </section>

      <section class="pi-card" id="price-adjust-card">
        <h2>경보를 중앙값에 반영하면?</h2>
        <p class="note">급락 경보가 뜬 날 12~14시의 중앙값을 하한 쪽으로 옮겨 봤습니다(25%·50%·100%). 편의는 목표 안으로 들어오지만 MAE·rMAE는 나빠집니다.</p>
        <div class="pi-tbl">
          <table id="price-adjust" data-source="price_adjust" data-row-key="기간,방법,기준">
            <thead><tr><th data-field="방법" class="wrap">2026 · 전체 시간</th><th data-field="MAE">MAE</th><th data-field="rMAE">rMAE</th><th data-field="MAPE(%)">MAPE(%)</th><th data-field="편의(%)">편의(%)</th><th data-field="달성 수">달성</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <div class="pi-callout">2025년 MAE로 고르면 <b>조정하지 않는 쪽</b>이 뽑혀 최종 모델은 그대로 둡니다. 편의 목표가 더 중요하면 25% 낮춤을 쓸 수 있습니다(MAE <span {PA} data-field="MAE" data-where="기간=2026&amp;방법=급락 경보일 낮 시간 낮춤 25%25&amp;기준=전체 시간">—</span>원, 편의 <span {PA} data-field="편의(%)" data-where="기간=2026&amp;방법=급락 경보일 낮 시간 낮춤 25%25&amp;기준=전체 시간">—</span>%). 급등 경보일에 중앙값을 올리는 조정은 모든 지표가 나빠져 뺐습니다.</div>
        <details class="pi-more"><summary>자세히: 2025년 결과</summary>
          <div class="pi-tbl">
            <table id="price-adjust-25" data-source="price_adjust" data-row-key="기간,방법,기준">
              <thead><tr><th data-field="방법" class="wrap">2025 · 전체 시간</th><th data-field="MAE">MAE</th><th data-field="rMAE">rMAE</th><th data-field="MAPE(%)">MAPE(%)</th><th data-field="편의(%)">편의(%)</th><th data-field="달성 수">달성</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </details>
      </section>
    </div>

    <section class="pi-card wide">
      <h2>목표를 넘으려면</h2>
      <ul class="pi-plain">
        <li><b>MAE·rMAE:</b> 오차의 대부분(평소 시간 <span {RG('평소', '오차 비중(%)')}>—</span>%)은 평소 시간에서 나옵니다. 평소 가격 모델 자체를 개선해야 합니다. 2026년 실측 수요·풍력이 비어 있고 태양광은 6월부터 비어 있어, 이 값을 채우는 것이 첫 번째 후보입니다.</li>
        <li><b>MAPE:</b> 가격이 0원 근처인 급락 시간에 크게 튑니다. 급락 경보와 함께 쓰면 줄일 수 있지만 MAE와 맞바꿔야 합니다.</li>
        <li><b>편의:</b> 급락 경보일 낮 시간을 25% 낮추면 목표 안으로 들어옵니다(위 표).</li>
      </ul>
    </section>
  </section>
'''

OVERVIEW = '''  <!-- ================= 한눈에 ================= -->
  <section class="pi-tab" id="tab-overview">
''' + shead('01 · 한눈에', '무엇이 좋아졌고, 무엇이 남았나요?', '이전 모델(앙상블 + 등각 보정)과 비교한 2026년 1~9월 결과입니다.') + '''    <div class="pi-big">
      <div class="pi-bigcard">
        <span class="q">급락한 시간, 실제 가격이 예측보다 더 떨어진 비율</span>
        <span class="a"><span class="was" data-source="spike_actions" data-field="기존" data-where="항목=[모두 적용] 급락 시간 놓침(%25, 2026)">—</span>% → <span data-source="spike_actions" data-field="대책 후" data-where="항목=[모두 적용] 급락 시간 놓침(%25, 2026)">—</span>%</span>
        <span class="d">낮을수록 좋음 · 이전 모델 → 지금</span>
      </div>
      <div class="pi-bigcard">
        <span class="q">급등한 시간, 실제 가격이 예측보다 더 오른 비율</span>
        <span class="a"><span class="was" data-source="spike_actions" data-field="기존" data-where="항목=[모두 적용] 급등 시간 놓침(%25, 2026)">—</span>% → <span data-source="spike_actions" data-field="대책 후" data-where="항목=[모두 적용] 급등 시간 놓침(%25, 2026)">—</span>%</span>
        <span class="d">낮을수록 좋음 · 이전 모델 → 지금</span>
      </div>
      <div class="pi-bigcard">
        <span class="q">대가: 예측 범위가 넓어졌어요</span>
        <span class="a"><span class="was" data-source="spike_actions" data-field="기존" data-where="항목=[모두 적용] 평균 범위 폭(원, 2026)">—</span> → <span data-source="spike_actions" data-field="대책 후" data-where="항목=[모두 적용] 평균 범위 폭(원, 2026)">—</span><small>원</small></span>
        <span class="d">범위 안에 든 시간 <span data-source="spike_actions" data-field="기존" data-where="항목=[모두 적용] 범위 안에 든 비율(%25, 2026)">—</span>% → <span data-source="spike_actions" data-field="대책 후" data-where="항목=[모두 적용] 범위 안에 든 비율(%25, 2026)">—</span>% (과제 목표 75~85%를 넘음)</span>
      </div>
    </div>

    <div class="pi-grid">
      <section class="pi-card">
        <h2>아직 안 되는 것</h2>
        <ul class="pi-plain">
          <li><b>평소 가격 목표.</b> MAE·rMAE·MAPE·편의 모두 목표에 조금씩 못 미칩니다(평소 가격 구역).</li>
          <li><b>처음 터지는 겨울 급등을 하루 전에 맞히기.</b> 수요·태양광·원전·석탄·가스가 평소와 같은 날에도 터졌습니다. 대신 급등이 몰리는 시각의 범위를 늘 넓혀 둡니다.</li>
          <li><b>평일에 생기는 0원 급락.</b> 놓친 급락일은 수요로 보면 평범한 날이었습니다.</li>
          <li><b>필요한 데이터:</b> 원전·석탄 발전량, 시장 밖(PPA·자가용) 태양광, 가격결정발전기 이력.</li>
        </ul>
      </section>
      <section class="pi-card">
        <h2>용어</h2>
        <dl class="pi-terms">
          <dt>급락일</dt><dd>그날 최저가가 직전 28일 최저가 중앙값의 절반 이하인 날. 대부분 휴일 13시 0원.</dd>
          <dt>급등일</dt><dd>그날 최고가가 직전 28일 최고가 중앙값의 1.25배 이상인 날. 대부분 평일 1시간.</dd>
          <dt>예측 범위</dt><dd>"실제 가격이 이 사이에 있을 것"이라는 하한~상한. 10시간 중 8시간이 들어오게 맞춥니다.</dd>
          <dt>중앙값</dt><dd>예측 범위의 가운데 값. 평소 가격 성적(MAE 등)은 이 값으로 잽니다.</dd>
          <dt>경보 문턱</dt><dd>모델이 계산한 확률이 이 값 이상이면 경보. 급락은 2025년 급락일의 75%를 잡는 값, 급등은 2025년 확률 상위 20일이 되는 값.</dd>
        </dl>
      </section>
    </div>
  </section>
'''

JS_PRICE = r'''
  // ---------- 평소 가격 예측
  function drawPrice() {
    ['price_targets', 'price_regimes', 'price_adjust'].forEach(fillWhere);
    document.querySelectorAll('.pi-chip[data-source="price_targets"]').forEach(el => {
      el.classList.toggle('ok', el.textContent === '달성'); el.classList.toggle('bad', el.textContent === '미달');
    });
    const is = (y, b) => r => String(r['기간']) === y && r['기준'] === b;
    fillTable('#price-adjust', 'price_adjust', null, is('2026', '전체 시간'));
    fillTable('#price-adjust-25', 'price_adjust', null, is('2025', '전체 시간'));
    fillTable('#price-regimes', 'price_regimes');
    ['#price-adjust', '#price-adjust-25'].forEach(s => document.querySelectorAll(s + ' tbody tr').forEach(tr => {
      if (tr.firstChild && tr.firstChild.textContent.indexOf('최종 모델') === 0) tr.className = 'final';
    }));
    const t = dash.data('price_targets');
    document.querySelectorAll('.pi-goal').forEach(card => {
      const box = card.querySelector('.pi-bullet');
      box.innerHTML = '';
      box.classList.toggle('dash-skeleton', t.status === 'loading');
      if (t.status !== 'ok') return;
      const r = t.data.find(x => x['지표'] === card.dataset.metric);
      if (!r) return;
      const v = Math.abs(+r['2026 전체 시간']), g = +r['목표값'], mx = Math.max(v, g, Math.abs(+r['2025 전체 시간'])) * 1.25;
      const fill = document.createElement('div'); fill.className = 'fill'; fill.style.width = (100 * v / mx) + '%';
      if (r['판정'] === '미달') fill.style.background = 'linear-gradient(90deg, var(--pi-brand) ' + (100 * g / v) + '%, var(--color-bad) ' + (100 * g / v) + '%)';
      const tk = document.createElement('div'); tk.className = 'tick'; tk.style.left = (100 * g / mx) + '%';
      tk.title = '목표';
      box.appendChild(fill); box.appendChild(tk);
    });
    const box = document.getElementById('price-share');
    const s = dash.data('price_regimes');
    if (s.status !== 'ok') { pending(box, s.status); return; }
    box.classList.remove('dash-skeleton');
    const col = { '평소': 'var(--pi-brand)', '급등': 'var(--color-warn)', '급락': 'var(--cds-chart-status-critical)' };
    legend('share-legend', s.data.map(r => [r['구간'], col[r['구간']] || 'var(--cds-chart-muted)']));
    box.innerHTML = '';
    [['시간 비중(%)', '시간 비중'], ['오차 비중(%)', '오차 비중']].forEach(([k, lab]) => {
      const row = document.createElement('div'); row.className = 'row';
      const l = document.createElement('span'); l.textContent = lab; row.appendChild(l);
      const bar = document.createElement('div'); bar.className = 'bar';
      s.data.forEach(r => {
        const d = document.createElement('div'); const v = +r[k];
        d.style.width = v + '%'; d.style.background = col[r['구간']] || 'var(--cds-chart-muted)';
        if (v >= 8) d.textContent = v + '%';
        d.title = `${r['구간']} ${v}%`;
        bar.appendChild(d);
      });
      row.appendChild(bar); box.appendChild(row);
    });
  }
'''

JS_NAV = r'''  const redraw = () => { drawPrice(); drawDrop(); drawSpike(); drawKpis(); drawMethods(); drawFan(); drawHourly(); drawWeights(); drawRegimes(); };
  dash.onData(redraw);
  // ---------- 위쪽 메뉴 : 해당 구역으로 이동 + 지금 보는 구역 표시
  const navLinks = [...document.querySelectorAll('.pi-nav a')];
  const mark = (id) => navLinks.forEach(a => a.classList.toggle('on', a.dataset.to === id));
  const go = (id) => { const el = document.getElementById(id); if (!el) return false; el.scrollIntoView({ behavior: 'smooth', block: 'start' }); mark(id); return true; };
  document.querySelectorAll('[data-to]').forEach(a => a.addEventListener('click', (e) => { e.preventDefault(); go(a.dataset.to); dash.setLink(a.dataset.to); }));
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((ents) => {
      ents.filter(e => e.isIntersecting).forEach(e => mark(e.target.id));
    }, { rootMargin: '-30% 0px -60% 0px' });
    document.querySelectorAll('.pi-tab').forEach(s => io.observe(s));
  }
  const named = location.hash.slice(1);
  if (named) {
    const el = document.getElementById(named);
    if (el) { const sec = el.closest('.pi-tab'); requestAnimationFrame(() => { el.scrollIntoView(); if (sec) mark(sec.id); }); }
  }
})();
</script>
'''
