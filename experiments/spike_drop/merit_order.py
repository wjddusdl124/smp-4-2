# -*- coding: utf-8 -*-
"""
merit_order.py — 기업 제공 「변동비 순위」(전력거래소 월별, 2022.3~2026.11)로 급등·급락 경보가 나아지나
==============================================================================
변동비 순위는 그 달 시작 전에 정해지는 값이라 D-1 에 쓸 수 있음 (자료 안내 v1).
수력·양수 등 「기타」는 변동비 0 으로 표시돼 빼고, 나머지 발전기를 변동비 순으로 쌓아 그 달의 공급 곡선을 만든다.

새 변수 (그날이 속한 달의 공급 곡선 + 그날 기준가)
  mo_band_up   : 기준가(직전 28일 일 최고가 중앙값) ~ 1.25배 사이에 있는 발전기 출력 합(MW) — 작을수록 조금만 밀려도 급등 문턱을 넘음
  mo_next_up   : 기준가보다 비싼 첫 발전기의 변동비 ÷ 기준가
  mo_up_imp    : 수요예측 최대가 최근 28일 중앙값보다 늘어난 만큼 공급 곡선을 따라 올라갔을 때의 변동비 ÷ 기준가
  mo_shift_up  : 이번 달 곡선에서 기준가 자리(누적 출력)의 변동비 ÷ 지난달 곡선의 같은 자리 변동비 — 월초 단가 변화
  mo_band_dn   : 기준 최저가의 절반 ~ 기준 최저가 사이 출력 합(MW)
  mo_lng_dn    : 그 달 직도입 LNG 변동비 중앙값 ÷ 기준 최저가
  mo_tier_gap  : 일반 LNG 중앙값 ÷ 직도입 LNG 중앙값
규칙 : 기존과 같음 — 학습 ~2024 → 2025 평가·문턱(급등 상위 20일 / 급락 75%) → 학습 ~2025 → 2026.1~9 한 번 적용
"""
import os, sys, warnings
import numpy as np, pandas as pd
from sklearn.metrics import average_precision_score
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import day_features as DF, spike_supply as S, drop_final as DFN

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'data', 'external', 'fuel_2026', '변동비순위_발전기별_202203-202611.csv')
SUMM = os.path.join(ROOT, 'data', 'external', 'fuel_2026', '변동비_연료별_월별요약_202203-202611.csv')
MO_UP = ['mo_band_up', 'mo_next_up', 'mo_up_imp', 'mo_shift_up', 'mo_tier_gap']
MO_DN = ['mo_band_dn', 'mo_lng_dn', 'mo_tier_gap', 'mo_shift_up']


def 곡선():
    r = pd.read_csv(SRC, encoding='utf-8-sig')
    r = r[(r['연료구분'] != '기타(수력·양수 등)') & (r['변동비_원kWh'] > 0)].copy()
    out = {}
    for m, g in r.groupby('연월'):
        g = g.sort_values('변동비_원kWh'); out[m] = (g['변동비_원kWh'].values, g['최대출력_MW'].cumsum().values, g['최대출력_MW'].values)
    return out


def 변수(x):
    C = 곡선()
    s = pd.read_csv(SUMM, encoding='utf-8-sig').pivot(index='연월', columns='연료구분', values='변동비_중앙값')
    mon = pd.to_datetime(x.index).to_period('M').astype(str); prev = (pd.to_datetime(x.index).to_period('M') - 1).astype(str)
    fmed = x['f_max'].shift(1).rolling(28, min_periods=14).median()
    rows = []
    for d, m, pm, rmx, rmn, fm, f28 in zip(x.index, mon, prev, x['ref_max'], x['ref_min'], x['f_max'], fmed):
        v = dict.fromkeys(MO_UP + MO_DN, np.nan)
        if m in C and pd.notna(rmx):
            c, cum, mw = C[m]
            v['mo_band_up'] = mw[(c > rmx) & (c <= 1.25 * rmx)].sum()
            up = c[c > rmx]; v['mo_next_up'] = up[0] / rmx if len(up) else np.nan
            pos = cum[np.searchsorted(c, rmx, side='right') - 1] if (c <= rmx).any() else 0.0
            if pd.notna(fm) and pd.notna(f28):
                k = min(np.searchsorted(cum, pos + (fm - f28)), len(c) - 1); v['mo_up_imp'] = c[max(k, 0)] / rmx
            if pm in C:
                pc, pcum, _ = C[pm]; k1 = min(np.searchsorted(cum, pos), len(c) - 1); k0 = min(np.searchsorted(pcum, pos), len(pc) - 1)
                v['mo_shift_up'] = c[k1] / pc[k0]
            if pd.notna(rmn) and rmn > 0:
                v['mo_band_dn'] = mw[(c >= 0.5 * rmn) & (c < rmn)].sum()
                v['mo_lng_dn'] = s.loc[m, 'LNG(직도입)'] / rmn
            v['mo_tier_gap'] = s.loc[m, 'LNG'] / s.loc[m, 'LNG(직도입)']
        rows.append(v)
    return pd.DataFrame(rows, index=x.index)


