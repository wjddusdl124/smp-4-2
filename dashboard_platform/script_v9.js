<script>
(() => {
  const FINAL = 'F_앙상블+등각보정(최종)';
  const NAMES = {
    'A_잔차분위수': 'A 잔차 분위수 (쉬운 방법)',
    'B_LightGBM분위수': 'B LightGBM 분위수 회귀',
    'C_Chronos2_수요예측': 'C Chronos-2 + 수요예측',
    'D_Chronos2_단변량': 'D Chronos-2 단변량',
    'E_앙상블': 'E 앙상블 (보정 전)',
    [FINAL]: 'F 앙상블 + 등각 보정 (최종)'
  };
  const f1 = d3.format('.1f'), f2 = d3.format('.2f');
  const parseDT = d3.utcParse('%Y-%m-%d %H:%M');
  const C = () => dash.colors;

  const fail = (box) => { box.innerHTML = ''; const d = document.createElement('div'); d.className = 'pi-fail'; d.textContent = 'Failed to load'; box.appendChild(d); };
  const pending = (box, st) => { box.innerHTML = ''; box.classList.toggle('dash-skeleton', st === 'loading'); if (st === 'error') fail(box); };

  function legend(id, items) {
    const el = document.getElementById(id);
    el.innerHTML = '';
    items.forEach(([label, color, kind]) => {
      const s = document.createElement('span');
      const i = document.createElement('i');
      if (kind) i.className = kind;
      i.style.background = color;
      s.appendChild(i);
      s.appendChild(document.createTextNode(label));
      el.appendChild(s);
    });
  }

  function tipAt(box, tip, x, y) {
    const w = box.clientWidth, tw = tip.node().offsetWidth;
    tip.style('left', Math.max(0, Math.min(w - tw, x + 12)) + 'px').style('top', Math.max(0, y - 10) + 'px');
  }

  function cleanAxis(g) { g.attr('font-size', null).attr('font-family', null); }

  // ---------- 머리말 수치
  function drawKpis() {
    const m = dash.data('metrics');
    document.querySelectorAll('[data-source="metrics"][data-row]').forEach(el => el.classList.toggle('dash-skeleton', m.status === 'loading'));
    if (m.status !== 'ok') return;
    const row = m.data[5];
    const fmt = { 'PICP(%)': v => f1(v) + '%', 'MPIW(원)': v => f1(v) + '원', 'Winkler': v => f1(v), 'MAE(중앙값)': v => f2(v) + '원', 'MAE(어제같은시각)': v => f2(v) + '원', '개선율(%)': v => f1(v) + '%' };
    document.querySelectorAll('[data-source="metrics"][data-row="5"]').forEach(el => {
      const k = el.dataset.field;
      el.textContent = fmt[k](+row[k]);
    });
    const p = +row['PICP(%)'];
    const sub = document.getElementById('kpi-picp-sub');
    sub.textContent = (p >= 75 && p <= 85 ? '목표 범위 안 · ' : '목표 범위 밖 · ') + '시험 구간 2026.1.1~9.30';
    sub.className = 'sub' + (p >= 75 && p <= 85 ? ' ok' : '');
  }

  // ---------- 방법별 표
  function drawMethods() {
    const m = dash.data('metrics');
    const tb = document.querySelector('#methods tbody');
    tb.innerHTML = '';
    if (m.status !== 'ok') return;
    const cols = ['PICP(%)', 'MPIW(원)', 'Winkler', 'pinball_0.1', 'pinball_0.5', 'pinball_0.9', '하한아래(%)', '상한위(%)', 'MAE(중앙값)', '개선율(%)'];
    m.data.forEach(r => {
      const tr = document.createElement('tr');
      tr.dataset.key = r['방법'];
      if (r['방법'] === FINAL) tr.className = 'final';
      const td0 = document.createElement('td');
      td0.textContent = NAMES[r['방법']] || r['방법'];
      tr.appendChild(td0);
      cols.forEach(c => {
        const td = document.createElement('td');
        const v = +r[c];
        td.textContent = c.startsWith('pinball') ? f2(v) : (c === 'MAE(중앙값)' ? f2(v) : f1(v));
        if (c === 'PICP(%)') td.className = v >= 75 && v <= 85 ? 'in' : 'out';
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
  }

  // ---------- 예측 범위 시계열
  const sel = document.getElementById('fan-month');
  let fanMonth = null;
  sel.addEventListener('change', () => { fanMonth = sel.value; drawFan(); });

  function drawFan() {
    const box = document.getElementById('fan');
    const s = dash.data('series');
    if (s.status !== 'ok') { pending(box, s.status); return; }
    box.classList.remove('dash-skeleton');
    const all = s.data.map(r => ({ t: parseDT(r.datetime), y: r.actual === '' ? NaN : +r.actual, lo: +r.lower, md: +r.median, hi: +r.upper }));
    const months = Array.from(new Set(s.data.map(r => r.datetime.slice(0, 7))));
    if (sel.options.length !== months.length + 1) {
      sel.innerHTML = '';
      months.forEach(mo => { const o = document.createElement('option'); o.value = mo; o.textContent = `${+mo.slice(0, 4)}년 ${+mo.slice(5)}월`; sel.appendChild(o); });
      const o = document.createElement('option'); o.value = 'all'; o.textContent = '시험 구간 전체'; sel.appendChild(o);
      if (!fanMonth) fanMonth = months[months.length - 1];
      sel.value = fanMonth;
    }
    const rows = fanMonth === 'all' ? all : all.filter((r, i) => s.data[i].datetime.startsWith(fanMonth));
    const inR = rows.filter(r => !isNaN(r.y));
    const cov = d3.mean(inR, r => (r.y >= r.lo && r.y <= r.hi) ? 1 : 0);
    document.getElementById('fan-note').textContent =
      `음영이 80% 예측 범위(하한 10% · 상한 90% 분위)입니다. 주황 점은 실제 가격이 범위를 벗어난 시간입니다. 이 기간 커버리지 ${f1(cov * 100)}%, 평균 폭 ${f1(d3.mean(rows, r => r.hi - r.lo))}원.`;
    legend('fan-legend', [['80% 예측 범위', C()[0], 'band'], ['예측 중앙값', C()[0]], ['실제 SMP', 'var(--color-fg)'], ['범위 밖', C()[1], 'dot']]);

    const W = Math.max(320, box.clientWidth), H = 320, m = { t: 10, r: 12, b: 26, l: 40 };
    box.innerHTML = '';
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    const x = d3.scaleUtc(d3.extent(rows, r => r.t), [m.l, W - m.r]);
    const ymax = d3.max(rows, r => Math.max(r.hi, isNaN(r.y) ? 0 : r.y));
    const y = d3.scaleLinear([0, ymax * 1.05], [H - m.b, m.t]).nice();
    svg.append('g').attr('class', 'grid').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(W - m.l - m.r)).tickFormat(''));
    svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(Math.max(3, Math.floor(W / 110))).tickFormat(d3.utcFormat('%-m/%-d'))).call(cleanAxis);
    svg.append('g').attr('class', 'axis').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5)).call(cleanAxis);
    svg.append('path').datum(rows).attr('fill', C()[0]).attr('fill-opacity', 0.2)
      .attr('d', d3.area().x(r => x(r.t)).y0(r => y(r.lo)).y1(r => y(r.hi)));
    const line = (acc) => d3.line().defined(r => !isNaN(acc(r))).x(r => x(r.t)).y(r => y(acc(r)));
    svg.append('path').datum(rows).attr('fill', 'none').attr('stroke', C()[0]).attr('stroke-width', fanMonth === 'all' ? 1 : 1.6).attr('stroke-linejoin', 'round').attr('d', line(r => r.md));
    svg.append('path').datum(rows).attr('fill', 'none').attr('stroke', 'var(--color-fg)').attr('stroke-width', fanMonth === 'all' ? 1 : 1.4).attr('stroke-linejoin', 'round').attr('d', line(r => r.y));
    if (fanMonth !== 'all') {
      svg.append('g').selectAll('circle').data(inR.filter(r => r.y < r.lo || r.y > r.hi)).join('circle')
        .attr('cx', r => x(r.t)).attr('cy', r => y(r.y)).attr('r', 3.2).attr('fill', C()[1]).attr('stroke', 'var(--color-panel)').attr('stroke-width', 1.5);
    }
    const rule = svg.append('line').attr('y1', m.t).attr('y2', H - m.b).attr('stroke', 'var(--cds-chart-reference)').style('display', 'none');
    const tip = d3.select(box).append('div').attr('class', 'pi-tip').style('display', 'none');
    const bis = d3.bisector(r => r.t).center;
    svg.append('rect').attr('x', m.l).attr('y', m.t).attr('width', W - m.l - m.r).attr('height', H - m.t - m.b).attr('fill', 'transparent')
      .on('pointermove', (ev) => {
        const [px] = d3.pointer(ev);
        const r = rows[bis(rows, x.invert(px))];
        rule.attr('x1', x(r.t)).attr('x2', x(r.t)).style('display', null);
        tip.style('display', null).html('');
        tip.append('div').attr('class', 't').text(d3.utcFormat('%Y-%m-%d %H시')(r.t));
        [['실제', isNaN(r.y) ? '—' : f1(r.y) + '원', 'var(--color-fg)'], ['중앙값', f1(r.md) + '원', C()[0]], ['범위', `${f1(r.lo)} ~ ${f1(r.hi)}원`, C()[0]]]
          .forEach(([k, v, c]) => { const d = tip.append('div').attr('class', 'r'); d.append('i').style('background', c); d.append('span').text(`${k} ${v}`); });
        const [bx, by] = d3.pointer(ev, box);
        tipAt(box, tip, bx, by);
      })
      .on('pointerleave', () => { rule.style('display', 'none'); tip.style('display', 'none'); });
  }

  // ---------- 시간대별 커버리지
  function drawHourly() {
    const box = document.getElementById('hourly');
    const s = dash.data('hourly');
    if (s.status !== 'ok') { pending(box, s.status); return; }
    box.classList.remove('dash-skeleton');
    const series = [['B_LightGBM분위수', 'LightGBM 분위수', C()[2]], ['E_앙상블', '앙상블 (보정 전)', C()[1]], [FINAL, '앙상블 + 등각 보정 (최종)', C()[0]]];
    legend('hourly-legend', series.map(([, l, c]) => [l, c]));
    const rows = s.data.map(r => ({ h: +r.h, p: +r.PICP, w: +r.MPIW, k: r['방법'] }));
    const W = Math.max(300, box.clientWidth), H = 300, m = { t: 10, r: 12, b: 30, l: 36 };
    box.innerHTML = '';
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    const x = d3.scaleLinear([1, 24], [m.l, W - m.r]);
    const y = d3.scaleLinear([Math.min(50, d3.min(rows, r => r.p) - 5), 100], [H - m.b, m.t]).nice();
    svg.append('rect').attr('x', m.l).attr('width', W - m.l - m.r).attr('y', y(85)).attr('height', y(75) - y(85)).attr('fill', 'var(--color-ok)').attr('fill-opacity', 0.1);
    svg.append('g').attr('class', 'grid').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(W - m.l - m.r)).tickFormat(''));
    svg.append('line').attr('x1', m.l).attr('x2', W - m.r).attr('y1', y(80)).attr('y2', y(80)).attr('stroke', 'var(--cds-chart-reference)').attr('stroke-dasharray', '4 3');
    svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(W < 420 ? 6 : 12).tickFormat(d => d + '시')).call(cleanAxis);
    svg.append('g').attr('class', 'axis').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(d => d + '%')).call(cleanAxis);
    series.forEach(([k, , c]) => {
      const rr = rows.filter(r => r.k === k);
      svg.append('path').datum(rr).attr('fill', 'none').attr('stroke', c).attr('stroke-width', 2).attr('stroke-linecap', 'round').attr('stroke-linejoin', 'round')
        .attr('d', d3.line().x(r => x(r.h)).y(r => y(r.p)));
    });
    const tip = d3.select(box).append('div').attr('class', 'pi-tip').style('display', 'none');
    const rule = svg.append('line').attr('y1', m.t).attr('y2', H - m.b).attr('stroke', 'var(--cds-chart-reference)').style('display', 'none');
    svg.append('rect').attr('x', m.l).attr('y', m.t).attr('width', W - m.l - m.r).attr('height', H - m.t - m.b).attr('fill', 'transparent')
      .on('pointermove', (ev) => {
        const h = Math.max(1, Math.min(24, Math.round(x.invert(d3.pointer(ev)[0]))));
        rule.attr('x1', x(h)).attr('x2', x(h)).style('display', null);
        tip.style('display', null).html('');
        tip.append('div').attr('class', 't').text(`${h}시`);
        series.forEach(([k, l, c]) => {
          const r = rows.find(q => q.k === k && q.h === h);
          const d = tip.append('div').attr('class', 'r'); d.append('i').style('background', c);
          d.append('span').text(`${l} ${f1(r.p)}% · 폭 ${f1(r.w)}원`);
        });
        const [bx, by] = d3.pointer(ev, box);
        tipAt(box, tip, bx, by);
      })
      .on('pointerleave', () => { rule.style('display', 'none'); tip.style('display', 'none'); });
  }

  // ---------- 앙상블 가중치
  function drawWeights() {
    const box = document.getElementById('weights');
    const s = dash.data('weights');
    if (s.status !== 'ok') { pending(box, s.status); return; }
    box.classList.remove('dash-skeleton');
    const parts = [['lgb', 'LightGBM 분위수', C()[2]], ['chr_cov', 'Chronos-2 + 수요예측', C()[0]], ['chr_uni', 'Chronos-2 단변량', C()[1]]];
    legend('weights-legend', parts.map(([, l, c]) => [l, c]));
    const lab = { q10: '하한 (10%)', q50: '중앙 (50%)', q90: '상한 (90%)' };
    const W = Math.max(280, box.clientWidth), H = 200, m = { t: 6, r: 8, b: 22, l: 78 };
    box.innerHTML = '';
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    const yb = d3.scaleBand(s.data.map(r => r['분위수']), [m.t, H - m.b]).padding(0.35);
    const x = d3.scaleLinear([0, 1], [m.l, W - m.r]);
    svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(5).tickFormat(d3.format('.0%'))).call(cleanAxis);
    s.data.forEach(r => {
      let acc = 0;
      svg.append('text').attr('x', m.l - 8).attr('y', yb(r['분위수']) + yb.bandwidth() / 2).attr('dy', '0.35em').attr('text-anchor', 'end')
        .attr('fill', 'var(--color-fg-muted)').attr('font-size', 11).text(lab[r['분위수']] || r['분위수']);
      parts.forEach(([k, , c]) => {
        const v = +r[k];
        if (v <= 0) return;
        const x0 = x(acc), x1 = x(acc + v);
        svg.append('rect').attr('x', x0 + 1).attr('width', Math.max(0, x1 - x0 - 2)).attr('y', yb(r['분위수'])).attr('height', yb.bandwidth()).attr('rx', 4).attr('fill', c);
        if (x1 - x0 > 34) svg.append('text').attr('x', (x0 + x1) / 2).attr('y', yb(r['분위수']) + yb.bandwidth() / 2).attr('dy', '0.35em')
          .attr('text-anchor', 'middle').attr('fill', 'var(--color-bg)').attr('font-size', 11).text(d3.format('.0%')(v));
        acc += v;
      });
    });
  }

  // ---------- 급등 · 일반 · 급락
  function drawRegimes() {
    const box = document.getElementById('regime');
    const tb = document.querySelector('#regime-tbl tbody');
    const s = dash.data('regimes');
    tb.innerHTML = '';
    if (s.status !== 'ok') { pending(box, s.status); return; }
    box.classList.remove('dash-skeleton');
    const order = ['급등', '일반', '급락'];
    const rows = order.map(g => s.data.find(r => r['방법'] === FINAL && r['구간'] === g)).filter(Boolean);
    const bars = [['실제_평균가격', '실제 평균', 'var(--color-fg-muted)'], ['예측중앙_평균', '예측 중앙값 평균', C()[0]], ['어제같은시각_평균', '어제 같은 시각 평균', C()[2]]];
    legend('regime-legend', bars.map(([, l, c]) => [l, c]));
    const W = Math.max(280, box.clientWidth), H = 300, m = { t: 18, r: 8, b: 28, l: 40 };
    box.innerHTML = '';
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    const x0 = d3.scaleBand(order, [m.l, W - m.r]).padding(0.25);
    const x1 = d3.scaleBand(bars.map(b => b[0]), [0, x0.bandwidth()]).padding(0.12);
    const y = d3.scaleLinear([0, d3.max(rows, r => d3.max(bars, b => +r[b[0]])) * 1.1], [H - m.b, m.t]).nice();
    svg.append('g').attr('class', 'grid').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(W - m.l - m.r)).tickFormat(''));
    svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x0)).call(cleanAxis);
    svg.append('g').attr('class', 'axis').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5)).call(cleanAxis);
    const bw = Math.min(32, x1.bandwidth());
    rows.forEach(r => {
      bars.forEach(([k, , c]) => {
        const v = +r[k];
        const cx = x0(r['구간']) + x1(k) + (x1.bandwidth() - bw) / 2;
        svg.append('path').attr('fill', c)
          .attr('d', `M${cx},${y(0)} V${y(v) + 4} Q${cx},${y(v)} ${cx + 4},${y(v)} H${cx + bw - 4} Q${cx + bw},${y(v)} ${cx + bw},${y(v) + 4} V${y(0)} Z`);
        if (x1.step() >= 28) svg.append('text').attr('x', cx + bw / 2).attr('y', y(v) - 4).attr('text-anchor', 'middle').attr('fill', 'var(--color-fg-muted)').attr('font-size', 10).text(d3.format('.0f')(v));
      });
    });
    rows.forEach(r => {
      const tr = document.createElement('tr');
      tr.dataset.key = `${encodeURIComponent(r['방법'])},${encodeURIComponent(r['구간'])}`;
      [['구간', v => v], ['시간수', v => d3.format(',')(+v)], ['PICP(%)', v => f1(+v)], ['MPIW(원)', v => f1(+v)], ['MAE(중앙값)', v => f2(+v)], ['상한위(%)', v => f1(+v)], ['하한아래(%)', v => f1(+v)]]
        .forEach(([k, fm]) => { const td = document.createElement('td'); td.textContent = fm(r[k]); tr.appendChild(td); });
      tb.appendChild(tr);
    });
  }


  // ---------- 급락·급등 경보 (공통 채우기)
  const 행찾기 = (rows, where) => {
    const conds = where.split('&').map(s => s.split('=').map(decodeURIComponent));
    return rows.find(r => conds.every(([k, v]) => String(r[k]) === v));
  };
  function fillWhere(id) {
    const s = dash.data(id);
    document.querySelectorAll(`[data-source="${id}"][data-where]`).forEach(el => {
      el.classList.toggle('dash-skeleton', s.status === 'loading');
      if (s.status !== 'ok') { el.textContent = '—'; return; }
      const r = 행찾기(s.data, el.dataset.where);
      el.textContent = r ? String(r[el.dataset.field]) : '—';
    });
  }
  function fillTable(sel, id, cls, keep) {
    const s = dash.data(id);
    const tbl = document.querySelector(sel);
    const tb = tbl.querySelector('tbody');
    tb.innerHTML = '';
    if (s.status !== 'ok') return;
    const cols = [...tbl.querySelectorAll('th')].map(th => th.dataset.field);
    const wrap = [...tbl.querySelectorAll('th')].map(th => th.classList.contains('wrap'));
    s.data.filter(r => !keep || keep(r)).forEach(r => {
      const tr = document.createElement('tr');
      cols.forEach((c, i) => {
        const td = document.createElement('td');
        td.textContent = String(r[c]);
        if (wrap[i]) td.classList.add('wrap');
        if (cls) { const k = cls(c, r[c]); if (k) td.classList.add(k); }
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
  }

  function drawDrop() {
    fillWhere('drop_perf');
    fillWhere('drop_missed_ref');
    fillTable('#drop-perf', 'drop_perf');
    fillTable('#drop-compare', 'drop_compare');
    fillTable('#drop-missed', 'drop_missed');
    fillTable('#drop-missed-ref', 'drop_missed_ref');
    fillTable('#drop-days', 'drop_days_final', (c, v) => {
      if (c === '대비 결과') return v === '놓침' ? 'miss' : 'hit';
      if (c === '하루 전 경보') return v === '예' ? 'hit' : null;
      return null;
    });
    document.querySelectorAll('#drop-perf tbody tr, #drop-compare tbody tr').forEach(tr => {
      if (tr.firstChild && tr.firstChild.textContent.indexOf('75%') >= 0) tr.className = 'final';
    });
    const box = document.getElementById('drop-chart');
    const s = dash.data('drop_daily'), pf = dash.data('drop_perf');
    if (s.status !== 'ok' || pf.status !== 'ok') { pending(box, s.status !== 'ok' ? s.status : pf.status); return; }
    box.classList.remove('dash-skeleton');
    const tr75 = pf.data.find(x => String(x['목표']) === '75%');
    const tW = tr75 ? +tr75['확률 문턱(%)'] : NaN;
    const rows = s.data.map(r => ({ date: r.date, dow: r['요일'], kind: r['구분'], p: +r['급락확률(%)'],
      on: r['경보'] === '경보', min: r['실제최저가'], act: r['실제'] }));
    const cW = 'var(--pi-brand)', cM = 'var(--cds-chart-muted)', cBad = 'var(--cds-chart-status-critical)';
    legend('drop-legend', [['경보', cW], ['경보 없음', cM], ['실제 급락일', cBad, 'dot']]);
    const W = Math.max(320, box.clientWidth), H = 300, m = { t: 18, r: 12, b: 26, l: 44 };
    box.innerHTML = '';
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    const x = d3.scaleBand(rows.map(r => r.date), [m.l, W - m.r]).padding(0.15);
    const y = d3.scaleLog([0.05, 100], [H - m.b, m.t]).clamp(true);
    const ticks = [0.1, 1, 10, 100];
    svg.append('g').attr('class', 'grid').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).tickValues(ticks).tickSize(-(W - m.l - m.r)).tickFormat(''));
    svg.append('g').attr('class', 'axis').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).tickValues(ticks).tickFormat(v => v + '%')).call(cleanAxis);
    const months = rows.filter((r, i) => i === 0 || r.date.slice(5, 7) !== rows[i - 1].date.slice(5, 7));
    svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).tickValues(months.map(r => r.date)).tickFormat(v => `${+v.slice(5, 7)}월`).tickSizeOuter(0)).call(cleanAxis);
    svg.append('g').selectAll('rect').data(rows).join('rect')
      .attr('x', r => x(r.date)).attr('width', x.bandwidth()).attr('rx', 1)
      .attr('y', r => y(Math.max(0.05, r.p))).attr('height', r => (H - m.b) - y(Math.max(0.05, r.p)))
      .attr('fill', r => r.on ? cW : cM);
    if (!isNaN(tW)) {
      svg.append('line').attr('x1', m.l).attr('x2', W - m.r).attr('y1', y(tW)).attr('y2', y(tW))
        .attr('stroke', 'var(--cds-chart-reference)').attr('stroke-dasharray', '4 3');
      svg.append('text').attr('x', W - m.r).attr('y', y(tW) - 4).attr('text-anchor', 'end')
        .attr('fill', 'var(--color-fg-muted)').attr('font-size', 11).text('경보 문턱 ' + tW + '%');
    }
    svg.append('g').selectAll('circle').data(rows.filter(r => r.act === '급락')).join('circle')
      .attr('cx', r => x(r.date) + x.bandwidth() / 2).attr('cy', m.t - 8).attr('r', 3.2).attr('fill', cBad);
    const tip = d3.select(box).append('div').attr('class', 'pi-tip').style('display', 'none');
    svg.append('rect').attr('x', m.l).attr('y', 0).attr('width', W - m.l - m.r).attr('height', H - m.b).attr('fill', 'transparent')
      .on('pointermove', (ev) => {
        const [px] = d3.pointer(ev);
        const i = Math.max(0, Math.min(rows.length - 1, Math.floor((px - m.l) / x.step())));
        const r = rows[i];
        tip.style('display', null).html('');
        tip.append('div').attr('class', 't').text(`${r.date} (${r.dow}) · ${r.kind}`);
        [['급락 확률', r.p + '%'], ['경보', r.on ? '있음' : '없음'], ['실제 최저가', r.min === '' ? '—' : r.min + '원'], ['판정', r.act]]
          .forEach(([k, v]) => tip.append('div').attr('class', 'r').append('span').text(`${k} ${v}`));
        const [bx, by] = d3.pointer(ev, box);
        tipAt(box, tip, bx, by);
      })
      .on('pointerleave', () => tip.style('display', 'none'));
  }

  function drawSpike() {
    fillWhere('spike_summary');
    fillWhere('spike_actions');
    fillTable('#spike-actions', 'spike_actions');
    fillTable('#spike-alarm', 'spike_alarm');
    fillTable('#spike-summary', 'spike_summary');
    document.querySelectorAll('#spike-alarm tbody tr').forEach(tr => { if (tr.firstChild && tr.firstChild.textContent.indexOf('지금') === 0) tr.className = 'final'; });
    fillTable('#spike-days', 'spike_days_final', (c, v) => {
      if (c === '대비 결과') return v === '놓침' ? 'miss' : 'hit';
      if (c === '하루 전 경보' || c === '범위 안') return v === '예' ? 'hit' : null;
      return null;
    });
    const box = document.getElementById('spike-chart');
    const s = dash.data('spike_daily'), sm = dash.data('spike_summary');
    if (s.status !== 'ok' || sm.status !== 'ok') { pending(box, s.status !== 'ok' ? s.status : sm.status); return; }
    box.classList.remove('dash-skeleton');
    const r26 = sm.data.find(x => String(x['기간']) === '2026');
    const tW = r26 ? +r26['경보 문턱(%)'] : NaN;
    const rows = s.data.map(r => ({ date: r.date, dow: r['요일'], kind: r['구분'], p: +r['급등확률(%)'],
      on: r['경보'] === '경보', prev: r['전날 급등'] === '예', max: r['최고가'], act: r['실제'] }));
    const cW = 'var(--pi-brand)', cM = 'var(--cds-chart-muted)', cBad = 'var(--cds-chart-status-critical)';
    legend('spike-legend', [['경보', cW], ['경보 없음', cM], ['실제 급등일', cBad, 'dot']]);
    const W = Math.max(320, box.clientWidth), H = 300, m = { t: 18, r: 12, b: 26, l: 44 };
    box.innerHTML = '';
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
    const x = d3.scaleBand(rows.map(r => r.date), [m.l, W - m.r]).padding(0.15);
    const y = d3.scaleLog([0.05, 100], [H - m.b, m.t]).clamp(true);
    const ticks = [0.1, 1, 10, 100];
    svg.append('g').attr('class', 'grid').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).tickValues(ticks).tickSize(-(W - m.l - m.r)).tickFormat(''));
    svg.append('g').attr('class', 'axis').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).tickValues(ticks).tickFormat(v => v + '%')).call(cleanAxis);
    const months = rows.filter((r, i) => i === 0 || r.date.slice(5, 7) !== rows[i - 1].date.slice(5, 7));
    svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).tickValues(months.map(r => r.date)).tickFormat(v => `${+v.slice(5, 7)}월`).tickSizeOuter(0)).call(cleanAxis);
    svg.append('g').selectAll('rect').data(rows).join('rect')
      .attr('x', r => x(r.date)).attr('width', x.bandwidth()).attr('rx', 1)
      .attr('y', r => y(Math.max(0.05, r.p))).attr('height', r => (H - m.b) - y(Math.max(0.05, r.p)))
      .attr('fill', r => r.on ? cW : cM);
    if (!isNaN(tW)) {
      svg.append('line').attr('x1', m.l).attr('x2', W - m.r).attr('y1', y(tW)).attr('y2', y(tW))
        .attr('stroke', 'var(--cds-chart-reference)').attr('stroke-dasharray', '4 3');
      svg.append('text').attr('x', W - m.r).attr('y', y(tW) - 4).attr('text-anchor', 'end')
        .attr('fill', 'var(--color-fg-muted)').attr('font-size', 11).text('경보 문턱 ' + tW + '%');
    }
    svg.append('g').selectAll('circle').data(rows.filter(r => r.act === '급등')).join('circle')
      .attr('cx', r => x(r.date) + x.bandwidth() / 2).attr('cy', m.t - 8).attr('r', 3.2).attr('fill', cBad);
    const tip = d3.select(box).append('div').attr('class', 'pi-tip').style('display', 'none');
    svg.append('rect').attr('x', m.l).attr('y', 0).attr('width', W - m.l - m.r).attr('height', H - m.b).attr('fill', 'transparent')
      .on('pointermove', (ev) => {
        const [px] = d3.pointer(ev);
        const i = Math.max(0, Math.min(rows.length - 1, Math.floor((px - m.l) / x.step())));
        const r = rows[i];
        tip.style('display', null).html('');
        tip.append('div').attr('class', 't').text(`${r.date} (${r.dow}) · ${r.kind}`);
        [['급등 확률', r.p + '%'], ['경보', r.on ? '있음' : '없음'], ['전날 급등', r.prev ? '예' : '아니오'], ['그날 최고가', r.max === '' ? '—' : r.max + '원'], ['판정', r.act]]
          .forEach(([k, v]) => tip.append('div').attr('class', 'r').append('span').text(`${k} ${v}`));
        const [bx, by] = d3.pointer(ev, box);
        tipAt(box, tip, bx, by);
      })
      .on('pointerleave', () => tip.style('display', 'none'));
  }


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

  const redraw = () => { drawPrice(); drawDrop(); drawSpike(); drawKpis(); drawMethods(); drawFan(); drawHourly(); drawWeights(); drawRegimes(); };
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
