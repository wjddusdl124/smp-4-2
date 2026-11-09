# -*- coding: utf-8 -*-
"""
fuel_tests.py — 기업 연료비 자료(변동비 순위)·10/28 피드백 관련 시험을 한 표로 (대시보드 fuel_tests)
  ① 급등 경보에서 예비력 계열 변수(예상예비율·전날 예비율)를 빼면?  ← 기업 정정: 예비력 확보는 하루전 가격 결정과 관련 적음
  ② merit_order.py (results/43) · ③ spike_height_mo.py (results/45) 결과를 합침
"""
import os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import spike_supply as S
RES = os.path.join(HERE, 'results'); OUT = os.path.join(HERE, 'dash_export')
CAP = ['supply_d1', 'supply_chg_w1', 'supply_cap_ratio_d1']


def 예비력빼기():
    x = S.변수(); P = {}
    for tag, e0, s, e in (('2025', '2024-12-31', '2025-01-01', '2025-12-31'), ('2026', '2025-12-31', '2026-01-01', '2026-09-30')):
        tr = x[(x.index <= e0) & x.spike.notna()]; te = x[(x.index >= s) & (x.index <= e) & x.spike.notna()]
        P[tag] = (S.부스팅3(tr, te, S.BASE + CAP), te.spike.values.astype(int))
    thr = np.sort(P['2025'][0])[::-1][19]
    return {t: (int(((P[t][0] >= thr) & (P[t][1] == 1)).sum()), int(P[t][1].sum()), int((P[t][0] >= thr).sum())) for t in P}


def main():
    a = pd.read_csv(os.path.join(RES, '43_변동비순위_경보.csv'), encoding='utf-8-sig').set_index('방식')
    h = pd.read_csv(os.path.join(RES, '45_급등높이_변동비순위.csv'), encoding='utf-8-sig')
    r = 예비력빼기()
    f = lambda row, t: f"{row[f'{t} 잡은 날']} · 경보 {row[f'{t} 경보일']}일"
    rows = [
        {'대상': '급등 경보', '방법': '지금 (운영 변수 + 일별 전력수급실적)', '2025': f(a.loc['급등: 기존 (운영+수급)'], '2025'), '2026': f(a.loc['급등: 기존 (운영+수급)'], '2026'), '판정': '기준'},
        {'대상': '급등 경보', '방법': '예비력 계열 빼고 공급능력만', '2025': f"{r['2025'][0]}/{r['2025'][1]} · 경보 {r['2025'][2]}일", '2026': f"{r['2026'][0]}/{r['2026'][1]} · 경보 {r['2026'][2]}일", '판정': '나빠짐'},
        {'대상': '급등 경보', '방법': '+ 변동비 순위 변수 5종', '2025': f(a.loc['급등: + 변동비 순위'], '2025'), '2026': f(a.loc['급등: + 변동비 순위'], '2026'), '판정': '나빠짐'},
        {'대상': '급락 경보', '방법': '지금 (V2)', '2025': f(a.loc['급락: 기존 V2'], '2025'), '2026': f(a.loc['급락: 기존 V2'], '2026'), '판정': '기준'},
        {'대상': '급락 경보', '방법': '+ 변동비 순위 변수 4종', '2025': f(a.loc['급락: + 변동비 순위'], '2025'), '2026': f(a.loc['급락: + 변동비 순위'], '2026'), '판정': '미채택'}]
    for lab, m in (('지금 (+67.8원 고정)', '지금: +67.8원 고정'), ('그 달 일반 LNG 변동비 95% 자리', 'LNG 95% 자리')):
        x5 = h[(h['기간'] == 2025) & (h['방법'] == m)].iloc[0]; x6 = h[(h['기간'] == 2026) & (h['방법'] == m)].iloc[0]
        rows.append({'대상': '급등 높이 (위험 시각 상한)', '방법': lab, '2025': f"최고가 {x5['급등일 최고가 담음']} · 폭 {x5['평균 폭(원)']:.2f}원",
                     '2026': f"최고가 {x6['급등일 최고가 담음']} · 폭 {x6['평균 폭(원)']:.2f}원", '판정': '기준' if m.startswith('지금') else '나빠짐'})
    t = pd.DataFrame(rows); t.to_csv(os.path.join(OUT, 'fuel_tests.csv'), index=False, encoding='utf-8')
    t.to_csv(os.path.join(RES, '46_연료비자료_시험정리.csv'), index=False, encoding='utf-8-sig'); print(t.to_string(index=False))


if __name__ == '__main__':
    main()
