# -*- coding: utf-8 -*-
"""spike_monthly.py — 월별 공개 데이터(연료비단가 전월, 연료원별 SMP 결정 시간 전전월)를 급등일 경보에 추가하면 나아지나
   EPSIS 공표 시점: 연료비용은 매월 초 전월치, SMP 결정 연료원은 다음 달 말 → 하루 전에 쓸 수 있는 것은 각각 전월, 전전월"""
import os, numpy as np, pandas as pd
from sklearn.metrics import average_precision_score
import spike_supply as S
HERE = os.path.dirname(os.path.abspath(__file__)); EXT = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'data', 'external')
f = pd.read_csv(os.path.join(EXT, 'fuel_cost.csv'), encoding='utf-8-sig').set_index('ym')
s = pd.read_csv(os.path.join(EXT, 'smp_fuel_set.csv'), encoding='utf-8-sig').set_index('ym')
x = S.변수()
ym = lambda k: [(pd.Period(i[:7]) - k).strftime('%Y-%m') for i in x.index]
x['lng_cost_m1'] = [f['연료비단가_LNG'].get(m) for m in ym(1)]
x['coal_cost_m1'] = [f['연료비단가_유연탄'].get(m) for m in ym(1)]
x['spread_m1'] = x['lng_cost_m1'] - x['coal_cost_m1']
x['lng_share_m2'] = [s['LNG비중'].get(m) for m in ym(2)]
x['coal_share_m2'] = [s['유연탄비중'].get(m) for m in ym(2)]
x['ref_over_lng'] = x['ref_max'] / x['lng_cost_m1']
MON = ['lng_cost_m1', 'coal_cost_m1', 'spread_m1', 'lng_share_m2', 'coal_share_m2', 'ref_over_lng']
rows = []
for tag, tr_end, a, b in (('2025', '2024-12-31', '2025-01-01', '2025-12-31'), ('2026', '2025-12-31', '2026-01-01', '2026-09-30')):
    tr = x[(x.index <= tr_end) & x.spike.notna()]; te = x[(x.index >= a) & (x.index <= b) & x.spike.notna()]; y = te.spike.values.astype(int)
    for sn, fe in (('기존 + 공급(D-1)', S.BASE + S.SUP), ('기존 + 공급 + 월별 연료', S.BASE + S.SUP + MON)):
        p = S.부스팅3(tr, te, fe); rk = pd.Series(p, te.index).rank(ascending=False)
        rows.append({'기간': tag, '변수': sn, 'PR-AUC': round(average_precision_score(y, p), 3), '급등일 순위': ' '.join(str(int(v)) for v in sorted(rk[y == 1]))})
r = pd.DataFrame(rows); r.to_csv(os.path.join(HERE, 'results', '37_급등_월별연료_추가.csv'), index=False, encoding='utf-8-sig'); print(r.to_string(index=False))
