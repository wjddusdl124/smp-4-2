# -*- coding: utf-8 -*-
"""
day_alarm.py — D-1 급등일·급락일 경보 모델 (LightGBM 이진 분류)
==============================================================================
규칙 (task2 와 같음)
  · 학습 2021~2024 → 2025 예측 : 경보 기준값(확률 문턱)을 여기서만 정함
  · 학습 2021~2025 → 2026.1.1~9.30 예측 : 기준값 그대로 1회 평가
  · 문턱 = 2025년에 급등(급락)일을 목표 비율 이상 잡는 가장 높은 확률
      - 급등 85% (7일 중 6일 이상), 급락 85% (19일 중 17일 이상)
  · 모델 설정은 미리 고정(시험 결과를 보고 바꾸지 않음)

비교하는 변수 묶음 (day_features.py)
  ① 운영     : 지금 D-1 에 확보 가능한 값만
  ② +기상예보 : ① + 기온·강수 (단기예보 항목을 실측으로 대신 → 낙관적)
  ③ +실측상한 : ② + 일사·태양광·풍력·수요 실적 (지금은 D-1 에 알 수 없음 → 분석 전용 상한)
"""
import os
import sys

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import day_features as DF

OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)

TEST_END = "2026-09-30"
TARGET_RECALL = 0.85
SEEDS = [9, 19, 29, 39, 49]
PARAMS = dict(n_estimators=300, learning_rate=0.03, num_leaves=7, min_child_samples=10,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1)
SETS = {"① 운영": DF.OPER, "② +기상예보(낙관)": DF.OPER + DF.WX,
        "③ +실측상한(분석용)": DF.OPER + DF.WX + DF.ORACLE}


def 학습_예측(g, feats, target, train_end, start, end):
    tr = g[(g.index <= train_end) & g[target].notna()]
    te = g[(g.index >= start) & (g.index <= end) & g[target].notna()]
    pos = tr[target].sum()
    p = np.zeros(len(te))
    for sd in SEEDS:
        m = lgb.LGBMClassifier(scale_pos_weight=(len(tr) - pos) / pos, random_state=sd, **PARAMS)
        m.fit(tr[feats], tr[target])
        p += m.predict_proba(te[feats])[:, 1] / len(SEEDS)
    imp = pd.Series(m.booster_.feature_importance("gain"), index=feats)
    return pd.Series(p, index=te.index), te[target], imp


def 문턱(p, y, target_recall):
    """target_recall 이상 잡는 가장 높은 문턱"""
    pos = np.sort(p[y == 1].values)[::-1]
    k = int(np.ceil(target_recall * len(pos)))
    return pos[k - 1]


def 성적(p, y, thr):
    a = p >= thr
    tp = int((a & (y == 1)).sum())
    return {"실제일수": int(y.sum()), "잡은일수": tp, "놓친일수": int(y.sum()) - tp,
            "탐지율(%)": round(100 * tp / max(1, y.sum()), 1), "경보일수": int(a.sum()),
            "경보적중률(%)": round(100 * tp / max(1, a.sum()), 1),
            "PR-AUC": round(average_precision_score(y, p), 3)}


def main():
    _, g = DF.만들기()
    rows, daily, imps = [], [], {}
    for target, name in (("spike", "급등일"), ("drop", "급락일")):
        for sname, feats in SETS.items():
            p25, y25, _ = 학습_예측(g, feats, target, "2024-12-31", "2025-01-01", "2025-12-31")
            thr = 문턱(p25, y25, TARGET_RECALL)
            p26, y26, imp = 학습_예측(g, feats, target, "2025-12-31", "2026-01-01", TEST_END)
            imps[(name, sname)] = imp
            for tag, p, y in (("보정 2025", p25, y25), ("시험 2026", p26, y26)):
                rows.append({"대상": name, "변수": sname, "기간": tag, "문턱": round(thr, 3), **성적(p, y, thr)})
            daily.append(pd.DataFrame({"date": p26.index, "대상": name, "변수": sname,
                                       "확률": p26.values, "실제": y26.values, "경보": p26.values >= thr}))
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(OUT, "21_경보_성적.csv"), index=False, encoding="utf-8-sig")
    pd.concat(daily).to_csv(os.path.join(OUT, "22_경보_일별_2026.csv"), index=False, encoding="utf-8-sig")
    imp = pd.DataFrame(imps)
    imp.to_csv(os.path.join(OUT, "23_변수중요도.csv"), encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    print(res.to_string(index=False))
    for k in (("급등일", "① 운영"), ("급락일", "① 운영"), ("급등일", "③ +실측상한(분석용)"), ("급락일", "③ +실측상한(분석용)")):
        s = imp[k].dropna()
        print("\n변수중요도", k, (s / s.sum() * 100).sort_values(ascending=False).head(8).round(1).to_dict())


if __name__ == "__main__":
    main()
