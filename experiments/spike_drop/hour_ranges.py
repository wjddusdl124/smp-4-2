# -*- coding: utf-8 -*-
"""
hour_ranges.py — 급등·급락 「시간」을 놓치지 않는 예측 범위
==============================================================================
급등·급락 시간 (task2 와 같은 정의)
  · 어제 같은 시각 대비 변화가 2025년 분포 상위 5% 이상 → 급등, 하위 5% 이하 → 급락

비교 (모든 설정값은 2025년에서만 정하고 2026.1~9 에 1회 적용)
  F  현재 최종 모델 (앙상블 + 등각 보정)
  G1 F + 「예측 방향 쪽만 넓히기」
       중앙값이 어제보다 높으면 상한만, 낮으면 하한만 k 배 넓힘
       k 는 2025년 급등(급락) 시간 놓침이 15% 이하가 되는 가장 작은 값
  G2 급변 중심 앙상블 가중치 (급등·급락 시간 pinball 에 5배 가중) + 등각 보정 + G1 방식
  G3 G1 + 급락일 경보 날 한낮(10~16시) 하한을 0원까지 내림 (day_alarm 의 ① 운영 모델)
"""
import itertools
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
T2 = os.path.join(os.path.dirname(HERE), "task2_interval")
sys.path.insert(0, T2)
sys.path.insert(0, HERE)
import task2_interval as T
import day_features as DF
import day_alarm as A

OUT = os.path.join(HERE, "results")
MISS_TARGET = 0.15
KS = np.round(np.arange(1.0, 4.01, 0.1), 2)
NAMES = ["lgb", "chr_cov", "chr_uni"]
REG_W = 5.0


def 구성요소():
    """task2 와 같은 순서로 2025(보정)·2026(시험)의 B·C·D 분위수 예측을 만든다"""
    d, f = T.데이터_준비()
    lg_cal = T.lgbm_분위수(f, T.TRAIN_END, T.CAL_START, T.CAL_END)
    lg_test = T.lgbm_분위수(f, T.CAL_END, T.TEST_START, T.TEST_END)
    ch = pd.read_csv(os.path.join(T.RES_DIR, "chronos_preds.csv"), encoding="utf-8-sig")
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

    return 합치기(lg_cal, T.CAL_START, T.CAL_END), 합치기(lg_test, T.TEST_START, T.TEST_END)


def 가중치(cal, w_row):
    """분위수별 (가중) pinball 최소 가중치 — 0.05 격자"""
    y = cal["y"].values
    steps = np.round(np.arange(0, 1.0001, 0.05), 2)
    combos = [w for w in itertools.product(steps, repeat=3) if abs(sum(w) - 1) < 1e-9]
    W = {}
    for q in T.QS:
        tag = f"q{int(q * 100)}"
        P = np.vstack([cal[f"{n}_{tag}"].values for n in NAMES])

        def loss(w):
            e = y - np.dot(w, P)
            return np.nansum(w_row * np.maximum(q * e, (q - 1) * e)) / np.nansum(w_row)
        W[tag] = min(combos, key=loss)
    return W


def 앙상블(b, W):
    out = {tag: sum(w * b[f"{n}_{tag}"].values for n, w in zip(NAMES, W[tag])) for tag in W}
    return T.정리(out["q10"], out["q50"], out["q90"])


def 방향_넓히기(L, M, U, naive, ku, kd):
    up = (M - naive) > 0
    dn = (M - naive) < 0
    U2 = np.where(up, M + ku * (U - M), U)
    L2 = np.where(dn, M - kd * (M - L), L)
    return np.clip(L2, 0, None), M, U2


def 성적(b, L, M, U, reg):
    y = b["y"].values
    ok = ~np.isnan(y)
    r = {}
    r["전체 커버리지(%)"] = 100 * np.mean(((y >= L) & (y <= U))[ok])
    r["평균 폭(원)"] = np.mean((U - L)[ok])
    for nm, m in (("급등", reg == "급등"), ("급락", reg == "급락"), ("일반", reg == "일반")):
        m = m & ok
        if nm == "급등":
            r["급등 놓침(%)"] = 100 * np.mean(y[m] > U[m])
        elif nm == "급락":
            r["급락 놓침(%)"] = 100 * np.mean(y[m] < L[m])
        else:
            r["일반 시간 폭(원)"] = np.mean((U - L)[m])
            r["일반 커버리지(%)"] = 100 * np.mean(((y >= L) & (y <= U))[m])
    r["Winkler"] = np.mean((U - L + 10 * (L - y) * (y < L) + 10 * (y - U) * (y > U))[ok])
    return r


