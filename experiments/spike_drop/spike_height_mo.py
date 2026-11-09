# -*- coding: utf-8 -*-
"""
spike_height_mo.py — 급등 높이를 「변동비 순위」로 정하기
==============================================================================
발견 : 2023~2026 급등일 36일의 그날 최고가는 모두 그 달 일반 LNG 발전기 변동비 순위의 92~97% 자리(평균 94%)에 있었다.
        → 급등하면 가격이 「그 달 비싼 쪽 LNG 발전기」 단가까지 오른다 (수요와 무관하게 높이가 거의 정해짐)
지금 : 평일 10·11·15·16시 상한 = max(방향 넓힌 상한, 원래 상한 + 67.8원)          ← 고정 폭
시험 : 평일 10·11·15·16시 상한 = max(방향 넓힌 상한, 그 달 일반 LNG 변동비 q 분위)   ← 달마다 바뀌는 높이
       q 는 2025 에서 「급등일 최고가를 담는 수」가 지금 이상이면서 평균 폭이 가장 좁은 값으로 고르고 2026 에 한 번 적용
"""
import os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hour_ranges as H, day_features as DF

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'data', 'external', 'fuel_2026', '변동비순위_발전기별_202203-202611.csv')
HOURS = [10, 11, 15, 16]; X = 67.8; KU, KD = 2.0, 1.7


def lng_q(q):
    r = pd.read_csv(SRC, encoding='utf-8-sig'); r = r[(r['연료구분'] == 'LNG') & (r['변동비_원kWh'] > 0)]
    return r.groupby('연월')['변동비_원kWh'].quantile(q)


def 위치표(d, g):
    r = pd.read_csv(SRC, encoding='utf-8-sig'); l = r[(r['연료구분'] == 'LNG') & (r['변동비_원kWh'] > 0)]
    sp = g[(g.spike == 1) & (g.index >= '2022-03-01') & (g.index <= '2026-09-30')]
    rows = []
    for dt, row in sp.iterrows():
        c = np.sort(l[l['연월'] == dt[:7]]['변동비_원kWh'].values)
        if len(c): rows.append({'date': dt, '최고가': round(row.day_max, 1), 'LNG 중앙값': round(np.median(c), 1), '최고가의 LNG 순위 위치': round((c <= row.day_max).mean(), 3)})
    return pd.DataFrame(rows)


def main():
    d, g = DF.만들기()
    pos = 위치표(d, g); pos.to_csv(os.path.join(HERE, 'results', '44_급등최고가_LNG순위위치.csv'), index=False, encoding='utf-8-sig')
    print(f"급등일 {len(pos)}일 · 최고가의 LNG 순위 위치 평균 {pos.iloc[:, -1].mean():.3f} (최소 {pos.iloc[:, -1].min():.3f}, 최대 {pos.iloc[:, -1].max():.3f})")
    R = pd.read_pickle(os.path.join(HERE, 'results', '_spike_level.pkl'))['R']
    b25 = R['2025']; ch = (b25.y - b25.naive).dropna(); up, dn = np.quantile(ch, .95), np.quantile(ch, .05)
    spk = set(g[g.spike == 1].index)

    def 결과(b, U):
        ok = b.y.notna().values; y = b.y.values; L2, _, _ = H.방향_넓히기(b.L.values, b.M.values, b.U.values, b.naive.values, KU, KD)
        rg = np.where(b.y - b.naive >= up, '급등', np.where(b.y - b.naive <= dn, '급락', '일반'))
        s = b.assign(Uc=U); pk = s[s.date.isin(spk)].sort_values('y').groupby('date').tail(1)
        m = ok & (rg == '급등')
        return {'급등일 최고가 담음': f'{int((pk.y <= pk.Uc).sum())}/{len(pk)}', '_n': int((pk.y <= pk.Uc).sum()),
                '급등 시간 놓침(%)': round(100 * np.mean(y[m] > U[m]), 1), '평균 폭(원)': round(np.mean((U - L2)[ok]), 2),
                '범위 안(%)': round(100 * np.mean(((y >= L2) & (y <= U))[ok]), 1)}

    rows = []
    for tag in ('2025', '2026'):
        b = R[tag]; _, _, Ug = H.방향_넓히기(b.L.values, b.M.values, b.U.values, b.naive.values, KU, KD)
        risk = ((b.date.map(g.offday) == 0) & b.hour_n.isin(HOURS)).values
        rows.append({'기간': tag, '방법': '지금: +67.8원 고정', **결과(b, np.where(risk, np.maximum(Ug, b.U.values + X), Ug))})
        for q in (0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 1.0):
            lq = b.date.str[:7].map(lng_q(q)).values
            rows.append({'기간': tag, '방법': f'LNG {int(q * 100)}% 자리', 'q': q, **결과(b, np.where(risk, np.maximum(Ug, lq), Ug))})
    t = pd.DataFrame(rows)
    a = t[t['기간'] == '2025']; base = a.iloc[0]
    cand = a[(a['_n'] >= base['_n']) & a['q'].notna()].sort_values('평균 폭(원)')
    best = cand.iloc[0]['방법'] if len(cand) else None
    t['2025로 고름'] = np.where(t['방법'] == best, '선택', '')
    t.drop(columns=['_n', 'q']).to_csv(os.path.join(HERE, 'results', '45_급등높이_변동비순위.csv'), index=False, encoding='utf-8-sig')
    pd.set_option('display.width', 200); print(t.drop(columns=['_n']).to_string(index=False)); print('2025 로 고른 것 :', best)


if __name__ == '__main__':
    main()
