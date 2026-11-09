# -*- coding: utf-8 -*-
"""
event_models.py — 기업 1104 판정 기준(v1.1)에 맞춘 「시간별」 사건 확률 모델
==============================================================================
사건(정답, events.py)
  · 육지 급등 : 실적 SMP ≥ 같은 시각 직전 28일 중앙값 + 20원
  · 육지 급락 : 11~15시 실적 SMP < 30원
  · 제주 급락 : 제주 SMP 0원
입력 : D-1 에 알 수 있는 값만 (과거 SMP, 하루전 수요예측, 달력, D-2 이전 태양광, 전날 공급능력)
모델 : LightGBM + XGBoost + CatBoost 확률 평균
규칙 : ① 학습 ~2024 → 2025 예측으로 설정(최근 가중 여부)·경보/주의 문턱 선택
       ② 같은 설정으로 학습 ~2025 → 2026.1.1~데이터 끝(10.2) 1회 적용 = 「2차 시험」
판정(확률 모델) : 구간 시간의 절반 이상이 경보 → 성공, 절반 이상이 주의 이상 → 부분, 그 밖 실패
헛경보 : 경보(또는 주의)를 낸 날 중 그날 실제 사건이 없었던 날 수
"""
import os, sys, warnings
import numpy as np, pandas as pd
import lightgbm as lgb, xgboost as xgb
from catboost import CatBoostClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import events as EV

ROOT = EV.ROOT
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)
SUPPLY = os.path.join(ROOT, "data", "external", "supply_daily_raw.csv")
SPIKE_ADD, DROP_WON = 20, 30


# ---------------------------------------------------------------- 변수
def wide(d, col, days):
    return d.pivot(index="date", columns="hour_n", values=col).reindex(days)


def long(w, name):
    s = w.stack(future_stack=True).rename(name)
    s.index.names = ["date", "hour_n"]
    return s


