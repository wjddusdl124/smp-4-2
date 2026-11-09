# -*- coding: utf-8 -*-
"""corp_bias.py — 기업 문서(실행계획서 v1.7 A-1)의 편의 보정을 최종 모델 중앙값에 적용해 봄
보정값 = clip(γ × 최근 21일(같은 평일/휴일 구분·같은 시각) 평균 잔차, ±25원), M' = M − 보정값.  γ 는 2025 MAE 로 선택"""
import os, numpy as np, pandas as pd, itertools
from point_improve import 지표, 달성
HERE = os.path.dirname(os.path.abspath(__file__))
R = pd.read_pickle(os.path.join(HERE, 'results', '_spike_level.pkl'))['R']
b = pd.concat([R['2025'], R['2026']], ignore_index=True).sort_values(['date', 'hour_n']).reset_index(drop=True)
b['err'] = b['M'] - b['y']
def 보정(win, split):
    out = np.zeros(len(b))
    for key, g in b.groupby(['hour_n'] + (['offday'] if split else [])):
        e = g['err']; c = e.shift(1).rolling(win, min_periods=5).mean()   # D-1 까지의 같은 구분 날
        out[g.index] = c.fillna(0).values
    return out
rows = []
for win, split, gam, cap in itertools.product((21, 14, 7), (True, False), (0.5, 0.7, 1.0, 1.2, 1.5), (25, 1e9)):
    M = b.M.values - np.clip(gam * 보정(win, split), -cap, cap)
    for tag in ('2025', '2026'):
        k = (b.date.str[:4] == tag).values
        e = 지표(b.y.values[k], M[k], b.naive.values[k])
        rows.append({'창': win, '평일휴일분리': split, 'γ': gam, '상한': '±25' if cap == 25 else '없음', '기간': tag, **{a: round(v, 3) for a, v in e.items()}, '달성': 달성(e)})
r = pd.DataFrame(rows)
p = r.pivot_table(index=['창', '평일휴일분리', 'γ', '상한'], columns='기간', values=['MAE', 'rMAE', 'MAPE(%)', '편의(%)'])
p.columns = [f'{a} {b}' for a, b in p.columns]; p = p.sort_values('MAE 2025')
base = 지표(b.y.values[(b.date.str[:4] == '2026').values], b.M.values[(b.date.str[:4] == '2026').values], b.naive.values[(b.date.str[:4] == '2026').values])
print('기존 2026', {k: round(v, 3) for k, v in base.items()})
print(p.head(8).to_string()); print('기업 설정(21·분리·1.5·±25):'); print(p.loc[(21, True, 1.5, '±25')].to_string())
p.to_csv(os.path.join(HERE, 'results', '42_기업편의보정_적용.csv'), encoding='utf-8-sig')
