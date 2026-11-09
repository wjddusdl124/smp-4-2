# -*- coding: utf-8 -*-
"""
spike_days.py — 급등일 vs 일반일 비교 (과제 2 보충 분석)
==============================================================================
급등일 정의 (과제 기준)
  · 그날 최고 SMP 가 직전 28일 「일 최고 SMP」 중앙값보다 25% 이상 높은 날
    → 2021년 이후 59일
  · 기준값(직전 28일 중앙값)은 D-1 까지의 값이라 전날 알 수 있음.
    그날 최고 SMP 는 D일 실제값이므로 「급등일」 구분은 사후 평가용으로만 쓴다(모델 입력 아님)

무엇을 보나
  ① 시간 단위 성능 : 급등일 vs 일반일의 커버리지·폭·Winkler·MAE·rMAE·MAPE·편의
  ② 하루 최고가(피크) : 피크 시각에 범위가 맞았나, 예측 최고가가 실제 최고가를 얼마나 따라갔나
  ③ D-1 탐지 : 예측 최고가(중앙값·상한)만 보고 전날 급등일을 알아챌 수 있었나
  ④ 59일 전체의 특징 : 연도·월·요일·피크 시각

기간
  · 시험(2026.1.1~9.30) — 최종 평가. 설정은 task2_interval.py 그대로(바꾸지 않음)
  · 보정(2025) — 참고. LightGBM·Chronos 는 학습에 쓰지 않은 해지만,
    앙상블 가중치·등각 보정값을 2025년으로 정했으므로 E·F 의 2025년 수치는 다소 유리하게 나옴

실행
  .venv\\Scripts\\python.exe experiments\\task2_interval\\spike_days.py
  (task2_interval.py 를 한 번 실행해 results/chronos_preds.csv 가 있어야 함)
"""
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import task2_interval as T   # 같은 폴더의 본 실험 코드 — 함수만 가져다 씀(수정하지 않음)

SPIKE_RATIO = 1.25            # 직전 28일 일 최고가 중앙값 대비 25% 이상
REF_DAYS = 28
MAPE_FLOOR = 20.0             # MAPE·편의 분모 하한(원) — 운영 코드와 같은 정의
METHODS = ["A_잔차분위수", "B_LightGBM분위수", "C_Chronos2_수요예측", "D_Chronos2_단변량",
           "E_앙상블", "F_앙상블+등각보정(최종)"]
FINAL = "F_앙상블+등각보정(최종)"
C_GRAY = "#8a8983"


# =============================================================================
# [1] 데이터 준비 — 급등일 표시
# =============================================================================
def 급등일_표(d):
    """날짜별 최고 SMP, 직전 28일 일 최고가 중앙값(기준), 급등 여부"""
    day = d.groupby("date").agg(day_max=("smp_land", "max"))
    peak_h = d.loc[d["smp_land"].notna()].sort_values("smp_land").groupby("date")["hour_n"].last()
    day["peak_hour"] = peak_h
    day["ref"] = day["day_max"].shift(1).rolling(REF_DAYS, min_periods=REF_DAYS).median()
    day["ratio"] = day["day_max"] / day["ref"]
    day["spike"] = (day["ratio"] >= SPIKE_RATIO) & (day.index >= "2021-01-01")
    # 급등 기준(기준값 × 1.25)을 넘은 시간 수 — 급등이 몇 시간 동안 이어졌나
    thr = d["date"].map(day["ref"] * SPIKE_RATIO)
    day["hot_hours"] = (d["smp_land"] >= thr).groupby(d["date"]).sum()
    return day