def build():
    raw = pd.read_csv(EV.DATA, encoding="utf-8-sig", low_memory=False, parse_dates=["date"])
    days = pd.date_range(raw.date.min(), raw.date.max())
    W = {c: wide(raw, c, days) for c in ["smp_land", "smp_jeju", "demand_fcst_land", "demand_fcst_jeju",
                                          "pv_land", "pv_jeju", "wind_jeju"]}
    Y, J, F, FJ = W["smp_land"], W["smp_jeju"], W["demand_fcst_land"], W["demand_fcst_jeju"]
    sh = lambda w, k=1: w.shift(k)
    roll = lambda w, k, fn, lag=1: getattr(sh(w, lag).rolling(k, min_periods=k), fn)()

    med = sh(Y).rolling(28, min_periods=25).median()  # 7/31 결측 1일 허용
    med[med.index < "2021-01-29"] = np.nan
    ev_s = (Y >= med + SPIKE_ADD).where(Y.notna() & med.notna())
    ev_d = (Y < DROP_WON).where(Y.notna()); ev_d.loc[:, [h for h in ev_d.columns if not 11 <= h <= 15]] = np.nan
    ev_j = (J <= 0).where(J.notna())
    Yz = (Y < DROP_WON).astype(float).where(Y.notna())

    X = {}
    # 정답
    X["y_spike"], X["y_drop"], X["y_jeju"] = ev_s, ev_d, ev_j
    X["smp"], X["med28"], X["jsmp"] = Y, med, J
    # 육지 가격 (D-1 까지)
    X["y1_gap"] = sh(Y) - med
    X["y2_gap"] = sh(Y, 2) - med
    X["y7_gap"] = sh(Y, 7) - med
    X["q75_gap"] = sh(Y).rolling(28, min_periods=28).quantile(0.75) - med
    X["q25_gap"] = sh(Y).rolling(28, min_periods=28).quantile(0.25) - med
    X["std28"] = roll(Y, 28, "std")
    X["med7_gap"] = roll(Y, 7, "median") - med
    X["spk_cnt7"] = sh(ev_s.astype(float)).rolling(7, min_periods=1).sum()
    X["spk_cnt28"] = sh(ev_s.astype(float)).rolling(28, min_periods=1).sum()
    X["low_cnt7"] = sh(Yz).rolling(7, min_periods=1).sum()
    X["low_cnt28"] = sh(Yz).rolling(28, min_periods=1).sum()
    rowb = lambda s: pd.DataFrame(np.repeat(s.values[:, None], 24, 1), index=s.index, columns=Y.columns)
    X["d1_spk_hours"] = rowb(sh(ev_s.astype(float)).sum(axis=1))
    X["d1_low_hours"] = rowb(sh(Yz).sum(axis=1))
    X["d1_min"] = rowb(sh(Y).min(axis=1))
    X["d1_max_gap"] = rowb(sh(Y).max(axis=1) - med.max(axis=1))
    X["med_level"] = rowb(med.mean(axis=1))
    # 수요예측 (D일 값, D-1 공표)
    fmed = roll(F, 28, "median")
    X["f"] = F
    X["f_r28"] = F / fmed
    X["f_d1"] = F - sh(F)
    X["f_w1"] = F - sh(F, 7)
    X["f_max_r28"] = rowb(F.max(axis=1) / sh(F.max(axis=1)).rolling(28, min_periods=14).median())
    X["f_ramp"] = rowb(F[10] - F[7])
    # 태양광 대리지표 (D-2 ~ D-29 같은 시각 실적 중앙값·최댓값)
    pvm = W["pv_land"].shift(2).rolling(28, min_periods=10).median()
    pvx = W["pv_land"].shift(2).rolling(28, min_periods=10).max()
    X["pv_med"], X["pv_max"] = pvm, pvx
    net = F - pvm.fillna(0)
    X["net"] = net
    X["net_r28"] = net / sh(net).rolling(28, min_periods=14).median()
    X["net_min_r28"] = rowb(net.min(axis=1) / sh(net.min(axis=1)).rolling(28, min_periods=14).median())
    # 제주
    jmed = roll(J, 28, "median")
    X["j1"] = sh(J); X["j7"] = sh(J, 7); X["jmed28"] = jmed
    X["jz_cnt7"] = sh(ev_j.astype(float)).rolling(7, min_periods=1).sum()
    X["jz_cnt28"] = sh(ev_j.astype(float)).rolling(28, min_periods=1).sum()
    X["d1_jz_hours"] = rowb(sh(ev_j.astype(float)).sum(axis=1))
    X["jf"] = FJ
    X["jf_r28"] = FJ / roll(FJ, 28, "median")
    pvj = W["pv_jeju"].shift(2).rolling(28, min_periods=10).median()
    X["jpv_med"] = pvj
    X["jnet"] = FJ - pvj.fillna(0)
    X["jnet_r28"] = X["jnet"] / sh(X["jnet"]).rolling(28, min_periods=14).median()
    X["jwind_med"] = W["wind_jeju"].shift(2).rolling(14, min_periods=5).median()

    df = pd.concat([long(v, k) for k, v in X.items()], axis=1).reset_index()

    # 달력
    cal = raw.drop_duplicates("date").set_index("date")[["is_weekend", "is_holiday", "holiday_name"]].reindex(days)
    off = ((cal.is_weekend == 1) | (cal.is_holiday == 1)).astype(int)
    blk = (off != off.shift()).cumsum()
    c = pd.DataFrame(index=days)
    c["offday"] = off
    c["prev_offday"] = off.shift(1).fillna(0)
    c["next_offday"] = off.shift(-1).fillna(0)
    c["off_run"] = off.groupby(blk).transform("size") * off
    c["off_pos"] = (off.groupby(blk).cumcount() + 1) * off
    c["major_hol"] = cal.holiday_name.fillna("").str.contains("설날|추석").astype(int)
    c["dow"] = days.dayofweek
    c["month"] = days.month
    c["doy_sin"] = np.sin(2 * np.pi * days.dayofyear / 365.25)
    c["doy_cos"] = np.cos(2 * np.pi * days.dayofyear / 365.25)
    # 공급 여유 (전날 공급능력 − 내일 수요예측 최대), 2023년부터
    s = pd.read_csv(SUPPLY, encoding="cp949").drop_duplicates()
    s["date"] = pd.to_datetime(dict(year=s["년"], month=s["월"], day=s["일"]))
    s = s.drop_duplicates("date").set_index("date").sort_index().reindex(days)
    fmax = F.max(axis=1)
    c["supply_margin_pct"] = (s["공급능력(MW)"].shift(1) - fmax) / fmax * 100
    c.index.name = "date"
    df = df.merge(c.reset_index(), on="date", how="left")
    df["holiday"] = df["offday"]
    return df


