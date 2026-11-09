# -*- coding: utf-8 -*-
"""
peak_risk.py — 급등 대응 실험 ①② : 위험 시각과 상한 높이를 데이터로 정하기
==============================================================================
기준 모델 F (앙상블 + 등각 보정) 의 상한을 「평일 위험 시각」에서만 올린다. 하한·다른 시각은 그대로.

위험 시각 (어느 시각을 올릴까)
  H0  고정 10시·16시 (기존 상시 확대와 같음)
  H1  그날 수요예측이 가장 높은 시각 1개      ← ② (D-1 공표 수요예측으로 앎)
  H2  그날 수요예측 상위 2개 시각
  H3  그날 수요예측 상위 3개 시각

상한 높이 (얼마나 올릴까)
  L0  F 상한 + X원 (X = 2025 급등일 위험 시각 피크의 최대 초과폭) — 기존 방식
  L1  max(F 상한, 직전 급등 최고가 + m)   ← ① 직전 60일 안 급등이 없으면 max(F 상한, 기준×1.25 + m)
  L2  max(F 상한, 기준×1.25 + m)          (기준 = 직전 28일 일 최고가 중앙값, 급등 판정선)
  m 은 2025 급등일 피크(위험 시각에 걸린 날)를 모두 덮는 가장 작은 값(0~80원, 1원 간격)

규칙: 시각·높이·m 은 2025 에서만 정하고 2026.1~9 에 1회 적용. 입력은 모두 D-1 에 알 수 있는 값.
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hour_ranges as H, task2_interval as T, day_features as DF

W = {"q10": (0.15, 0.85, 0), "q50": (0.15, 0.8, 0.05), "q90": (0.25, 0.75, 0)}


def 준비():
    d, g = DF.만들기()
    cal, test = H.구성요소()
    cf = cal.dropna(subset=["y"]).reset_index(drop=True)
    Lc, Mc, Uc = H.앙상블(cf, W); C = T.등각_보정값(cf, Lc, Uc, cf.group.values)

    def F(b):
        L, M, U = H.앙상블(b, W); gg = b.group
        L, M, U = T.정리(L - gg.map(C["하한_보정"]).values, M, U + gg.map(C["상한_보정"]).values)
        return b.assign(L=L, M=M, U=U)
    # D-1 에 아는 값: 수요예측 순위, 기준선, 직전 급등 최고가(60일 내)
    Fc = d.pivot(index="date", columns="hour_n", values="demand_fcst_land")
    rank = Fc.rank(axis=1, ascending=False, method="first").stack().rename("frank").reset_index()
    sp = g["spike"].fillna(0)
    last = pd.Series(np.where(sp == 1, g["day_max"], np.nan), index=g.index).shift(1)
    lastd = pd.Series(np.where(sp == 1, np.arange(len(g)), np.nan), index=g.index).shift(1)
    last = last.ffill(); lastd = lastd.ffill()
    age = np.arange(len(g)) - lastd
    info = pd.DataFrame({"ref_max": g["ref_max"], "last_spike": last.where(age <= 60),
                         "off_d": g["offday"], "spike": g["spike"], "day_max": g["day_max"]})
    out = []
    for b in (cal, test):
        x = F(b).merge(rank, on=["date", "hour_n"], how="left").merge(info, left_on="date", right_index=True, how="left")
        out.append(x)
    return out


def 위험(x, hs):
    wk = x["off_d"] == 0
    if hs == "H0":
        return wk & x["hour_n"].isin([10, 16])
    k = {"H1": 1, "H2": 2, "H3": 3}[hs]
    return wk & (x["frank"] <= k)


def 새상한(x, mask, lv, val):
    U = x["U"].values.copy()
    if lv == "L0":
        U2 = U + val
    elif lv == "L1":
        base = x["last_spike"].fillna(x["ref_max"] * 1.25).values
        U2 = np.maximum(U, base + val)
    else:
        U2 = np.maximum(U, x["ref_max"].values * 1.25 + val)
    return np.where(mask, U2, U)


def 피크(x):
    s = x[x["spike"] == 1]
    return s.loc[s.groupby("date")["y"].idxmax()]


def 평가(x, U2):
    ok = x["y"].notna()
    pk = 피크(x); u = pd.Series(U2, index=x.index)
    return {"급등일 피크 포함": f"{int((pk.y <= u[pk.index]).sum())}/{len(pk)}",
            "_hit": int((pk.y <= u[pk.index]).sum()),
            "평균 폭(원)": round(float((U2 - x["L"])[ok].mean()), 2),
            "올린 시간 수": int((U2 > x["U"].values + 1e-9).sum())}


def main():
    cal, test = 준비()
    rows = []
    for hs in ("H0", "H1", "H2", "H3"):
        for lv in ("L0", "L1", "L2"):
            m = 위험(cal, hs); pk = 피크(cal); inm = m[pk.index]
            if lv == "L0":
                gap = (pk.y - pk.U)[inm]
                val = max(0.0, float(gap.max())) if len(gap) else 0.0
            else:
                val = 80.0
                for v in range(0, 81):
                    u = 새상한(cal, m, lv, v)
                    if all(pk.y[inm] <= pd.Series(u, index=cal.index)[pk.index][inm]):
                        val = float(v); break
            r25 = 평가(cal, 새상한(cal, m, lv, val)); r26 = 평가(test, 새상한(test, 위험(test, hs), lv, val))
            rows.append({"위험 시각": hs, "상한 높이": lv, "값(원)": val,
                         "2025 피크 포함": r25["급등일 피크 포함"], "2025 평균 폭": r25["평균 폭(원)"],
                         "2026 피크 포함": r26["급등일 피크 포함"], "2026 평균 폭": r26["평균 폭(원)"], "2026 올린 시간": r26["올린 시간 수"],
                         "_s25": r25["_hit"], "_w25": r25["평균 폭(원)"]})
    base25 = 평가(cal, cal["U"].values); base26 = 평가(test, test["U"].values)
    R = pd.DataFrame(rows)
    print(f"기준 F : 2025 피크 {base25['급등일 피크 포함']} 폭 {base25['평균 폭(원)']} / 2026 피크 {base26['급등일 피크 포함']} 폭 {base26['평균 폭(원)']}")
    pd.set_option("display.width", 220)
    print(R.drop(columns=["_s25", "_w25"]).to_string(index=False))
    # 2025 에서 선택: 피크 포함 최대 → 평균 폭 최소
    best = R.sort_values(["_s25", "_w25"], ascending=[False, True]).iloc[0]
    print("\n2025 기준 선택 :", best["위험 시각"], best["상한 높이"], best["값(원)"])
    R.drop(columns=["_s25", "_w25"]).to_csv(os.path.join(HERE, "results", "32_급등_위험시각_실험.csv"), index=False, encoding="utf-8-sig")
    # 2025 피크 시각 순위 정보
    pk = 피크(cal); print("2025 급등일 피크 시각·수요예측 순위:", pk[["date", "hour_n", "frank"]].values.tolist())
    pk = 피크(test); print("2026 급등일 피크 시각·수요예측 순위:", pk[["date", "hour_n", "frank", "last_spike", "ref_max"]].round(1).values.tolist())


if __name__ == "__main__":
    main()
