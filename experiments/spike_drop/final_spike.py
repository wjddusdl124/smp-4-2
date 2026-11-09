# -*- coding: utf-8 -*-
"""
final_spike.py — 급등 대응 최종안 (2026-10-31 채택)
==============================================================================
① 하루 전 급등 경보 : LightGBM·XGBoost·CatBoost 확률 1/3씩 평균 (각 3회 시드 평균)
     입력 = 운영 변수 16개(spike_prob.FEATS) + 일별 전력수급실적 6개(spike_supply.SUP)
     학습 2023-01-08~2025 → 2026 예측, 경보 문턱 = 2025년(학습 ~2024) 확률 상위 20일 값
② 연속 급등 경계 : 전날 급등이면 다음 날 경계 (①이 대부분 포함)
③ 범위 대비 : 기존 앙상블(LightGBM 15~25% · Chronos-2 수요예측 75~85% · 단변량 0~5%) + 등각 보정
     + 예측 방향 쪽 넓히기(상한 ×2.0 / 하한 ×1.7) + 평일 10·11·15·16시 상한 = max(넓힌 상한, 상한 + 67.8원)
"""
import os, numpy as np, pandas as pd
import hour_ranges as H, day_features as DF, spike_supply as S

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'dash_export')
HOURS = [10, 11, 15, 16]; X = 67.8; KU, KD = 2.0, 1.7
MV = ('LGB·XGB·Cat 평균', '기존 + 공급(D-1)')


def main():
    P = pd.read_pickle(os.path.join(HERE, 'results', '_spike_supply_probs.pkl'))
    x = S.변수()
    p25, p26 = P[('2025',) + MV], P[('2026',) + MV]
    thr = float(p25.sort_values(ascending=False).iloc[19])
    d, g = DF.만들기()
    Y = d.pivot(index='date', columns='hour_n', values='smp_land')
    dow = '월화수목금토일'

    # ---- 일별 (2026.1~9)
    idx = p26.index
    daily = pd.DataFrame({'date': idx, '요일': [dow[pd.Timestamp(i).dayofweek] for i in idx],
                          '구분': np.where(g.loc[idx, 'offday'] == 1, '휴일', '평일'),
                          '급등확률(%)': (100 * p26.values).round(2),
                          '경보': np.where(p26.values >= thr, '경보', ''),
                          '전날 급등': np.where(g['spike'].shift(1).reindex(idx).fillna(0).values == 1, '예', ''),
                          '최고가': Y.loc[idx].max(axis=1).round(1).values,
                          '실제': np.where(x.loc[idx, 'spike'].values == 1, '급등', '-')})
    daily.to_csv(os.path.join(OUT, 'spike_daily.csv'), index=False, encoding='utf-8')

    # ---- 최종 범위 (③) 의 급등일 최고가 시각 상한
    P2 = pd.read_pickle(os.path.join(HERE, 'results', '_spike_level.pkl')); R = P2['R']
    rows, sumrows = [], []
    for tag, pp in (('2025', p25), ('2026', p26)):
        b = R[tag]
        L2, _, Ug = H.방향_넓히기(b.L.values, b.M.values, b.U.values, b.naive.values, KU, KD)
        m = ((b.date.map(g.offday) == 0) & b.hour_n.isin(HOURS)).values
        Uc = np.where(m, np.maximum(Ug, b.U.values + X), Ug)
        s = b.assign(Uc=Uc, F=b.U.values)
        spk = sorted(x[(x.spike == 1) & x.index.isin(pp.index)].index)
        pk = s[s.date.isin(spk)].sort_values('y').groupby('date').tail(1).set_index('date').loc[spk]
        al = pp.reindex(spk) >= thr
        inr = pk.y <= pk.Uc
        for dt in spk:
            a, r_ = bool(al[dt]), bool(inr[dt])
            res = '경보 + 범위' if a and r_ else ('경보' if a else ('범위' if r_ else '놓침'))
            if tag == '2026':
                rows.append({'date': dt, '최고가 시각': int(pk.loc[dt, 'hour_n']), '실제 최고가': round(pk.loc[dt, 'y'], 1),
                             '하루 전 확률(%)': round(100 * pp[dt], 2), '하루 전 경보': '예' if a else '아니오',
                             '이전 모델 상한': round(pk.loc[dt, 'F'], 1), '최종 상한': round(pk.loc[dt, 'Uc'], 1),
                             '범위 안': '예' if r_ else '아니오', '대비 결과': res})
        n = len(spk); alarms = int((pp >= thr).sum())
        sumrows.append({'기간': tag, '급등일': n, '하루 전 경보로 잡음': int(al.sum()), '경보일': alarms,
                        '경보 적중률(%)': round(100 * al.sum() / max(1, alarms), 1),
                        '범위로 담음': int(inr.sum()), '경보 또는 범위로 대비': int((al | inr).sum()),
                        '경보 문턱(%)': round(100 * thr, 2)})
    pd.DataFrame(rows).to_csv(os.path.join(OUT, 'spike_days_final.csv'), index=False, encoding='utf-8')
    sm = pd.DataFrame(sumrows); sm.to_csv(os.path.join(OUT, 'spike_summary.csv'), index=False, encoding='utf-8')
    sm.to_csv(os.path.join(HERE, 'results', '38_급등_최종.csv'), index=False, encoding='utf-8-sig')
    print(sm.to_string(index=False)); print(pd.DataFrame(rows).to_string(index=False))
    print('2026 경보일 수', int((daily['경보'] == '경보').sum()))


if __name__ == '__main__':
    main()
