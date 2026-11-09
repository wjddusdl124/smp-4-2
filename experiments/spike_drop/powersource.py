# -*- coding: utf-8 -*-
"""powersource.py — 전력거래소 발전원별 실시간(5분) 엑셀을 시간 단위로 합치기
   시간 표기: 5분 값의 끝 시각 기준 → SMP 거래시간(1~24, 끝점 표기)과 맞춤"""
import glob, os, numpy as np, pandas as pd
EXT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'external')
def 시간별():
    fr = []
    for f in sorted(glob.glob(os.path.join(EXT, 'powersource', '*.xlsx'))):
        d = pd.read_excel(f, header=1); d.columns = [str(c).strip() for c in d.columns]; fr.append(d)
    a = pd.concat(fr).drop_duplicates(subset=['날짜', '시간'])
    num = [c for c in a.columns if c not in ('날짜', '시간')]
    for c in num: a[c] = pd.to_numeric(a[c], errors='coerce')
    ts = pd.to_datetime(a['날짜'].astype(str) + ' ' + a['시간'].astype(str)) - pd.Timedelta(minutes=5)
    a['date'] = ts.dt.strftime('%Y-%m-%d'); a['hour_n'] = ts.dt.hour + 1
    a['solar_all'] = a[['태양광(BTM,추정)', '태양광(PPA,추정)', '태양광(전력시장)']].sum(axis=1)
    a['coal'] = a[['석탄', '유연탄', '국내탄']].sum(axis=1, min_count=1)
    a['total'] = a[num].sum(axis=1)
    h = a.groupby(['date', 'hour_n'])[['원자력', 'coal', '가스', 'solar_all', '태양광(전력시장)', '풍력', '양수', 'total']].mean().reset_index()
    h['need'] = h['total'] - h['원자력'] - h['coal'] - h['solar_all'] - h['풍력'].fillna(0)
    return h
if __name__ == '__main__':
    h = 시간별(); h.to_csv(os.path.join(EXT, 'powersource_hourly.csv'), index=False, encoding='utf-8-sig')
    print(h.date.nunique(), h.date.min(), h.date.max(), h.groupby('date').size().lt(24).sum(), '일 24시간 미만')
