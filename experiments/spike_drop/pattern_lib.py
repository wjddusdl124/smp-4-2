import pandas as pd,numpy as np,day_features as DF
d,g=DF.만들기()
Y=d.pivot(index='date',columns='hour_n',values='smp_land')
S=d.pivot(index='date',columns='hour_n',values='solar_land')
PV=d.pivot(index='date',columns='hour_n',values='pv_land')
F=d.pivot(index='date',columns='hour_n',values='demand_fcst_land')
T=d.pivot(index='date',columns='hour_n',values='temp_land')
g['solar_day']=S[list(range(9,18))].sum(axis=1)
g['solar_r']=g.solar_day/g.solar_day.shift(1).rolling(60,min_periods=30).median()
g['pv_share_mid']=PV[[11,12,13,14,15]].mean(axis=1)/F[[11,12,13,14,15]].mean(axis=1)
g['t_h10']=T[10]
g['yr']=g.index.str[:4]
g['season']=g.month.map({12:'겨울',1:'겨울',2:'겨울',3:'봄',4:'봄',5:'봄',6:'여름',7:'여름',8:'여름',9:'가을',10:'가을',11:'가을'})
def lift(sub,tgt,col,bins=None,labels=None,q=None):
    x=sub[[col,tgt]].dropna()
    if q: x['b']=pd.qcut(x[col],q,duplicates='drop')
    elif bins is not None: x['b']=pd.cut(x[col],bins,labels=labels)
    else: x['b']=x[col]
    base=x[tgt].mean()
    t=x.groupby('b',observed=True)[tgt].agg(['sum','count','mean'])
    t['배수']=(t['mean']/base).round(2); t['발생률%']=(100*t['mean']).round(1)
    return t[['sum','count','발생률%','배수']].rename(columns={'sum':'발생','count':'일수'})
