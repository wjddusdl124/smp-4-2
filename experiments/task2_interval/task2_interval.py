# -*- coding: utf-8 -*-
"""
task2_interval.py — 과제 2 : 예측값에 「80% 예측 범위」 함께 보여주기
==============================================================================
목표
  · D-1(전날)에 D일 24시간의 육지 SMP 를 예측하면서 하한(10% 분위)·중앙값·상한(90% 분위)을 함께 낸다
  · 시험 구간(2026.1.1~9.30) 커버리지(PICP) 75~85% + 폭은 가능한 한 좁게

방법 (모두 비교)
  A. 잔차 분위수 (가장 쉬운 방법) : LightGBM 중앙값 + 2025년 오차의 시간대·평일/휴일별 10%/90% 값
  B. LightGBM 분위수 회귀 (α = 0.1 / 0.5 / 0.9)
  C. Chronos-2 + 수요예측 공변량 (제로샷)
  D. Chronos-2 단변량 (제로샷)
  E. 앙상블 (B·C·D 분위수를 2025년 pinball 손실 최소 가중치로 결합)
  F. 앙상블 + 등각 보정(CQR, 시간대 × 평일/휴일) ← 최종 제안

기간 (CLAUDE.md 규칙, 변경 금지)
  · 학습 2021~2024 / 보정 2025 (가중치·보정값은 여기서만) / 시험 2026.1.1~9.30 (1회 평가)
  · LightGBM 은 「직전 연도까지 학습 → 다음 해 예측」 규칙을 두 번 적용
      - 보정용 : 2021~2024 학습 → 2025 예측 (가중치·보정값 산출에 사용)
      - 시험용 : 2021~2025 학습 → 2026 예측 (하이퍼파라미터·가중치·보정값은 그대로)
  · Chronos-2 는 학습하지 않으므로 날마다 D-1 23시까지의 과거만 보고 예측

누출 차단
  · D일 실제 SMP·실제 수요·실제 기상·태양광 실적 사용 안 함
  · 회사 태양광 전망(pv_fcst)은 D일 실측 기상으로 만든 값이라 제외
    → 대신 D-2 까지의 태양광 실적으로 만든 「설비 증가 대리지표」 사용

실행
  .venv\\Scripts\\python.exe experiments\\task2_interval\\task2_interval.py
  (Chronos 예측은 results/chronos_preds.csv 에 저장되어 두 번째 실행부터는 재사용)
  옵션 : --rerun-chronos  Chronos 다시 예측 / --chronos-model autogluon/chronos-2-small
         --chronos-revision <커밋>  (생략 시 amazon/chronos-2 는 결과를 만든 버전으로 고정)
"""
import argparse
import itertools
import os
import platform
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import lightgbm as lgb

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data", "processed", "smp_dataset_hourly.csv")
PLOT_DIR = os.path.join(HERE, "plots")
RES_DIR = os.path.join(HERE, "results")
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(RES_DIR, exist_ok=True)

# 기간 분할 — 절대 바꾸지 않음
TRAIN_END = "2024-12-31"
CAL_START, CAL_END = "2025-01-01", "2025-12-31"
TEST_START, TEST_END = "2026-01-01", "2026-09-30"

QS = [0.1, 0.5, 0.9]          # 하한 · 중앙 · 상한
ALPHA = 0.2                   # 80% 범위 → 바깥 확률 20%
SEED = 9
CONTEXT = 2048                # Chronos 가 보는 과거 길이(시간) ≈ 85일
# 결과를 만든 Chronos-2 모델 버전(Hugging Face 커밋) — 다른 PC 에서 다시 예측해도 같은 가중치를 쓰도록 고정
CHRONOS_REVISION = {"amazon/chronos-2": "29ec3766d36d6f73f0696f85560a422f50e8498c"}

# 그래프 — 한글 글꼴과 색 (색은 역할별로 고정)
plt.rcParams["font.family"] = "Malgun Gothic" if platform.system() == "Windows" else "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
C_BLUE, C_ORANGE, C_AQUA = "#2a78d6", "#eb6834", "#1baf7a"


def 스타일(ax):
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2)


