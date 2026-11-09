# -*- coding: utf-8 -*-
"""
drop_final.py — 지금 가진 데이터로 급락일을 최대한 잡는 최종 경보
==============================================================================
1) 개선 후보를 2025년(학습 ~2024)에서만 비교해 고른다
     V0 기존 앙상블(XGB+Cat+RF, 운영 변수)
     V1 V0 + 명절·연휴 위치·직전 급락 경과일 변수
     V2 V1 + 최근 연도 가중(2024년 이후 3배) — 급락이 2024년부터 잦아짐
2) 고른 설정으로 학습 ~2025 → 2026.1.1~9.30 1회 평가
   (11/2 부터 성적 채점은 기업 급락 정의 「11~15시 중 30원 미만」 — 모델·문턱은 그대로)
3) 경보 문턱 = 2025년 탐지율 90% / 95% 를 달성하는 확률 (탐지 우선)
4) 2026.10.1~10.6 (데이터 끝까지) 경보도 함께 출력 — 정답 확인 가능한 범위만
"""
import os, sys, warnings
import numpy as np, pandas as pd
import xgboost as xgb
from catboost import CatBoostClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import day_features as DF

SEEDS = (9, 19, 29)


def 변수_추가(d, g):
    hn = d.groupby("date")["holiday_name"].first().reindex(g.index)
    g["major_hol"] = hn.fillna("").str.contains("설날|추석").astype(int)
    off = g["offday"]
    blk = (off != off.shift()).cumsum()
    g["off_pos"] = off.groupby(blk).cumcount() + 1                      # 연휴 몇째 날
    g["off_pos"] = g["off_pos"].where(off == 1, 0)
    g["off_left"] = (g["off_run_len"] - g["off_pos"]).where(off == 1, 0)  # 연휴 남은 날
    last = g["drop"].shift(1).fillna(0)
    idx = np.arange(len(g)); lastpos = pd.Series(np.where(last == 1, idx, np.nan), index=g.index).ffill()
    g["days_since_drop"] = (idx - lastpos).clip(upper=120).fillna(120)
    return g


EXTRA = ["major_hol", "off_pos", "off_left", "days_since_drop"]


def 앙상블(tr, te, feats, w=None):
    X, Xt = tr[feats], te[feats]; med = X.median()
    ps = []
    for sd in SEEDS:
        m1 = xgb.XGBClassifier(n_estimators=300, learning_rate=0.03, max_depth=3, subsample=0.8,
                               colsample_bytree=0.8, min_child_weight=2, random_state=sd, verbosity=0)
        m1.fit(X, tr["drop"], sample_weight=w)
        m2 = CatBoostClassifier(iterations=400, learning_rate=0.03, depth=4, random_seed=sd, verbose=0)
        m2.fit(X, tr["drop"], sample_weight=w)
        m3 = RandomForestClassifier(n_estimators=500, min_samples_leaf=3, max_features=0.3, random_state=sd, n_jobs=-1)
        m3.fit(X.fillna(med), tr["drop"], sample_weight=w)
        ps.append((m1.predict_proba(Xt)[:, 1] + m2.predict_proba(Xt)[:, 1] + m3.predict_proba(Xt.fillna(med))[:, 1]) / 3)
    return np.mean(ps, axis=0)


def 문턱(p, y, t):
    pos = np.sort(p[y == 1])[::-1]; return pos[int(np.ceil(t * len(pos))) - 1]


def 필요경보(p, y, t):
    o = np.argsort(-p); c = np.cumsum(y[o]); return int(np.argmax(c >= np.ceil(t * y.sum())) + 1)


def 성적(p, y, thr):
    a = p >= thr; tp = int((a & (y == 1)).sum())
    return {"잡은일수": f"{tp}/{int(y.sum())}", "탐지율(%)": round(100 * tp / y.sum(), 1),
            "경보일수": int(a.sum()), "경보적중률(%)": round(100 * tp / max(1, a.sum()), 1)}