COMMON = ["hour_n", "dow", "month", "doy_sin", "doy_cos", "offday", "prev_offday", "next_offday",
          "off_run", "off_pos", "major_hol"]
LAND = ["med28", "y1_gap", "y2_gap", "y7_gap", "q75_gap", "q25_gap", "std28", "med7_gap", "spk_cnt7",
        "spk_cnt28", "low_cnt7", "low_cnt28", "d1_spk_hours", "d1_low_hours", "d1_min", "d1_max_gap",
        "med_level", "f", "f_r28", "f_d1", "f_w1", "f_max_r28", "f_ramp", "pv_med", "pv_max", "net",
        "net_r28", "net_min_r28", "supply_margin_pct"]
JEJU = ["j1", "j7", "jmed28", "jz_cnt7", "jz_cnt28", "d1_jz_hours", "jf", "jf_r28", "jpv_med", "jnet",
        "jnet_r28", "jwind_med"]
EVENTS = {  # 이름: (정답 열, 변수, 대상 시간)
    "육지 급등": ("y_spike", COMMON + LAND, list(range(1, 25))),
    "육지 급락": ("y_drop", COMMON + LAND, list(range(11, 16))),
    "제주 급락": ("y_jeju", COMMON + JEJU + ["med28", "y1_gap", "d1_low_hours", "f", "net", "pv_med"],
              list(range(1, 25))),
}


# ---------------------------------------------------------------- 모델
def fit_predict(tr, te, feats, target, w=None, seed=7):
    X, y, Xt = tr[feats], tr[target].astype(int), te[feats]
    m1 = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=31, min_child_samples=30,
                            subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=seed, verbose=-1)
    m1.fit(X, y, sample_weight=w)
    m2 = xgb.XGBClassifier(n_estimators=400, learning_rate=0.03, max_depth=5, subsample=0.8,
                           colsample_bytree=0.8, min_child_weight=3, random_state=seed, verbosity=0)
    m2.fit(X, y, sample_weight=w)
    m3 = CatBoostClassifier(iterations=500, learning_rate=0.05, depth=6, random_seed=seed, verbose=0)
    m3.fit(X, y, sample_weight=w)
    return (m1.predict_proba(Xt)[:, 1] + m2.predict_proba(Xt)[:, 1] + m3.predict_proba(Xt)[:, 1]) / 3


def run(df, name, train_end, start, end, recent_w):
    tgt, feats, hours = EVENTS[name]
    sub = df[df.hour_n.isin(hours) & df[tgt].notna()]
    tr = sub[(sub.date >= "2021-01-29") & (sub.date <= train_end)]
    te = sub[(sub.date >= start) & (sub.date <= end)].copy()
    w = np.where(tr.date >= "2024-01-01", 3.0, 1.0) if recent_w else None
    te["p"] = fit_predict(tr, te, feats, tgt, w)
    return te


