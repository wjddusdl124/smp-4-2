# -*- coding: utf-8 -*-
"""
spike_prob.py — 급등일 「확률 경보」 : 확률이 몇 % 이상이면 경보를 낼까
규칙: 학습 ~2024 → 2025 로 모델·문턱 선택 / 학습 ~2025 → 2026.1~9 확인
확률은 class weight 없이 학습해 「실제 발생 빈도」에 맞도록 함 (보정 확인: 2025 Brier·구간별 실제 발생률)
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

FEATS = ["offday", "prev_offday", "dow", "doy_sin", "doy_cos", "f_ramp_7_10", "f_max_r28", "f_max_d1",
         "f_h10", "net_mid_proxy", "spike_cnt7", "spike_cnt28", "y_max_r", "max7_r", "y_h10_r", "ref_max"]
THRS = [0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30]


def 점수표(tr, te):
    """평일 + 조건 개수(아침 수요증가 상위25%, 수요 평소대비 상위25%, 최근7일 급등) 칸별 과거 발생률"""
    r75, f75 = tr["f_ramp_7_10"].quantile(.75), tr["f_max_r28"].quantile(.75)
    sc = lambda x: np.where(x["offday"] == 1, -1, (x["f_ramp_7_10"] >= r75).astype(int)
                            + (x["f_max_r28"] >= f75).astype(int) + (x["spike_cnt7"] >= 1).astype(int))
    rate = tr.assign(s=sc(tr)).groupby("s")["spike"].mean()
    return pd.Series(sc(te)).map(rate).fillna(tr["spike"].mean()).values


def 로지스틱(tr, te):
    m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=0.3, max_iter=3000))
    m.fit(tr[FEATS], tr["spike"]); return m.predict_proba(te[FEATS])[:, 1]


def lgbm(tr, te):
    p = np.zeros(len(te))
    for sd in (9, 19, 29, 39, 49):
        m = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=5, min_child_samples=20,
                               subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=sd, verbose=-1)
        m.fit(tr[FEATS], tr["spike"]); p += m.predict_proba(te[FEATS])[:, 1] / 5
    return p


MODELS = {"점수표": 점수표, "로지스틱": 로지스틱, "LightGBM": lgbm}


def 표(p, y):
    rows = []
    for t in THRS:
        a = p >= t; tp = int((a & (y == 1)).sum())
        rows.append({"문턱": f"{int(t*100)}%", "경보일수": int(a.sum()), "잡은 급등일": f"{tp}/{int(y.sum())}",
                     "적중률(%)": round(100 * tp / max(1, a.sum()), 1)})
    return pd.DataFrame(rows)


def main():
    _, g = DF.만들기()
    pd.set_option("display.width", 200)
    out = []
    for start in ("2021-01-01", "2023-01-01"):
        for tag, tr_end, s, e in (("2025", "2024-12-31", "2025-01-01", "2025-12-31"),
                                  ("2026", "2025-12-31", "2026-01-01", "2026-09-30")):
            tr = g[(g.index >= start) & (g.index <= tr_end) & g["spike"].notna()]
            te = g[(g.index >= s) & (g.index <= e) & g["spike"].notna()]
            y = te["spike"].values
            for nm, fn in MODELS.items():
                p = np.asarray(fn(tr, te))
                print(f"\n■ 학습시작 {start[:4]} · {nm} · {tag}  PR-AUC {average_precision_score(y, p):.3f}  "
                      f"Brier {brier_score_loss(y, p):.4f}  평균확률 {100*p.mean():.1f}% (실제 {100*y.mean():.1f}%)  최대확률 {100*p.max():.1f}%")
                t = 표(p, y); print(t.to_string(index=False))
                out.append(t.assign(학습시작=start[:4], 모델=nm, 기간=tag))
                if nm == "점수표" and start == "2023-01-01":
                    pd.DataFrame({"date": te.index, "확률": p, "급등": y}).to_csv(
                        os.path.join(HERE, "results", f"27_급등확률_점수표_{tag}.csv"), index=False, encoding="utf-8-sig")
    pd.concat(out).to_csv(os.path.join(HERE, "results", "26_급등경보_문턱표.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
