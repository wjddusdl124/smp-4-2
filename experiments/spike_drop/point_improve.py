# -*- coding: utf-8 -*-
"""
point_improve.py — 평소 가격(중앙값 하나) 개선 실험 1~4
==============================================================================
목표 : rMAE ≤ 0.65 · MAE ≤ 7.0원 · MAPE < 5% · |편의| ≤ 1.5%  (전체 시간, 2026.1~9)
규칙 : 설정은 2025년(보정 구간)에서만 고르고 2026년에는 한 번만 적용. D-1에 알 수 있는 값만 사용.
  E0 기존          : 최종 모델 중앙값 M
  E1 비중 다시 고르기 : LightGBM·Chronos-2 수요예측·Chronos-2 단변량 q50 + 어제 같은 시각, 2025 MAE 최소 비중(0.05 간격)
  E2 최근 오차 보정  : M − k × (지난 N일 같은 시각 평균 오차), N·k 는 2025 MAE 로 선택
  E3 2단계 모델     : LightGBM(L1)이 「실제 − M」을 예측. 입력 = 세 모델 분위수, 어제·지난주 같은 시각, 수요예측,
                     최근 오차, 급락·급등 경보 확률, 일별 전력수급실적(D-1), 연료비 단가·LNG 가격결정 비중(전월)
                     2025년은 분기별 교차검증 예측, 2026년은 2025 전체로 학습해 예측
  E4 최근 가중치    : E3 에서 최근 자료일수록 큰 가중치(반감기 90일)
"""
import os, itertools, warnings
import numpy as np, pandas as pd, lightgbm as lgb
warnings.filterwarnings('ignore')
import day_features as DF, spike_supply as S

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
RES = os.path.join(HERE, 'results')
TGT = {'rMAE': 0.65, 'MAE': 7.0, 'MAPE(%)': 5.0, '편의(%)': 1.5}


def 지표(y, M, nv):
    ok = ~np.isnan(y); y, M, nv = y[ok], M[ok], nv[ok]
    den = np.maximum(y, 20.0); mae = np.mean(np.abs(M - y))
    return {'MAE': mae, 'rMAE': mae / np.nanmean(np.abs(nv - y)), 'MAPE(%)': 100 * np.mean(np.abs(M - y) / den),
            '편의(%)': 100 * np.mean((M - y) / den)}


def 달성(e):
    return int(e['rMAE'] <= .65) + int(e['MAE'] <= 7.0) + int(e['MAPE(%)'] < 5.0) + int(abs(e['편의(%)']) <= 1.5)