def main():
    d, g = DF.만들기()
    g = 변수_추가(d, g)
    V = {"V0 기존": (DF.OPER, False), "V1 +명절·연휴위치": (DF.OPER + EXTRA, False),
         "V2 +최근연도 가중": (DF.OPER + EXTRA, True)}
    tr = g[(g.index <= "2024-12-31") & g["drop"].notna()]
    te = g[(g.index >= "2025-01-01") & (g.index <= "2025-12-31") & g["drop"].notna()]
    y25 = te["drop"].values.astype(int)
    sel = []
    for nm, (fe, wt) in V.items():
        w = np.where(tr.index >= "2024-01-01", 3.0, 1.0) if wt else None
        p = 앙상블(tr, te, fe, w)
        sel.append({"후보": nm, "2025 PR-AUC": round(average_precision_score(y25, p), 3),
                    "90% 탐지 필요 경보일": 필요경보(p, y25, .9), "95% 탐지 필요 경보일": 필요경보(p, y25, .95), "_p": p})
        print(f"  · {nm} 완료", flush=True)
    S = pd.DataFrame(sel)
    best = S.sort_values(["90% 탐지 필요 경보일", "2025 PR-AUC"], ascending=[True, False]).iloc[0]
    print(S.drop(columns="_p").to_string(index=False)); print("  → 선택:", best["후보"])

    fe, wt = V[best["후보"]]
    p25 = best["_p"]
    tr2 = g[(g.index <= "2025-12-31") & g["drop"].notna()]
    te2 = g[(g.index >= "2026-01-01") & (g.index <= "2026-10-06")]
    w2 = np.where(tr2.index >= "2024-01-01", 3.0, 1.0) if wt else None
    p26 = pd.Series(앙상블(tr2, te2, fe, w2), te2.index)
    # 채점은 기업 정의(drop_corp)로 — 문턱은 위처럼 2025 우리 정의 급락의 75% 를 잡는 값 그대로
    test = te2[(te2.index <= "2026-09-30") & te2["drop_corp"].notna()]; y26 = test["drop_corp"].values.astype(int); pt = p26[test.index].values
    okc = te["drop_corp"].notna().values; p25c, y25c = p25[okc], te["drop_corp"].values[okc].astype(int)

    rows = []
    for t in (0.75, 0.80, 0.90, 0.95):
        thr = 문턱(p25, y25, t)
        rows.append({"2025 목표 탐지율": f"{int(t*100)}%", "확률 문턱": round(thr, 6),
                     **{f"2025 {k}": v for k, v in 성적(p25c, y25c, thr).items()},
                     **{f"2026 {k}": v for k, v in 성적(pt, y26, thr).items()}})
    R = pd.DataFrame(rows); print(R.to_string(index=False))

    thr75 = 문턱(p25, y25, .75); thr90 = 문턱(p25, y25, .90); thr95 = 문턱(p25, y25, .95)
    print(f"  · 문턱 75% {thr75:.5f} / 90% {thr90:.5f}")
    out = pd.DataFrame({"date": te2.index, "요일": pd.to_datetime(te2.index).day_name().str[:3],
                        "휴일": te2["offday"].values, "급락확률": p26.values.round(4),
                        "경보(75%기준)": p26.values >= thr75,
                        "경보(90%기준)": p26.values >= thr90, "경보(95%기준)": p26.values >= thr95,
                        "실제_최저가": te2["day_min"].values, "기준_28일최저중앙": te2["ref_min"].values.round(1),
                        "한낮_최저가": te2["mid_min"].values, "실제_급락": te2["drop_corp"].values,
                        "우리정의_급락": te2["drop"].values})
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    out.to_csv(os.path.join(HERE, "results", "30_급락경보_2026_일별.csv"), index=False, encoding="utf-8-sig")
    S.drop(columns="_p").to_csv(os.path.join(HERE, "results", "29_급락_개선후보_2025.csv"), index=False, encoding="utf-8-sig")
    R.to_csv(os.path.join(HERE, "results", "31_급락경보_최종성적.csv"), index=False, encoding="utf-8-sig")
    miss = out[(out["실제_급락"] == 1) & ~out["경보(90%기준)"]]
    print("  · 90% 기준 놓친 급락일:", miss[["date", "요일", "급락확률", "실제_최저가"]].to_dict("records"))
    print("  · 10/1~10/6:", out[out.date >= "2026-10-01"][["date", "요일", "급락확률", "경보(90%기준)", "실제_최저가", "실제_급락"]].to_dict("records"))


if __name__ == "__main__":
    main()