# ---------------------------------------------------------------- 문턱·판정
def pick_thresholds(te, tgt):
    """경보 = 2025 시간 단위 F1 최대, 주의 = 2025 시간 단위 F2 최대(탐지에 가중, 경보보다 낮게).
    (첫 실행의 「탐지율 90%」 주의 문턱은 2025 에서 0.001~0.006 으로 거의 매일 주의가 켜져 버림 → 11/7 교체)"""
    y, p = te[tgt].astype(int).values, te["p"].values
    grid = np.unique(np.round(np.quantile(p, np.linspace(0.3, 0.999, 400)), 4))

    def fbeta(t, b):
        a = p >= t; tp = (a & (y == 1)).sum()
        if not tp: return 0
        pr, rc = tp / a.sum(), tp / y.sum()
        return (1 + b * b) * pr * rc / (b * b * pr + rc)
    warn = max(grid, key=lambda t: fbeta(t, 1))
    caut = max([t for t in grid if t <= warn], key=lambda t: fbeta(t, 2))
    return float(warn), float(caut)


def level(p, warn, caut):
    return np.where(p >= warn, 2, np.where(p >= caut, 1, 0))


def judge_prob(te, tgt, warn, caut):
    te = te.copy(); te["lv"] = level(te.p.values, warn, caut); te["ev"] = te[tgt] == 1
    rows = []
    for dt, g in te[te.ev].groupby("date"):
        h = g.hour_n.values; br = np.where(np.diff(h) != 1)[0]
        for s, e in zip(np.r_[0, br + 1], np.r_[br, len(h) - 1]):
            lv = g.lv.values[s:e + 1]
            r = "성공" if (lv == 2).mean() >= 0.5 else ("부분" if (lv >= 1).mean() >= 0.5 else "실패")
            rows.append((dt, h[s], h[e], int(g.holiday.iloc[0]), r))
    seg = pd.DataFrame(rows, columns=["date", "start", "end", "holiday", "판정"])
    day = te.groupby("date").agg(ev=("ev", "max"), lv=("lv", "max"), holiday=("holiday", "first"))
    fa = day[~day.ev]
    return seg, {"경보 헛경보": fa[fa.lv == 2].groupby("holiday").size(),
                 "주의 헛경보": fa[fa.lv == 1].groupby("holiday").size(),
                 "경보일": day[day.lv == 2].groupby("holiday").size()}, te


def judge_price(te, tgt, pred_col, name):
    """가격 모델 판정. te: date, hour_n, smp(실적), med28, pred, holiday, 정답열."""
    te = te.copy(); te["ev"] = te[tgt] == 1
    if name == "육지 급등":
        hit = te[pred_col] >= te.med28 + SPIKE_ADD
        part = (te[pred_col] - te.med28) >= (te.smp - te.med28) / 2
    elif name == "육지 급락":
        hit = te[pred_col] < DROP_WON
        part = (te.med28 - te[pred_col]) >= (te.med28 - te.smp) / 2
    else:
        hit = te[pred_col] <= 0
        part = (te.jmed28 - te[pred_col]) >= (te.jmed28 - te.jsmp) / 2
    te["hit"], te["part"] = hit.values, part.values
    rows = []
    for dt, g in te[te.ev].groupby("date"):
        h = g.hour_n.values; br = np.where(np.diff(h) != 1)[0]
        for s, e in zip(np.r_[0, br + 1], np.r_[br, len(h) - 1]):
            gg = g.iloc[s:e + 1]
            r = "성공" if gg.hit.mean() >= 0.5 else ("부분" if gg.part.mean() >= 0.5 else "실패")
            rows.append((dt, h[s], h[e], int(g.holiday.iloc[0]), r))
    seg = pd.DataFrame(rows, columns=["date", "start", "end", "holiday", "판정"])
    fa = te[te.hit & ~te.ev]
    n = {}
    for hol, g in fa.groupby("holiday"):
        k = 0
        for dt, gg in g.groupby("date"):
            k += 1 + int((np.diff(gg.hour_n.values) != 1).sum())
        n[hol] = k
    return seg, pd.Series(n, dtype=float)


