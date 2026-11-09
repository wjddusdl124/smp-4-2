# -*- coding: utf-8 -*-
"""combined.py — 방향 넓히기(G1) + 위험 시각 상한 확대를 함께 적용한 최종 결과 (2026, 설정은 모두 2025에서 결정)"""
import numpy as np, pandas as pd, hour_ranges as H, day_features as DF
P = pd.read_pickle('results/_spike_level.pkl'); R = P['R']; spk = P['spk']
d, g = DF.만들기()
X = 67.8; KU, KD = 2.0, 1.7
c = R['2025']; ch = c.y - c.naive; lo, hi = np.nanquantile(ch, .05), np.nanquantile(ch, .95)
rows = []
for name, hours in [('기존 F', None), ('G1 방향 넓히기', []), ('G1 + 10·16시', [10, 16]), ('G1 + 10·11·15·16시', [10, 11, 15, 16]), ('10·11·15·16시만', 'only')]:
    b = R['2026']; L, M, U = b.L.values, b.M.values, b.U.values
    if hours is None: L2, U2 = L, U
    elif hours == 'only':
        m = ((b.date.map(g.offday) == 0) & b.hour_n.isin([10, 11, 15, 16])).values; L2, U2 = L, np.where(m, U + X, U)
    else:
        L2, _, U2 = H.방향_넓히기(L, M, U, b.naive.values, KU, KD)
        if hours:
            m = ((b.date.map(g.offday) == 0) & b.hour_n.isin(hours)).values; U2 = np.where(m, np.maximum(U2, U + X), U2)
    y = b.y.values; ok = ~np.isnan(y); chg = y - b.naive.values
    up, dn = (chg >= hi) & ok, (chg <= lo) & ok
    s = b.assign(U2=U2, L2=L2)
    pk = s[s.date.isin(spk)].sort_values('y').groupby('date').tail(1)
    dr = g.index[(g['drop'] == 1)]
    mn = s[s.date.isin(dr)].sort_values('y').groupby('date').head(1)
    rows.append({'방법': name, '전체 커버리지(%)': round(100 * np.mean(((y >= L2) & (y <= U2))[ok]), 1), '평균 폭(원)': round(float(np.mean((U2 - L2)[ok])), 2),
                 '급등 시간 놓침(%)': round(100 * np.mean(y[up] > U2[up]), 1), '급락 시간 놓침(%)': round(100 * np.mean(y[dn] < L2[dn]), 1),
                 '급등일 최고가 포함': f"{int((pk.y <= pk.U2).sum())}/{len(pk)}", '급락일 최저가 포함': f"{int((mn.y >= mn.L2).sum())}/{len(mn)}"})
r = pd.DataFrame(rows); r.to_csv('results/33_최종결합_2026.csv', index=False, encoding='utf-8-sig')
pd.set_option('display.width', 200); print(r.to_string(index=False))
