# -*- coding: utf-8 -*-
"""
drop_weekday.py — 3차 수업 피드백(10/30) 공통 요청 ③ + 「가격 문턱 급락 경보」 비교
==============================================================================
① 급락 경보 결과를 평일·휴일로 나눠 표시 (모델은 처음부터 평일 포함 전체 날로 학습 — drop_final V2 그대로)
② 기업 정의로도 채점 : 「거래시간 11~15시 중 1시간이라도 30원 미만」
③ 기업이 11월부터 기록하려는 「예측 가격 85원 미만이면 주의」를 우리 최종 모델 중앙값으로 계산해 비교
확률은 2025 = ~2024 학습, 2026 = ~2025 학습 (median_adjust.py 저장본), 문턱 3.894% 는 2025에서 정한 값
"""
import os, sys, warnings
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import day_features as DF

HOURS = [11, 12, 13, 14, 15]


def main():
    d, g = DF.만들기()
    A = pd.read_pickle(os.path.join(HERE, 'results', '_median_adjust.pkl')); thr = A['thr_d']
    R = pd.read_pickle(os.path.join(HERE, 'results', '_spike_level.pkl'))['R']
    Y = d.pivot(index='date', columns='hour_n', values='smp_land')
    corp = (Y[HOURS].min(axis=1) < 30).astype(float).where(Y[HOURS].notna().all(axis=1))
    print('기업 정의 평일 급락 (2024~) :', ', '.join(x for x in corp.index if x >= '2024-01-01' and corp[x] == 1 and g.loc[x, 'offday'] == 0))
    rows = []
    for tag, p in (('2025', A['pd25']), ('2026', A['pd26'])):
        b = R[tag]; mmin = b[b.hour_n.isin(HOURS)].groupby('date').M.min()
        idx = p.index.intersection(mmin.index)
        df = pd.DataFrame({'p': p[idx], 'mmin': mmin[idx], 'ours': g.loc[idx, 'drop'], 'corp': corp.reindex(idx), 'off': g.loc[idx, 'offday']})
        for lab, col in (('우리 정의 (28일 최저가 중앙값의 절반 이하)', 'ours'), ('기업 정의 (11~15시 30원 미만)', 'corp')):
            for kind, m in (('휴일', df.off == 1), ('평일', df.off == 0), ('전체', df.off.notna())):
                x = df[m & df[col].notna()]; yv = x[col].values.astype(int)
                for way, al in (('급락 경보 모델 (문턱 3.894%)', x.p >= thr), ('가격 문턱 (예측 중앙값 85원 미만)', x.mmin < 85),
                                ('경보 모델 + 평일만 가격 문턱', (x.p >= thr) | ((x.off == 0) & (x.mmin < 85)))):
                    al = al.values
                    rows.append({'기간': tag, '급락 정의': lab, '구분': kind, '방식': way, '급락일': int(yv.sum()),
                                 '잡은 날': int((al & (yv == 1)).sum()), '경보일': int(al.sum()),
                                 '적중률(%)': round(100 * (al & (yv == 1)).sum() / max(1, al.sum()), 1),
                                 'ROC-AUC': (round(roc_auc_score(yv, x.p if way.startswith('급락') else -x.mmin), 3) if 0 < yv.sum() < len(yv) else np.nan) if not way.startswith('경보 모델 +') else np.nan})
    t = pd.DataFrame(rows); t.to_csv(os.path.join(HERE, 'results', '48_급락_평일휴일_기업정의.csv'), index=False, encoding='utf-8-sig')
    pd.set_option('display.width', 250); print(t.to_string(index=False))
    o = t[t['급락 정의'].str.startswith('기업')].drop(columns='급락 정의').copy()   # 11/2 부터 대시보드는 기업 정의
    o['ROC-AUC'] = o['ROC-AUC'].map(lambda v: '' if pd.isna(v) else f'{v:.3f}')
    o.to_csv(os.path.join(HERE, 'dash_export', 'drop_weekday.csv'), index=False, encoding='utf-8')


if __name__ == '__main__':
    main()
