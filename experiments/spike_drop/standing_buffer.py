# -*- coding: utf-8 -*-
"""standing_buffer.py — 「평일 위험 시간대」 상한 상시 확대
  · 위험 시간대 = 2023~2025 급등일 최고가 시각 상위 2개 (10시·16시)
  · 확대폭 X = 2025 급등일 중 그 시간대 피크가 상한을 넘은 최대 폭 (2025에서만 결정)
  · 2026.1~9 에 1회 적용
"""
import numpy as np, pandas as pd, hour_ranges as H, task2_interval as T, day_features as DF
d, g = DF.만들기()
Y = d.pivot(index="date", columns="hour_n", values="smp_land")
pk = Y.fillna(-1).idxmax(axis=1)
sd = g[(g.spike == 1) & (g.index >= "2023-01-01") & (g.index <= "2025-12-31")].index
hours = pk[sd].value_counts().index[:2].tolist()
cal, test = H.구성요소()
W = {"q10": (0.15, 0.85, 0), "q50": (0.15, 0.8, 0.05), "q90": (0.25, 0.75, 0)}
cf = cal.dropna(subset=["y"]).reset_index(drop=True)
Lc, Mc, Uc = H.앙상블(cf, W); C = T.등각_보정값(cf, Lc, Uc, cf.group.values)
def bo(b):
    L, M, U = H.앙상블(b, W); gg = b.group
    return T.정리(L - gg.map(C["하한_보정"]).values, M, U + gg.map(C["상한_보정"]).values)
L, M, U = bo(cal); c = cal.assign(L=L, U=U)
X = max(0, c[c.date.isin(g[g.spike == 1].index) & c.hour_n.isin(hours)].eval("y-U").max())
L, M, U = bo(test); t = test.assign(L=L, U=U); t["wk"] = t.date.map(g.offday) == 0
m = t.hour_n.isin(hours) & t.wk; t["U2"] = np.where(m, t.U + X, t.U)
sp = t[t.date.isin(g[g.spike == 1].index)].sort_values("y").groupby("date").tail(1)
ok = t.y.notna()
print(f"위험 시간대 {hours} · 확대폭 {X:.1f}원 · 대상 {int(m.sum())}시간")
print(f"2026 급등일 최고가 포함 {int((sp.y <= sp.U2).sum())}/{len(sp)} (기존 {int((sp.y <= sp.U).sum())}/{len(sp)})")
print(f"평균 폭 {(t.U - t.L)[ok].mean():.2f} → {(t.U2 - t.L)[ok].mean():.2f}원")
print(sp[["date", "hour_n", "y", "U", "U2"]].round(1).to_string(index=False))
