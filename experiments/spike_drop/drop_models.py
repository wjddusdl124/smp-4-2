# -*- coding: utf-8 -*-
"""
drop_models.py — 급락일 예측 모델 후보 비교
규칙: 학습 ~2024 → 2025 평가로 모델 선택 / 학습 ~2025 → 2026.1~9 평가(참고, 선택에 쓰지 않음)
모두 D-1 에 알 수 있는 변수만 사용 (WX 묶음은 실측 기온·강수를 예보 대신 넣은 낙관적 버전)
"""
import os, sys
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, brier_score_loss

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import day_features as DF

SMALL = ["offday", "prev_offday", "next_offday", "off_run_len", "y_mean", "f_min_r28", "y_mid_min_r",
         "f_ramp_7_10", "f_mid", "net_mid_proxy", "net_mid_r", "ref_min_lvl", "y_min_r", "min7_r",
         "drop_cnt7", "drop_cnt28", "doy_cos", "doy_sin"]
P_LGB = dict(n_estimators=300, learning_rate=0.03, num_leaves=7, min_child_samples=10, subsample=0.8,
             subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1)


def 규칙(tr, te):
    """휴일 × 한낮 수요예측(평소 대비) 4분위 칸별 과거 발생률을 그대로 확률로"""
    q = tr["f_min_r28"].quantile([.25, .5, .75]).values
    cell = lambda x: x["offday"].astype(int).astype(str) + "_" + np.digitize(x["f_min_r28"].fillna(1), q).astype(str)
    rate = tr.groupby(cell(tr))["drop"].mean()
    return cell(te).map(rate).fillna(tr["drop"].mean()).values


def 로지스틱(tr, te, feats):
    m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=0.3, max_iter=3000))
    m.fit(tr[feats], tr["drop"]); return m.predict_proba(te[feats])[:, 1]


def lgbm(tr, te, feats, off_only=False):
    p = np.zeros(len(te))
    for sd in (9, 19, 29, 39, 49):
        m = lgb.LGBMClassifier(random_state=sd, **P_LGB); m.fit(tr[feats], tr["drop"])
        p += m.predict_proba(te[feats])[:, 1] / 5
    return p


MODELS = {
    "A 규칙(휴일×수요 칸별 발생률)": lambda tr, te: 규칙(tr, te),
    "B 로지스틱(핵심 18개)": lambda tr, te: 로지스틱(tr, te, SMALL),
    "C LightGBM(운영 전체)": lambda tr, te: lgbm(tr, te, DF.OPER),
    "D LightGBM(휴일만 학습)": None,
    "E LightGBM(운영+기온·강수, 낙관)": lambda tr, te: lgbm(tr, te, DF.OPER + DF.WX),
}


def 평가(p, y, k_list=(20, 30, 40)):
    o = np.argsort(-p); yy = y.values[o]
    r = {"PR-AUC": round(average_precision_score(y, p), 3), "Brier": round(brier_score_loss(y, p), 4)}
    for k in k_list:
        r[f"상위{k}일 탐지"] = f"{int(yy[:k].sum())}/{int(y.sum())}"
    return r


def main():
    _, g = DF.만들기()
    rows = []
    for tag, tr_end, s, e in (("2025(선택용)", "2024-12-31", "2025-01-01", "2025-12-31"),
                              ("2026(참고)", "2025-12-31", "2026-01-01", "2026-09-30")):
        tr = g[(g.index <= tr_end) & g["drop"].notna()]
        te = g[(g.index >= s) & (g.index <= e) & g["drop"].notna()]
        for name, fn in MODELS.items():
            if name.startswith("D"):
                p = np.zeros(len(te)); off = te["offday"] == 1
                p[off.values] = lgbm(tr[tr.offday == 1], te[off], DF.OPER)
            else:
                p = fn(tr, te)
            rows.append({"기간": tag, "모델": name, **평가(np.asarray(p), te["drop"])})
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(HERE, "results", "25_급락모델_비교.csv"), index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200); print(res.to_string(index=False))


if __name__ == "__main__":
    main()
