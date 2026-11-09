# -*- coding: utf-8 -*-
"""
make_dashboard_data.py — 대시보드 데이터셋 22개를 한 번에 만듦 (dash_export/*.csv)
==============================================================================
앞 단계 결과(results/ 와 task2_interval/results/)만 읽어서 정리한다. 새 모델 학습은 하지 않는다
(급락 놓친 날 표만 drop_final 모델을 다시 돌려 2025 확률을 구함 — drop_final.py 와 같은 계산).
실행 순서는 REPRODUCE_SPIKE_DROP.md 참고 (run_all.py 가 순서대로 실행).
"""
import os, shutil, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import day_features as DF, drop_final as DFN

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results'); OUT = os.path.join(HERE, 'dash_export')
T2 = os.path.join(HERE, '..', 'task2_interval', 'results')
os.makedirs(OUT, exist_ok=True)
w = lambda df, name: df.to_csv(os.path.join(OUT, name), index=False, encoding='utf-8')
DOW = '월화수목금토일'


def 기본모델():
    """task2_interval 결과 5개 → 예측 범위 구역"""
    for src, dst in (('05_평가_시험구간.csv', 'metrics.csv'), ('08_최종모델_예측범위.csv', 'series.csv'),
                     ('07_시간대별_커버리지.csv', 'hourly.csv'), ('02_앙상블_가중치.csv', 'weights.csv'),
                     ('06_급등_일반_급락_비교.csv', 'regimes.csv')):
        shutil.copyfile(os.path.join(T2, src), os.path.join(OUT, dst))


