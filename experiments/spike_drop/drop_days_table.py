# -*- coding: utf-8 -*-
"""drop_days_table.py — 2026 급락일 하나하나 표 (급등일 표와 같은 모양으로) : drop_daily.csv 에서 만듦"""
import os, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dash_export')
d = pd.read_csv(os.path.join(OUT, 'drop_daily.csv'))
K = dict(zip('Mon Tue Wed Thu Fri Sat Sun'.split(), '월화수목금토일'))
x = d[d['실제'] == '급락'].copy()
t = pd.DataFrame({'date': x['date'], '요일': x['요일'].map(K), '구분': x['구분'],
                  '실제 최저가': x['실제최저가'].round(1), '급락 기준가': (x['기준최저가'] / 2).round(1),
                  '하루 전 확률(%)': x['급락확률(%)'], '하루 전 경보': (x['경보'] == '경보').map({True: '예', False: '아니오'})})
t['대비 결과'] = t['하루 전 경보'].map({'예': '잡음', '아니오': '놓침'})
t.to_csv(os.path.join(OUT, 'drop_days_final.csv'), index=False, encoding='utf-8')
print(t.to_string(index=False))