# =============================================================================
# [2] 모델 / 범위 산출 — task2_interval.py 와 같은 순서로 2025·2026 예측 재현
# =============================================================================
def 예측_재현(d, f):
    lg_cal = T.lgbm_분위수(f, T.TRAIN_END, T.CAL_START, T.CAL_END)
    lg_test = T.lgbm_분위수(f, T.CAL_END, T.TEST_START, T.TEST_END)
    cache = os.path.join(T.RES_DIR, "chronos_preds.csv")
    if not os.path.exists(cache):
        raise SystemExit("[중단] results/chronos_preds.csv 없음 → task2_interval.py 를 먼저 실행")
    ch = pd.read_csv(cache, encoding="utf-8-sig")
    ch["date"] = ch["date"].astype(str).str[:10]

    def 합치기(lg, start, end):
        b = f[(f["date"] >= start) & (f["date"] <= end)][["date", "hour_n", "smp_land", "naive", "offday"]]
        b = b.rename(columns={"smp_land": "y"}).merge(
            lg.rename(columns={c: f"lgb_{c}" for c in ("q10", "q50", "q90")}), on=["date", "hour_n"])
        for mode in ("cov", "uni"):
            c = ch[ch["mode"] == mode].drop(columns="mode")
            b = b.merge(c.rename(columns={q: f"chr_{mode}_{q}" for q in ("q10", "q50", "q90")}),
                        on=["date", "hour_n"], how="left")
        b["group"] = b["hour_n"].astype(str).str.zfill(2) + "시_" + np.where(b["offday"] == 1, "휴일", "평일")
        return b.reset_index(drop=True)

    cal = 합치기(lg_cal, T.CAL_START, T.CAL_END)
    test = 합치기(lg_test, T.TEST_START, T.TEST_END)
    cal_fit = cal.dropna(subset=["y"]).reset_index(drop=True)
    cal_fit["err"] = cal_fit["y"] - cal_fit["lgb_q50"]
    err_q = cal_fit.groupby("group")["err"].quantile([0.1, 0.5, 0.9]).unstack()
    err_q.columns = ["오차_10%", "오차_50%", "오차_90%"]
    names = ["lgb", "chr_cov", "chr_uni"]
    W = T.앙상블_가중치(cal_fit, names)

    def 앙상블(b):
        out = {}
        for _, r in W.iterrows():
            out[r["분위수"]] = sum(r[n] * b[f"{n}_{r['분위수']}"].values for n in names)
        return T.정리(out["q10"], out["q50"], out["q90"])

    eL, _, eU = 앙상블(cal_fit)
    C = T.등각_보정값(cal_fit, eL, eU, cal_fit["group"].values)

    def 모든_방법(b):
        g = b["group"]
        lo, hi = g.map(err_q["오차_10%"]).values, g.map(err_q["오차_90%"]).values
        m = b["lgb_q50"].values
        res = {"A_잔차분위수": T.정리(m + lo, m, m + hi),
               "B_LightGBM분위수": T.정리(b["lgb_q10"].values, m, b["lgb_q90"].values),
               "C_Chronos2_수요예측": T.정리(b["chr_cov_q10"].values, b["chr_cov_q50"].values, b["chr_cov_q90"].values),
               "D_Chronos2_단변량": T.정리(b["chr_uni_q10"].values, b["chr_uni_q50"].values, b["chr_uni_q90"].values)}
        L, M, U = 앙상블(b)
        res["E_앙상블"] = (L, M, U)
        res[FINAL] = T.정리(L - g.map(C["하한_보정"]).values, M, U + g.map(C["상한_보정"]).values)
        return res

    out = {}
    for tag, b in (("보정 2025", cal), ("시험 2026", test)):
        p = b[["date", "hour_n", "y", "naive"]].copy()
        for k, (L, M, U) in 모든_방법(b).items():
            p[f"{k}|L"], p[f"{k}|M"], p[f"{k}|U"] = L, M, U
        out[tag] = p
    return out


def 재현_확인(test_pred):
    """시험 구간 예측이 저장된 04 결과와 같은지 확인(다르면 중단)"""
    old = pd.read_csv(os.path.join(T.RES_DIR, "04_시험구간_예측범위.csv"), encoding="utf-8-sig")
    gap = 0.0
    for k in METHODS:
        for s, c in (("L", "하한"), ("M", "중앙"), ("U", "상한")):
            gap = max(gap, float(np.nanmax(np.abs(test_pred[f"{k}|{s}"].values - old[f"{k}_{c}"].values))))
    if gap > 1e-6:
        raise SystemExit(f"[중단] 시험 구간 예측이 04 결과와 다름(최대 차이 {gap:.4f}원)")
    print(f"  · 재현 확인 : 시험 구간 6개 방법 예측이 04 결과와 일치 (최대 차이 {gap:.1e}원)")


# =============================================================================
# [4] 평가 함수
# =============================================================================
def 지표(y, L, M, U, naive):
    ok = ~np.isnan(y)
    y, L, M, U, naive = y[ok], L[ok], M[ok], U[ok], naive[ok]
    if len(y) == 0:
        return {}
    base = T.평가(y, L, M, U, naive)
    den = np.maximum(y, MAPE_FLOOR)
    base["rMAE"] = base["MAE(중앙값)"] / base["MAE(어제같은시각)"]
    base["MAPE(%)"] = float(np.mean(np.abs(M - y) / den) * 100)
    base["편의(%)"] = float(np.mean((M - y) / den) * 100)
    return base


