# -*- coding: utf-8 -*-
"""
common_period.py — 3차 수업 피드백(10/30) 4-2조 요청 ① : 가격 모델 여러 안을 「같은 기간·같은 지표」 한 표로
==============================================================================
  python common_period.py                    # 2026-01-01 ~ 2026-10-02 (기업 예시 기간)
  python common_period.py --end 2026-09-30   # 지금 대시보드 기간
기간 끝을 늘리면 Chronos-2 예측이 그만큼 더 필요하다. 저장본(chronos_preds.csv)은 2026-09-30 까지이므로
모자란 날만 따로 예측해 task2_interval/results/chronos_preds_ext.csv 에 저장한다(인터넷·torch·chronos-forecasting 필요).
그게 안 되는 환경이면 Chronos 가 있는 마지막 날까지만 계산하고 표에 실제 기간을 적는다.
설정(앙상블 가중치·등각 보정값·방향 넓히기 배율·위험 시각 폭)은 모두 2025년에서 정한 값 그대로 — 시험 기간을 보고 바꾸지 않음.
"""
import os, sys, argparse, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'task2_interval'))
import task2_interval as T, hour_ranges as H, day_features as DF

KU, KD, HOURS, X = 2.0, 1.7, [10, 11, 15, 16], 67.8
W = {'q10': (0.15, 0.85, 0), 'q50': (0.15, 0.8, 0.05), 'q90': (0.25, 0.75, 0)}


