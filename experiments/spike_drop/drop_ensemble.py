# -*- coding: utf-8 -*-
"""
drop_ensemble.py — 급락일 경보 : 여러 모델을 함께 써서 탐지율 75~85% 를 적은 경보로 달성할 수 있나
규칙
  · 학습 ~2024 → 2025 예측 : 모델 선택·경보 문턱 결정 (탐지율 목표 80% 를 넘는 가장 높은 확률)
  · 학습 ~2025 → 2026.1~9 예측 : 같은 문턱으로 1회 평가
  · 입력은 D-1 운영 변수(day_features.OPER)만
"""
import os, sys, warnings
import numpy as np, pandas as pd
import lightgbm as lgb, xgboost as xgb
from catboost import CatBoostClassifier
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import day_features as DF
from drop_models import SMALL

FE = DF.OPER
TARGET = 0.80
SEEDS = (9, 19, 29)


def _avg(make, tr, te, feats, impute=False):
    X, Xt = tr[feats], te[feats]
    if impute:
        med = X.median(); X, Xt = X.fillna(med), Xt.fillna(med)
    p = np.zeros(len(te))
    for sd in SEEDS:
        m = make(sd); m.fit(X, tr["drop"]); p += m.predict_proba(Xt)[:, 1] / len(SEEDS)
    return p


MODELS = {
    "LightGBM": lambda tr, te: _avg(lambda s: lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=7,
        min_child_samples=10, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=s, verbose=-1), tr, te, FE),
    "XGBoost": lambda tr, te: _avg(lambda s: xgb.XGBClassifier(n_estimators=300, learning_rate=0.03, max_depth=3,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=2, random_state=s, verbosity=0), tr, te, FE),
    "CatBoost": lambda tr, te: _avg(lambda s: CatBoostClassifier(iterations=400, learning_rate=0.03, depth=4,
        random_seed=s, verbose=0), tr, te, FE),
    "RandomForest": lambda tr, te: _avg(lambda s: RandomForestClassifier(n_estimators=500, min_samples_leaf=3,
        max_features=0.3, random_state=s, n_jobs=-1), tr, te, FE, impute=True),
    "ExtraTrees": lambda tr, te: _avg(lambda s: ExtraTreesClassifier(n_estimators=500, min_samples_leaf=3,
        max_features=0.3, random_state=s, n_jobs=-1), tr, te, FE, impute=True),
    "로지스틱": lambda tr, te: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
        LogisticRegression(C=0.3, max_iter=3000)).fit(tr[SMALL], tr["drop"]).predict_proba(te[SMALL])[:, 1],
}


def 문턱(p, y, target):
    pos = np.sort(p[y == 1])[::-1]
    return pos[int(np.ceil(target * len(pos))) - 1]


def 성적(p, y, thr):
    a = p >= thr; tp = int((a & (y == 1)).sum())
    return {"잡은일수": f"{tp}/{int(y.sum())}", "탐지율(%)": round(100 * tp / y.sum(), 1),
            "경보일수": int(a.sum()), "경보적중률(%)": round(100 * tp / max(1, a.sum()), 1)}


def 필요경보(p, y, target):
    """탐지율 target 을 달성하려면 확률 상위 몇 일에 경보를 내야 하나"""
    o = np.argsort(-p); c = np.cumsum(y[o]); need = int(np.ceil(target * y.sum()))
    return int(np.argmax(c >= need) + 1)


def main():
    _, g = DF.만들기()
    P = {}
    for tag, tr_end, s, e in (("2025", "2024-12-31", "2025-01-01", "2025-12-31"),
                              ("2026", "2025-12-31", "2026-01-01", "2026-09-30")):
        tr = g[(g.index <= tr_end) & g["drop"].notna()]
        te = g[(g.index >= s) & (g.index <= e) & g["drop"].notna()]
        P[tag] = {"y": te["drop"].values.astype(int), "idx": te.index}
        for nm, fn in MODELS.items():
            P[tag][nm] = np.asarray(fn(tr, te)); print(f"  · {tag} {nm} 완료", flush=True)

    names = list(MODELS)
    ap25 = {n: average_precision_score(P["2025"]["y"], P["2025"][n]) for n in names}
    top3 = sorted(names, key=lambda n: -ap25[n])[:3]
    ens = {"앙상블: 전체 6개 평균": names, f"앙상블: 2025 상위3 평균({'+'.join(top3)})": top3,
           "앙상블: 부스팅3 평균(LGB+XGB+Cat)": ["LightGBM", "XGBoost", "CatBoost"]}
    for tag in P:
        for en, mem in ens.items():
            P[tag][en] = np.mean([P[tag][m] for m in mem], axis=0)

    rows = []
    for nm in names + list(ens):
        y25, y26 = P["2025"]["y"], P["2026"]["y"]
        thr = 문턱(P["2025"][nm], y25, TARGET)
        rows.append({"모델": nm,
                     "2025 PR-AUC": round(average_precision_score(y25, P["2025"][nm]), 3),
                     "2025 80% 탐지 필요 경보일": 필요경보(P["2025"][nm], y25, TARGET),
                     "2026 PR-AUC": round(average_precision_score(y26, P["2026"][nm]), 3),
                     "2026 80% 탐지 필요 경보일": 필요경보(P["2026"][nm], y26, TARGET),
                     **{f"2026 {k}": v for k, v in 성적(P["2026"][nm], y26, thr).items()}})
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(HERE, "results", "28_급락_앙상블_비교.csv"), index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 250); print(res.to_string(index=False))
    # 탐지율-경보일 곡선 (2026, 2025 선택 모델 + LightGBM)
    pd.to_pickle(P, os.path.join(HERE, "results", "_drop_probs.pkl"))


if __name__ == "__main__":
    main()