# =============================================================================
# [1] 데이터 준비
# =============================================================================
def 데이터_준비():
    raw = pd.read_csv(DATA, encoding="utf-8-sig", low_memory=False)
    raw["date"] = raw["date"].astype(str).str[:10]
    d = raw[["date", "hour_n", "smp_land", "demand_fcst_land", "pv_land",
             "is_holiday", "is_weekend", "dow", "month"]].copy()

    # 빠진 시각이 있어도 날짜 × 24시간 격자가 되도록 채움
    days = pd.date_range(d["date"].min(), d["date"].max(), freq="D").strftime("%Y-%m-%d")
    grid = pd.MultiIndex.from_product([days, range(1, 25)], names=["date", "hour_n"]).to_frame(index=False)
    d = grid.merge(d, on=["date", "hour_n"], how="left").sort_values(["date", "hour_n"]).reset_index(drop=True)
    dt = pd.to_datetime(d["date"])
    d["timestamp"] = dt + pd.to_timedelta(d["hour_n"] - 1, unit="h")
    d["dow"] = dt.dt.dayofweek
    d["month"] = dt.dt.month
    d["is_weekend"] = (d["dow"] >= 5).astype(int)
    d["is_holiday"] = d.groupby("date")["is_holiday"].transform(lambda s: s.ffill().bfill()).fillna(0)
    d["offday"] = ((d["is_holiday"] == 1) | (d["is_weekend"] == 1)).astype(int)

    # 날짜 × 시간 표로 바꿔 「며칠 전 같은 시각」을 쉽게 꺼냄
    Y = d.pivot(index="date", columns="hour_n", values="smp_land")
    F = d.pivot(index="date", columns="hour_n", values="demand_fcst_land")
    PV = d.pivot(index="date", columns="hour_n", values="pv_land")
    off = d.groupby("date")["offday"].first()

    def 시각별(표, k):                      # k일 전 같은 시각 → 세로형
        return 표.shift(k).stack(future_stack=True).rename(None)

    def 일별(값):                          # 날짜 단위 값 → 24시간에 복사
        return d["date"].map(값)

    f = d[["date", "hour_n", "timestamp", "smp_land", "offday", "is_holiday", "dow", "month"]].copy()
    key = pd.MultiIndex.from_frame(f[["date", "hour_n"]])
    # 달력 (전날 알 수 있는 값)
    doy = pd.to_datetime(f["date"]).dt.dayofyear
    f["hour_sin"] = np.sin(2 * np.pi * f["hour_n"] / 24)
    f["hour_cos"] = np.cos(2 * np.pi * f["hour_n"] / 24)
    f["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    f["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    f["prev_offday"] = 일별(off.shift(1)).fillna(0).values
    # 전력거래소 하루전 수요예측 (D일 값 — 전날 발표)
    f["fcst"] = d["demand_fcst_land"].values
    f["fcst_day_max"] = 일별(F.max(axis=1)).values
    f["fcst_day_min"] = 일별(F.min(axis=1)).values
    f["fcst_ratio"] = f["fcst"] / f["fcst_day_max"]
    f["fcst_diff_d1"] = f["fcst"] - 시각별(F, 1).reindex(key).values
    # SMP 과거값 (D-1 까지만)
    for k in (1, 2, 3, 7, 14):
        f[f"smp_d{k}"] = 시각별(Y, k).reindex(key).values
    f["smp_d1_mean"] = 일별(Y.mean(axis=1).shift(1)).values
    f["smp_d1_min"] = 일별(Y.min(axis=1).shift(1)).values
    f["smp_d1_max"] = 일별(Y.max(axis=1).shift(1)).values
    f["smp_d1_std"] = 일별(Y.std(axis=1).shift(1)).values
    f["smp_d1_last"] = 일별(Y[24].shift(1)).values
    f["smp_d1_mid_min"] = 일별(Y[[11, 12, 13, 14, 15]].min(axis=1).shift(1)).values
    f["smp_7d_same_h"] = sum(시각별(Y, k).reindex(key).values for k in range(1, 8)) / 7
    f["smp_7d_mean"] = 일별(Y.mean(axis=1).rolling(7, min_periods=4).mean().shift(1)).values
    f["smp_28d_mean"] = 일별(Y.mean(axis=1).rolling(28, min_periods=14).mean().shift(1)).values
    # 태양광 설비 증가 대리지표 : D-2 ~ D-31 같은 시각 태양광 실적의 최댓값
    cap = PV.shift(2).rolling(30, min_periods=10).max()
    f["pv_cap_proxy"] = 시각별(cap, 0).reindex(key).values
    f["net_load_proxy"] = f["fcst"] - f["pv_cap_proxy"]
    f["naive"] = f["smp_d1"]                 # 기준선 : 어제 같은 시각
    return d, f


FEATS = ["hour_n", "hour_sin", "hour_cos", "dow", "month", "doy_sin", "doy_cos", "offday",
         "is_holiday", "prev_offday", "fcst", "fcst_day_max", "fcst_day_min", "fcst_ratio",
         "fcst_diff_d1", "smp_d1", "smp_d2", "smp_d3", "smp_d7", "smp_d14", "smp_d1_mean",
         "smp_d1_min", "smp_d1_max", "smp_d1_std", "smp_d1_last", "smp_d1_mid_min",
         "smp_7d_same_h", "smp_7d_mean", "smp_28d_mean", "pv_cap_proxy", "net_load_proxy"]

# LightGBM 설정 — 사전에 고정 (시험 결과를 보고 바꾸지 않음)
LGB_PARAMS = dict(n_estimators=700, learning_rate=0.03, num_leaves=31, min_child_samples=40,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                  random_state=SEED, verbose=-1)


# =============================================================================
# [2] 모델 / 범위 산출
# =============================================================================
def lgbm_분위수(f, train_end, pred_start, pred_end):
    """train_end 까지 학습 → [pred_start, pred_end] 예측. 분위수별 모델 3개"""
    tr = f[(f["date"] <= train_end) & f["smp_land"].notna() & f["smp_d7"].notna()]
    te = f[(f["date"] >= pred_start) & (f["date"] <= pred_end)]
    out = te[["date", "hour_n"]].copy()
    for q in QS:
        m = lgb.LGBMRegressor(objective="quantile", alpha=q, **LGB_PARAMS)
        m.fit(tr[FEATS], tr["smp_land"])
        out[f"q{int(q * 100)}"] = m.predict(te[FEATS])
    return out


def chronos_예측(d, start, end, model_id, cache, revision=None):
    """날마다 D-1 23시까지의 과거 CONTEXT 시간만 보고 D일 24시간을 예측 (학습 없음)"""
    if os.path.exists(cache):
        print(f"  · Chronos 저장본 사용 : {os.path.relpath(cache, BASE)}")
        return pd.read_csv(cache, encoding="utf-8-sig")
    import torch
    from chronos import Chronos2Pipeline
    torch.set_num_threads(max(1, os.cpu_count() - 1))
    t0 = time.time()
    pipe = Chronos2Pipeline.from_pretrained(model_id, device_map="cpu", revision=revision)
    print(f"  · {model_id} (revision {revision or '최신'}) 적재 {time.time() - t0:.0f}초")

    s = d[["date", "timestamp", "smp_land", "demand_fcst_land"]].reset_index(drop=True)
    s["demand_fcst_land"] = s["demand_fcst_land"].interpolate(limit_direction="both")
    days = pd.date_range(start, end, freq="D").strftime("%Y-%m-%d").tolist()
    first_row = s.groupby("date").head(1).set_index("date").index
    pos = {dd: i for i, dd in zip(s.groupby("date").head(1).index, first_row)}

    outs = []
    for mode in ("cov", "uni"):
        for b in range(0, len(days), 30):              # 30일씩 묶어서 한 번에 예측
            batch = days[b:b + 30]
            ctx, fut = [], []
            for dd in batch:
                i = pos[dd]
                c = s.iloc[i - CONTEXT:i]
                cd = pd.DataFrame({"id": dd, "timestamp": c["timestamp"].values,
                                   "target": c["smp_land"].astype(float).values})
                if mode == "cov":
                    cd["fcst"] = c["demand_fcst_land"].values
                    nx = s.iloc[i:i + 24]
                    fut.append(pd.DataFrame({"id": dd, "timestamp": nx["timestamp"].values,
                                             "fcst": nx["demand_fcst_land"].values}))
                ctx.append(cd)
            p = pipe.predict_df(pd.concat(ctx), future_df=pd.concat(fut) if fut else None,
                                prediction_length=24, quantile_levels=QS, id_column="id",
                                timestamp_column="timestamp", target="target")
            p = p.sort_values(["id", "timestamp"])
            p["hour_n"] = p.groupby("id").cumcount() + 1
            o = p.rename(columns={"id": "date", "0.1": "q10", "0.5": "q50", "0.9": "q90"})
            o["mode"] = mode
            outs.append(o[["date", "hour_n", "mode", "q10", "q50", "q90"]])
            print(f"  · Chronos-{mode} {min(b + 30, len(days))}/{len(days)}일 ({time.time() - t0:.0f}초)",
                  flush=True)
    res = pd.concat(outs, ignore_index=True)
    res.to_csv(cache, index=False, encoding="utf-8-sig")
    return res


def 정리(L, M, U):
    """분위수가 뒤집히면 정렬, 하한은 0 미만이면 0"""
    a = np.sort(np.vstack([L, M, U]), axis=0)
    a[0] = np.clip(a[0], 0, None)
    a[1] = np.clip(a[1], 0, None)
    a[2] = np.clip(a[2], 0, None)
    return a[0], a[1], a[2]


def pinball(y, q, tau):
    e = y - q
    return float(np.nanmean(np.maximum(tau * e, (tau - 1) * e)))


def 앙상블_가중치(cal, names):
    """분위수마다 pinball 손실이 가장 작은 가중치 (0.05 간격 격자, 합 = 1) — 2025년만 사용"""
    y = cal["y"].values
    steps = np.round(np.arange(0, 1.0001, 0.05), 2)
    combos = [w for w in itertools.product(steps, repeat=len(names)) if abs(sum(w) - 1) < 1e-9]
    rows = []
    for q in QS:
        tag = f"q{int(q * 100)}"
        P = np.vstack([cal[f"{n}_{tag}"].values for n in names])
        best = min(combos, key=lambda w: pinball(y, np.dot(w, P), q))
        rows.append({"분위수": tag, **{n: w for n, w in zip(names, best)},
                     "pinball": round(pinball(y, np.dot(best, P), q), 3)})
    return pd.DataFrame(rows)


def 등각_보정값(cal, L, U, groups):
    """CQR : 그룹(시간대 × 평일/휴일)마다 하한·상한을 얼마나 넓히거나 좁힐지 (2025년만 사용)"""
    y = cal["y"].values
    s_lo = L - y                      # 양수면 하한 아래로 벗어남
    s_hi = y - U                      # 양수면 상한 위로 벗어남
    t = pd.DataFrame({"g": groups, "lo": s_lo, "hi": s_hi}).dropna()
    rows = []
    for g, x in t.groupby("g"):
        n = len(x)
        lev = min(1.0, np.ceil((n + 1) * (1 - ALPHA / 2)) / n)   # 유한표본 보정
        rows.append({"그룹": g, "n": n, "하한_보정": np.quantile(x["lo"], lev, method="higher"),
                     "상한_보정": np.quantile(x["hi"], lev, method="higher")})
    return pd.DataFrame(rows).set_index("그룹")


# =============================================================================
# [4] 평가 함수
# =============================================================================
def 평가(y, L, M, U, naive):
    ok = ~np.isnan(y)
    y, L, M, U, naive = y[ok], L[ok], M[ok], U[ok], naive[ok]
    width = U - L
    wink = width + (2 / ALPHA) * (L - y) * (y < L) + (2 / ALPHA) * (y - U) * (y > U)
    mae = np.mean(np.abs(y - M))
    mae_n = np.nanmean(np.abs(y - naive))
    return {"PICP(%)": 100 * np.mean((y >= L) & (y <= U)),
            "MPIW(원)": np.mean(width),
            "Winkler": np.mean(wink),
            "pinball_0.1": pinball(y, L, 0.1), "pinball_0.5": pinball(y, M, 0.5),
            "pinball_0.9": pinball(y, U, 0.9),
            "하한아래(%)": 100 * np.mean(y < L), "상한위(%)": 100 * np.mean(y > U),
            "MAE(중앙값)": mae, "MAE(어제같은시각)": mae_n,
            "개선율(%)": 100 * (1 - mae / mae_n), "n": len(y)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerun-chronos", action="store_true")
    ap.add_argument("--chronos-model", default="amazon/chronos-2")
    ap.add_argument("--chronos-revision", default=None,
                    help="Hugging Face 커밋. 생략하면 amazon/chronos-2 는 결과를 만든 버전으로 고정")
    args = ap.parse_args()
    revision = args.chronos_revision or CHRONOS_REVISION.get(args.chronos_model)

    print("=" * 70 + "\n[1] 데이터 준비\n" + "=" * 70)
    d, f = 데이터_준비()
    print(f"  · {f['date'].min()} ~ {f['date'].max()} / {len(f):,}행, 입력 변수 {len(FEATS)}개")
    print(f"  · 학습 ~{TRAIN_END} / 보정 {CAL_START}~{CAL_END} / 시험 {TEST_START}~{TEST_END}")

    print("=" * 70 + "\n[2] 모델 / 범위 산출\n" + "=" * 70)
    t0 = time.time()
    lg_cal = lgbm_분위수(f, TRAIN_END, CAL_START, CAL_END)
    lg_test = lgbm_분위수(f, CAL_END, TEST_START, TEST_END)
    print(f"  · LightGBM 분위수 회귀 2회 학습 완료 ({time.time() - t0:.0f}초)")

    cache = os.path.join(RES_DIR, "chronos_preds.csv")
    if args.rerun_chronos and os.path.exists(cache):
        os.remove(cache)
    ch = chronos_예측(d, CAL_START, TEST_END, args.chronos_model, cache, revision)
    ch["date"] = ch["date"].astype(str).str[:10]

    def 합치기(lg, start, end):
        b = f[(f["date"] >= start) & (f["date"] <= end)][["date", "hour_n", "smp_land", "naive", "offday"]]
        b = b.rename(columns={"smp_land": "y"}).merge(
            lg.rename(columns={c: f"lgb_{c}" for c in ("q10", "q50", "q90")}), on=["date", "hour_n"])
        for mode in ("cov", "uni"):
            c = ch[ch["mode"] == mode].drop(columns="mode")
            b = b.merge(c.rename(columns={q: f"chr_{mode}_{q}" for q in ("q10", "q50", "q90")}),
                        on=["date", "hour_n"], how="left")
        b["group"] = b["hour_n"].astype(str).str.zfill(2) + "시_" + np.where(b["offday"] == 1, "휴일", "평일")
        return b.reset_index(drop=True)

    cal = 합치기(lg_cal, CAL_START, CAL_END)
    test = 합치기(lg_test, TEST_START, TEST_END)
    cal_fit = cal.dropna(subset=["y"]).reset_index(drop=True)

    # ① 과거 예측 오차(실제 − 예측)를 시간대·평일/휴일별로 정리 (2025년, LightGBM 중앙값 기준)
    cal_fit["err"] = cal_fit["y"] - cal_fit["lgb_q50"]
    err_q = cal_fit.groupby("group")["err"].quantile([0.1, 0.5, 0.9]).unstack()
    err_q.columns = ["오차_10%", "오차_50%", "오차_90%"]
    err_q.to_csv(os.path.join(RES_DIR, "01_오차분위수_2025_시간대x평일휴일.csv"), encoding="utf-8-sig")

    # ⑤ 앙상블 가중치 (2025년 pinball 손실 최소)
    names = ["lgb", "chr_cov", "chr_uni"]
    W = 앙상블_가중치(cal_fit, names)
    W.to_csv(os.path.join(RES_DIR, "02_앙상블_가중치.csv"), index=False, encoding="utf-8-sig")
    print("  · 앙상블 가중치 (2025년 pinball 최소)\n" + W.to_string(index=False))

    def 앙상블(b):
        out = {}
        for _, r in W.iterrows():
            out[r["분위수"]] = sum(r[n] * b[f"{n}_{r['분위수']}"].values for n in names)
        return 정리(out["q10"], out["q50"], out["q90"])

    eL_cal, eM_cal, eU_cal = 앙상블(cal_fit)
    C = 등각_보정값(cal_fit, eL_cal, eU_cal, cal_fit["group"].values)
    C.to_csv(os.path.join(RES_DIR, "03_등각보정값_시간대x평일휴일.csv"), encoding="utf-8-sig")
    print(f"  · 등각 보정값 {len(C)}개 그룹 — 하한 평균 {C['하한_보정'].mean():+.2f}원, "
          f"상한 평균 {C['상한_보정'].mean():+.2f}원 (양수 = 넓힘)")

    print("=" * 70 + "\n[3] 예측\n" + "=" * 70)

    def 모든_방법(b):
        g = b["group"]
        lo = g.map(err_q["오차_10%"]).values
        hi = g.map(err_q["오차_90%"]).values
        res = {"A_잔차분위수": 정리(b["lgb_q50"].values + lo, b["lgb_q50"].values, b["lgb_q50"].values + hi),
               "B_LightGBM분위수": 정리(b["lgb_q10"].values, b["lgb_q50"].values, b["lgb_q90"].values),
               "C_Chronos2_수요예측": 정리(b["chr_cov_q10"].values, b["chr_cov_q50"].values, b["chr_cov_q90"].values),
               "D_Chronos2_단변량": 정리(b["chr_uni_q10"].values, b["chr_uni_q50"].values, b["chr_uni_q90"].values)}
        eL, eM, eU = 앙상블(b)
        res["E_앙상블"] = (eL, eM, eU)
        res["F_앙상블+등각보정(최종)"] = 정리(eL - g.map(C["하한_보정"]).values, eM,
                                      eU + g.map(C["상한_보정"]).values)
        return res

    R_cal = 모든_방법(cal)
    R_test = 모든_방법(test)
    pred = test[["date", "hour_n", "y", "naive", "offday"]].copy()
    for k, (L, M, U) in R_test.items():
        pred[f"{k}_하한"], pred[f"{k}_중앙"], pred[f"{k}_상한"] = L, M, U
    pred.to_csv(os.path.join(RES_DIR, "04_시험구간_예측범위.csv"), index=False, encoding="utf-8-sig")
    # 최종 모델만 담은 가벼운 파일 (대시보드 · 발표용)
    fL, fM, fU = R_test["F_앙상블+등각보정(최종)"]
    pd.DataFrame({"datetime": (pd.to_datetime(test["date"]) + pd.to_timedelta(test["hour_n"] - 1, unit="h"))
                  .dt.strftime("%Y-%m-%d %H:00"), "actual": test["y"].round(2), "lower": fL.round(2),
                  "median": fM.round(2), "upper": fU.round(2), "naive": test["naive"].round(2)}) \
        .to_csv(os.path.join(RES_DIR, "08_최종모델_예측범위.csv"), index=False, encoding="utf-8-sig")
    print(f"  · 시험 구간 {test['date'].nunique()}일 × 24시간 예측 저장 (방법 {len(R_test)}개)")

    print("=" * 70 + "\n[4] 평가 · 시각화\n" + "=" * 70)
    pd.set_option("display.width", 200)
    tabs = {}
    for tag, b, R in (("보정(2025, 참고)", cal, R_cal), ("시험(2026.1~9)", test, R_test)):
        rows = [{"방법": k, **평가(b["y"].values, L, M, U, b["naive"].values)} for k, (L, M, U) in R.items()]
        t = pd.DataFrame(rows).set_index("방법")
        tabs[tag] = t
        print(f"\n■ {tag}  — 목표 PICP 75~85%, 폭·Winkler·pinball 은 작을수록 좋음")
        print(t.drop(columns=["n"]).round(2).to_string())
    tabs["시험(2026.1~9)"].round(3).to_csv(os.path.join(RES_DIR, "05_평가_시험구간.csv"), encoding="utf-8-sig")
    tabs["보정(2025, 참고)"].round(3).to_csv(os.path.join(RES_DIR, "05_평가_보정구간_참고.csv"), encoding="utf-8-sig")

    # 급등 · 일반 · 급락 구간 비교 — 기준 : 어제 같은 시각 대비 변화 (임계값은 2025년 분포에서)
    ch_cal = (cal["y"] - cal["naive"]).dropna()
    up_thr, dn_thr = np.quantile(ch_cal, 0.95), np.quantile(ch_cal, 0.05)
    chg = test["y"] - test["naive"]
    test_regime = np.where(chg >= up_thr, "급등", np.where(chg <= dn_thr, "급락", "일반"))
    rows = []
    for k in ("B_LightGBM분위수", "E_앙상블", "F_앙상블+등각보정(최종)"):
        L, M, U = R_test[k]
        for rg in ("급등", "일반", "급락"):
            m = (test_regime == rg) & test["y"].notna().values
            e = 평가(test["y"].values[m], L[m], M[m], U[m], test["naive"].values[m])
            rows.append({"방법": k, "구간": rg, "시간수": int(m.sum()),
                         "실제_평균가격": test["y"].values[m].mean(),
                         "어제같은시각_평균": np.nanmean(test["naive"].values[m]),
                         "예측중앙_평균": M[m].mean(), "PICP(%)": e["PICP(%)"],
                         "MPIW(원)": e["MPIW(원)"], "MAE(중앙값)": e["MAE(중앙값)"],
                         "상한위(%)": e["상한위(%)"], "하한아래(%)": e["하한아래(%)"]})
    reg = pd.DataFrame(rows)
    reg.round(2).to_csv(os.path.join(RES_DIR, "06_급등_일반_급락_비교.csv"), index=False, encoding="utf-8-sig")
    print(f"\n■ 급등(전일 대비 ≥ {up_thr:+.1f}원) · 일반 · 급락(≤ {dn_thr:+.1f}원) 구간별 — 시험 구간")
    print(reg.round(1).to_string(index=False))

    # 시간대별 커버리지
    hc = []
    for k in ("B_LightGBM분위수", "E_앙상블", "F_앙상블+등각보정(최종)"):
        L, M, U = R_test[k]
        t = pd.DataFrame({"h": test["hour_n"], "y": test["y"], "L": L, "U": U}).dropna()
        t["in"] = (t["y"] >= t["L"]) & (t["y"] <= t["U"])
        t["w"] = t["U"] - t["L"]
        g = t.groupby("h").agg(PICP=("in", "mean"), MPIW=("w", "mean"))
        g["PICP"] *= 100
        g["방법"] = k
        hc.append(g.reset_index())
    hc = pd.concat(hc)
    hc.round(2).to_csv(os.path.join(RES_DIR, "07_시간대별_커버리지.csv"), index=False, encoding="utf-8-sig")

    그래프(cal_fit, err_q, tabs["시험(2026.1~9)"], test, R_test, hc, reg)
    print(f"\n  · 결과 CSV : {os.path.relpath(RES_DIR, BASE)}\\  그래프 : {os.path.relpath(PLOT_DIR, BASE)}\\")


def 그래프(cal_fit, err_q, tab, test, R_test, hc, reg):
    final = "F_앙상블+등각보정(최종)"

    # (1) 2025년 오차의 시간대별 10%·50%·90% — 평일 / 휴일
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), sharey=True)
    for ax, kind in zip(axes, ("평일", "휴일")):
        e = err_q[err_q.index.str.endswith(kind)].copy()
        h = e.index.str[:2].astype(int)
        ax.fill_between(h, e["오차_10%"], e["오차_90%"], color=C_BLUE, alpha=0.18, lw=0, label="오차 10~90% 범위")
        ax.plot(h, e["오차_50%"], color=C_BLUE, lw=2, label="오차 중앙값")
        ax.axhline(0, color=INK2, lw=1)
        ax.set_title(f"{kind}", color=INK, loc="left")
        ax.set_xlabel("시각")
        ax.set_xticks(range(1, 25, 2))
        스타일(ax)
    axes[0].set_ylabel("실제 - 예측 (원/kWh)")
    axes[0].legend(frameon=False, loc="lower left")
    fig.suptitle("① 2025년 예측 오차 분포 — 한낮·휴일일수록 오차 범위가 넓음", x=0.01, ha="left", color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "01_오차분포_시간대별.png"), dpi=150)
    plt.close(fig)

    # (2) 방법별 커버리지 vs 평균 폭
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    t = tab.copy()
    names = t.index.tolist()
    yy = np.arange(len(names))[::-1]
    col = [C_ORANGE if n == final else C_BLUE for n in names]
    axes[0].barh(yy, t["PICP(%)"], color=col, height=0.55)
    axes[0].axvspan(75, 85, color=C_AQUA, alpha=0.15, lw=0)
    axes[0].axvline(80, color=C_AQUA, lw=1.5, ls="--")
    for y_, v in zip(yy, t["PICP(%)"]):
        axes[0].text(v + 1, y_, f"{v:.1f}%", va="center", color=INK, fontsize=9)
    axes[0].set_yticks(yy, names)
    axes[0].set_xlim(0, 100)
    axes[0].set_title("커버리지 PICP (목표 75~85%, 초록 띠)", loc="left", color=INK)
    axes[1].barh(yy, t["MPIW(원)"], color=col, height=0.55)
    for y_, v, w in zip(yy, t["MPIW(원)"], t["Winkler"]):
        axes[1].text(v + 0.5, y_, f"{v:.1f}원 (Winkler {w:.1f})", va="center", color=INK, fontsize=9)
    axes[1].set_yticks(yy, [""] * len(names))
    axes[1].set_xlim(0, t["MPIW(원)"].max() * 1.6)
    axes[1].set_title("평균 폭 MPIW (좁을수록 좋음)", loc="left", color=INK)
    for ax in axes:
        스타일(ax)
        ax.grid(axis="x", color=GRID, lw=0.8)
        ax.grid(axis="y", visible=False)
    fig.suptitle("② 시험 구간(2026.1~9) 방법별 80% 예측 범위 성능", x=0.01, ha="left", color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "02_방법별_커버리지_폭.png"), dpi=150)
    plt.close(fig)

    # (3) 예측 범위 그래프 — 시험 구간 마지막 14일 + 급등이 가장 많았던 14일
    L, M, U = R_test[final]
    p = test[["date", "hour_n", "y", "naive"]].copy()
    p["L"], p["M"], p["U"] = L, M, U
    p["ts"] = pd.to_datetime(p["date"]) + pd.to_timedelta(p["hour_n"] - 1, unit="h")
    p["out"] = (p["y"] < p["L"]) | (p["y"] > p["U"])
    days = sorted(p["date"].unique())
    jump = (p["y"] - p["naive"]).groupby(p["date"]).max()
    roll = jump.rolling(14).sum()
    end_spike = roll.idxmax()
    i_end = days.index(end_spike)
    windows = [("급등이 많았던 2주", days[i_end - 13], days[i_end]), ("시험 구간 마지막 2주", days[-14], days[-1])]
    fig, axes = plt.subplots(2, 1, figsize=(14, 8.5))
    for ax, (ttl, a, b) in zip(axes, windows):
        w = p[(p["date"] >= a) & (p["date"] <= b)]
        cov = 100 * (1 - w["out"].mean())
        ax.fill_between(w["ts"], w["L"], w["U"], color=C_BLUE, alpha=0.2, lw=0, label="80% 예측 범위")
        ax.plot(w["ts"], w["M"], color=C_BLUE, lw=1.6, label="예측 중앙값")
        ax.plot(w["ts"], w["y"], color=INK, lw=1.4, label="실제 SMP")
        o = w[w["out"]]
        ax.scatter(o["ts"], o["y"], s=26, color=C_ORANGE, zorder=5, edgecolor="white", lw=0.8,
                   label="범위 밖")
        ax.set_title(f"{ttl} ({a} ~ {b}) — 커버리지 {cov:.1f}%, 평균 폭 {(w['U'] - w['L']).mean():.1f}원",
                     loc="left", color=INK)
        ax.set_ylabel("원/kWh")
        스타일(ax)
    axes[0].legend(frameon=False, ncol=4, loc="upper left")
    fig.suptitle("③ 최종 모델(앙상블 + 등각 보정)의 시간별 예측 범위", x=0.01, ha="left", color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "03_예측범위_시계열.png"), dpi=150)
    plt.close(fig)

    # (4) 시간대별 커버리지 — 보정 전/후
    fig, ax = plt.subplots(figsize=(12, 4.6))
    for k, c, lab in (("B_LightGBM분위수", C_AQUA, "LightGBM 분위수"),
                      ("E_앙상블", C_BLUE, "앙상블(보정 전)"),
                      (final, C_ORANGE, "앙상블 + 등각 보정(최종)")):
        g = hc[hc["방법"] == k]
        ax.plot(g["h"], g["PICP"], color=c, lw=2, marker="o", ms=5, label=lab)
    ax.axhspan(75, 85, color=C_AQUA, alpha=0.12, lw=0)
    ax.axhline(80, color=INK2, lw=1, ls="--")
    ax.set_xticks(range(1, 25))
    ax.set_xlabel("시각")
    ax.set_ylabel("커버리지 (%)")
    ax.legend(frameon=False, ncol=3, loc="lower left")
    스타일(ax)
    ax.set_title("④ 시간대별 커버리지 — 시험 구간 (띠 = 목표 75~85%)", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "04_시간대별_커버리지.png"), dpi=150)
    plt.close(fig)

    # (5) 급등 · 일반 · 급락 — 최종 모델의 가격 수준과 범위
    r = reg[reg["방법"] == final].set_index("구간").loc[["급등", "일반", "급락"]]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    x = np.arange(3)
    bw = 0.26
    for j, (colname, c, lab) in enumerate((("실제_평균가격", INK2, "실제 평균"),
                                          ("예측중앙_평균", C_BLUE, "예측 중앙값 평균"),
                                          ("어제같은시각_평균", C_AQUA, "어제 같은 시각"))):
        axes[0].bar(x + (j - 1) * bw, r[colname], width=bw - 0.03, color=c, label=lab)
    axes[0].set_xticks(x, [f"{k}\n({n:,}시간)" for k, n in zip(r.index, r["시간수"])])
    axes[0].set_ylabel("원/kWh")
    axes[0].legend(frameon=False, loc="upper right")
    axes[0].set_title("평균 가격 — 급등 시간은 예측이 실제를 못 따라감", loc="left", color=INK)
    axes[1].bar(x - 0.2, r["PICP(%)"], width=0.36, color=C_ORANGE, label="커버리지(%)")
    axes[1].bar(x + 0.2, r["MPIW(원)"], width=0.36, color=C_BLUE, label="평균 폭(원)")
    for xi, v1, v2 in zip(x, r["PICP(%)"], r["MPIW(원)"]):
        axes[1].text(xi - 0.2, v1 + 1, f"{v1:.0f}%", ha="center", color=INK, fontsize=9)
        axes[1].text(xi + 0.2, v2 + 1, f"{v2:.0f}원", ha="center", color=INK, fontsize=9)
    axes[1].axhline(80, color=INK2, lw=1, ls="--")
    axes[1].set_xticks(x, r.index)
    axes[1].legend(frameon=False, loc="upper right")
    axes[1].set_title("구간별 커버리지와 평균 폭", loc="left", color=INK)
    for ax in axes:
        스타일(ax)
    fig.suptitle("⑤ 급등 · 일반 · 급락 시간 비교 (최종 모델, 시험 구간)", x=0.01, ha="left", color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "05_급등_일반_급락_비교.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