# ---------------------------------------------------------------- 데이터
def 준비():
    R = pd.read_pickle(os.path.join(RES, '_spike_level.pkl'))['R']
    b = pd.concat([R['2025'].assign(tag='2025'), R['2026'].assign(tag='2026')], ignore_index=True)
    h = pd.read_csv(os.path.join(ROOT, 'data', 'processed', 'smp_dataset_hourly.csv'),
                    usecols=['date', 'hour_n', 'smp_land', 'demand_fcst_land'])
    h = h.sort_values(['date', 'hour_n']).reset_index(drop=True)
    h['naive_w'] = h['smp_land'].shift(168)                                   # 지난주 같은 시각
    dd = h.groupby('date').agg(y_mean=('smp_land', 'mean'), y_min=('smp_land', 'min'), y_max=('smp_land', 'max'),
                               dmax=('demand_fcst_land', 'max'), dmean=('demand_fcst_land', 'mean'))
    for c in ['y_mean', 'y_min', 'y_max']: dd[c + '_d1'] = dd[c].shift(1)     # 어제 하루 값
    dd['dmax_r28'] = dd['dmax'] / dd['dmax'].shift(1).rolling(28).mean()
    b = b.merge(h[['date', 'hour_n', 'demand_fcst_land', 'naive_w']], on=['date', 'hour_n'], how='left')
    b = b.merge(dd[['y_mean_d1', 'y_min_d1', 'y_max_d1', 'dmax', 'dmean', 'dmax_r28']], left_on='date', right_index=True, how='left')
    b['d_ratio'] = b['demand_fcst_land'] / b['dmean']
    # 최근 오차 (D-1 까지) : 같은 시각 지난 N일, 모든 시각 지난 3일
    b = b.sort_values(['date', 'hour_n']).reset_index(drop=True)
    b['err'] = b['M'] - b['y']
    p = b.pivot(index='date', columns='hour_n', values='err')
    for n in (1, 3, 7, 14, 28):
        r = p.shift(1).rolling(n, min_periods=1).mean().stack().rename(f'res{n}')
        b = b.merge(r, left_on=['date', 'hour_n'], right_index=True, how='left')
    a3 = p.mean(axis=1).shift(1).rolling(3, min_periods=1).mean().rename('res_all3')
    b = b.merge(a3, left_on='date', right_index=True, how='left')
    # 경보 확률 (2025: ~2024 학습, 2026: ~2025 학습)
    A = pd.read_pickle(os.path.join(RES, '_median_adjust.pkl'))
    P = pd.read_pickle(os.path.join(RES, '_spike_supply_probs.pkl')); MV = ('LGB·XGB·Cat 평균', '기존 + 공급(D-1)')
    pdp = pd.concat([A['pd25'], A['pd26']]); psp = pd.concat([P[('2025',) + MV], P[('2026',) + MV]])
    b['p_drop'] = b['date'].map(pdp); b['p_spike'] = b['date'].map(psp)
    # 전력수급실적 (D-1)
    x = S.변수()[S.SUP]
    x.index = x.index.astype(str)
    b = b.merge(x, left_on='date', right_index=True, how='left')
    # 연료비·LNG 가격결정 비중 (전월)
    fc = pd.read_csv(os.path.join(ROOT, 'data', 'external', 'fuel_cost.csv'), encoding='utf-8-sig').set_index('ym')
    fs = pd.read_csv(os.path.join(ROOT, 'data', 'external', 'smp_fuel_set.csv'), encoding='utf-8-sig').set_index('ym')
    prev = (pd.to_datetime(b['date']).dt.to_period('M') - 1).astype(str)
    b['lng_cost_m1'] = prev.map(fc['연료비단가_LNG']); b['coal_cost_m1'] = prev.map(fc['연료비단가_유연탄'])
    b['lng_set_m1'] = prev.map(fs['LNG비중'])
    b['naive_raw'] = b['naive']              # rMAE 분모는 원래 값(빈 시간 제외)으로
    b['naive'] = b['naive'].fillna(b['M'])   # 어제 값이 빈 날은 기존 중앙값으로 대신
    b['dow'] = pd.to_datetime(b['date']).dt.dayofweek; b['month'] = pd.to_datetime(b['date']).dt.month
    return b


COMP = ['lgb_q10', 'lgb_q50', 'lgb_q90', 'chr_cov_q10', 'chr_cov_q50', 'chr_cov_q90', 'chr_uni_q10', 'chr_uni_q50', 'chr_uni_q90', 'L', 'M', 'U']
BASE_F = COMP + ['hour_n', 'offday', 'dow', 'naive', 'naive_w', 'y_mean_d1', 'y_min_d1', 'y_max_d1',
                 'demand_fcst_land', 'dmax', 'dmax_r28', 'd_ratio', 'res1', 'res3', 'res7', 'res14', 'res28', 'res_all3']
ALARM_F = ['p_drop', 'p_spike']
EXT_F = S.SUP + ['lng_cost_m1', 'coal_cost_m1', 'lng_set_m1']
PRM = dict(objective='l1', learning_rate=0.03, num_leaves=15, min_data_in_leaf=60, feature_fraction=0.8,
           bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1)


def 가중치(d, half):
    if not half: return None
    age = (pd.to_datetime(d['date']).max() - pd.to_datetime(d['date'])).dt.days.values
    return 0.5 ** (age / half)