def 비교표(preds, day):
    """기간 × 방법 × (급등일/일반일) 시간 단위 지표"""
    rows = []
    for tag, p in preds.items():
        sp = p["date"].map(day["spike"]).fillna(False).values
        for k in METHODS:
            for name, m in (("급등일", sp), ("일반일", ~sp)):
                e = 지표(p["y"].values[m], p[f"{k}|L"].values[m], p[f"{k}|M"].values[m],
                       p[f"{k}|U"].values[m], p["naive"].values[m])
                rows.append({"기간": tag, "방법": k, "구분": name, "일수": int(p.loc[m, "date"].nunique()), **e})
    return pd.DataFrame(rows)


def 피크_분석(preds, day, k=FINAL):
    """날마다 실제 최고가 vs 예측 최고가, 피크 시각의 범위 적중, D-1 탐지 신호"""
    rows = []
    for tag, p in preds.items():
        for dt, g in p.groupby("date"):
            g = g.dropna(subset=["y"])
            if len(g) < 20:
                continue
            ip = g["y"].idxmax()
            r = day.loc[dt]
            M, U, L = g[f"{k}|M"], g[f"{k}|U"], g[f"{k}|L"]
            inside = (g["y"] >= L) & (g["y"] <= U)
            rows.append({
                "기간": tag, "date": dt, "급등일": bool(r["spike"]), "기준_28일중앙(원)": r["ref"],
                "실제_최고(원)": g.loc[ip, "y"], "실제_배율": g.loc[ip, "y"] / r["ref"], "실제_피크시": int(g.loc[ip, "hour_n"]),
                "예측중앙_최고(원)": M.max(), "예측상한_최고(원)": U.max(),
                "예측중앙_피크시": int(g.loc[M.idxmax(), "hour_n"]),
                "피크시_범위적중": bool(inside.loc[ip]), "피크시_상한(원)": U.loc[ip],
                "피크시_부족분(원)": max(0.0, g.loc[ip, "y"] - U.loc[ip]),
                "하루_커버리지(%)": inside.mean() * 100, "하루_MAE(원)": (g["y"] - M).abs().mean(),
                "D-1신호_중앙": M.max() >= SPIKE_RATIO * r["ref"],
                "D-1신호_상한": U.max() >= SPIKE_RATIO * r["ref"],
            })
    return pd.DataFrame(rows)


def 피크_요약(pk):
    rows = []
    for (tag, sp), g in pk.groupby(["기간", "급등일"]):
        rows.append({
            "기간": tag, "구분": "급등일" if sp else "일반일", "일수": len(g),
            "실제_최고_평균(원)": g["실제_최고(원)"].mean(),
            "예측중앙_최고_평균(원)": g["예측중앙_최고(원)"].mean(),
            "예측상한_최고_평균(원)": g["예측상한_최고(원)"].mean(),
            "최고가_과소예측_평균(원)": (g["실제_최고(원)"] - g["예측중앙_최고(원)"]).mean(),
            "피크시_범위적중(%)": g["피크시_범위적중"].mean() * 100,
            "피크시_부족분_평균(원)": g["피크시_부족분(원)"].mean(),
            "피크시각_일치(±1시간,%)": ((g["실제_피크시"] - g["예측중앙_피크시"]).abs() <= 1).mean() * 100,
            "D-1신호_중앙(%)": g["D-1신호_중앙"].mean() * 100,
            "D-1신호_상한(%)": g["D-1신호_상한"].mean() * 100,
        })
    return pd.DataFrame(rows)


def 시간대_모양(preds, day, k=FINAL):
    """급등일·일반일의 시간대별 평균 실제가 / 예측 중앙 / 하한 / 상한 (시험·보정 합산)"""
    p = pd.concat(preds.values(), ignore_index=True).dropna(subset=["y"])
    p["구분"] = np.where(p["date"].map(day["spike"]).fillna(False), "급등일", "일반일")
    g = p.groupby(["구분", "hour_n"]).agg(실제=("y", "mean"), 중앙=(f"{k}|M", "mean"),
                                         하한=(f"{k}|L", "mean"), 상한=(f"{k}|U", "mean"))
    return g.reset_index()