def k_고르기(L, M, U, b, reg):
    """2025 에서 급등·급락 놓침이 MISS_TARGET 이하가 되는 가장 작은 k (상한·하한 따로)"""
    y, nv = b["y"].values, b["naive"].values
    ku = next((k for k in KS if np.nanmean(y[reg == "급등"] > 방향_넓히기(L, M, U, nv, k, 1)[2][reg == "급등"]) <= MISS_TARGET), KS[-1])
    kd = next((k for k in KS if np.nanmean(y[reg == "급락"] < 방향_넓히기(L, M, U, nv, 1, k)[0][reg == "급락"]) <= MISS_TARGET), KS[-1])
    return ku, kd


def main():
    cal, test = 구성요소()
    cal = cal.dropna(subset=["y"]).reset_index(drop=True)
    chg_c = cal["y"] - cal["naive"]
    lo_t, hi_t = np.nanquantile(chg_c, 0.05), np.nanquantile(chg_c, 0.95)
    print(f"  · 급등 ≥ +{hi_t:.1f}원, 급락 ≤ {lo_t:.1f}원 (2025년 기준)")

    def 구간(b):
        c = b["y"] - b["naive"]
        return np.where(c >= hi_t, "급등", np.where(c <= lo_t, "급락", "일반"))
    reg_c, reg_t = 구간(cal), 구간(test)

    # ---- 급락일 경보 (day_alarm ① 운영) : 2025 문턱 → 2026
    _, g = DF.만들기()
    p25, y25, _ = A.학습_예측(g, DF.OPER, "drop", "2024-12-31", "2025-01-01", "2025-12-31")
    thr = A.문턱(p25, y25, A.TARGET_RECALL)
    p26, _, _ = A.학습_예측(g, DF.OPER, "drop", "2025-12-31", "2026-01-01", A.TEST_END)
    alarm = pd.concat([p25 >= thr, p26 >= thr])

    rows, kinfo = [], {}
    for label, wrow in (("기존 가중치", np.ones(len(cal))),
                        ("급변 중심 가중치", np.where(reg_c != "일반", REG_W, 1.0))):
        W = 가중치(cal, wrow)
        kinfo[label] = {k: v for k, v in W.items()}
        Lc, Mc, Uc = 앙상블(cal, W)
        C = T.등각_보정값(cal, Lc, Uc, cal["group"].values)

        def 보정(b, L, M, U):
            gr = b["group"]
            return T.정리(L - gr.map(C["하한_보정"]).values, M, U + gr.map(C["상한_보정"]).values)
        Fc = 보정(cal, Lc, Mc, Uc)
        ku, kd = k_고르기(*Fc, cal, reg_c)
        kinfo[label]["k"] = (ku, kd)
        Ft = 보정(test, *앙상블(test, W))
        for tag, b, F, reg in (("보정 2025", cal, Fc, reg_c), ("시험 2026", test, Ft, reg_t)):
            G = 방향_넓히기(*F, b["naive"].values, ku, kd)
            mid = b["hour_n"].between(10, 16).values & b["date"].map(alarm).fillna(False).values.astype(bool)
            G3 = (np.where(mid, 0.0, G[0]), G[1], G[2])
            if label == "기존 가중치":
                rows.append({"방법": "F 현재 최종", "기간": tag, **성적(b, *F, reg)})
                rows.append({"방법": "G1 F+방향 넓히기", "기간": tag, **성적(b, *G, reg)})
                rows.append({"방법": "G3 G1+급락일 경보", "기간": tag, **성적(b, *G3, reg)})
            else:
                rows.append({"방법": "G2 급변 가중치+방향 넓히기", "기간": tag, **성적(b, *G, reg)})
                rows.append({"방법": "G4 G2+급락일 경보", "기간": tag, **성적(b, *G3, reg)})
    res = pd.DataFrame(rows).round(2)
    order = ["F 현재 최종", "G1 F+방향 넓히기", "G2 급변 가중치+방향 넓히기", "G3 G1+급락일 경보", "G4 G2+급락일 경보"]
    res["o"] = res["방법"].map({m: i for i, m in enumerate(order)})
    res = res.sort_values(["기간", "o"]).drop(columns="o")
    res.to_csv(os.path.join(OUT, "24_급변시간_범위_비교.csv"), index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    print(res.to_string(index=False))
    print("  · 가중치·k :", kinfo)
    print(f"  · 급락일 경보 문턱 {thr:.4f} / 2026 경보일 {int((p26 >= thr).sum())}일")


if __name__ == "__main__":
    main()
