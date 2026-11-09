# -*- coding: utf-8 -*-
"""
spike_level.py — 급등 대응 2차: 「어느 시각에」 「얼마까지」 상한을 올릴까
==============================================================================
급등일 정의 (프로젝트 기준, day_features 와 같음)
  그날 최고 SMP ≥ 직전 28일 일 최고 SMP 중앙값 × 1.25  → 2021년 이후 59일

기본 범위 = 기존 최종 모델 F (LightGBM·Chronos-2 앙상블 + 등각 보정, 비율 그대로)
비교하는 상한 올리기 (평일에만, D-1 에 알 수 있는 값만 사용)
  시각 : ① 고정 10시·16시  ② 수요예측 1위 시각  ③ 수요예측 상위 2개 시각  ④ 상위 3개 시각
  높이 : (가) 상한 + 고정폭 X   (나) 「급등 가격 수준」까지 = max(상한, 수준 + 여유)
         수준 = 직전 급등일 최고가 / 최근 3번 급등 최고가 중 최댓값 / 최근 365일 급등 최고가 최댓값
         (D-1 까지 확정된 급등일만 사용)
선택 규칙 (2025년에서만)
  2025 급등일 최고가를 가장 많이 범위에 담는 설정 → 같으면 평균 폭이 가장 좁은 설정
  고정폭 X 와 여유는 2025 에서 정함. 2026.1~9 에는 1회 적용
"""
import itertools, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hour_ranges as H, task2_interval as T, day_features as DF

W = {"q10": (0.15, 0.85, 0), "q50": (0.15, 0.8, 0.05), "q90": (0.25, 0.75, 0)}   # 기존 앙상블 비율
OUT = os.path.join(HERE, "results")


def 기본범위():
    cal, test = H.구성요소()
    cf = cal.dropna(subset=["y"]).reset_index(drop=True)
    Lc, Mc, Uc = H.앙상블(cf, W); C = T.등각_보정값(cf, Lc, Uc, cf.group.values)
    out = {}
    for tag, b in (("2025", cal), ("2026", test)):
        L, M, U = H.앙상블(b, W); gg = b.group
        L, M, U = T.정리(L - gg.map(C["하한_보정"]).values, M, U + gg.map(C["상한_보정"]).values)
        out[tag] = b.assign(L=L, M=M, U=U).reset_index(drop=True)
    return out


def main():
    d, g = DF.만들기()
    F = d.pivot(index="date", columns="hour_n", values="demand_fcst_land")
    rank = F.rank(axis=1, ascending=False, method="first")
    Y = d.pivot(index="date", columns="hour_n", values="smp_land")
    spk = g.index[g["spike"] == 1]
    peak = Y.max(axis=1)
    # D-1 까지 확정된 급등 가격 수준
    lv = {}
    for x in g.index:
        prev = [s for s in spk if s < x]
        lv[x] = {"직전 급등": peak[prev[-1]] if prev else np.nan,
                 "최근 3번 최대": peak[prev[-3:]].max() if prev else np.nan,
                 "최근 365일 최대": peak[[s for s in prev if (pd.Timestamp(x) - pd.Timestamp(s)).days <= 365]].max() if prev else np.nan}
    R = 기본범위()
    hour_sets = {"고정 10·16시": None, "수요 1위 시각": 1, "수요 상위 2개": 2, "수요 상위 3개": 3}

    def 대상(b, hs):
        wk = (b["date"].map(g["offday"]) == 0).values
        if hours_key(hs) is None:
            return wk & b["hour_n"].isin([10, 16]).values
        r = np.array([rank.at[x, h] if x in rank.index else np.nan for x, h in zip(b["date"], b["hour_n"])])
        return wk & (r <= hs)

    def hours_key(hs): return hs

    def 평가(b, U2):
        ok = b["y"].notna().values
        sp = b[b["date"].isin(spk)].copy(); sp["U2"] = U2[sp.index]
        pk = sp.sort_values("y").groupby("date").tail(1)
        return {"급등일 최고가 포함": int((pk["y"] <= pk["U2"]).sum()), "급등일 수": len(pk),
                "평균 폭(원)": round(float(np.mean((U2 - b["L"].values)[ok])), 2),
                "_pk": pk}

    rows = []
    masks = {tag: {hn: 대상(R[tag], hs) for hn, hs in hour_sets.items()} for tag in R}
    for hn in hour_sets:
        # (가) 고정폭 : 2025 급등일 중 대상 시각 피크의 상한 부족분 최댓값
        b = R["2025"]; m = masks["2025"][hn]
        sp = b[b["date"].isin(spk) & m]
        X = max(0.0, float((sp["y"] - sp["U"]).max())) if len(sp) else 0.0
        for tag in R:
            b = R[tag]; U2 = np.where(masks[tag][hn], b["U"] + X, b["U"])
            e = 평가(b, U2); rows.append({"시각": hn, "높이": f"상한 +{X:.1f}원", "기간": tag, **{k: v for k, v in e.items() if k != "_pk"}})
        # (나) 급등 가격 수준
        for lname, marg in itertools.product(["직전 급등", "최근 3번 최대", "최근 365일 최대"], [0, 5, 10, 15, 20]):
            for tag in R:
                b = R[tag]
                level = np.array([lv[x][lname] for x in b["date"]]) + marg
                U2 = np.where(masks[tag][hn] & ~np.isnan(level), np.maximum(b["U"].values, np.nan_to_num(level)), b["U"].values)
                e = 평가(b, U2); rows.append({"시각": hn, "높이": f"{lname} +{marg}원", "기간": tag, **{k: v for k, v in e.items() if k != "_pk"}})
    res = pd.DataFrame(rows)
    p = res.pivot_table(index=["시각", "높이"], columns="기간", values=["급등일 최고가 포함", "평균 폭(원)"]).reset_index()
    p.columns = ["시각", "높이", "2025 포함", "2026 포함", "2025 폭", "2026 폭"]
    p = p.sort_values(["2025 포함", "2025 폭"], ascending=[False, True])
    p.to_csv(os.path.join(OUT, "32_급등_수준_시각_비교.csv"), index=False, encoding="utf-8-sig")
    base = {t: round(float(np.mean((R[t]["U"] - R[t]["L"])[R[t]["y"].notna()])), 2) for t in R}
    print("기본 모델 평균 폭", base, "/ 2025 급등일", int(g.loc["2025-01-01":"2025-12-31", "spike"].sum()), "2026", int(g.loc["2026-01-01":"2026-09-30", "spike"].sum()))
    pd.set_option("display.width", 200)
    print(p.head(15).to_string(index=False))
    print("...\n고정폭 행:"); print(p[p["높이"].str.startswith("상한")].to_string(index=False))
    best = p.iloc[0]; print("\n→ 2025 규칙으로 선택:", best["시각"], best["높이"])
    pd.to_pickle({"R": R, "lv": lv, "masks": masks, "spk": list(spk), "best": best}, os.path.join(OUT, "_spike_level.pkl"))


if __name__ == "__main__":
    main()
