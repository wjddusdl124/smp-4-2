# -*- coding: utf-8 -*-
"""
median_adjust.py — 급락·급등 경보를 「중앙값」에 반영하면 평소 가격 목표(rMAE·MAE·MAPE·편의)에 다가가나
==============================================================================
기본 : 최종 모델 F 의 중앙값 M (LightGBM 15% · Chronos-2 수요예측 80% · 단변량 5%), 하한 L, 상한 U
급락 조정 : 급락 경보일(확률 ≥ 75% 문턱 3.894%) 한낮 시각 H 에서  M' = M − a × (M − L)
급등 조정 : 급등 경보일(확률 ≥ 6.79%) 평일 10·11·15·16시에서   M' = M + c × (U − M)
a, c, H 는 2025년(각 경보 모델은 ~2024 학습) 전체 MAE 가 가장 작은 값으로 고르고 2026.1~9 에 1회 적용
지표 : MAE, rMAE(= MAE / 어제 같은 시각 MAE), MAPE·편의(분모 하한 20원) — spike_days.py 와 같은 정의
"""
import os, itertools, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import day_features as DF, drop_final as DFN, spike_supply as S

HERE = os.path.dirname(os.path.abspath(__file__))
R = pd.read_pickle(os.path.join(HERE, 'results', '_spike_level.pkl'))['R']


def 지표(y, M, nv):
    ok = ~np.isnan(y); y, M, nv = y[ok], M[ok], nv[ok]
    den = np.maximum(y, 20.0); mae = np.mean(np.abs(M - y))
    return {'MAE': mae, 'rMAE': mae / np.nanmean(np.abs(nv - y)), 'MAPE(%)': 100 * np.mean(np.abs(M - y) / den),
            '편의(%)': 100 * np.mean((M - y) / den)}


def 급락확률():
    d, g = DF.만들기(); g = DFN.변수_추가(d, g); fe = DF.OPER + DFN.EXTRA
    tr = g[(g.index <= '2024-12-31') & g['drop'].notna()]; te = g[(g.index >= '2025-01-01') & (g.index <= '2025-12-31')]
    p25 = pd.Series(DFN.앙상블(tr, te, fe, np.where(tr.index >= '2024-01-01', 3.0, 1.0)), te.index)
    tr2 = g[(g.index <= '2025-12-31') & g['drop'].notna()]; te2 = g[(g.index >= '2026-01-01') & (g.index <= '2026-09-30')]
    p26 = pd.Series(DFN.앙상블(tr2, te2, fe, np.where(tr2.index >= '2024-01-01', 3.0, 1.0)), te2.index)
    return p25, p26, g


def main():
    pd25, pd26, g = 급락확률()
    y25 = g.loc['2025-01-01':'2025-12-31', 'drop'].dropna()
    thr_d = DFN.문턱(pd25[y25.index].values, y25.values.astype(int), .75)
    P = pd.read_pickle(os.path.join(HERE, 'results', '_spike_supply_probs.pkl'))
    MV = ('LGB·XGB·Cat 평균', '기존 + 공급(D-1)')
    ps25, ps26 = P[('2025',) + MV], P[('2026',) + MV]; thr_s = float(ps25.sort_values(ascending=False).iloc[19])
    print(f'급락 문턱 {100*thr_d:.3f}% / 급등 문턱 {100*thr_s:.2f}%')

    def 적용(b, pdp, psp, a, H, c):
        M = b.M.values.copy()
        dal = b.date.map(pdp).fillna(0).values >= thr_d
        m1 = dal & b.hour_n.isin(H).values
        M[m1] = M[m1] - a * (M[m1] - b.L.values[m1])
        sal = b.date.map(psp).fillna(0).values >= thr_s
        wk = (b.date.map(g.offday) == 0).values
        m2 = sal & wk & b.hour_n.isin([10, 11, 15, 16]).values
        M[m2] = M[m2] + c * (b.U.values[m2] - M[m2])
        return M, int(m1.sum()), int(m2.sum())

    HS = {'12~14시': [12, 13, 14], '11~15시': [11, 12, 13, 14, 15], '13시만': [13]}
    grid = []
    b25 = R['2025']
    for (hn, H), a, c in itertools.product(HS.items(), [0, .25, .5, .75, 1.0], [0, .25, .5, .75, 1.0]):
        M, n1, n2 = 적용(b25, pd25, ps25, a, H, c)
        e = 지표(b25.y.values, M, b25.naive.values); grid.append({'시각': hn, 'a': a, 'c': c, **e})
    G = pd.DataFrame(grid).sort_values('MAE'); best = G.iloc[0]
    print('2025 상위 5개 설정'); print(G.head(5).round(3).to_string(index=False))

    rows = []
    for tag, b, pdp, psp in (('2025', b25, pd25, ps25), ('2026', R['2026'], pd26, ps26)):
        for name, a, H, c in (('기존 (조정 없음)', 0, [13], 0),
                              (f"급락만 조정 ({best['시각']}, a={best['a']})", best['a'], HS[best['시각']], 0),
                              (f"급등만 조정 (c={best['c']})", 0, [13], best['c']),
                              (f"둘 다 조정", best['a'], HS[best['시각']], best['c'])):
            M, n1, n2 = 적용(b, pdp, psp, a, H, c)
            e = 지표(b.y.values, M, b.naive.values)
            rows.append({'기간': tag, '방법': name, **{k: round(v, 3) for k, v in e.items()}, '조정 시간 수': n1 + n2})
    r = pd.DataFrame(rows)
    r.to_csv(os.path.join(HERE, 'results', '40_중앙값조정_목표점검.csv'), index=False, encoding='utf-8-sig')
    pd.set_option('display.width', 220); print(r.to_string(index=False))
    pd.to_pickle({'best': best.to_dict(), 'thr_d': thr_d, 'thr_s': thr_s, 'pd25': pd25, 'pd26': pd26}, os.path.join(HERE, 'results', '_median_adjust.pkl'))


if __name__ == '__main__':
    main()
