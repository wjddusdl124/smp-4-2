# 대시보드용 데이터셋 만들기 — 모두 results/ 와 같은 계산에서 나온 값
import numpy as np, pandas as pd, hour_ranges as H, task2_interval as T, day_features as DF, os
O='dash_export'
# 1) 급락 일별
o=pd.read_csv('results/30_급락경보_2026_일별.csv'); o=o[o.date<='2026-09-30'].copy()
o['단계']=np.where(o['경보(75%기준)'],'경계',np.where(o['경보(90%기준)'],'주의',''))
o['실제']=o['실제_급락'].map({1.0:'급락',0.0:'-'}).fillna('데이터없음')
dd=pd.DataFrame({'date':o.date,'요일':o['요일'],'구분':o['휴일'].map({1:'휴일',0:'평일'}),'급락확률(%)':(100*o['급락확률']).round(2),
  '경보단계':o['단계'],'실제최저가':o['실제_최저가'].round(2),'기준최저가':o['기준_28일최저중앙'],'실제':o['실제']})
dd.to_csv(f'{O}/drop_daily.csv',index=False,encoding='utf-8')
# 2) 급락 성적
r=pd.read_csv('results/31_급락경보_최종성적.csv')
pr=pd.DataFrame({'목표':r['2025 목표 탐지율'],'2025 잡은 날':r['2025 잡은일수'],'2025 경보일':r['2025 경보일수'],
  '2026 잡은 날':r['2026 잡은일수'],'2026 탐지율(%)':r['2026 탐지율(%)'],'2026 경보일':r['2026 경보일수'],'2026 적중률(%)':r['2026 경보적중률(%)']})
pr.to_csv(f'{O}/drop_perf.csv',index=False,encoding='utf-8')
# 3) 급등일 피크 (standing_buffer 와 같은 계산)
d,g=DF.만들기(); Y=d.pivot(index='date',columns='hour_n',values='smp_land'); pk=Y.fillna(-1).idxmax(axis=1)
sd=g[(g.spike==1)&(g.index>='2023-01-01')&(g.index<='2025-12-31')].index
hours=sorted(pk[sd].value_counts().index[:4].tolist())
cal,test=H.구성요소()
W={'q10':(0.15,0.85,0),'q50':(0.15,0.8,0.05),'q90':(0.25,0.75,0)}
cf=cal.dropna(subset=['y']).reset_index(drop=True); Lc,Mc,Uc=H.앙상블(cf,W); C=T.등각_보정값(cf,Lc,Uc,cf.group.values)
def bo(b):
    L,M,U=H.앙상블(b,W); gg=b.group; return T.정리(L-gg.map(C['하한_보정']).values,M,U+gg.map(C['상한_보정']).values)
L,M,U=bo(cal); c=cal.assign(L=L,U=U)
X=max(0,c[c.date.isin(g[g.spike==1].index)&c.hour_n.isin(hours)].eval('y-U').max())
L,M,U=bo(test); t=test.assign(L=L,U=U); t['wk']=t.date.map(g.offday)==0
m=t.hour_n.isin(hours)&t.wk; t['U2']=np.where(m,t.U+X,t.U)
sp=t[t.date.isin(g[g.spike==1].index)].sort_values('y').groupby('date').tail(1).sort_values('date')
spk=pd.DataFrame({'date':sp.date,'최고가 시각':sp.hour_n.astype(int),'실제 최고가':sp.y.round(1),'기존 상한':sp.U.round(1),
  '대책 상한':sp.U2.round(1),'결과':np.where(sp.y<=sp.U2,'포함','놓침')})
spk.to_csv(f'{O}/spike_peaks.csv',index=False,encoding='utf-8')
ok=t.y.notna()
# 4) 대책 효과 요약
h=pd.read_csv('results/24_급변시간_범위_비교.csv'); f=h[(h['기간']=='시험 2026')].set_index('방법')
P=g[(g.index>='2023-01-01')&(g.index<='2026-09-30')&(g.offday==0)]; prev=g.spike.shift(1).reindex(P.index)
rows=[
 {'항목':'급등일 최고가가 범위 안에 든 날 (2026)','기존':f"{int((sp.y<=sp.U).sum())}/{len(sp)}",'대책 후':f"{int((sp.y<=sp.U2).sum())}/{len(sp)}",'대책':f"평일 {'·'.join(str(h) for h in hours)}시 상한 +{X:.1f}원"},
 {'항목':'평균 범위 폭(원, 2026)','기존':f"{(t.U-t.L)[ok].mean():.2f}",'대책 후':f"{(t.U2-t.L)[ok].mean():.2f}",'대책':'위험 시각 상시 확대만 적용'},
 {'항목':'급등 시간 놓침(%, 2026)','기존':f"{f.loc['F 현재 최종','급등 놓침(%)']:.1f}",'대책 후':f"{f.loc['G1 F+방향 넓히기','급등 놓침(%)']:.1f}",'대책':'예측 방향 쪽만 범위 넓히기'},
 {'항목':'급락 시간 놓침(%, 2026)','기존':f"{f.loc['F 현재 최종','급락 놓침(%)']:.1f}",'대책 후':f"{f.loc['G1 F+방향 넓히기','급락 놓침(%)']:.1f}",'대책':'예측 방향 쪽만 범위 넓히기'},
 {'항목':'평일 급등 확률(2023~2026.9)','기존':f"{100*P.spike[prev==0].mean():.1f}% (전날 급등 없음)",'대책 후':f"{100*P.spike[prev==1].mean():.1f}% (전날 급등)",'대책':'전날 급등 시 연속 급등 경계'},
]
cb=pd.read_csv('results/33_최종결합_2026.csv').set_index('방법'); a0=cb.loc['기존 F']; a1=cb.loc['G1 + 10·11·15·16시']
for k,lab in [('급등 시간 놓침(%)','[모두 적용] 급등 시간 놓침(%, 2026)'),('급락 시간 놓침(%)','[모두 적용] 급락 시간 놓침(%, 2026)'),('평균 폭(원)','[모두 적용] 평균 범위 폭(원, 2026)'),('전체 커버리지(%)','[모두 적용] 범위 안에 든 비율(%, 2026)')]:
    rows.append({'항목':lab,'기존':f"{a0[k]}",'대책 후':f"{a1[k]}",'대책':'방향 넓히기 + 평일 10·11·15·16시 상한 확대'})
pd.DataFrame(rows).to_csv(f'{O}/spike_actions.csv',index=False,encoding='utf-8')
for fn in os.listdir(O): print(fn); print(open(f'{O}/{fn}').read()[:600])