def 그래프(cmp_, pk, shape, day):
    # (6) 급등일 vs 일반일 — 최종 모델, 두 기간
    #     하루 전체 지표(왼쪽)는 비슷하지만, 최고가 시간(가운데·오른쪽)에서 차이가 드러남
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    f = cmp_[cmp_["방법"] == FINAL]
    ps = 피크_요약(pk).set_index(["기간", "구분"])
    cats = ["보정 2025", "시험 2026"]
    x = np.arange(len(cats))
    for ax, col, title, unit in ((axes[0], "PICP(%)", "하루 전체 시간 적중률", "%"),
                                 (axes[1], "피크시_범위적중(%)", "최고가 시간 적중률", "%"),
                                 (axes[2], "피크시_부족분_평균(원)", "최고가 시간에 상한을 넘은 폭", "원")):
        for j, (name, c) in enumerate((("일반일", C_GRAY), ("급등일", T.C_ORANGE))):
            if col == "PICP(%)":
                v = [f[(f["기간"] == t) & (f["구분"] == name)][col].iloc[0] for t in cats]
            else:
                v = [ps.loc[(t, name), col] for t in cats]
            bars = ax.bar(x + (j - 0.5) * 0.36, v, 0.34, color=c, label=name)
            for b_, vv in zip(bars, v):
                ax.text(b_.get_x() + b_.get_width() / 2, vv, f"{vv:.1f}", ha="center", va="bottom",
                        fontsize=9, color=T.INK2)
        if col == "PICP(%)":
            ax.axhspan(75, 85, color=T.C_AQUA, alpha=0.12, lw=0)
        ax.set_xticks(x, [f"{t}\n(급등 {int(f[(f['기간'] == t) & (f['구분'] == '급등일')]['일수'].iloc[0])}일)" for t in cats])
        ax.set_title(f"{title} ({unit})", loc="left", fontsize=11, color=T.INK)
        T.스타일(ax)
    axes[0].legend(frameon=False, fontsize=9, loc="lower left")
    fig.suptitle("⑥ 급등일 vs 일반일 — 하루 전체로는 비슷하지만 최고가 1시간은 한 번도 못 잡음 (최종 모델)",
                 x=0.01, ha="left", color=T.INK)
    fig.tight_layout()
    fig.savefig(os.path.join(T.PLOT_DIR, "06_급등일_일반일_비교.png"), dpi=150)
    plt.close(fig)

    # (7) 시간대별 평균 모양 — 급등일 vs 일반일
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.4), sharey=True)
    for ax, name in zip(axes, ("일반일", "급등일")):
        s = shape[shape["구분"] == name]
        ax.fill_between(s["hour_n"], s["하한"], s["상한"], color=T.C_BLUE, alpha=0.15, lw=0, label="80% 범위(평균)")
        ax.plot(s["hour_n"], s["중앙"], color=T.C_BLUE, lw=2, ls="--", label="예측 중앙값(평균)")
        ax.plot(s["hour_n"], s["실제"], color=T.INK, lw=2, label="실제 SMP(평균)")
        ax.set_title(f"{name} — 시간대별 평균", loc="left", fontsize=11, color=T.INK)
        ax.set_xticks(range(1, 25, 3))
        ax.set_xlabel("시")
        T.스타일(ax)
    axes[0].set_ylabel("원/kWh")
    axes[0].legend(frameon=False, fontsize=9)
    fig.suptitle("⑦ 급등일에는 단 1시간(주로 오전 10시)이 범위 위로 솟음 (2025·2026 합산, 급등일 13일)",
                 x=0.01, ha="left", color=T.INK)
    fig.tight_layout()
    fig.savefig(os.path.join(T.PLOT_DIR, "07_급등일_시간대별_모양.png"), dpi=150)
    plt.close(fig)

    # (8) 59일의 분포 — 월 · 피크 시각
    sp = day[day["spike"]]
    fig, axes = plt.subplots(1, 2, figsize=(14, 3.8))
    m = sp.index.to_series().str[5:7].astype(int).value_counts().reindex(range(1, 13), fill_value=0)
    axes[0].bar(m.index, m.values, color=T.C_BLUE)
    axes[0].set_xticks(range(1, 13), [f"{i}월" for i in range(1, 13)])
    axes[0].set_title(f"월별 급등일 수 (2021~, 총 {len(sp)}일)", loc="left", fontsize=11, color=T.INK)
    h = sp["peak_hour"].value_counts().reindex(range(1, 25), fill_value=0)
    axes[1].bar(h.index, h.values, color=T.C_ORANGE)
    axes[1].set_xticks(range(1, 25, 2))
    axes[1].set_title("급등일의 최고가 시각", loc="left", fontsize=11, color=T.INK)
    for ax in axes:
        T.스타일(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(T.PLOT_DIR, "08_급등일_월_시각_분포.png"), dpi=150)
    plt.close(fig)


