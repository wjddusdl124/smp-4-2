# -*- coding: utf-8 -*-
"""spike_fuel.py — 급등 높이를 「전월 LNG 연료비단가」로 정하기
  데이터 : EPSIS 연료비용(연료비단가, 월별, 매월 초 전월치 공표) → 하루 전에 전월 값 사용 가능
  위험 시각(평일 10·11·15·16시) 상한 = max(기존 상한, k × 전월 LNG 연료비단가)
  k 는 2025 급등일 중 위험 시각 최고가를 모두 담는 최소값(0.01 간격) → 2026 에 1회 적용
  비교 : 지금 방식(상한 + 67.8원)"""
import os, numpy as np, pandas as pd, hour_ranges as H, day_features as DF
HERE = os.path.dirname(os.path.abspath(__file__)); EXT = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'data', 'external')
f = pd.read_csv(os.path.join(EXT, 'fuel_cost.csv'), encoding='utf-8-sig').set_index('ym')
lng = f['연료비단가_LNG']
P = pd.read_pickle(os.path.join(HERE, 'results', '_spike_level.pkl')); R = P['R']; spk = P['spk']
d, g = DF.만들기()
HOURS = [10, 11, 15, 16]; X = 67.8; KU, KD = 2.0, 1.7
lvl = lambda dates: np.array([lng.get((pd.Period(x[:7]) - 1).strftime('%Y-%m'), np.nan) for x in dates])
def mask(b): return ((b.date.map(g.offday) == 0) & b.hour_n.isin(HOURS)).values
c = R['2025']; mc = mask(c); L1 = lvl(c.date)
sp = c[c.date.isin(spk) & mc]; k = float(np.ceil(((sp.y / L1[sp.index]).max()) * 100) / 100)
print('2025에서 정한 k =', k)
rows = []
ch = c.y - c.naive; lo, hi = np.nanquantile(ch, .05), np.nanquantile(ch, .95)
for tag in R:
    b = R[tag]; m = mask(b); lv = lvl(b.date); ok = b.y.notna().values
    for name, U2 in [('지금: 상한 +67.8원', np.where(m, b.U + X, b.U)), (f'새: max(상한, {k}×전월 LNG 연료비단가)', np.where(m, np.maximum(b.U, k * lv), b.U))]:
        s = b.assign(U2=U2); pk = s[s.date.isin(spk)].sort_values('y').groupby('date').tail(1)
        L2, _, Ug = H.방향_넓히기(b.L.values, b.M.values, b.U.values, b.naive.values, KU, KD)
        Uc = np.where(m, np.maximum(Ug, U2), Ug); y = b.y.values; chg = y - b.naive.values; up = (chg >= hi) & ok
        rows.append({'기간': tag, '방식': name, '급등일 최고가 포함': f"{int((pk.y <= pk.U2).sum())}/{len(pk)}",
                     '평균 폭(원)': round(float(np.mean((U2 - b.L.values)[ok])), 2),
                     '위험 시각 평균 상한(원)': round(float(np.mean(U2[m & ok])), 1),
                     '모두 적용 시 평균 폭(원)': round(float(np.mean((Uc - L2)[ok])), 2),
                     '모두 적용 시 급등 시간 놓침(%)': round(100 * np.mean(y[up] > Uc[up]), 1),
                     '모두 적용 시 커버리지(%)': round(100 * np.mean(((y >= L2) & (y <= Uc))[ok]), 1)})
r = pd.DataFrame(rows); r.to_csv(os.path.join(HERE, 'results', '36_급등높이_LNG연료비.csv'), index=False, encoding='utf-8-sig')
pd.set_option('display.width', 250); print(r.to_string(index=False))
