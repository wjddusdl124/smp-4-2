/* 과제 2 — 80% 예측 범위 웹사이트
 * data.js(window.DATA)를 읽어 SVG 차트를 직접 그린다. 외부 차트 라이브러리 없음.
 */
(function () {
  "use strict";
  const D = window.DATA;
  const TARGET = [75, 85];
  const DOW = ["일", "월", "화", "수", "목", "금", "토"];

  // ── [1] 공통 도우미 ─────────────────────────────────
  const $ = (s) => document.querySelector(s);
  const NS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) {
      if (k === "style") e.style.cssText = attrs[k];
      else if (k === "text") e.textContent = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    if (parent) parent.appendChild(e);
    return e;
  }
  function scale(d0, d1, r0, r1) {
    const f = (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
    f.inv = (p) => d0 + ((p - r0) / (r1 - r0)) * (d1 - d0);
    return f;
  }
  function niceTicks(min, max, count) {
    const raw = (max - min) / count;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
    const lo = Math.floor(min / step) * step;
    const hi = Math.ceil(max / step) * step;
    const out = [];
    for (let v = lo; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
    return out;
  }
  const fmt = (v, d = 1) => (v == null ? "–" : v.toFixed(d));

  // 컨테이너 크기에 맞춘 빈 SVG
  function makeSvg(box) {
    box.innerHTML = "";
    const w = box.clientWidth, h = box.clientHeight;
    const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, role: "img" }, box);
    return { svg, w, h };
  }

  // 툴팁
  const tip = $("#tooltip");
  function showTip(html, x, y) {
    tip.innerHTML = html;
    tip.classList.add("show");
    const r = tip.getBoundingClientRect();
    let left = x + 16, top = y + 16;
    if (left + r.width > window.innerWidth - 8) left = x - r.width - 16;
    if (top + r.height > window.innerHeight - 8) top = y - r.height - 16;
    tip.style.left = Math.max(8, left) + "px";
    tip.style.top = Math.max(8, top) + "px";
  }
  const hideTip = () => tip.classList.remove("show");
  const row = (k, v) => `<div class="t-r"><span>${k}</span><b>${v}</b></div>`;

  // 가로 격자 + y축 눈금
  function yGrid(svg, ticks, y, x0, x1, suffix = "") {
    const g = svgEl("g", { class: "grid" }, svg);
    ticks.forEach((t) => {
      svgEl("line", { x1: x0, x2: x1, y1: y(t), y2: y(t) }, g);
      svgEl("text", { x: x0 - 8, y: y(t) + 4, "text-anchor": "end", text: t + suffix }, svg);
    });
  }

  // null 로 끊기는 구간마다 path 문자열 생성
  function linePath(xs, ys) {
    let d = "", pen = false;
    for (let i = 0; i < xs.length; i++) {
      if (ys[i] == null) { pen = false; continue; }
      d += (pen ? "L" : "M") + xs[i].toFixed(1) + "," + ys[i].toFixed(1);
      pen = true;
    }
    return d;
  }

  // ── [2] 시계열 데이터 준비 ─────────────────────────
  const S = D.series;
  const N = S.actual.length;
  const t0 = Date.UTC(+S.start.slice(0, 4), +S.start.slice(5, 7) - 1, +S.start.slice(8, 10));
  const HOUR = 3600e3, DAY = 24 * HOUR;
  const dateAt = (i) => new Date(t0 + i * HOUR);           // UTC 로 다뤄 시간대 영향 제거
  const isoDay = (dt) => dt.toISOString().slice(0, 10);
  const dayLabel = (dt) => `${dt.getUTCMonth() + 1}/${dt.getUTCDate()} (${DOW[dt.getUTCDay()]})`;
  const isOut = (i) => S.actual[i] != null && (S.actual[i] < S.lower[i] || S.actual[i] > S.upper[i]);

  // 성공 기준 — 정확도(중앙값 예측)
  const CRIT = {
    rmae: { max: 0.65, label: "rMAE 0.65 이하" },
    mae: { max: 7.0, label: "MAE 7.0원 이하" },
    mape: { max: 5.0, strict: true, label: "MAPE 5.0% 미만" },
    bias: { abs: 1.5, label: "|편의| 1.5% 이하" },
  };
  const MAPE_FLOOR = 20;   // MAPE·편의 분모 하한(원) — 운영 코드와 같은 정의
  function passes(k, v) {
    if (v == null) return null;
    if (k === "cov") return v >= TARGET[0] && v <= TARGET[1];
    const c = CRIT[k];
    if (c.abs != null) return Math.abs(v) <= c.abs;
    return c.strict ? v < c.max : v <= c.max;
  }
  const mark = (k, v) => (passes(k, v) ? `<b class="ok-mark" title="기준 충족">✓</b>` : "");
  const sign = (v, d = 2) => (v == null ? "–" : (v > 0 ? "+" : "") + v.toFixed(d));

  function windowStats(i0, i1) {
    let n = 0, cov = 0, w = 0, ae = 0, aeN = 0, nN = 0, ape = 0, pe = 0;
    for (let i = i0; i < i1; i++) {
      const a = S.actual[i];
      if (a == null) continue;
      n++;
      if (!isOut(i)) cov++;
      const e = S.median[i] - a, den = Math.max(a, MAPE_FLOOR);
      w += S.upper[i] - S.lower[i];
      ae += Math.abs(e);
      ape += Math.abs(e) / den;
      pe += e / den;
      // 전날 실제값이 없는 시간은 단순 예측도 없음 → 단순 예측 오차에서만 제외
      if (S.naive[i] != null) { aeN += Math.abs(S.naive[i] - a); nN++; }
    }
    if (!n) return null;
    const maeN = nN ? aeN / nN : null;
    return {
      n, cov: (cov / n) * 100, w: w / n, mae: ae / n, maeN,
      rmae: maeN ? ae / n / maeN : null, mape: (ape / n) * 100, bias: (pe / n) * 100,
    };
  }

  // ── [3] 성공 기준 점검 ─────────────────────────────
  const evalOf = (p, c) => D.evals[p].find((r) => r.code === c);
  const pill = (ok) => `<span class="pill ${ok ? "ok" : "no"}">${ok ? "달성" : "미달"}</span>`;

  // 값과 기준선을 같은 축에 그린 작은 막대. lo~hi 는 막대 전체 범위
  function gauge(v, lo, hi, opts) {
    const p = (x) => Math.max(0, Math.min(100, ((x - lo) / (hi - lo)) * 100));
    let s = `<div class="kpi-bar v2" aria-hidden="true">`;
    if (opts.band) s += `<span class="tgt" style="left:${p(opts.band[0])}%;width:${p(opts.band[1]) - p(opts.band[0])}%"></span>`;
    (opts.thr || []).forEach((t) => (s += `<span class="thr" style="left:calc(${p(t)}% - 1px)"></span>`));
    if (opts.fill) s += `<span class="fill" style="width:${p(v)}%;background:${opts.fill}"></span>`;
    s += `<span class="val" style="left:calc(${p(v)}% - 1.5px)"></span></div>`;
    return s;
  }

  function kpi({ k, tag, value, unit, target, ok, bar, gap }) {
    return `<div class="kpi">
      <div class="kpi-top"><span class="kpi-k">${k}</span>${tag ? `<span class="kpi-tag">${tag}</span>` : ""}</div>
      <div class="kpi-v">${value}<small>${unit || ""}</small></div>
      <div class="kpi-tgt">${target}${ok == null ? "" : " " + pill(ok)}</div>
      ${bar || ""}
      ${gap ? `<div class="kpi-gap">${gap}</div>` : ""}
    </div>`;
  }

  function renderCriteria() {
    const F = evalOf("test", "F"), A = evalOf("test", "A");
    const best = (k) => D.evals.test.reduce((a, b) => (b[k] < a[k] ? b : a));
    const okCov = passes("cov", F.picp);

    $("#kpisRange").innerHTML = [
      kpi({
        k: "커버리지 (PICP)", tag: "핵심", value: fmt(F.picp), unit: "%", target: "목표 75–85%", ok: okCov,
        bar: gauge(F.picp, 50, 100, { band: TARGET }),
        gap: `하한 아래 ${fmt(F.below)}% · 상한 위 ${fmt(F.above)}%`,
      }),
      kpi({
        k: "평균 범위 폭 (MPIW)", value: fmt(F.mpiw), unit: "원", target: "커버리지를 지키며 좁게",
        gap: `쉬운 방법(A) ${fmt(A.mpiw)}원보다 ${fmt(A.mpiw - F.mpiw)}원 좁음`,
      }),
      kpi({
        k: "Winkler score", value: fmt(F.winkler), target: "낮을수록 좋음",
        gap: best("winkler").code === "F" ? "6개 방법 중 가장 낮음" : `가장 낮은 방법: ${best("winkler").name}`,
      }),
    ].join("");

    // 정확도 기준: 목표까지 남은 거리를 원/kWh 로도 보여줌
    const maeForRmae = CRIT.rmae.max * F.mae_naive;
    $("#kpisPoint").innerHTML = [
      kpi({
        k: "rMAE", tag: "목표", value: F.rmae.toFixed(3), target: CRIT.rmae.label, ok: passes("rmae", F.rmae),
        bar: gauge(F.rmae, 0.4, 1.0, { thr: [CRIT.rmae.max], fill: "var(--accent-soft)" }),
        gap: passes("rmae", F.rmae) ? "기준 충족"
          : `MAE를 ${fmt(maeForRmae, 2)}원까지 (${fmt(F.mae - maeForRmae, 2)}원 더) 줄여야 함`,
      }),
      kpi({
        k: "MAE", tag: "도전", value: fmt(F.mae, 2), unit: "원", target: CRIT.mae.label, ok: passes("mae", F.mae),
        bar: gauge(F.mae, 4, 12, { thr: [CRIT.mae.max], fill: "var(--accent-soft)" }),
        gap: passes("mae", F.mae) ? "기준 충족" : `${fmt(F.mae - CRIT.mae.max, 2)}원 부족 · 어제 같은 시각 ${fmt(F.mae_naive, 2)}원`,
      }),
      kpi({
        k: "MAPE", tag: "보조", value: fmt(F.mape, 2), unit: "%", target: CRIT.mape.label, ok: passes("mape", F.mape),
        bar: gauge(F.mape, 0, 12, { thr: [CRIT.mape.max], fill: "var(--accent-soft)" }),
        gap: passes("mape", F.mape) ? "기준 충족" : `${fmt(F.mape - CRIT.mape.max, 2)}%p 부족`,
      }),
      kpi({
        k: "편의 (bias)", tag: "보조", value: sign(F.bias), unit: "%", target: CRIT.bias.label, ok: passes("bias", F.bias),
        bar: gauge(F.bias, -4, 4, { band: [-CRIT.bias.abs, CRIT.bias.abs] }),
        gap: passes("bias", F.bias) ? "기준 충족"
          : `실제보다 ${F.bias > 0 ? "높게" : "낮게"} 예측 · ${fmt(Math.abs(F.bias) - CRIT.bias.abs, 2)}%p 초과`,
      }),
    ].join("");

    // 한 줄 판정
    const pts = ["rmae", "mae", "mape", "bias"].filter((k) => passes(k, F[k])).length;
    $("#verdict").innerHTML =
      `<b>판정</b> — 예측 범위 커버리지 ${fmt(F.picp)}%로 목표(75–85%)를 ${okCov ? "<b>달성</b>" : "달성하지 못함"}. ` +
      `중앙값 정확도 기준은 4개 중 <b>${pts}개 달성</b> ` +
      `(rMAE ${F.rmae.toFixed(3)} · MAE ${fmt(F.mae, 2)}원 · MAPE ${fmt(F.mape, 2)}% · 편의 ${sign(F.bias)}%).`;
  }

  // ── [4] 예측 범위 탐색 차트 ─────────────────────────
  const state = { i0: 0, days: 7 };

  function clampStart(i) {
    const len = state.days * 24;
    return Math.max(0, Math.min(N - len, Math.floor(i / 24) * 24));
  }

  function renderTs() {
    const box = $("#tsChart");
    const { svg, w, h } = makeSvg(box);
    const len = state.days * 24, i0 = state.i0, i1 = Math.min(N, i0 + len);
    const m = { l: 44, r: 12, t: 10, b: 28 };

    let lo = Infinity, hi = -Infinity;
    for (let i = i0; i < i1; i++) {
      [S.lower[i], S.upper[i], S.actual[i]].forEach((v) => {
        if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
      });
    }
    const ticks = niceTicks(Math.max(0, lo - 5), hi + 5, 5);
    const x = scale(i0, i1 - 1, m.l, w - m.r);
    const y = scale(ticks[0], ticks[ticks.length - 1], h - m.b, m.t);

    yGrid(svg, ticks, y, m.l, w - m.r);

    // x 축 눈금
    const step = state.days === 1 ? 3 : state.days === 7 ? 24 : 24 * 5;
    for (let i = i0; i < i1; i += step) {
      const dt = dateAt(i);
      const label = state.days === 1 ? `${dt.getUTCHours() + 1}시` : dayLabel(dt);
      svgEl("text", { x: x(i), y: h - 8, "text-anchor": i === i0 ? "start" : "middle", text: label }, svg);
      if (state.days > 1 && i > i0) svgEl("line", { x1: x(i), x2: x(i), y1: m.t, y2: h - m.b, style: "stroke:var(--grid)" }, svg);
    }

    // 범위(띠) — 결측 구간마다 따로 그림
    const idx = [];
    for (let i = i0; i < i1; i++) idx.push(i);
    let seg = [];
    const flush = () => {
      if (seg.length < 1) return;
      const top = seg.map((i) => `${x(i).toFixed(1)},${y(S.upper[i]).toFixed(1)}`);
      const bot = seg.slice().reverse().map((i) => `${x(i).toFixed(1)},${y(S.lower[i]).toFixed(1)}`);
      svgEl("path", { d: "M" + top.join("L") + "L" + bot.join("L") + "Z", style: "fill:var(--accent-band)" }, svg);
      seg = [];
    };
    idx.forEach((i) => (S.upper[i] == null ? flush() : seg.push(i)));
    flush();

    const xs = idx.map(x);
    const thin = state.days === 30 ? 1.25 : 1.75;
    svgEl("path", { d: linePath(xs, idx.map((i) => (S.median[i] == null ? null : y(S.median[i])))), style: `fill:none;stroke:var(--s1);stroke-width:${thin + 0.25};stroke-linejoin:round` }, svg);
    svgEl("path", { d: linePath(xs, idx.map((i) => (S.actual[i] == null ? null : y(S.actual[i])))), style: `fill:none;stroke:var(--ink);stroke-width:${thin};stroke-linejoin:round` }, svg);

    // 범위 밖 시간
    const r = state.days === 30 ? 2.5 : 4;
    idx.forEach((i) => {
      if (isOut(i)) svgEl("circle", { cx: x(i), cy: y(S.actual[i]), r, style: "fill:var(--s2);stroke:var(--surface);stroke-width:1.5" }, svg);
    });

    // 호버: 십자선 + 툴팁
    const cross = svgEl("line", { y1: m.t, y2: h - m.b, style: "stroke:var(--ink-3);stroke-dasharray:3 3;opacity:0" }, svg);
    const dotA = svgEl("circle", { r: 4.5, style: "fill:var(--ink);stroke:var(--surface);stroke-width:2;opacity:0" }, svg);
    const dotM = svgEl("circle", { r: 4.5, style: "fill:var(--s1);stroke:var(--surface);stroke-width:2;opacity:0" }, svg);
    const hit = svgEl("rect", { x: m.l, y: 0, width: w - m.l - m.r, height: h, style: "fill:transparent;cursor:crosshair" }, svg);
    hit.addEventListener("mousemove", (ev) => {
      const pt = svg.getBoundingClientRect();
      const i = Math.max(i0, Math.min(i1 - 1, Math.round(x.inv(ev.clientX - pt.left))));
      const cx = x(i);
      cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.style.opacity = 1;
      const a = S.actual[i];
      if (a != null) { dotA.setAttribute("cx", cx); dotA.setAttribute("cy", y(a)); dotA.style.opacity = 1; } else dotA.style.opacity = 0;
      if (S.median[i] != null) { dotM.setAttribute("cx", cx); dotM.setAttribute("cy", y(S.median[i])); dotM.style.opacity = 1; }
      const dt = dateAt(i);
      let tag = "";
      if (a == null) tag = `<div class="t-tag">실제값 없음</div>`;
      else if (a > S.upper[i]) tag = `<div class="t-tag out">▲ 상한 위로 ${fmt(a - S.upper[i])}원</div>`;
      else if (a < S.lower[i]) tag = `<div class="t-tag out">▼ 하한 아래로 ${fmt(S.lower[i] - a)}원</div>`;
      else tag = `<div class="t-tag in">● 범위 안</div>`;
      showTip(
        `<div class="t-h">${dt.getUTCFullYear()}. ${dayLabel(dt)} ${dt.getUTCHours() + 1}시</div>` +
        row("실제", fmt(a, 2)) + row("중앙값", fmt(S.median[i], 2)) +
        row("80% 범위", `${fmt(S.lower[i], 1)} – ${fmt(S.upper[i], 1)}`) +
        row("어제 같은 시각", fmt(S.naive[i], 2)) + tag,
        ev.clientX, ev.clientY);
    });
    hit.addEventListener("mouseleave", () => {
      hideTip(); cross.style.opacity = 0; dotA.style.opacity = 0; dotM.style.opacity = 0;
    });

    // 선택 구간 요약
    const st = windowStats(i0, i1);
    const covCls = st && st.cov >= TARGET[0] && st.cov <= TARGET[1] ? "ok" : "no";
    $("#windowStats").innerHTML = st ? `
      <div><div class="k">커버리지</div><div class="v">${fmt(st.cov)}% <span class="pill ${covCls}">${covCls === "ok" ? "목표 안" : "목표 밖"}</span></div></div>
      <div><div class="k">평균 범위 폭</div><div class="v">${fmt(st.w)}원</div></div>
      <div><div class="k">MAE <span class="muted">(어제 ${fmt(st.maeN, 2)})</span></div><div class="v">${fmt(st.mae, 2)}원${mark("mae", st.mae)}</div></div>
      <div><div class="k">rMAE</div><div class="v">${st.rmae == null ? "–" : st.rmae.toFixed(3)}${mark("rmae", st.rmae)}</div></div>
      <div><div class="k">MAPE</div><div class="v">${fmt(st.mape, 2)}%${mark("mape", st.mape)}</div></div>
      <div><div class="k">편의</div><div class="v">${sign(st.bias)}%${mark("bias", st.bias)}</div></div>` :
      `<div><div class="k">이 기간</div><div class="v">실제값 없음</div></div>`;

    $("#dateInput").value = isoDay(dateAt(i0));
  }

  function setupExplorer() {
    // 바로가기: 처음 / 가장 크게 빗나간 날 / 커버리지가 가장 낮은 달 / 마지막
    let worstDay = 0, worstVal = -1;
    for (let d = 0; d < N / 24; d++) {
      let s = 0;
      for (let i = d * 24; i < d * 24 + 24; i++) {
        const a = S.actual[i];
        if (a == null) continue;
        s += Math.max(0, a - S.upper[i]) + Math.max(0, S.lower[i] - a);
      }
      if (s > worstVal) { worstVal = s; worstDay = d; }
    }
    const months = monthlyCoverage();
    const lowMonth = months.reduce((a, b) => (b.cov < a.cov ? b : a));
    const presets = [
      { label: "1월 첫 주", i: 0, days: 7 },
      { label: `가장 크게 빗나간 날 (${dayLabel(dateAt(worstDay * 24))})`, i: worstDay * 24, days: 1 },
      { label: `${lowMonth.m}월 (커버리지 최저)`, i: lowMonth.i0, days: 30 },
      { label: "마지막 주", i: N - 7 * 24, days: 7 },
    ];
    const pbox = $("#presets");
    presets.forEach((p) => {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = p.label;
      b.onclick = () => { setDays(p.days); state.i0 = clampStart(p.i); renderTs(); };
      pbox.appendChild(b);
    });

    function setDays(d) {
      state.days = d;
      document.querySelectorAll("#spanSeg button").forEach((b) => b.classList.toggle("on", +b.dataset.days === d));
    }
    document.querySelectorAll("#spanSeg button").forEach((b) => {
      b.onclick = () => { setDays(+b.dataset.days); state.i0 = clampStart(state.i0); renderTs(); };
    });
    $("#prevBtn").onclick = () => { state.i0 = clampStart(state.i0 - state.days * 24); renderTs(); };
    $("#nextBtn").onclick = () => { state.i0 = clampStart(state.i0 + state.days * 24); renderTs(); };
    $("#dateInput").onchange = (e) => {
      const v = e.target.value;
      if (!v) return;
      const t = Date.UTC(+v.slice(0, 4), +v.slice(5, 7) - 1, +v.slice(8, 10));
      state.i0 = clampStart(Math.round((t - t0) / HOUR));
      renderTs();
    };
  }

  // ── [5] 방법 비교: 산점도 + 표 ──────────────────────
  let period = "test";

  function renderScatter() {
    const box = $("#scatter");
    const { svg, w, h } = makeSvg(box);
    const rows = D.evals[period];
    const m = { l: 44, r: 16, t: 12, b: 40 };
    const xMin = Math.floor(Math.min(...rows.map((r) => r.mpiw)) - 1.5);
    const xMax = Math.ceil(Math.max(...rows.map((r) => r.mpiw)) + 1.5);
    const x = scale(xMin, xMax, m.l, w - m.r);
    const y = scale(60, 90, h - m.b, m.t);

    svgEl("rect", { x: m.l, width: w - m.l - m.r, y: y(TARGET[1]), height: y(TARGET[0]) - y(TARGET[1]), style: "fill:var(--target-band)" }, svg);
    svgEl("text", { x: w - m.r - 6, y: y(TARGET[1]) + 15, "text-anchor": "end", class: "axis-label", style: "fill:var(--good)", text: "목표 75–85%" }, svg);
    yGrid(svg, [60, 70, 80, 90], y, m.l, w - m.r, "%");
    niceTicks(xMin, xMax, 5).filter((t) => t >= xMin && t <= xMax).forEach((t) =>
      svgEl("text", { x: x(t), y: h - m.b + 18, "text-anchor": "middle", text: t }, svg));
    svgEl("text", { x: (m.l + w - m.r) / 2, y: h - 4, "text-anchor": "middle", class: "axis-label", text: "평균 범위 폭 (원) →  좁을수록 좋음" }, svg);

    // 레이블 겹침 회피: 오른쪽에 두되 이미 놓인 레이블과 겹치면 왼쪽으로
    const placed = [];
    rows.slice().sort((a, b) => (a.code === "F" ? 1 : b.code === "F" ? -1 : 0)).forEach((r) => {
      const cx = x(r.mpiw), cy = y(r.picp), fin = r.code === "F";
      const g = svgEl("g", { style: "cursor:default" }, svg);
      svgEl("circle", { cx, cy, r: 14, style: "fill:transparent" }, g);
      svgEl("circle", { cx, cy, r: fin ? 7 : 5.5, style: `fill:${fin ? "var(--s1)" : "var(--ink-3)"};stroke:var(--surface);stroke-width:2` }, g);
      let lx = cx + 11, anchor = "start";
      const box = { x0: lx, x1: lx + 12, y0: cy - 8, y1: cy + 8 };
      const hitL = placed.some((p) => !(box.x1 < p.x0 || box.x0 > p.x1 || box.y1 < p.y0 || box.y0 > p.y1) || Math.hypot(p.cx - cx, p.cy - cy) < 18 && p.cx > cx);
      if (hitL) { lx = cx - 11; anchor = "end"; }
      placed.push({ x0: anchor === "start" ? lx : lx - 12, x1: anchor === "start" ? lx + 12 : lx, y0: cy - 8, y1: cy + 8, cx, cy });
      svgEl("text", { x: lx, y: cy + 4, "text-anchor": anchor, class: fin ? "lbl lbl-strong" : "lbl", text: r.code }, g);
      g.addEventListener("mousemove", (ev) => showTip(
        `<div class="t-h">${r.code} · ${r.name}</div>` + row("커버리지", fmt(r.picp) + "%") +
        row("평균 폭", fmt(r.mpiw) + "원") + row("Winkler", fmt(r.winkler)) + row("MAE", fmt(r.mae, 2) + "원"),
        ev.clientX, ev.clientY));
      g.addEventListener("mouseleave", hideTip);
    });
  }

  function renderTable() {
    const rows = D.evals[period];
    const best = (k, dir = 1) => rows.reduce((a, b) => (b[k] * dir < a[k] * dir ? b : a))[k];
    const bW = best("winkler"), bM = best("mpiw"), bP10 = best("pb10"), bP90 = best("pb90");
    const cls = (v, b) => (v === b ? "best" : "");
    const head = [
      ["방법"], ["커버리지", "grp"], ["평균 폭"], ["Winkler"], ["pinball 0.1 / 0.5 / 0.9"], ["벗어남 ↓ / ↑"],
      ["MAE", "grp"], ["rMAE"], ["MAPE"], ["편의"],
    ];
    $("#evalTable").innerHTML =
      `<thead><tr>${head.map(([x, c]) => `<th class="${c || ""}">${x}</th>`).join("")}</tr></thead><tbody>` +
      rows.map((r) => {
        const ok = passes("cov", r.picp);
        return `<tr class="${r.code === "F" ? "final" : ""}">
          <td><span class="code">${r.code}</span>${r.name}</td>
          <td class="grp">${fmt(r.picp)}% <span class="pill ${ok ? "ok" : "no"}">${ok ? "목표 안" : "미달"}</span></td>
          <td class="${cls(r.mpiw, bM)}">${fmt(r.mpiw)}원</td>
          <td class="${cls(r.winkler, bW)}">${fmt(r.winkler)}</td>
          <td><span class="${cls(r.pb10, bP10)}">${fmt(r.pb10, 2)}</span> / ${fmt(r.pb50, 2)} / <span class="${cls(r.pb90, bP90)}">${fmt(r.pb90, 2)}</span></td>
          <td>${fmt(r.below)}% / ${fmt(r.above)}%</td>
          <td class="grp">${fmt(r.mae, 2)}${mark("mae", r.mae)}</td>
          <td>${r.rmae.toFixed(3)}${mark("rmae", r.rmae)}</td>
          <td>${r.mape == null ? "–" : fmt(r.mape, 2) + "%"}${mark("mape", r.mape)}</td>
          <td>${r.bias == null ? "–" : sign(r.bias) + "%"}${mark("bias", r.bias)}</td>
        </tr>`;
      }).join("") + "</tbody>";
    $("#calibNote").textContent = period === "calib"
      ? "보정 구간(2025)은 시간별 예측이 저장되어 있지 않아 MAPE·편의를 표시하지 않습니다." : "";
  }

  // ── [6] 월별 추이 (최종 모델) ──────────────────────
  function monthlyCoverage() {
    const out = [];
    for (let i = 0; i < N; ) {
      const m = dateAt(i).getUTCMonth() + 1;
      let j = i;
      while (j < N && dateAt(j).getUTCMonth() + 1 === m) j++;
      out.push({ m, i0: i, ...windowStats(i, j), mpiw: windowStats(i, j).w });
      i = j;
    }
    return out;
  }

  // 지표별 축 범위·기준선(ref: 줄기의 기준, band/line: 성공 기준)
  const MONTH_METRIC = {
    cov: { name: "커버리지", unit: "%", d: 1, dom: [60, 90], band: TARGET, ref: 80 },
    rmae: { name: "rMAE", unit: "", d: 3, dom: [0.4, 1.0], line: CRIT.rmae.max, ref: CRIT.rmae.max },
    mae: { name: "MAE", unit: "원", d: 2, dom: [0, 12], line: CRIT.mae.max, ref: CRIT.mae.max },
    mape: { name: "MAPE", unit: "%", d: 2, dom: [0, 14], line: CRIT.mape.max, ref: CRIT.mape.max },
    bias: { name: "편의", unit: "%", d: 2, dom: [-8, 8], band: [-CRIT.bias.abs, CRIT.bias.abs], ref: 0 },
  };
  let monthMetric = "cov";

  function renderMonthly() {
    const box = $("#monthly");
    const { svg, w, h } = makeSvg(box);
    const data = monthlyCoverage();
    const spec = MONTH_METRIC[monthMetric];
    const vals = data.map((d) => d[monthMetric]);
    const ticks = niceTicks(Math.min(spec.dom[0], ...vals), Math.max(spec.dom[1], ...vals), 4);
    const m = { l: 44, r: 16, t: 14, b: 40 };
    const band = (w - m.l - m.r) / data.length;
    const x = (k) => m.l + band * (k + 0.5);
    const y = scale(ticks[0], ticks[ticks.length - 1], h - m.b, m.t);

    if (spec.band) svgEl("rect", { x: m.l, width: w - m.l - m.r, y: y(spec.band[1]), height: y(spec.band[0]) - y(spec.band[1]), style: "fill:var(--target-band)" }, svg);
    yGrid(svg, ticks, y, m.l, w - m.r, spec.unit === "%" ? "%" : "");
    if (spec.line != null) {
      svgEl("line", { x1: m.l, x2: w - m.r, y1: y(spec.line), y2: y(spec.line), style: "stroke:var(--good);stroke-width:1.5;stroke-dasharray:5 4" }, svg);
    }
    const crit = monthMetric === "cov" ? "목표 75–85%" : CRIT[monthMetric].label;
    svgEl("text", { x: w - m.r - 4, y: m.t - 2, "text-anchor": "end", class: "axis-label", style: "fill:var(--good)", text: "기준: " + crit }, svg);
    svgEl("text", { x: (m.l + w - m.r) / 2, y: h - 4, "text-anchor": "middle", class: "axis-label", text: "2026년" }, svg);

    // 점 + 기준값까지의 줄기로 기준 대비 차이를 보여줌
    data.forEach((d, k) => {
      const v = d[monthMetric], ok = passes(monthMetric, v);
      svgEl("text", { x: x(k), y: h - m.b + 18, "text-anchor": "middle", text: d.m + "월" }, svg);
      svgEl("line", { x1: x(k), x2: x(k), y1: y(spec.ref), y2: y(v), style: "stroke:var(--ink-3);stroke-width:2;stroke-linecap:round" }, svg);
      const g = svgEl("g", {}, svg);
      svgEl("rect", { x: x(k) - band / 2, y: m.t, width: band, height: h - m.t - m.b, style: "fill:transparent" }, g);
      svgEl("circle", { cx: x(k), cy: y(v), r: 6, style: `fill:${ok ? "var(--s1)" : "var(--s2)"};stroke:var(--surface);stroke-width:2` }, g);
      const above = v >= spec.ref;
      const txt = monthMetric === "bias" ? sign(v, 1) : v.toFixed(spec.d === 3 ? 2 : 1);
      svgEl("text", { x: x(k), y: y(v) + (above ? -12 : 20), "text-anchor": "middle", class: "lbl", text: txt }, g);
      g.addEventListener("mousemove", (ev) => showTip(
        `<div class="t-h">2026년 ${d.m}월</div>` +
        row("커버리지", fmt(d.cov) + "%") + row("평균 폭", fmt(d.mpiw) + "원") +
        row("MAE", fmt(d.mae, 2) + "원") + row("rMAE", d.rmae.toFixed(3)) +
        row("MAPE", fmt(d.mape, 2) + "%") + row("편의", sign(d.bias) + "%") +
        row("시간 수", d.n.toLocaleString()) +
        `<div class="t-tag ${ok ? "in" : "out"}">${spec.name} ${ok ? "기준 충족" : "기준 미달"}</div>`, ev.clientX, ev.clientY));
      g.addEventListener("mouseleave", hideTip);
    });
  }

  // ── [7] 시간대별 커버리지 ──────────────────────────
  const HOUR_SERIES = [
    { code: "F", name: "앙상블 + 등각 보정 (최종)", color: "var(--s1)" },
    { code: "B", name: "LightGBM 분위수 회귀", color: "var(--s2)" },
    { code: "E", name: "앙상블 (보정 전)", color: "var(--s3)" },
  ];
  let hourMetric = "picp";

  function renderHourly() {
    $("#hourLegend").innerHTML = HOUR_SERIES.map((s) =>
      `<span><i class="sw sw-line" style="background:${s.color};height:3px"></i>${s.name}</span>`).join("");
    const box = $("#hourChart");
    const { svg, w, h } = makeSvg(box);
    const m = { l: 44, r: 22, t: 12, b: 30 };
    const all = HOUR_SERIES.flatMap((s) => D.hourly[s.code].map((r) => r[hourMetric]));
    const ticks = hourMetric === "picp" ? [40, 50, 60, 70, 80, 90, 100] : niceTicks(0, Math.max(...all) + 2, 4);
    const x = scale(1, 24, m.l, w - m.r);
    const y = scale(ticks[0], ticks[ticks.length - 1], h - m.b, m.t);

    if (hourMetric === "picp") {
      svgEl("rect", { x: m.l, width: w - m.l - m.r, y: y(TARGET[1]), height: y(TARGET[0]) - y(TARGET[1]), style: "fill:var(--target-band)" }, svg);
    }
    yGrid(svg, ticks, y, m.l, w - m.r, hourMetric === "picp" ? "%" : "");
    for (let hh = 1; hh <= 24; hh += (w < 500 ? 3 : 1)) svgEl("text", { x: x(hh), y: h - 10, "text-anchor": "middle", text: hh }, svg);

    HOUR_SERIES.slice().reverse().forEach((s) => {
      const pts = D.hourly[s.code];
      svgEl("path", {
        d: linePath(pts.map((p) => x(p.h)), pts.map((p) => y(p[hourMetric]))),
        style: `fill:none;stroke:${s.color};stroke-width:${s.code === "F" ? 2.5 : 2};stroke-linejoin:round`,
      }, svg);
    });

    const cross = svgEl("line", { y1: m.t, y2: h - m.b, style: "stroke:var(--ink-3);stroke-dasharray:3 3;opacity:0" }, svg);
    const dots = HOUR_SERIES.map((s) => svgEl("circle", { r: 4.5, style: `fill:${s.color};stroke:var(--surface);stroke-width:2;opacity:0` }, svg));
    const hit = svgEl("rect", { x: m.l, y: 0, width: w - m.l - m.r, height: h, style: "fill:transparent" }, svg);
    hit.addEventListener("mousemove", (ev) => {
      const pt = svg.getBoundingClientRect();
      const hh = Math.max(1, Math.min(24, Math.round(x.inv(ev.clientX - pt.left))));
      cross.setAttribute("x1", x(hh)); cross.setAttribute("x2", x(hh)); cross.style.opacity = 1;
      let html = `<div class="t-h">${hh}시 (${hh - 1}:00–${hh}:00)</div>`;
      HOUR_SERIES.forEach((s, k) => {
        const r = D.hourly[s.code][hh - 1];
        dots[k].setAttribute("cx", x(hh)); dots[k].setAttribute("cy", y(r[hourMetric])); dots[k].style.opacity = 1;
        html += row(`<i class="sw sw-line" style="background:${s.color};height:3px;margin-right:6px;vertical-align:middle"></i>${s.code}`,
          hourMetric === "picp" ? fmt(r.picp) + "%" : fmt(r.mpiw) + "원");
      });
      showTip(html, ev.clientX, ev.clientY);
    });
    hit.addEventListener("mouseleave", () => { hideTip(); cross.style.opacity = 0; dots.forEach((d) => (d.style.opacity = 0)); });
  }

  // ── [8] 급등·일반·급락 ─────────────────────────────
  function renderRegimes() {
    const rows = D.regimes.filter((r) => r.code === "F");
    const order = ["급등", "일반", "급락"];
    const desc = { 급등: "어제보다 크게 오른 시간", 일반: "그 밖의 시간", 급락: "어제보다 크게 내린 시간" };
    $("#regimes").innerHTML = order.map((k) => {
      const r = rows.find((x) => x.regime === k);
      const inside = 100 - r.above - r.below;
      return `<div class="regime">
        <div class="regime-top"><span class="regime-name">${k}</span><span class="regime-n">${r.n.toLocaleString()}시간 · ${desc[k]}</span></div>
        <div class="regime-cov">${fmt(r.picp)}%<small>커버리지</small></div>
        <div class="stack" aria-hidden="true">
          ${r.below > 0 ? `<i class="below" style="width:${r.below}%"></i>` : ""}
          <i class="in" style="width:${inside}%"></i>
          ${r.above > 0 ? `<i class="above" style="width:${r.above}%"></i>` : ""}
        </div>
        <div class="stack-lbl"><span>하한 아래 ${fmt(r.below)}%</span><span>상한 위 ${fmt(r.above)}%</span></div>
        <dl>
          <dt>실제 평균</dt><dd>${fmt(r.actual)}원</dd>
          <dt>예측 중앙값 평균</dt><dd>${fmt(r.pred)}원</dd>
          <dt>평균 범위 폭</dt><dd>${fmt(r.mpiw)}원</dd>
          <dt>중앙값 MAE</dt><dd>${fmt(r.mae)}원</dd>
        </dl>
      </div>`;
    }).join("");
  }

  // ── [9] 앙상블 가중치 ─────────────────────────────
  function renderWeights() {
    const parts = [
      { k: "lgb", name: "LightGBM", color: "var(--s2)" },
      { k: "cov", name: "Chronos 수요예측", color: "var(--s1)" },
      { k: "uni", name: "Chronos 단변량", color: "var(--s3)" },
    ];
    const qName = { q10: "하한", q50: "중앙", q90: "상한" };
    $("#weights").innerHTML = D.weights.map((wt) =>
      `<div class="w-row"><span>${qName[wt.q]}</span><div class="w-bar" title="${parts.map((p) => `${p.name} ${Math.round(wt[p.k] * 100)}%`).join(" · ")}">` +
      parts.filter((p) => wt[p.k] > 0).map((p) => `<i style="width:${wt[p.k] * 100}%;background:${p.color}"></i>`).join("") +
      `</div></div>`).join("") +
      `<div class="w-legend">${parts.map((p) => `<span><i style="background:${p.color}"></i>${p.name}</span>`).join("")}</div>`;
  }

  // ── [10] 테마 전환 · 초기화 ─────────────────────────
  function setupTheme() {
    const root = document.documentElement;
    try { const t = localStorage.getItem("theme"); if (t) root.dataset.theme = t; } catch (e) { /* 저장소 없음 */ }
    $("#themeBtn").onclick = () => {
      const dark = root.dataset.theme
        ? root.dataset.theme === "dark"
        : window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.dataset.theme = dark ? "light" : "dark";
      try { localStorage.setItem("theme", root.dataset.theme); } catch (e) { /* 무시 */ }
    };
  }

  function renderAll() {
    renderTs(); renderScatter(); renderMonthly(); renderHourly();
  }

  // ── [11] 급등일 vs 일반일 (과제 기준, spike_days.py 결과) ─────
  let spkPeriod = "test";
  function renderSpikeDays() {
    const SP = D.spike;
    if (!SP) return;
    const rows = SP.cmp.filter((r) => r.period === spkPeriod);
    const get = (c, k) => rows.find((r) => r.code === c && r.kind === k);
    const names = Object.fromEntries(D.evals.test.map((r) => [r.code, r.name]));
    const s0 = get("F", "급등일"), n0 = get("F", "일반일");
    $("#spkMethodTable").innerHTML =
      `<thead><tr><th>방법</th><th class="grp">커버리지 급등일 / 일반일</th><th>폭 급등일 / 일반일</th><th>상한 위 급등일 / 일반일</th>` +
      `<th class="grp">MAE 급등일 / 일반일</th><th>rMAE 급등일 / 일반일</th><th>편의 급등일 / 일반일</th></tr></thead><tbody>` +
      "ABCDEF".split("").map((c) => {
        const s = get(c, "급등일"), n = get(c, "일반일");
        return `<tr class="${c === "F" ? "final" : ""}"><td><span class="code">${c}</span>${names[c]}</td>
          <td class="grp">${fmt(s.picp)}% / ${fmt(n.picp)}%</td><td>${fmt(s.mpiw)} / ${fmt(n.mpiw)}원</td>
          <td>${fmt(s.above)}% / ${fmt(n.above)}%</td>
          <td class="grp">${fmt(s.mae, 2)} / ${fmt(n.mae, 2)}원</td><td>${s.rmae.toFixed(3)} / ${n.rmae.toFixed(3)}</td>
          <td>${sign(s.bias)}% / ${sign(n.bias)}%</td></tr>`;
      }).join("") + "</tbody>";
    $("#spkMethodNote").textContent =
      `시간 단위 지표. 급등일 ${s0.days}일(${s0.n}시간) · 일반일 ${n0.days}일(${n0.n.toLocaleString()}시간). ` +
      (spkPeriod === "calib" ? "보정 2025는 E·F의 가중치·보정값을 정한 해라 E·F 수치가 다소 유리하게 나옵니다." : "급등일 표본이 6일뿐이라 비율은 하루만 달라져도 크게 움직입니다.");

    const pk = SP.peak.filter((r) => r.period === spkPeriod);
    const pn = pk.find((r) => r.kind === "일반일"), ps = pk.find((r) => r.kind === "급등일");
    const tr = (k, a, b) => `<tr><td>${k}</td><td>${a}</td><td>${b}</td></tr>`;
    $("#spkPeakTable").innerHTML =
      `<thead><tr><th>하루 최고가 · 최종 모델</th><th>일반일 (${pn.days}일)</th><th>급등일 (${ps.days}일)</th></tr></thead><tbody>` +
      tr("실제 최고가 평균", fmt(pn.actualMax) + "원", fmt(ps.actualMax) + "원") +
      tr("예측 중앙값의 하루 최고 평균", fmt(pn.medMax) + "원", fmt(ps.medMax) + "원") +
      tr("예측 상한의 하루 최고 평균", fmt(pn.upMax) + "원", fmt(ps.upMax) + "원") +
      tr("최고가를 낮게 본 정도", fmt(pn.under) + "원", `<b>${fmt(ps.under)}원</b>`) +
      tr("최고가 시간 적중", fmt(pn.peakHit, 0) + "%", `<b>${fmt(ps.peakHit, 0)}%</b>`) +
      tr("최고가 시간에 상한을 넘은 평균", fmt(pn.shortfall) + "원", `<b>${fmt(ps.shortfall)}원</b>`) +
      tr("최고가 시각 맞힘 (±1시간)", fmt(pn.timing, 0) + "%", fmt(ps.timing, 0) + "%") +
      tr("D-1 신호 (상한 ≥ 기준 × 1.25)", fmt(pn.sigUp) + "%", `<b>${fmt(ps.sigUp)}%</b>`) +
      "</tbody>";
  }
  document.querySelectorAll("#spkPeriodSeg button").forEach((b) => {
    b.onclick = () => {
      spkPeriod = b.dataset.p;
      document.querySelectorAll("#spkPeriodSeg button").forEach((x) => x.classList.toggle("on", x === b));
      renderSpikeDays();
    };
  });

  setupTheme();
  renderCriteria();
  setupExplorer();
  renderTable();
  renderSpikeDays();
  renderRegimes();
  renderWeights();

  document.querySelectorAll("#periodSeg button").forEach((b) => {
    b.onclick = () => {
      period = b.dataset.p;
      document.querySelectorAll("#periodSeg button").forEach((x) => x.classList.toggle("on", x === b));
      renderScatter(); renderTable();
    };
  });
  document.querySelectorAll("#hourMetricSeg button").forEach((b) => {
    b.onclick = () => {
      hourMetric = b.dataset.m;
      document.querySelectorAll("#hourMetricSeg button").forEach((x) => x.classList.toggle("on", x === b));
      renderHourly();
    };
  });

  $("#monthMetric").onchange = (e) => { monthMetric = e.target.value; renderMonthly(); };

  renderAll();
  let rz;
  window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(renderAll, 120); });
})();