def 평가(name, p25, p26, y25, y26, mode):
    thr = float(np.sort(p25)[::-1][19]) if mode == 'top20' else (DFN.문턱(p25, y25, .75) if mode == '75' else mode)
    a25, a26 = p25 >= thr, p26 >= thr
    return {'방식': name, '2025 PR-AUC': round(average_precision_score(y25, p25), 3), '2026 PR-AUC': round(average_precision_score(y26, p26), 3),
            '2025 잡은 날': f'{int((a25 & (y25 == 1)).sum())}/{int(y25.sum())}', '2025 경보일': int(a25.sum()),
            '2026 잡은 날': f'{int((a26 & (y26 == 1)).sum())}/{int(y26.sum())}', '2026 경보일': int(a26.sum())}


def main():
    rows = []
    # ---- 급등 (spike_supply 와 같은 설정)
    x = S.변수(); x = x.join(변수(x))
    print(x.loc[x.spike == 1, ['day_max', 'ref_max'] + MO_UP].round(2).tail(15).to_string())
    for name, f in (('급등: 기존 (운영+수급)', S.BASE + S.SUP), ('급등: + 변동비 순위', S.BASE + S.SUP + MO_UP)):
        P = {}
        for tag, tr_end, s, e in (('2025', '2024-12-31', '2025-01-01', '2025-12-31'), ('2026', '2025-12-31', '2026-01-01', '2026-09-30')):
            tr = x[(x.index <= tr_end) & x['spike'].notna()]; te = x[(x.index >= s) & (x.index <= e) & x['spike'].notna()]
            P[tag] = (S.부스팅3(tr, te, f), te['spike'].values.astype(int), te.index)
        r = 평가(name, P['2025'][0], P['2026'][0], P['2025'][1], P['2026'][1], 'top20')
        thr = float(np.sort(P['2025'][0])[::-1][19]); hit = P['2026'][2][(P['2026'][0] >= thr) & (P['2026'][1] == 1)]
        r['2026 잡은 급등일'] = ' · '.join(d[5:] for d in hit); rows.append(r); print(r)
    # ---- 급락 (drop_final V2 와 같은 설정)
    d, g = DF.만들기(); g = DFN.변수_추가(d, g); g = g.join(변수(g))
    for name, f in (('급락: 기존 V2', DF.OPER + DFN.EXTRA), ('급락: + 변동비 순위', DF.OPER + DFN.EXTRA + MO_DN)):
        P = {}
        for tag, tr_end, s, e in (('2025', '2024-12-31', '2025-01-01', '2025-12-31'), ('2026', '2025-12-31', '2026-01-01', '2026-09-30')):
            tr = g[(g.index <= tr_end) & g['drop'].notna()]; te = g[(g.index >= s) & (g.index <= e) & g['drop_corp'].notna()]
            P[tag] = (DFN.앙상블(tr, te, f, np.where(tr.index >= '2024-01-01', 3.0, 1.0)), te['drop'].fillna(0).values.astype(int), te['drop_corp'].values)
        # 문턱은 2025 우리 정의로 정하고(모델 설정), 채점은 기업 정의(11~15시 30원 미만)로
        thr = DFN.문턱(P['2025'][0], P['2025'][1], .75)
        r = 평가(name, *[P[t][0][~np.isnan(P[t][2])] for t in ('2025', '2026')], *[P[t][2][~np.isnan(P[t][2])].astype(int) for t in ('2025', '2026')], thr)
        rows.append(r); print(r)
    out = pd.DataFrame(rows); out.to_csv(os.path.join(HERE, 'results', '43_변동비순위_경보.csv'), index=False, encoding='utf-8-sig')
    print(out.to_string(index=False))


if __name__ == '__main__':
    main()
