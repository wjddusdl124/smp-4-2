# -*- coding: utf-8 -*-
"""price_targets.py — 평소 가격 목표표(전체 시간=판정 / 평소 시간=참고) + 급락 경보 중앙값 조정 실험을 대시보드용으로 내보냄"""
import os, numpy as np, pandas as pd
import day_features as DF
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'dash_export')
R = pd.read_pickle(os.path.join(HERE, 'results', '_spike_level.pkl'))['R']
A = pd.read_pickle(os.path.join(HERE, 'results', '_median_adjust.pkl'))
TGT = {'rMAE': 0.65, 'MAE': 7.0, 'MAPE(%)': 5.0, '편의(%)': 1.5}

def 지표(y, M, nv):
    ok = ~np.isnan(y); y, M, nv = y[ok], M[ok], nv[ok]
    den = np.maximum(y, 20.0); mae = np.mean(np.abs(M - y))
    return {'MAE': mae, 'rMAE': mae / np.nanmean(np.abs(nv - y)), 'MAPE(%)': 100*np.mean(np.abs(M-y)/den), '편의(%)': 100*np.mean((M-y)/den), 'n': int(ok.sum())}

b25, b26 = R['2025'], R['2026']
ch = (b25.y - b25.naive).dropna(); up, dn = np.quantile(ch, .95), np.quantile(ch, .05)
def 구간(b):
    c = b.y - b.naive
    return np.where(c >= up, '급등', np.where(c <= dn, '급락', '일반'))

def 조정(b, p, a):
    M = b.M.values.copy(); m = (b.date.map(p).fillna(0).values >= A['thr_d']) & b.hour_n.isin([12, 13, 14]).values
    M[m] = M[m] - a * (M[m] - b.L.values[m]); return M

rows = []
for tag, b, p in (('2025', b25, A['pd25']), ('2026', b26, A['pd26'])):
    rg = 구간(b)
    for name, a in (('최종 모델 (조정 없음)', 0), ('급락 경보일 낮 시간 낮춤 25%', .25), ('급락 경보일 낮 시간 낮춤 50%', .5), ('급락 경보일 낮 시간 낮춤 100%', 1.0)):
        M = 조정(b, p, a)
        for base, m in (('전체 시간', np.ones(len(b), bool)), ('평소 시간만', rg == '일반'), ('급등 시간', rg == '급등'), ('급락 시간', rg == '급락')):
            e = 지표(b.y.values[m], M[m], b.naive.values[m])
            rows.append({'기간': tag, '방법': name, '기준': base, **{k: (v if k == 'n' else round(v, 3 if k == 'rMAE' else 2)) for k, v in e.items()}})
T = pd.DataFrame(rows).rename(columns={'n': '시간수'})
T['달성 수'] = sum((T[k].abs() <= v) if k == '편의(%)' else (T[k] < v if k == 'MAPE(%)' else T[k] <= v) for k, v in TGT.items()).astype(int)
T.to_csv(os.path.join(OUT, 'price_adjust.csv'), index=False, encoding='utf-8')

# 목표표 (지표별 1행)
f = lambda tag, meth, base, k: float(T[(T['기간']==tag)&(T['방법']==meth)&(T['기준']==base)][k].iloc[0])
F0 = '최종 모델 (조정 없음)'
tr = []
for k, lab, goal, rule in (('rMAE', 'rMAE', '0.65 이하', 'le'), ('MAE', 'MAE (원)', '7.0 이하 (도전)', 'le'), ('MAPE(%)', 'MAPE (%)', '5.0 미만', 'lt'), ('편의(%)', '편의 (%)', '절대값 1.5 이하', 'abs')):
    v = f('2026', F0, '전체 시간', k); v25 = f('2025', F0, '전체 시간', k)
    ok = (abs(v) <= TGT[k]) if rule == 'abs' else (v < TGT[k] if rule == 'lt' else v <= TGT[k])
    tr.append({'지표': lab, '목표': goal, '목표값': TGT[k], '2026 전체 시간': v, '판정': '달성' if ok else '미달',
               '차이': round(abs(v) - TGT[k], 3 if k == 'rMAE' else 2), '2025 전체 시간': v25,
               '2026 평소 시간만 (참고)': f('2026', F0, '평소 시간만', k), '2026 급락 낮춤 25%': f('2026', '급락 경보일 낮 시간 낮춤 25%', '전체 시간', k)})
pd.DataFrame(tr).to_csv(os.path.join(OUT, 'price_targets.csv'), index=False, encoding='utf-8')
# 오차 나눠보기 : 구간별 시간 비중·MAE 비중
sh = []
for base in ('평소 시간만', '급등 시간', '급락 시간'):
    r = T[(T['기간']=='2026')&(T['방법']==F0)&(T['기준']==base)].iloc[0]
    sh.append({'구간': {'평소 시간만': '평소', '급등 시간': '급등', '급락 시간': '급락'}[base], '시간수': int(r['시간수']), 'MAE': r['MAE'], '편의(%)': r['편의(%)']})
S = pd.DataFrame(sh); S['시간 비중(%)'] = (100*S['시간수']/S['시간수'].sum()).round(1)
S['오차 비중(%)'] = (100*S['시간수']*S['MAE']/(S['시간수']*S['MAE']).sum()).round(1)
S.to_csv(os.path.join(OUT, 'price_regimes.csv'), index=False, encoding='utf-8')
print(pd.DataFrame(tr).to_string(index=False)); print(S.to_string(index=False))
print(T[T['기준']=='전체 시간'].to_string(index=False))

# 표시용 자리수 고정 (rMAE 3자리, 나머지 2자리)
P = pd.read_csv(os.path.join(OUT, 'price_targets.csv'))
for c in ['목표값', '2026 전체 시간', '차이', '2025 전체 시간', '2026 평소 시간만 (참고)', '2026 급락 낮춤 25%']:
    P[c] = [f"{v:.3f}" if k == 'rMAE' else (f"{v:.1f}" if c == '목표값' else f"{v:.2f}") for k, v in zip(P['지표'], P[c])]
P.to_csv(os.path.join(OUT, 'price_targets.csv'), index=False, encoding='utf-8')
T = pd.read_csv(os.path.join(OUT, 'price_adjust.csv'))
T['rMAE'] = T['rMAE'].map(lambda v: f"{v:.3f}")
for c in ['MAE', 'MAPE(%)', '편의(%)']: T[c] = T[c].map(lambda v: f"{v:.2f}")
T.to_csv(os.path.join(OUT, 'price_adjust.csv'), index=False, encoding='utf-8')
S = pd.read_csv(os.path.join(OUT, 'price_regimes.csv'))
for c in ['MAE', '편의(%)']: S[c] = S[c].map(lambda v: f"{v:.2f}")
S.to_csv(os.path.join(OUT, 'price_regimes.csv'), index=False, encoding='utf-8')