def 학습예측(tr, te, f, n, half, seeds=(0, 1, 2)):
    tr = tr[tr['y'].notna()]
    out = np.zeros(len(te))
    for sd in seeds:
        m = lgb.train({**PRM, 'seed': sd}, lgb.Dataset(tr[f], tr['y'] - tr['M'], weight=가중치(tr, half)), n)
        out += m.predict(te[f]) / len(seeds)
    return te['M'].values + out


def 분기CV(b25, f, n, half):
    q = pd.to_datetime(b25['date']).dt.quarter.values
    pred = np.full(len(b25), np.nan)
    for k in (1, 2, 3, 4):
        pred[q == k] = 학습예측(b25[q != k], b25[q == k], f, n, half)
    return pred


def main():
    b = 준비()
    b25, b26 = b[b.tag == '2025'].reset_index(drop=True), b[b.tag == '2026'].reset_index(drop=True)
    rows, out = [], {}

    def 기록(name, M25, M26, note=''):
        e25 = 지표(b25.y.values, M25, b25.naive_raw.values); e26 = 지표(b26.y.values, M26, b26.naive_raw.values)
        rows.append({'실험': name, **{f'2025 {k}': round(v, 3) for k, v in e25.items()}, '2025 달성': 달성(e25),
                     **{f'2026 {k}': round(v, 3) for k, v in e26.items()}, '2026 달성': 달성(e26), '설정(2025에서 고름)': note})
        out[name] = (M25, M26)
        print(f"{name:28s} 2025 MAE {e25['MAE']:.3f} rMAE {e25['rMAE']:.3f} MAPE {e25['MAPE(%)']:.2f} 편의 {e25['편의(%)']:.2f} | "
              f"2026 MAE {e26['MAE']:.3f} rMAE {e26['rMAE']:.3f} MAPE {e26['MAPE(%)']:.2f} 편의 {e26['편의(%)']:.2f}  {note}")

    기록('E0 기존', b25.M.values, b26.M.values)

    # E1 — 점예측용 비중
    C = ['lgb_q50', 'chr_cov_q50', 'chr_uni_q50', 'naive']
    best = None
    for w in itertools.product(range(21), repeat=3):
        if sum(w) > 20: continue
        ww = np.array(list(w) + [20 - sum(w)]) / 20
        m = b25[C].values @ ww
        mae = np.nanmean(np.abs(m - b25.y.values))
        if best is None or mae < best[0]: best = (mae, ww)
    ww = best[1]; note1 = ' · '.join(f'{c} {v:.2f}' for c, v in zip(['LightGBM', 'Chronos-2 수요예측', '단변량', '어제 값'], ww))
    기록('E1 비중 다시 고르기', b25[C].values @ ww, b26[C].values @ ww, note1)

    # E2 — 최근 오차 보정
    g = []
    for n_, k in itertools.product((1, 3, 7, 14, 28), (0, .25, .5, .75, 1.0)):
        m = b25.M.values - k * b25[f'res{n_}'].fillna(0).values
        g.append((np.nanmean(np.abs(m - b25.y.values)), n_, k))
    _, n2, k2 = min(g)
    기록('E2 최근 오차 보정', b25.M.values - k2 * b25[f'res{n2}'].fillna(0).values,
         b26.M.values - k2 * b26[f'res{n2}'].fillna(0).values, f'지난 {n2}일 · k={k2}')

    # E5 — 시간대 × 평일/휴일 48그룹마다 비중 (0.1 간격, 2025 MAE)
    def 그룹비중(bb, W):
        m = np.full(len(bb), np.nan)
        for gname, w in W.items():
            k = (bb.group == gname).values; m[k] = bb.loc[k, C].values @ w
        return m
    W = {}
    for gname, gg in b25.groupby('group'):
        bb = None
        for w in itertools.product(range(11), repeat=3):
            if sum(w) > 10: continue
            ww_ = np.array(list(w) + [10 - sum(w)]) / 10
            mae = np.nanmean(np.abs(gg[C].values @ ww_ - gg.y.values))
            if bb is None or mae < bb[0]: bb = (mae, ww_)
        W[gname] = bb[1]
    기록('E5 시간대별 비중', 그룹비중(b25, W), 그룹비중(b26, W), '48그룹 · 2025 안에서 고름(같은 해 성적이라 낙관적)')
    # E6 — E1 비중 + E2 보정
    e1_25, e1_26 = b25[C].values @ ww, b26[C].values @ ww
    기록('E6 비중 + 최근 오차 보정', e1_25 - k2 * b25[f'res{n2}'].fillna(0).values, e1_26 - k2 * b26[f'res{n2}'].fillna(0).values, f'E1 비중 · 지난 {n2}일 · k={k2}')

    # E3·E4 — 2단계 모델 : 변수 묶음·학습 횟수·반감기를 2025 분기 교차검증 MAE 로 고름
    cand = []
    for fs_name, f in (('기본', BASE_F), ('기본+경보', BASE_F + ALARM_F), ('기본+경보+공개데이터', BASE_F + ALARM_F + EXT_F)):
        for n in (200, 500):
            for half in (None, 90):
                p25 = 분기CV(b25, f, n, half)
                cand.append((np.nanmean(np.abs(p25 - b25.y.values)), fs_name, n, half, p25))
                print(f'   후보 {fs_name:14s} n={n} 반감기={half}  2025 CV MAE {cand[-1][0]:.3f}')
    F = {'기본': BASE_F, '기본+경보': BASE_F + ALARM_F, '기본+경보+공개데이터': BASE_F + ALARM_F + EXT_F}
    for lab, pool in (('E3 2단계 모델', [c for c in cand if c[3] is None]), ('E4 2단계 + 최근 가중치', [c for c in cand if c[3] == 90])):
        c = min(pool, key=lambda z: z[0])
        p26 = 학습예측(b25, b26, F[c[1]], c[2], c[3])
        기록(lab, c[4], p26, f'변수 {c[1]} · {c[2]}회' + (' · 반감기 90일' if c[3] else ''))
    # 같은 변수 묶음별 결과 (참고 : 2025 에서 안 골랐어도 보여 줌)
    for fs_name in F:
        c = min([z for z in cand if z[1] == fs_name and z[3] is None], key=lambda z: z[0])
        p26 = 학습예측(b25, b26, F[fs_name], c[2], None)
        기록(f'참고 · 2단계 {fs_name}', c[4], p26, f'{c[2]}회')

    # 편의 목표용 : 가장 좋은 모델 + 급락 경보일 낮 시간 25% 낮춤
    A = pd.read_pickle(os.path.join(RES, '_median_adjust.pkl'))
    r = pd.DataFrame(rows); bestname = r[r['실험'].str.match(r'E[0-46]')].sort_values('2025 MAE').iloc[0]['실험']   # E5 는 2025 성적이 같은 해 선택이라 제외
    M25, M26 = out[bestname]
    def 낮춤(bb, M, a=.25):
        M = M.copy(); m = (bb.p_drop.fillna(0).values >= A['thr_d']) & bb.hour_n.isin([12, 13, 14]).values
        M[m] = M[m] - a * (M[m] - bb.L.values[m]); return M
    기록(f'{bestname.split()[0]} + 급락 경보일 25% 낮춤', 낮춤(b25, M25), 낮춤(b26, M26), '편의 목표용')

    r = pd.DataFrame(rows)
    r.to_csv(os.path.join(RES, '41_평소가격_개선실험.csv'), index=False, encoding='utf-8-sig')
    pd.to_pickle({'out': out, 'b25': b25[['date', 'hour_n', 'y', 'naive']], 'b26': b26[['date', 'hour_n', 'y', 'naive']], 'best': bestname},
                 os.path.join(RES, '_point_improve.pkl'))
    print('\n2025 MAE 로 고른 최선 :', bestname)


if __name__ == '__main__':
    main()
