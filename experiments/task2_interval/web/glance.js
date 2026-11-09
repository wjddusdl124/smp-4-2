/* 「한눈에」 페이지 — data.js(window.DATA)를 읽어 쉬운 말과 간단한 그림으로 보여준다 */
(function () {
  "use strict";
  const D = window.DATA;
  const S = D.series;
  const N = S.actual.length;
  const F = D.evals.test.find((r) => r.code === "F");
  const DOW = ["일", "월", "화", "수", "목", "금", "토"];
  const MAPE_FLOOR = 20;   // MAPE·편의 분모 하한(원) — 운영 코드와 같은 정의

  // ── [1] 도우미 ─────────────────────────────────────
  const $ = (s) => document.querySelector(s);
  const fmt = (v, d = 1) => (v == null ? "–" : v.toFixed(d));
  const sign = (v, d = 2) => (v > 0 ? "+" : "") + v.toFixed(d);
  const NS = "http://www.w3.org/2000/svg";
  function el(tag, a, p) {
    const e = document.createElementNS(NS, tag);
    for (const k in a) {
      if (k === "style") e.style.cssText = a[k];
      else if (k === "text") e.textContent = a[k];
      else e.setAttribute(k, a[k]);
    }
    if (p) p.appendChild(e);
    return e;
  }
  function makeSvg(box) {
    box.innerHTML = "";
    const w = box.clientWidth, h = box.clientHeight;
    return { svg: el("svg", { viewBox: `0 0 ${w} ${h}`, role: "img" }, box), w, h };
  }
  const lin = (d0, d1, r0, r1) => (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);

  const tip = $("#tip");
  function showTip(html, x, y) {
    tip.innerHTML = html; tip.classList.add("show");
    const r = tip.getBoundingClientRect();
    let l = x + 14, t = y + 14;
    if (l + r.width > innerWidth - 8) l = x - r.width - 14;
    if (t + r.height > innerHeight - 8) t = y - r.height - 14;
    tip.style.left = Math.max(8, l) + "px"; tip.style.top = Math.max(8, t) + "px";
  }
  const hideTip = () => tip.classList.remove("show");
  const row = (k, v) => `<div class="t-r"><span>${k}</span><b>${v}</b></div>`;

  // 시각: 배열 인덱스 i → 날짜(UTC 로 다뤄 브라우저 시간대 영향 제거)
  const t0 = Date.UTC(+S.start.slice(0, 4), +S.start.slice(5, 7) - 1, +S.start.slice(8, 10));
  const dateAt = (i) => new Date(t0 + i * 3600e3);
  const dayName = (dt) => `${dt.getUTCMonth() + 1}월 ${dt.getUTCDate()}일(${DOW[dt.getUTCDay()]})`;
  const isOut = (i) => S.actual[i] != null && (S.actual[i] < S.lower[i] || S.actual[i] > S.upper[i]);
  const NDAY = Math.floor(N / 24);

  function stats(i0, i1) {
    let n = 0, cin = 0, up = 0, dn = 0, w = 0, ae = 0, aeN = 0, nN = 0, ape = 0;
    for (let i = i0; i < i1; i++) {
      const a = S.actual[i];
      if (a == null) continue;
      n++;
      if (a > S.upper[i]) up++; else if (a < S.lower[i]) dn++; else cin++;
      w += S.upper[i] - S.lower[i];
      ae += Math.abs(S.median[i] - a);
      ape += Math.abs(S.median[i] - a) / Math.max(a, MAPE_FLOOR);
      // 전날 실제값이 없는 시간은 단순 예측도 없음 → 단순 예측 오차에서만 제외
      if (S.naive[i] != null) { aeN += Math.abs(S.naive[i] - a); nN++; }
    }
    if (!n) return null;
    const maeN = nN ? aeN / nN : null;
    return { n, cin, up, dn, cov: (cin / n) * 100, w: w / n, mae: ae / n, maeN, rmae: maeN ? ae / n / maeN : null, mape: (ape / n) * 100 };
  }

  // ── [2] 큰 숫자 4개 · 한 줄 요약 ────────────────────
  const CHECKS = [
    { k: "범위 적중률", tag: "핵심", plain: "실제 가격이 범위 안에 들어온 비율", target: "75–85%", v: F.picp, show: fmt(F.picp) + "%", ok: F.picp >= 75 && F.picp <= 85 },
    { k: "rMAE", tag: "목표", plain: "단순 예측(어제 같은 시각) 대비 오차 비율", target: "0.65 이하", v: F.rmae, show: F.rmae.toFixed(3), ok: F.rmae <= 0.65 },
    { k: "MAE", tag: "도전", plain: "예측값이 평균 몇 원 틀렸나", target: "7.0원 이하", v: F.mae, show: fmt(F.mae, 2) + "원", ok: F.mae <= 7.0 },
    { k: "MAPE", tag: "보조", plain: "가격 대비 평균 몇 % 틀렸나", target: "5.0% 미만", v: F.mape, show: fmt(F.mape, 2) + "%", ok: F.mape < 5.0 },
    { k: "편의", tag: "보조", plain: "한쪽으로 치우쳐 높게(+)/낮게(−) 예측하는 정도", target: "±1.5% 이내", v: F.bias, show: sign(F.bias) + "%", ok: Math.abs(F.bias) <= 1.5 },
  ];

  function renderTop() {
    const all = stats(0, N);
    let medSum = 0, medN = 0;
    for (let i = 0; i < N; i++) if (S.actual[i] != null) { medSum += S.median[i]; medN++; }
    const med = medSum / medN, half = all.w / 2;
    const okN = CHECKS.filter((c) => c.ok).length;

    $("#tiles").innerHTML = `
      <div class="tile">
        <span class="tile-badge">COVER</span>
        <div class="tile-k">범위 적중률</div>
        <div class="tile-v">${fmt(F.picp)}<small>%</small></div>
        <div class="tile-d">10시간 중 8시간은 실제 가격이 범위 안 · 목표 75–85%</div>
      </div>
      <div class="tile">
        <span class="tile-badge">WIDTH</span>
        <div class="tile-k">범위 폭 (평균)</div>
        <div class="tile-v">${fmt(F.mpiw)}<small>원</small></div>
        <div class="tile-d">예: 예측 ${Math.round(med)}원이면 범위는 약 ${Math.round(med - half)}–${Math.round(med + half)}원</div>
      </div>
      <div class="tile">
        <span class="tile-badge">ERROR</span>
        <div class="tile-k">예측 오차 (평균)</div>
        <div class="tile-v">${fmt(F.mae, 2)}<small>원</small></div>
        <div class="tile-d">단순 예측(어제 같은 시각) ${fmt(F.mae_naive, 2)}원보다 ${fmt(F.gain, 0)}% 작음</div>
      </div>
      <div class="tile">
        <span class="tile-badge">GOAL</span>
        <div class="tile-k">목표 달성</div>
        <div class="tile-v">${okN}<small>/ ${CHECKS.length}</small></div>
        <div class="tile-d">범위 목표는 달성 · 정확도 목표 ${CHECKS.length - okN}개는 아직</div>
      </div>`;

    $("#summary").innerHTML =
      `<span class="s-main">결론</span> — 실제 가격이 예측 범위 안에 들어온 비율은 <b>${fmt(F.picp)}%</b>로 ` +
      `<span class="s-ok">목표(75–85%) 달성</span>. 예측값 자체는 단순 예측보다 ${fmt(F.gain, 0)}% 정확하지만, ` +
      `평균 오차 ${fmt(F.mae, 2)}원은 도전 목표 7.0원까지 <span class="s-no">${fmt(F.mae - 7, 2)}원 부족</span>합니다.`;

    $("#checks").innerHTML = CHECKS.map((c) => `
      <li>
        <span class="ck ${c.ok ? "ok" : "no"}" aria-label="${c.ok ? "달성" : "미달"}">${c.ok ? "✓" : "✕"}</span>
        <div><div class="ck-name">${c.k}<small>${c.tag}</small></div><div class="ck-plain">${c.plain}</div></div>
        <div class="ck-val"><b>${c.show}</b><span>목표 ${c.target}</span></div>
      </li>`).join("");
  }

  // ── [3] 하루 예측 vs 실제 ──────────────────────────
  let day = 13;   // 1월 14일 — 적중률·오차가 전체 평균에 가까운 평범한 날

  function pickDays() {
    let worst = 0, worstV = -1, low = 0, lowV = Infinity;
    for (let d = 0; d < NDAY; d++) {
      let miss = 0;
      for (let i = d * 24; i < d * 24 + 24; i++) {
        const a = S.actual[i];
        if (a == null) continue;
        miss += Math.max(0, a - S.upper[i]) + Math.max(0, S.lower[i] - a);
        if (a < lowV) { lowV = a; low = d; }
      }
      if (miss > worstV) { worstV = miss; worst = d; }
    }
    return [
      { label: "평범한 날", d: 13 },
      { label: "가장 크게 빗나간 날", d: worst },
      { label: "가격이 가장 낮았던 날", d: low },
      { label: "마지막 날", d: NDAY - 1 },
    ];
  }

  function renderDay() {
    const box = $("#dayChart");
    const { svg, w, h } = makeSvg(box);
    const i0 = day * 24, idx = [...Array(24).keys()].map((k) => i0 + k);
    const m = { l: 40, r: 10, t: 10, b: 26 };
    let lo = Infinity, hi = -Infinity;
    idx.forEach((i) => [S.lower[i], S.upper[i], S.actual[i]].forEach((v) => { if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }));
    lo = Math.max(0, Math.floor((lo - 5) / 10) * 10); hi = Math.ceil((hi + 5) / 10) * 10;
    const x = lin(0, 23, m.l, w - m.r), y = lin(lo, hi, h - m.b, m.t);
    const step = hi - lo > 80 ? 20 : 10;
    for (let v = lo; v <= hi; v += step) {
      el("line", { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: "gl" }, svg);
      el("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", text: v }, svg);
    }
    for (let k = 0; k < 24; k += 3) el("text", { x: x(k), y: h - 7, "text-anchor": "middle", text: k + 1 + "시" }, svg);

    const pts = (arr) => idx.map((i, k) => `${x(k).toFixed(1)},${y(arr[i]).toFixed(1)}`);
    el("path", { d: "M" + pts(S.upper).join("L") + "L" + pts(S.lower).reverse().join("L") + "Z", style: "fill:var(--band);stroke:var(--band-line);stroke-width:1" }, svg);
    el("path", { d: "M" + pts(S.median).join("L"), style: "fill:none;stroke:var(--med);stroke-width:2.5;stroke-dasharray:6 4" }, svg);
    let d = "", pen = false;
    idx.forEach((i, k) => {
      if (S.actual[i] == null) { pen = false; return; }
      d += (pen ? "L" : "M") + x(k).toFixed(1) + "," + y(S.actual[i]).toFixed(1); pen = true;
    });
    el("path", { d, style: "fill:none;stroke:var(--ink);stroke-width:2.25;stroke-linejoin:round" }, svg);
    idx.forEach((i, k) => { if (isOut(i)) el("circle", { cx: x(k), cy: y(S.actual[i]), r: 5, style: "fill:var(--out);stroke:var(--panel);stroke-width:2" }, svg); });

    // 시간별 호버 영역
    const bw = (w - m.l - m.r) / 23;
    idx.forEach((i, k) => {
      const r = el("rect", { x: x(k) - bw / 2, y: m.t, width: bw, height: h - m.t - m.b, style: "fill:transparent" }, svg);
      r.addEventListener("mousemove", (ev) => {
        const a = S.actual[i];
        const tag = a == null ? "" : a > S.upper[i] ? `<div class="t-tag out">▲ 범위보다 ${fmt(a - S.upper[i])}원 높음</div>`
          : a < S.lower[i] ? `<div class="t-tag out">▼ 범위보다 ${fmt(S.lower[i] - a)}원 낮음</div>` : `<div class="t-tag in">● 범위 안</div>`;
        showTip(`<div class="t-h">${k + 1}시</div>` + row("실제", fmt(a, 1) + "원") + row("예측", fmt(S.median[i], 1) + "원") +
          row("범위", `${fmt(S.lower[i], 0)}–${fmt(S.upper[i], 0)}원`) + tag, ev.clientX, ev.clientY);
      });
      r.addEventListener("mouseleave", hideTip);
    });

    const s = stats(i0, i0 + 24);
    const dt = dateAt(i0);
    $("#dayText").innerHTML = s
      ? `<b>${dayName(dt)}</b> — 24시간 중 <b>${s.cin}시간(${fmt(s.cov, 0)}%)</b>이 범위 안에 들어왔습니다` +
        (s.up + s.dn ? ` (범위보다 높음 ${s.up}시간 · 낮음 ${s.dn}시간)` : "") +
        `. 예측값은 평균 <b>${fmt(s.mae)}원</b> 빗나갔고, 어제 같은 시각을 그대로 쓰면 ${fmt(s.maeN)}원 빗나갔을 것입니다.`
      : `<b>${dayName(dt)}</b> — 이 날은 실제 가격 자료가 없습니다.`;
    $("#dayInput").value = dt.toISOString().slice(0, 10);
    document.querySelectorAll("#quick button").forEach((b) => b.classList.toggle("on", +b.dataset.d === day));
  }

  function setupDay() {
    $("#quick").innerHTML = pickDays().map((p) => `<button type="button" data-d="${p.d}">${p.label}</button>`).join("");
    document.querySelectorAll("#quick button").forEach((b) => (b.onclick = () => { day = +b.dataset.d; renderDay(); }));
    $("#dayPrev").onclick = () => { day = Math.max(0, day - 1); renderDay(); };
    $("#dayNext").onclick = () => { day = Math.min(NDAY - 1, day + 1); renderDay(); };
    $("#dayInput").onchange = (e) => {
      const v = e.target.value; if (!v) return;
      const t = Date.UTC(+v.slice(0, 4), +v.slice(5, 7) - 1, +v.slice(8, 10));
      day = Math.max(0, Math.min(NDAY - 1, Math.round((t - t0) / 86400e3)));
      renderDay();
    };
  }

  // ── [4] 시간대별 적중률 막대 ────────────────────────
  function renderHours() {
    const data = D.hourly.F;
    const box = $("#hourBars");
    const { svg, w, h } = makeSvg(box);
    const m = { l: 36, r: 6, t: 10, b: 24 };
    const y = lin(0, 100, h - m.b, m.t);
    const band = (w - m.l - m.r) / 24, bw = Math.max(4, band - 3);
    el("rect", { x: m.l, width: w - m.l - m.r, y: y(85), height: y(75) - y(85), style: "fill:var(--target)" }, svg);
    [0, 25, 50, 75, 100].forEach((v) => {
      el("line", { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: "gl" }, svg);
      el("text", { x: m.l - 6, y: y(v) + 4, "text-anchor": "end", text: v + "%" }, svg);
    });
    data.forEach((r, k) => {
      const cx = m.l + band * k + band / 2, ok = r.picp >= 75 && r.picp <= 85, low = r.picp < 75;
      const top = y(r.picp), rad = Math.min(4, bw / 2);
      // 위쪽 모서리만 둥근 막대(바닥에 붙음)
      el("path", {
        d: `M${cx - bw / 2},${y(0)}V${top + rad}Q${cx - bw / 2},${top} ${cx - bw / 2 + rad},${top}H${cx + bw / 2 - rad}Q${cx + bw / 2},${top} ${cx + bw / 2},${top + rad}V${y(0)}Z`,
        style: `fill:${low ? "var(--bad)" : "var(--med)"};opacity:${ok || low ? 1 : 0.55}`,
      }, svg);
      if (k % 3 === 0) el("text", { x: cx, y: h - 6, "text-anchor": "middle", text: r.h + "시" }, svg);
      const hit = el("rect", { x: cx - band / 2, y: m.t, width: band, height: h - m.t - m.b, style: "fill:transparent" }, svg);
      hit.addEventListener("mousemove", (ev) => showTip(`<div class="t-h">${r.h}시</div>` + row("적중률", fmt(r.picp) + "%") +
        row("범위 폭", fmt(r.mpiw) + "원") + `<div class="t-tag ${low ? "out" : "in"}">${low ? "목표보다 낮음" : ok ? "목표대 안" : "목표보다 넉넉함"}</div>`, ev.clientX, ev.clientY));
      hit.addEventListener("mouseleave", hideTip);
    });
    const lows = data.filter((r) => r.picp < 75).sort((a, b) => a.picp - b.picp);
    $("#hourText").innerHTML = lows.length
      ? `<b>${lows.map((r) => `${r.h}시(${fmt(r.picp, 0)}%)`).join(" · ")}</b>는 목표보다 덜 맞습니다(주황 막대). ` +
        `태양광 발전이 몰리는 낮 시간이라 가격이 갑자기 떨어지는 일이 많기 때문입니다. 밤·새벽은 대부분 80% 이상입니다.`
      : "모든 시간대가 목표 이상입니다.";
  }

  // ── [5] 급등일 vs 일반일 ───────────────────────────
  // 급등일 = 그날 최고 SMP ≥ 직전 28일 「일 최고 SMP」 중앙값 × 1.25 (2021년 이후 59일)
  const SP = D.spike;
  let spkPeriod = "test";

  function renderSpikeStatic() {
    const A = SP.all, days = SP.days;
    const hit = days.filter((d) => d.shortfall === 0).length;
    const avgShort = days.reduce((s, d) => s + d.shortfall, 0) / days.length;
    const sig = SP.peak.filter((p) => p.kind === "급등일");
    const sigN = Math.round(sig.reduce((s, p) => s + (p.sigUp / 100) * p.days, 0));
    $("#spkDef").innerHTML =
      `<b>급등일</b> = 그날 최고 SMP가 직전 28일 「하루 최고 SMP」의 중앙값보다 25% 이상 높은 날. ` +
      `2021년 이후 ${A.n}일이고, 그중 보정 기간(2025) ${A.byYear["2025"] || 0}일 · 시험 기간(2026.1~9) ${A.byYear["2026"] || 0}일을 분석했습니다.`;
    $("#spkFacts").innerHTML = `
      <div class="fact"><div class="fact-v">${hit}<small>/ ${days.length}일</small></div>
        <div class="fact-k">최고가 시간이 범위 안에 든 급등일</div>
        <div class="fact-d">급등일의 최고가는 한 번도 80% 범위 안에 들지 못함</div></div>
      <div class="fact"><div class="fact-v">${fmt(avgShort, 0)}<small>원</small></div>
        <div class="fact-k">최고가가 상한을 넘은 평균 폭</div>
        <div class="fact-d">실제 최고가가 범위 상한보다 평균 ${fmt(avgShort, 0)}원 높았음</div></div>
      <div class="fact"><div class="fact-v">${sigN}<small>/ ${days.length}일</small></div>
        <div class="fact-k">전날 예측으로 미리 알아챈 급등일</div>
        <div class="fact-d">예측 상한의 최고값도 급등 기준(×1.25)에 못 미침</div></div>`;

    renderSpikeShape();

    // 급등일 목록 — 2026년은 하루 그래프로 이동 가능
    $("#spkDays").innerHTML =
      `<thead><tr><th>날짜</th><th>최고가 시각</th><th>기준(28일 중앙)</th><th>실제 최고가</th><th>예측 최고가</th><th>그 시각 상한</th><th>상한 초과</th><th>하루 적중률</th></tr></thead><tbody>` +
      days.map((d) => {
        const dt = new Date(d.date + "T00:00:00Z");
        const name = `${dt.getUTCFullYear()}. ${dayName(dt)}`;
        const cell = d.period === "test" ? `<button type="button" class="link" data-date="${d.date}">${name}</button>` : name;
        return `<tr><td>${cell}</td><td>${d.peakHour}시</td><td>${fmt(d.ref)}원</td>
          <td>${fmt(d.actualMax)}원 <span class="muted">(×${d.ratio.toFixed(2)})</span></td>
          <td>${fmt(d.medMax)}원</td><td>${fmt(d.upAtPeak)}원</td>
          <td class="hot">+${fmt(d.shortfall)}원</td><td>${fmt(d.dayCov, 0)}%</td></tr>`;
      }).join("") + "</tbody>";
    document.querySelectorAll("#spkDays .link").forEach((b) => (b.onclick = () => {
      const t = Date.UTC(+b.dataset.date.slice(0, 4), +b.dataset.date.slice(5, 7) - 1, +b.dataset.date.slice(8, 10));
      day = Math.round((t - t0) / 86400e3);
      renderDay();
      document.querySelector("#dayChart").scrollIntoView({ behavior: "smooth", block: "center" });
    }));

    const top = Object.entries(A.byHour).sort((a, b) => b[1] - a[1]).slice(0, 2);
    const topM = Object.entries(A.byMonth).sort((a, b) => b[1] - a[1])[0];
    $("#spkFoot").innerHTML =
      `<b>급등은 하루 중 딱 1시간짜리 “바늘”</b>입니다. 59일 중 ${A.oneHour}일은 급등 기준을 넘은 시간이 1시간뿐이었고, ` +
      `분석한 ${days.length}일은 모두 1시간이었습니다. 그래서 하루 전체 적중률은 평소와 비슷하게 나오지만, 정작 중요한 최고가 시간은 놓칩니다. ` +
      `최고가는 주로 <b>${top.map(([h, n]) => `${h}시(${n}일)`).join(" · ")}</b>에, 계절로는 ${topM[0]}월(${topM[1]}일)에 몰립니다. ` +
      `지난 가격·수요예측만으로는 이 1시간을 미리 알 수 없으므로, 급등 경보는 공급 쪽 정보(발전기 정지 등)가 있어야 가능합니다.`;
  }

  function renderSpikeTable() {
    const F = (kind) => SP.cmp.find((r) => r.period === spkPeriod && r.code === "F" && r.kind === kind);
    const P = (kind) => SP.peak.find((r) => r.period === spkPeriod && r.kind === kind);
    const n = F("일반일"), s = F("급등일"), pn = P("일반일"), ps = P("급등일");
    $("#spkPeriodLbl").textContent = `· 최종 모델, ${spkPeriod === "test" ? "시험 2026" : "보정 2025 (참고)"}`;
    const tr = (k, a, b, hot) => `<tr><td>${k}</td><td>${a}</td><td class="${hot ? "hot" : ""}">${b}</td></tr>`;
    $("#spkTable").innerHTML =
      `<thead><tr><th></th><th>일반일 (${n.days}일)</th><th>급등일 (${s.days}일)</th></tr></thead><tbody>` +
      tr("하루 전체 시간 적중률", fmt(n.picp) + "%", fmt(s.picp) + "%") +
      tr("최고가 시간 적중률", fmt(pn.peakHit, 0) + "%", fmt(ps.peakHit, 0) + "%", true) +
      tr("실제 최고가 (평균)", fmt(pn.actualMax) + "원", fmt(ps.actualMax) + "원") +
      tr("예측 최고가 (평균)", fmt(pn.medMax) + "원", fmt(ps.medMax) + "원") +
      tr("최고가를 낮게 본 정도", fmt(pn.under) + "원", fmt(ps.under) + "원", true) +
      tr("최고가 시각 맞힘 (±1시간)", fmt(pn.timing, 0) + "%", fmt(ps.timing, 0) + "%") +
      tr("평균 오차 MAE (하루 전체)", fmt(n.mae, 2) + "원", fmt(s.mae, 2) + "원") +
      `</tbody>`;
  }

  function renderSpikeShape() {
    const sh = SP.shape.spike;
    const box = $("#spkShape");
    const { svg, w, h } = makeSvg(box);
    const m = { l: 36, r: 8, t: 10, b: 24 };
    const vals = [...sh.하한, ...sh.상한, ...sh.실제];
    const lo = Math.floor(Math.min(...vals) / 20) * 20, hi = Math.ceil(Math.max(...vals) / 20) * 20;
    const x = lin(0, 23, m.l, w - m.r), y = lin(lo, hi, h - m.b, m.t);
    for (let v = lo; v <= hi; v += 20) {
      el("line", { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: "gl" }, svg);
      el("text", { x: m.l - 6, y: y(v) + 4, "text-anchor": "end", text: v }, svg);
    }
    for (let k = 0; k < 24; k += 3) el("text", { x: x(k), y: h - 6, "text-anchor": "middle", text: k + 1 + "시" }, svg);
    const pts = (a) => a.map((v, k) => `${x(k).toFixed(1)},${y(v).toFixed(1)}`);
    el("path", { d: "M" + pts(sh.상한).join("L") + "L" + pts(sh.하한).reverse().join("L") + "Z", style: "fill:var(--band);stroke:var(--band-line);stroke-width:1" }, svg);
    el("path", { d: "M" + pts(sh.중앙).join("L"), style: "fill:none;stroke:var(--med);stroke-width:2.5;stroke-dasharray:6 4" }, svg);
    el("path", { d: "M" + pts(sh.실제).join("L"), style: "fill:none;stroke:var(--ink);stroke-width:2.25;stroke-linejoin:round" }, svg);
    const k = sh.실제.indexOf(Math.max(...sh.실제));
    el("circle", { cx: x(k), cy: y(sh.실제[k]), r: 5, style: "fill:var(--out);stroke:var(--panel);stroke-width:2" }, svg);
    el("text", { x: x(k) + 9, y: y(sh.실제[k]) + 4, class: "lbl", text: `${k + 1}시 실제 ${fmt(sh.실제[k], 0)}원 · 상한 ${fmt(sh.상한[k], 0)}원` }, svg);
    sh.실제.forEach((v, i) => {
      const r = el("rect", { x: x(i) - (w - m.l - m.r) / 46, y: m.t, width: (w - m.l - m.r) / 23, height: h - m.t - m.b, style: "fill:transparent" }, svg);
      r.addEventListener("mousemove", (ev) => showTip(`<div class="t-h">${i + 1}시 · 급등일 평균</div>` + row("실제", fmt(v) + "원") +
        row("예측", fmt(sh.중앙[i]) + "원") + row("범위", `${fmt(sh.하한[i], 0)}–${fmt(sh.상한[i], 0)}원`), ev.clientX, ev.clientY));
      r.addEventListener("mouseleave", hideTip);
    });
  }

  function setupSpike() {
    renderSpikeStatic();
    renderSpikeTable();
    document.querySelectorAll("#spkSeg button").forEach((b) => (b.onclick = () => {
      spkPeriod = b.dataset.p;
      document.querySelectorAll("#spkSeg button").forEach((x) => x.classList.toggle("on", x === b));
      renderSpikeTable();
    }));
  }

  // ── [6] 월별 표 ──────────────────────────────────
  function renderMonths() {
    const rows = [];
    for (let i = 0; i < N; ) {
      const mo = dateAt(i).getUTCMonth() + 1;
      let j = i;
      while (j < N && dateAt(j).getUTCMonth() + 1 === mo) j++;
      rows.push({ mo, ...stats(i, j) });
      i = j;
    }
    const all = stats(0, N);
    const tr = (label, s, foot) => {
      const ok = s.cov >= 75 && s.cov <= 85;
      return `<tr><td>${label}</td>
        <td><span class="mbar" aria-hidden="true"><i style="width:${s.cov}%"></i></span>${fmt(s.cov)}%</td>
        <td>${fmt(s.w)}원</td><td>${fmt(s.mae, 2)}원</td><td>${fmt(s.maeN, 2)}원</td>
        <td>${foot ? "" : `<span class="tag ${ok ? "ok" : "no"}">${ok ? "목표 안" : s.cov < 75 ? "조금 낮음" : "조금 높음"}</span>`}</td></tr>`;
    };
    $("#monthTable").innerHTML =
      `<thead><tr><th>월</th><th>범위 적중률</th><th>범위 폭</th><th>예측 오차</th><th>단순 예측 오차</th><th>판정</th></tr></thead>` +
      `<tbody>${rows.map((r) => tr(r.mo + "월", r)).join("")}</tbody>` +
      `<tfoot>${tr("전체", all, true)}</tfoot>`;
  }

  // ── [7] 테마 · 시작 ────────────────────────────────
  const root = document.documentElement;
  try { const t = localStorage.getItem("theme"); if (t) root.dataset.theme = t; } catch (e) { /* 저장소 없음 */ }
  $("#themeBtn").onclick = () => {
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) { /* 무시 */ }
  };

  renderTop();
  setupDay();
  renderDay();
  renderHours();
  if (SP) setupSpike();
  renderMonths();
  let rz;
  addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { renderDay(); renderHours(); if (SP) renderSpikeShape(); }, 120); });
})();