def 급락():
    # 급락일 채점·표시는 기업 정의 (11~15시 중 30원 미만, day_features.drop_corp). 최저가 = 한낮(11~15시) 최저가
    d, g = DF.만들기()
    # drop_daily (75% 단일 경보)
    o = pd.read_csv(os.path.join(RES, '30_급락경보_2026_일별.csv'), encoding='utf-8-sig'); o = o[o.date <= '2026-09-30'].copy()
    dd = pd.DataFrame({'date': o.date, '요일': o['요일'], '구분': o['휴일'].map({1: '휴일', 0: '평일'}),
                       '급락확률(%)': (100 * o['급락확률']).round(2), '경보': o['경보(75%기준)'].map({True: '경보', False: ''}),
                       '실제최저가': o['한낮_최저가'].round(2), '기준최저가': 30,
                       '실제': o['실제_급락'].map({1.0: '급락', 0.0: '-'}).fillna('데이터없음')})
    w(dd, 'drop_daily.csv')
    # drop_perf
    r = pd.read_csv(os.path.join(RES, '31_급락경보_최종성적.csv'), encoding='utf-8-sig')
    pr = pd.DataFrame({'목표': r['2025 목표 탐지율'], '확률 문턱(%)': (100 * r['확률 문턱']).round(3),
                       '2025 잡은 날': r['2025 잡은일수'], '2025 경보일': r['2025 경보일수'], '2026 잡은 날': r['2026 잡은일수'],
                       '2026 탐지율(%)': r['2026 탐지율(%)'], '2026 경보일': r['2026 경보일수'], '2026 적중률(%)': r['2026 경보적중률(%)']})
    w(pr, 'drop_perf.csv')
    # drop_compare : 이전 모델 하한 신호 (하루 최저 하한 ≤ 기준의 절반) vs 경보 모델 75%
    R = pd.read_pickle(os.path.join(RES, '_spike_level.pkl'))['R']
    sig = {}
    for tag in ('2025', '2026'):
        lmin = R[tag].groupby('date').L.min(); gg = g.loc[lmin.index]
        a = lmin <= 0.5 * gg['ref_min']; y = gg['drop_corp']
        sig[tag] = (int((a & (y == 1)).sum()), int((y == 1).sum()), int(a.sum()))
    r75 = r[r['2025 목표 탐지율'] == '75%'].iloc[0]
    cmp = pd.DataFrame([
        {'방식': '이전 모델 하한 신호', '2025 잡은 날': f'{sig["2025"][0]}/{sig["2025"][1]}', '2025 경보일': sig['2025'][2],
         '2026 잡은 날': f'{sig["2026"][0]}/{sig["2026"][1]}', '2026 경보일': sig['2026'][2],
         '2026 적중률(%)': round(100 * sig['2026'][0] / sig['2026'][2], 1)},
        {'방식': '급락 경보 모델 (75% 기준)', '2025 잡은 날': r75['2025 잡은일수'], '2025 경보일': r75['2025 경보일수'],
         '2026 잡은 날': r75['2026 잡은일수'], '2026 경보일': r75['2026 경보일수'], '2026 적중률(%)': r75['2026 경보적중률(%)']}])
    w(cmp, 'drop_compare.csv')
    # drop_missed : 2025(~2024 학습)·2026(~2025 학습) 놓친 급락일
    g2 = DFN.변수_추가(d, g.copy())
    tr = g2[(g2.index <= '2024-12-31') & g2['drop'].notna()]; te = g2[(g2.index >= '2025-01-01') & (g2.index <= '2025-12-31') & g2['drop'].notna()]
    p25 = pd.Series(DFN.앙상블(tr, te, DF.OPER + DFN.EXTRA, np.where(tr.index >= '2024-01-01', 3.0, 1.0)), te.index)
    thr = DFN.문턱(p25.values, te['drop'].values.astype(int), .75)
    oo = o.set_index('date'); p26 = oo['급락확률']
    rows = [(x, p25[x]) for x in te[te['drop_corp'] == 1].index if p25[x] < thr]
    rows += [(x, p26[x]) for x in oo[(oo['실제_급락'] == 1) & (~oo['경보(75%기준)'])].index]
    miss = pd.DataFrame([{'date': x, '요일': DOW[pd.Timestamp(x).dayofweek], '구분': '휴일' if g.loc[x, 'offday'] == 1 else '평일',
                          '급락확률(%)': round(100 * p, 3), '경보 문턱(%)': round(100 * thr, 3), '문턱까지 부족(%p)': round(100 * (thr - p), 3),
                          '실제최저가': round(g.loc[x, 'mid_min'], 2), '한낮 수요예측(GW)': round(g.loc[x, 'f_mid'] / 1000, 1),
                          '수요예측 평소대비': round(g.loc[x, 'f_min_r28'], 2)} for x, p in rows])
    w(miss, 'drop_missed.csv')
    # drop_missed_ref
    dr = g[(g.index >= '2025-01-01') & (g.index <= '2026-09-30') & (g['drop_corp'] == 1)].index
    caught = [x for x in dr if x not in set(miss.date)]
    offs = g[(g.index >= '2025-01-01') & (g.index <= '2026-09-30') & (g.offday == 1) & (g['drop_corp'] == 0)].index
    w(pd.DataFrame([{'비교 대상': '잡은 급락일 (중앙값)', '일수': len(caught), '한낮 수요예측(GW)': round(g.loc[caught, 'f_mid'].median() / 1000, 1),
                     '수요예측 평소대비': round(g.loc[caught, 'f_min_r28'].median(), 2)},
                    {'비교 대상': '급락하지 않은 휴일 (중앙값)', '일수': len(offs), '한낮 수요예측(GW)': round(g.loc[offs, 'f_mid'].median() / 1000, 1),
                     '수요예측 평소대비': round(g.loc[offs, 'f_min_r28'].median(), 2)}]), 'drop_missed_ref.csv')
    # drop_days_final
    K = dict(zip('Mon Tue Wed Thu Fri Sat Sun'.split(), DOW))
    x = dd[dd['실제'] == '급락']
    t = pd.DataFrame({'date': x['date'], '요일': x['요일'].map(K), '구분': x['구분'], '실제 최저가': x['실제최저가'].round(1),
                      '급락 기준가': 30.0, '하루 전 확률(%)': x['급락확률(%)'],
                      '하루 전 경보': (x['경보'] == '경보').map({True: '예', False: '아니오'})})
    t['대비 결과'] = t['하루 전 경보'].map({'예': '잡음', '아니오': '놓침'})
    w(t, 'drop_days_final.csv')