def table1(seg, name, model):
    out = []
    for hol, lab in [(1, "휴일"), (0, "평일")]:
        s = seg[seg.holiday == hol]; n = len(s)
        cell = lambda k: f"{(s.판정 == k).sum()} ({(s.판정 == k).mean() * 100:.0f}%)" if n else "0"
        out.append(dict(모델=model, 사건=name, 구분=lab, 구간수=n, 성공=cell("성공"), 부분=cell("부분"), 실패=cell("실패")))
    return out


def main():
    df = build()
    df = df[df.med28.notna() | df.y_jeju.notna()]
    last = df.loc[df.smp.notna(), "date"].max().strftime("%Y-%m-%d")
    print("데이터 끝", last)
    T1, T2, SEL, CM, P26 = [], [], [], [], []
    for name, (tgt, feats, hours) in EVENTS.items():
        # ① 2025 에서 설정 선택 (학습 ~2024)
        cand = {}
        for rw in (False, True):
            te = run(df, name, "2024-12-31", "2025-01-01", "2025-12-31", rw)
            y = te[tgt].astype(int)
            ap = average_precision_score(y, te.p) if y.sum() else np.nan
            cand[rw] = (ap, te)
            SEL.append(dict(사건=name, 최근가중="2024~ ×3" if rw else "없음", 시간수=len(te), 사건시간=int(y.sum()),
                            AP_2025=round(ap, 4), AUC_2025=round(roc_auc_score(y, te.p), 4) if 0 < y.sum() < len(y) else np.nan))
        rw = max(cand, key=lambda k: -1 if np.isnan(cand[k][0]) else cand[k][0])
        te25 = cand[rw][1]
        warn, caut = pick_thresholds(te25, tgt)
        seg25, fa25, _ = judge_prob(te25, tgt, warn, caut)
        T1 += table1(seg25, name, "시간별 확률(2025, 설정 고른 구간)")
        # ② 2026 1회 적용 (학습 ~2025)
        te26 = run(df, name, "2025-12-31", "2026-01-01", last, rw)
        seg26, fa26, lv26 = judge_prob(te26, tgt, warn, caut)
        T1 += table1(seg26, name, "시간별 확률(2026 2차 시험)")
        for lab, fa in [("2025 설정구간", fa25), ("2026 2차 시험", fa26)]:
            T2.append(dict(구간=lab, 사건=name,
                           **{f"{k}_{h}": int(fa[k].get(v, 0)) for k in fa for h, v in [("휴일", 1), ("평일", 0)]}))
        y, a = lv26[tgt] == 1, lv26.lv == 2
        CM.append(dict(사건=name, 단위="시간(경보)", 실제있음_예측있음=int((y & a).sum()), 실제있음_예측없음=int((y & ~a).sum()),
                       실제없음_예측있음=int((~y & a).sum()), 실제없음_예측없음=int((~y & ~a).sum())))
        dd = lv26.groupby("date").agg(y=(tgt, "max"), lv=("lv", "max"))
        y, a = dd.y == 1, dd.lv == 2
        CM.append(dict(사건=name, 단위="날짜(경보)", 실제있음_예측있음=int((y & a).sum()), 실제있음_예측없음=int((y & ~a).sum()),
                       실제없음_예측있음=int((~y & a).sum()), 실제없음_예측없음=int((~y & ~a).sum())))
        print(f"{name}: 최근가중={rw} 경보≥{warn:.3f} 주의≥{caut:.3f}")
        SEL.append(dict(사건=name, 최근가중="선택=" + ("2024~ ×3" if rw else "없음"), 시간수=None, 사건시간=None,
                        AP_2025=None, AUC_2025=None, 경보문턱=round(warn, 4), 주의문턱=round(caut, 4)))
        x = lv26[["date", "hour_n", "holiday", tgt, "p", "lv"]].rename(columns={tgt: "실제"}); x["사건"] = name
        P26.append(x)

    # ③ 기준선 : 기존 평소가격 모델 F 의 중앙값(q50), 기업 모델 예측 — 가격 모델 판정 (2026.1~9)
    base = df[(df.date >= "2026-01-01")][["date", "hour_n", "holiday", "smp", "med28", "jsmp", "y_spike", "y_drop", "y_jeju"]].copy()
    base["jmed28"] = df.loc[base.index, "jmed28"]
    ser = pd.read_csv(os.path.join(ROOT, "experiments", "spike_drop", "dash_export", "series.csv"))
    ser["dt"] = pd.to_datetime(ser.datetime); ser["date"] = ser.dt.dt.normalize(); ser["hour_n"] = ser.dt.dt.hour + 1
    corp = pd.read_csv(os.path.join(ROOT, "data", "raw_uploads", "company_model", "model_predictions_smp_land.csv"),
                       parse_dates=["date"])
    base = base.merge(ser[["date", "hour_n", "median", "upper"]], on=["date", "hour_n"], how="left") \
               .merge(corp[["date", "hour_n", "pred"]], on=["date", "hour_n"], how="left")
    base = base[base["median"].notna()]
    for col, model in [("median", "기존 평소가격 F 중앙값(2026)"), ("pred", "기업 모델 예측(참고, 2026)")]:
        for name, (tgt, _, hours) in list(EVENTS.items())[:2]:
            b = base[base.hour_n.isin(hours) & base[tgt].notna()]
            seg, fa = judge_price(b, tgt, col, name)
            T1 += table1(seg, name, model)
            T2.append(dict(구간=model, 사건=name, **{f"가격헛경보_{h}": int(fa.get(v, 0)) for h, v in [("휴일", 1), ("평일", 0)]}))

    # ④ 기준선 : 기존 일별 경보(급등 6.79%, 급락 3.894%) — 그날 경보를 그날 모든 구간에 적용
    dash = os.path.join(ROOT, "experiments", "spike_drop", "dash_export")
    for f, name, tgt in [("spike_daily.csv", "육지 급등", "y_spike"), ("drop_daily.csv", "육지 급락", "y_drop")]:
        a = pd.read_csv(os.path.join(dash, f), encoding="utf-8-sig", parse_dates=["date"])
        a["lv"] = np.where(a["경보"].eq("경보"), 2, 0)
        if "전날 급등" in a: a["lv"] = np.where((a.lv == 0) & a["전날 급등"].eq("예"), 1, a.lv)
        hours = EVENTS[name][2]
        b = df[df.date.isin(a.date) & df.hour_n.isin(hours) & df[tgt].notna()].merge(a[["date", "lv"]], on="date")
        b["p"] = b.lv / 2.0
        seg, fa, _ = judge_prob(b, tgt, 1.0, 0.5)
        T1 += table1(seg, name, f"기존 일별 경보(2026, {a.date.min():%m/%d}~{a.date.max():%m/%d})")
        T2.append(dict(구간=f"기존 일별 경보(2026)", 사건=name,
                       **{f"{k}_{h}": int(fa[k].get(v, 0)) for k in fa for h, v in [("휴일", 1), ("평일", 0)]}))

    pd.DataFrame(T1).to_csv(os.path.join(RES, "01_표1_사건판정.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(T2).to_csv(os.path.join(RES, "02_표2_헛경보.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(SEL).to_csv(os.path.join(RES, "03_설정선택_2025.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(CM).to_csv(os.path.join(RES, "04_혼동행렬_2026.csv"), index=False, encoding="utf-8-sig")
    pd.concat(P26).to_csv(os.path.join(RES, "05_시간별확률_2026.csv"), index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    for f in ["03_설정선택_2025", "01_표1_사건판정", "02_표2_헛경보", "04_혼동행렬_2026"]:
        print("\n==", f); print(pd.read_csv(os.path.join(RES, f + ".csv"), encoding="utf-8-sig").fillna("").to_string(index=False))


if __name__ == "__main__":
    main()