def main():
    print("=" * 70 + "\n[1] 데이터 준비\n" + "=" * 70)
    d, f = T.데이터_준비()
    day = 급등일_표(d)
    sp = day[day["spike"]]
    print(f"  · 급등일(최고가 ≥ 직전 28일 일 최고가 중앙값 × {SPIKE_RATIO}) : 2021년 이후 {len(sp)}일")
    print("    연도별 " + ", ".join(f"{y}년 {n}일" for y, n in sp.index.str[:4].value_counts().sort_index().items()))
    lst = sp[["day_max", "ref", "ratio", "peak_hour", "hot_hours"]].copy()
    lst["기간"] = np.select([lst.index < "2025-01-01", lst.index <= "2025-12-31", lst.index <= "2026-09-30"],
                          ["학습", "보정 2025", "시험 2026"], "시험 이후")
    lst["요일"] = pd.to_datetime(lst.index).dayofweek.map(dict(enumerate("월화수목금토일")))
    lst.round(3).rename(columns={"day_max": "최고SMP", "ref": "기준_28일중앙", "ratio": "배율",
                                 "peak_hour": "피크시", "hot_hours": "기준초과_시간수"}).to_csv(
        os.path.join(T.RES_DIR, "09_급등일_목록.csv"), encoding="utf-8-sig")

    print("=" * 70 + "\n[2] 모델 / 범위 산출 (2025·2026 예측 재현)\n" + "=" * 70)
    preds = 예측_재현(d, f)
    재현_확인(preds["시험 2026"])

    print("=" * 70 + "\n[3] 예측 — 급등일 / 일반일로 나눔\n" + "=" * 70)
    for tag, p in preds.items():
        ds = p["date"].unique()
        n_sp = int(day.loc[ds, "spike"].sum())
        print(f"  · {tag} : {len(ds)}일 중 급등일 {n_sp}일 — {', '.join(day.loc[ds][day.loc[ds, 'spike']].index)}")

    print("=" * 70 + "\n[4] 평가 · 시각화\n" + "=" * 70)
    cmp_ = 비교표(preds, day)
    cmp_.round(3).to_csv(os.path.join(T.RES_DIR, "10_급등일_일반일_비교.csv"), index=False, encoding="utf-8-sig")
    cols = ["일수", "n", "PICP(%)", "MPIW(원)", "Winkler", "하한아래(%)", "상한위(%)", "MAE(중앙값)",
            "rMAE", "MAPE(%)", "편의(%)"]
    pd.set_option("display.width", 220)
    for tag in preds:
        print(f"\n■ {tag} — 시간 단위 지표")
        print(cmp_[cmp_["기간"] == tag].set_index(["방법", "구분"])[cols].round(2).to_string())

    pk = 피크_분석(preds, day)
    pk.round(2).to_csv(os.path.join(T.RES_DIR, "11_일별_피크_최종모델.csv"), index=False, encoding="utf-8-sig")
    ps = 피크_요약(pk)
    ps.round(2).to_csv(os.path.join(T.RES_DIR, "12_피크_D-1탐지_요약.csv"), index=False, encoding="utf-8-sig")
    print("\n■ 하루 최고가(피크)와 D-1 탐지 — 최종 모델")
    print(ps.round(1).to_string(index=False))
    print("\n■ 급등일별 상세 — 최종 모델")
    print(pk[pk["급등일"]].drop(columns=["급등일"]).round(1).to_string(index=False))

    shape = 시간대_모양(preds, day)
    shape.round(2).to_csv(os.path.join(T.RES_DIR, "13_급등일_시간대별_모양.csv"), index=False, encoding="utf-8-sig")
    그래프(cmp_, pk, shape, day)
    print(f"\n  · 결과 CSV : results/09~13  그래프 : plots/06~08")


if __name__ == "__main__":
    main()