def 급등():
    import final_spike
    final_spike.main()                     # spike_daily · spike_days_final · spike_summary
    d, g = DF.만들기()
    # spike_alarm : 이전(로지스틱, 기존 변수) vs 지금(부스팅3 + 공급), 문턱 = 2025 확률 상위 20일
    P = pd.read_pickle(os.path.join(RES, '_spike_supply_probs.pkl'))
    rows = []
    for lab, mv in (('이전: 로지스틱 (공급 데이터 없음)', ('로지스틱', '기존 변수')), ('지금: LGB·XGB·Cat 평균 + 공급 데이터', ('LGB·XGB·Cat 평균', '기존 + 공급(D-1)'))):
        p25, p26 = P[('2025',) + mv], P[('2026',) + mv]; thr = float(p25.sort_values(ascending=False).iloc[19])
        r = {'방식': lab}
        for tag, p in (('2025', p25), ('2026', p26)):
            y = g.loc[p.index, 'spike']; a = p >= thr
            r[f'{tag} 잡은 날'] = f'{int((a & (y == 1)).sum())}/{int((y == 1).sum())}'; r[f'{tag} 경보일'] = int(a.sum())
        hit = p26[(p26 >= thr) & (g.loc[p26.index, 'spike'] == 1)].index
        r['2026 잡은 급등일'] = ' · '.join(str(i)[5:] for i in hit); r['경보 문턱(%)'] = round(100 * thr, 2)
        rows.append(r)
    w(pd.DataFrame(rows)[['방식', '2025 잡은 날', '2025 경보일', '2026 잡은 날', '2026 경보일', '2026 잡은 급등일', '경보 문턱(%)']], 'spike_alarm.csv')
    # spike_actions : 대책별 효과 (export_dash.py 의 계산, 위험 시각 4개)
    import hour_ranges as H, task2_interval as T
    Y = d.pivot(index='date', columns='hour_n', values='smp_land'); pk = Y.fillna(-1).idxmax(axis=1)
    sd = g[(g.spike == 1) & (g.index >= '2023-01-01') & (g.index <= '2025-12-31')].index
    hours = sorted(pk[sd].value_counts().index[:4].tolist())
    cal, test = H.구성요소()
    W = {'q10': (0.15, 0.85, 0), 'q50': (0.15, 0.8, 0.05), 'q90': (0.25, 0.75, 0)}
    cf = cal.dropna(subset=['y']).reset_index(drop=True); Lc, Mc, Uc = H.앙상블(cf, W); C = T.등각_보정값(cf, Lc, Uc, cf.group.values)
    def bo(b):
        L, M, U = H.앙상블(b, W); gg = b.group
        return T.정리(L - gg.map(C['하한_보정']).values, M, U + gg.map(C['상한_보정']).values)
    L, M, U = bo(cal); c = cal.assign(L=L, U=U)
    X = max(0, c[c.date.isin(g[g.spike == 1].index) & c.hour_n.isin(hours)].eval('y-U').max())
    L, M, U = bo(test); t = test.assign(L=L, U=U); t['wk'] = t.date.map(g.offday) == 0
    t['U2'] = np.where(t.hour_n.isin(hours) & t.wk, t.U + X, t.U)
    sp = t[t.date.isin(g[g.spike == 1].index)].sort_values('y').groupby('date').tail(1).sort_values('date')
    ok = t.y.notna()
    h = pd.read_csv(os.path.join(RES, '24_급변시간_범위_비교.csv'), encoding='utf-8-sig'); f = h[h['기간'] == '시험 2026'].set_index('방법')
    Pd = g[(g.index >= '2023-01-01') & (g.index <= '2026-09-30') & (g.offday == 0)]; prev = g.spike.shift(1).reindex(Pd.index)
    rows = [
        {'항목': '급등일 최고가가 범위 안에 든 날 (2026)', '기존': f"{int((sp.y <= sp.U).sum())}/{len(sp)}", '대책 후': f"{int((sp.y <= sp.U2).sum())}/{len(sp)}", '대책': f"평일 {'·'.join(str(x) for x in hours)}시 상한 +{X:.1f}원"},
        {'항목': '평균 범위 폭(원, 2026)', '기존': f"{(t.U - t.L)[ok].mean():.2f}", '대책 후': f"{(t.U2 - t.L)[ok].mean():.2f}", '대책': '위험 시각 상시 확대만 적용'},
        {'항목': '급등 시간 놓침(%, 2026)', '기존': f"{f.loc['F 현재 최종', '급등 놓침(%)']:.1f}", '대책 후': f"{f.loc['G1 F+방향 넓히기', '급등 놓침(%)']:.1f}", '대책': '예측 방향 쪽만 범위 넓히기'},
        {'항목': '급락 시간 놓침(%, 2026)', '기존': f"{f.loc['F 현재 최종', '급락 놓침(%)']:.1f}", '대책 후': f"{f.loc['G1 F+방향 넓히기', '급락 놓침(%)']:.1f}", '대책': '예측 방향 쪽만 범위 넓히기'},
        {'항목': '평일 급등 확률(2023~2026.9)', '기존': f"{100 * Pd.spike[prev == 0].mean():.1f}% (전날 급등 없음)", '대책 후': f"{100 * Pd.spike[prev == 1].mean():.1f}% (전날 급등)", '대책': '전날 급등 시 연속 급등 경계'}]
    cb = pd.read_csv(os.path.join(RES, '33_최종결합_2026.csv'), encoding='utf-8-sig').set_index('방법'); a0 = cb.loc['기존 F']; a1 = cb.loc['G1 + 10·11·15·16시']
    for k, lab in (('급등 시간 놓침(%)', '[모두 적용] 급등 시간 놓침(%, 2026)'), ('급락 시간 놓침(%)', '[모두 적용] 급락 시간 놓침(%, 2026)'),
                   ('평균 폭(원)', '[모두 적용] 평균 범위 폭(원, 2026)'), ('전체 커버리지(%)', '[모두 적용] 범위 안에 든 비율(%, 2026)')):
        rows.append({'항목': lab, '기존': f"{a0[k]}", '대책 후': f"{a1[k]}", '대책': '방향 넓히기 + 평일 10·11·15·16시 상한 확대'})
    w(pd.DataFrame(rows), 'spike_actions.csv')