def 크로노스(d, start, end):
    ch = pd.read_csv(os.path.join(T.RES_DIR, 'chronos_preds.csv'), encoding='utf-8-sig'); ch['date'] = ch['date'].astype(str).str[:10]
    ext = os.path.join(T.RES_DIR, 'chronos_preds_ext.csv')
    have = set(ch['date'])
    need = [x for x in pd.date_range(start, end).strftime('%Y-%m-%d') if x not in have]
    if need:
        try:
            e = T.chronos_예측(d, need[0], need[-1], 'amazon/chronos-2', ext, T.CHRONOS_REVISION['amazon/chronos-2'])
            e['date'] = e['date'].astype(str).str[:10]; ch = pd.concat([ch, e], ignore_index=True)
        except Exception as ex:
            print(f'  · Chronos-2 추가 예측 불가 ({type(ex).__name__}) — Chronos 가 있는 날까지만 계산')
    return ch.drop_duplicates(['date', 'hour_n', 'mode'])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--end', default='2026-10-02'); a = ap.parse_args()
    d, f = T.데이터_준비()
    lg_cal = T.lgbm_분위수(f, T.TRAIN_END, T.CAL_START, T.CAL_END)
    lg_test = T.lgbm_분위수(f, T.CAL_END, T.TEST_START, a.end)
    ch = 크로노스(d, T.TEST_START, a.end)
    last = min(a.end, ch['date'].max())

    def 합치기(lg, s, e):
        b = f[(f['date'] >= s) & (f['date'] <= e)][['date', 'hour_n', 'smp_land', 'naive', 'offday']].rename(columns={'smp_land': 'y'})
        b = b.merge(lg.rename(columns={c: f'lgb_{c}' for c in ('q10', 'q50', 'q90')}), on=['date', 'hour_n'])
        for m in ('cov', 'uni'):
            c = ch[ch['mode'] == m].drop(columns='mode')
            b = b.merge(c.rename(columns={q: f'chr_{m}_{q}' for q in ('q10', 'q50', 'q90')}), on=['date', 'hour_n'], how='inner')
        b['group'] = b['hour_n'].astype(str).str.zfill(2) + '시_' + np.where(b['offday'] == 1, '휴일', '평일')
        return b.reset_index(drop=True)

    cal, test = 합치기(lg_cal, T.CAL_START, T.CAL_END), 합치기(lg_test, T.TEST_START, last)
    cf = cal.dropna(subset=['y']).reset_index(drop=True)
    cf['err'] = cf['y'] - cf['lgb_q50']; eq = cf.groupby('group')['err'].quantile([0.1, 0.9]).unstack()
    Lc, Mc, Uc = H.앙상블(cf, W); C = T.등각_보정값(cf, Lc, Uc, cf.group.values)
    _, g = DF.만들기()
    ch25 = (cf.y - cf.naive).dropna(); up, dn = np.quantile(ch25, .95), np.quantile(ch25, .05)

    b = test; gg = b['group']
    M = {'A 잔차 분위수': T.정리(b.lgb_q50 + gg.map(eq[0.1]).values, b.lgb_q50.values, b.lgb_q50 + gg.map(eq[0.9]).values),
         'B LightGBM 분위수': T.정리(b.lgb_q10.values, b.lgb_q50.values, b.lgb_q90.values),
         'C Chronos-2 + 수요예측': T.정리(b.chr_cov_q10.values, b.chr_cov_q50.values, b.chr_cov_q90.values),
         'D Chronos-2 단변량': T.정리(b.chr_uni_q10.values, b.chr_uni_q50.values, b.chr_uni_q90.values)}
    eL, eM, eU = H.앙상블(b, W); M['E 앙상블'] = (eL, eM, eU)
    fL, fM, fU = T.정리(eL - gg.map(C['하한_보정']).values, eM, eU + gg.map(C['상한_보정']).values); M['F 앙상블 + 등각 보정'] = (fL, fM, fU)
    L2, _, Ug = H.방향_넓히기(fL, fM, fU, b.naive.values, KU, KD)
    risk = ((b.date.map(g.offday) == 0) & b.hour_n.isin(HOURS)).values
    M['최종 (F + 방향 넓히기 + 위험 시각)'] = (L2, fM, np.where(risk, np.maximum(Ug, fU + X), Ug))

    y = b.y.values; nv = b.naive.values; ok = ~np.isnan(y); rg = np.where(y - nv >= up, '급등', np.where(y - nv <= dn, '급락', '일반'))
    rows = []
    for k, (L, Md, U) in M.items():
        den = np.maximum(y, 20.0); mae = np.nanmean(np.abs(Md - y)[ok])
        wk = (U - L) + 20 * (L - y) * (y < L) + 20 * (y - U) * (y > U)
        rows.append({'방법': k, '평가 기간': f'{T.TEST_START} ~ {last}', '시간': int(ok.sum()),
                     'MAE': round(mae, 2), 'rMAE': round(mae / np.nanmean(np.abs(nv - y)[ok & ~np.isnan(nv)]), 3),
                     'MAPE(%)': round(100 * np.mean((np.abs(Md - y) / den)[ok]), 2), '편의(%)': round(100 * np.mean(((Md - y) / den)[ok]), 2),
                     '범위 안(%)': round(100 * np.mean(((y >= L) & (y <= U))[ok]), 1), '평균 폭(원)': round(np.mean((U - L)[ok]), 2),
                     'Winkler': round(np.mean(wk[ok]), 1),
                     '급등 시간 놓침(%)': round(100 * np.mean((y > U)[ok & (rg == '급등')]), 1),
                     '급락 시간 놓침(%)': round(100 * np.mean((y < L)[ok & (rg == '급락')]), 1)})
    t = pd.DataFrame(rows)
    tag = last.replace('-', '')
    t.to_csv(os.path.join(HERE, 'results', f'47_공통기간_비교표_{tag}.csv'), index=False, encoding='utf-8-sig')
    o = t.copy()
    for c, fm in (('MAE', '{:.2f}'), ('rMAE', '{:.3f}'), ('MAPE(%)', '{:.2f}'), ('편의(%)', '{:.2f}'), ('범위 안(%)', '{:.1f}'),
                  ('평균 폭(원)', '{:.2f}'), ('Winkler', '{:.1f}'), ('급등 시간 놓침(%)', '{:.1f}'), ('급락 시간 놓침(%)', '{:.1f}')):
        o[c] = o[c].map(fm.format)
    o.to_csv(os.path.join(HERE, 'dash_export', 'common_period.csv'), index=False, encoding='utf-8')
    pd.set_option('display.width', 250); print(t.to_string(index=False))
    return t


if __name__ == '__main__':
    main()
