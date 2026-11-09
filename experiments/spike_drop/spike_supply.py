# -*- coding: utf-8 -*-
"""
spike_supply.py — 공개 「일별 전력수급실적」(공급능력·예비력)으로 급등일 예측이 나아지나
==============================================================================
데이터 : HOME_전력수급_전력수급실적 (전력거래소, 2023-01-01~2026-10-30, 일별)
         설비용량, 공급능력, 최대전력, 공급예비력, 공급예비율, 최대전력 시각  (중복 10일은 제거)
D-1 에 쓸 수 있는 변수만 사용 (실적은 하루 늦게 앎)
  · 예상예비율 = (전날 공급능력 − 내일 수요예측 최대) / 내일 수요예측 최대   ← 공급능력은 하루 사이 거의 같음
  · 전날 예비율, 전날 공급능력, 공급능력 지난주 대비 변화, 전날 공급능력 / 설비용량
분석용 상한 : 당일 실제 예비율(운영 불가)

급등일 : 그날 최고 SMP ≥ 직전 28일 일 최고 SMP 중앙값 × 1.25
규칙   : 학습 2023-01-08~2024 → 2025 평가로 선택 / 학습 ~2025 → 2026.1~9 확인
모델   : 로지스틱 회귀(지난 급등 실험에서 2025 점수 최고) + LightGBM·XGBoost·CatBoost 평균(비교)
"""
import os, sys, warnings
import numpy as np, pandas as pd, lightgbm as lgb, xgboost as xgb
from catboost import CatBoostClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import day_features as DF
from spike_prob import FEATS as BASE

SRC = os.path.join(os.path.dirname(os.path.dirname(HERE)), "data", "external", "supply_daily_raw.csv")
SUP = ["exp_reserve_pct", "exp_reserve", "reserve_pct_d1", "supply_d1", "supply_chg_w1", "supply_cap_ratio_d1"]
ORACLE = ["reserve_pct", "reserve"]


def 수급():
    s = pd.read_csv(SRC, encoding="cp949").drop_duplicates()
    s["date"] = pd.to_datetime(dict(year=s["년"], month=s["월"], day=s["일"])).dt.strftime("%Y-%m-%d")
    s = s.rename(columns={"설비용량(MW)": "cap", "공급능력(MW)": "supply", "최대전력(MW)": "peak",
                          "공급예비력(MW)": "reserve", "공급예비율(%)": "reserve_pct"})
    return s.set_index("date").sort_index()[["cap", "supply", "peak", "reserve", "reserve_pct"]]


def 변수():
    _, g = DF.만들기()
    s = 수급().reindex(g.index)
    x = g.join(s)
    x["exp_reserve"] = x["supply"].shift(1) - x["f_max"]
    x["exp_reserve_pct"] = x["exp_reserve"] / x["f_max"] * 100
    x["reserve_pct_d1"] = x["reserve_pct"].shift(1)
    x["supply_d1"] = x["supply"].shift(1)
    x["supply_chg_w1"] = x["supply"].shift(1) - x["supply"].shift(8)
    x["supply_cap_ratio_d1"] = (x["supply"] / x["cap"]).shift(1)
    return x[x.index >= "2023-01-08"]


def 로지스틱(tr, te, f):
    m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=0.3, max_iter=3000))
    m.fit(tr[f], tr["spike"]); return m.predict_proba(te[f])[:, 1]


def 부스팅3(tr, te, f):
    ps = []
    for sd in (9, 19, 29):
        a = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=5, min_child_samples=20, subsample=0.8,
                               subsample_freq=1, colsample_bytree=0.8, random_state=sd, verbose=-1).fit(tr[f], tr["spike"])
        b = xgb.XGBClassifier(n_estimators=200, learning_rate=0.03, max_depth=2, subsample=0.8, colsample_bytree=0.8,
                              random_state=sd, verbosity=0).fit(tr[f], tr["spike"])
        c = CatBoostClassifier(iterations=300, learning_rate=0.03, depth=3, random_seed=sd, verbose=0).fit(tr[f], tr["spike"])
        ps.append((a.predict_proba(te[f])[:, 1] + b.predict_proba(te[f])[:, 1] + c.predict_proba(te[f])[:, 1]) / 3)
    return np.mean(ps, axis=0)


def 필요경보(p, y, t):
    o = np.argsort(-p); c = np.cumsum(y[o]); return int(np.argmax(c >= np.ceil(t * y.sum())) + 1)


def 첫급등(idx, g):
    """전날이 급등이 아니었던 급등일 (처음 터지는 급등)"""
    prev = g["spike"].shift(1).reindex(idx).fillna(0)
    return (prev == 0).values


def main():
    x = 변수()
    sets = {"기존 변수": BASE, "기존 + 공급(D-1)": BASE + SUP, "기존 + 공급 + 당일 예비율(분석용 상한)": BASE + SUP + ORACLE}
    rows, keep = [], {}
    for tag, tr_end, s, e in (("2025", "2024-12-31", "2025-01-01", "2025-12-31"), ("2026", "2025-12-31", "2026-01-01", "2026-09-30")):
        tr = x[(x.index <= tr_end) & x["spike"].notna()]
        te = x[(x.index >= s) & (x.index <= e) & x["spike"].notna()]
        y = te["spike"].values.astype(int)
        first = 첫급등(te.index, x) & (y == 1)
        for mn, fn in (("로지스틱", 로지스틱), ("LGB·XGB·Cat 평균", 부스팅3)):
            for sn, f in sets.items():
                p = np.asarray(fn(tr, te, f)); keep[(tag, mn, sn)] = pd.Series(p, te.index)
                rk = pd.Series(p, te.index).rank(ascending=False)
                rows.append({"기간": tag, "모델": mn, "변수": sn, "PR-AUC": round(average_precision_score(y, p), 3),
                             "AUC": round(roc_auc_score(y, p), 3),
                             "급등일 확률 순위(1=가장 높음)": " ".join(str(int(v)) for v in sorted(rk[y == 1])),
                             "모두 잡는 데 필요한 경보일": 필요경보(p, y, 1.0), "절반 잡는 데 필요한 경보일": 필요경보(p, y, 0.5),
                             "처음 터진 급등 순위": " ".join(str(int(v)) for v in sorted(rk[first]))})
    r = pd.DataFrame(rows)
    r.to_csv(os.path.join(HERE, "results", "34_급등_공급데이터_비교.csv"), index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    print(r.to_string(index=False))
    pd.to_pickle(keep, os.path.join(HERE, "results", "_spike_supply_probs.pkl"))


if __name__ == "__main__":
    main()