def 평소가격():
    import runpy
    runpy.run_path(os.path.join(HERE, 'price_targets.py'), run_name='__main__')   # price_targets · price_regimes · price_adjust
    r = pd.read_csv(os.path.join(RES, '41_평소가격_개선실험.csv'), encoding='utf-8-sig')
    r = r[~r['실험'].str.startswith('참고')].copy()
    nm = {'E0 기존': '기존 최종 모델', 'E1 비중 다시 고르기': '① 평소 가격용 비중', 'E2 최근 오차 보정': '② 최근 14일 오차 보정',
          'E5 시간대별 비중': '①-2 시간대별 비중', 'E6 비중 + 최근 오차 보정': '① + ②', 'E3 2단계 모델': '③ 2단계 모델 (+공개 데이터)',
          'E4 2단계 + 최근 가중치': '④ ③ + 최근 가중치', 'E1 + 급락 경보일 25% 낮춤': '① + 급락일 낮 25% 낮춤'}
    res = {'E0 기존': '기준', 'E1 + 급락 경보일 25% 낮춤': '편의만 달성'}
    def 결과(row):
        if row['실험'] in res: return res[row['실험']]
        return '2026 나빠짐' if row['2026 MAE'] > r.iloc[0]['2026 MAE'] + 0.03 else '차이 없음'
    o = pd.DataFrame({'실험': r['실험'].map(nm), 'MAE': r['2026 MAE'].map('{:.2f}'.format), 'rMAE': r['2026 rMAE'].map('{:.3f}'.format),
                      'MAPE(%)': r['2026 MAPE(%)'].map('{:.2f}'.format), '편의(%)': r['2026 편의(%)'].map('{:.2f}'.format),
                      '달성': r['2026 달성'], '2025 MAE': r['2025 MAE'].map('{:.2f}'.format), '결과': r.apply(결과, axis=1)})
    w(o, 'price_experiments.csv')


if __name__ == '__main__':
    기본모델(); 급락(); 급등(); 평소가격()
    print('dash_export :', len(os.listdir(OUT)), '개 파일')
