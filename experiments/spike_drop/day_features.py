# -*- coding: utf-8 -*-
"""
day_features.py — 급등일·급락일 판별용 「날짜 단위」 입력 변수
==============================================================================
정의 (spike_days.py 와 같은 방식, 둘 다 D-1 까지의 값으로 기준을 잡음)
  · 급등일 : 그날 최고 SMP ≥ 직전 28일 「일 최고 SMP」 중앙값 × 1.25
  · 급락일 : 그날 최저 SMP ≤ 직전 28일 「일 최저 SMP」 중앙값 × 0.50  (경보 모델 학습용 "drop")
  · 채점용 급락일 : 거래시간 11~15시 중 1시간이라도 30원 미만 (기업 정의, "drop_corp") — 2026.11.2 부터 모든 성적표는 이 정의
    (2025~2026 급락일은 대부분 최저가 0~7원인 경부하·출력제어 날)

변수 묶음
  · OPER  : 지금 운영에서 D-1 에 확보 가능한 값 (과거 SMP, 하루전 수요예측, 달력, D-2 태양광 대리지표)
  · WX    : 기상청 단기예보로 받을 수 있는 항목(기온·강수)을 「실측값」으로 대신 넣은 것
            → 예보 오차가 없다고 가정하므로 실제보다 낙관적인 「상한」
  · ORACLE: 지금은 D-1 에 알 수 없는 실측(일사·일조·태양광/풍력 발전·수요 실적)
            → 분석 전용. 「이 정보를 미리 알 수 있다면」 최대 얼마나 좋아지나를 재는 용도
"""
import os

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(BASE, "data", "processed", "smp_dataset_hourly.csv")

SPIKE_RATIO = 1.25
DROP_RATIO = 0.50
REF_DAYS = 28
CORP_DROP_WON = 30   # 기업 급락 정의 (11~15시 중 30원 미만)


def 시간표(d, col):
    """날짜 × 시간(1~24) 표"""
    return d.pivot(index="date", columns="hour_n", values=col)


def 만들기():
    raw = pd.read_csv(DATA, encoding="utf-8-sig", low_memory=False)
    raw["date"] = raw["date"].astype(str).str[:10]
    days = pd.date_range(raw["date"].min(), raw["date"].max(), freq="D").strftime("%Y-%m-%d")
    grid = pd.MultiIndex.from_product([days, range(1, 25)], names=["date", "hour_n"]).to_frame(index=False)
    d = grid.merge(raw, on=["date", "hour_n"], how="left").sort_values(["date", "hour_n"])

    Y = 시간표(d, "smp_land")
    F = 시간표(d, "demand_fcst_land")
    PV = 시간표(d, "pv_land")
    dt = pd.to_datetime(pd.Series(Y.index, index=Y.index))

    g = pd.DataFrame(index=Y.index)
    # ---------------- 정답 (D일 실제값 — 평가용, 입력 아님)
    g["day_max"] = Y.max(axis=1)
    g["day_min"] = Y.min(axis=1)
    g["ref_max"] = g["day_max"].shift(1).rolling(REF_DAYS, min_periods=REF_DAYS).median()
    g["ref_min"] = g["day_min"].shift(1).rolling(REF_DAYS, min_periods=REF_DAYS).median()
    g["spike"] = (g["day_max"] >= g["ref_max"] * SPIKE_RATIO).astype(float)
    g["drop"] = (g["day_min"] <= g["ref_min"] * DROP_RATIO).astype(float)
    g.loc[g["day_max"].isna() | g["ref_max"].isna(), "spike"] = np.nan
    g.loc[g["day_min"].isna() | g["ref_min"].isna(), "drop"] = np.nan
    # 채점용 급락일 = 기업 정의 (3차 수업 피드백 v1.1) : 거래시간 11~15시 중 1시간이라도 30원 미만
    #   경보 모델의 학습 정답·문턱·입력 변수는 위 "drop"(우리 정의) 그대로 — 결과 채점·표시만 이 정의로 통일 (11/2)
    mid = Y[[11, 12, 13, 14, 15]]
    g["mid_min"] = mid.min(axis=1)
    g["drop_corp"] = (g["mid_min"] < CORP_DROP_WON).astype(float).where(mid.notna().all(axis=1))

    # ---------------- OPER : 달력 (미리 알 수 있음)
    hol = d.groupby("date")["is_holiday"].max().reindex(Y.index).fillna(0)
    off = ((dt.dt.dayofweek >= 5) | (hol == 1)).astype(int)
    g["dow"] = dt.dt.dayofweek
    g["month"] = dt.dt.month
    doy = dt.dt.dayofyear
    g["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    g["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    g["offday"] = off
    g["is_holiday"] = hol
    g["prev_offday"] = off.shift(1).fillna(0)
    g["next_offday"] = off.shift(-1).fillna(0)          # 내일 휴일 여부는 달력으로 미리 앎
    run = off.groupby((off != off.shift()).cumsum()).transform("size") * off
    g["off_run_len"] = run                               # 연휴 길이(평일 0)

    # ---------------- OPER : 과거 SMP (D-1 까지)
    s = lambda x, k=1: x.shift(k)
    g["y_max_r"] = s(g["day_max"]) / g["ref_max"]
    g["y_min_r"] = s(g["day_min"]) / g["ref_min"]
    g["y_mean"] = s(Y.mean(axis=1))
    g["y_std"] = s(Y.std(axis=1))
    g["y_h10_r"] = s(Y[10]) / g["ref_max"]
    g["y_mid_min_r"] = s(Y[[11, 12, 13, 14, 15]].min(axis=1)) / g["ref_min"]
    g["w1_max_r"] = s(g["day_max"], 7) / g["ref_max"]    # 지난주 같은 요일
    g["w1_min_r"] = s(g["day_min"], 7) / g["ref_min"]
    g["max7_r"] = s(g["day_max"]).rolling(7, min_periods=4).max() / g["ref_max"]
    g["min7_r"] = s(g["day_min"]).rolling(7, min_periods=4).min() / g["ref_min"]
    g["spike_cnt7"] = s(g["spike"]).rolling(7, min_periods=1).sum()
    g["spike_cnt28"] = s(g["spike"]).rolling(28, min_periods=1).sum()
    g["drop_cnt7"] = s(g["drop"]).rolling(7, min_periods=1).sum()
    g["drop_cnt28"] = s(g["drop"]).rolling(28, min_periods=1).sum()
    g["w1_spike"] = s(g["spike"], 7)
    g["w1_drop"] = s(g["drop"], 7)
    g["ref_max"] = g["ref_max"]
    g["ref_min_lvl"] = g["ref_min"]
    g["ref_gap"] = g["ref_max"] - g["ref_min"]

    # ---------------- OPER : 전력거래소 하루전 수요예측 (D일 값, D-1 공표)
    g["f_max"] = F.max(axis=1)
    g["f_min"] = F.min(axis=1)
    g["f_mean"] = F.mean(axis=1)
    g["f_max_r28"] = g["f_max"] / s(g["f_max"]).rolling(REF_DAYS, min_periods=14).median()
    g["f_min_r28"] = g["f_min"] / s(g["f_min"]).rolling(REF_DAYS, min_periods=14).median()
    g["f_max_d1"] = g["f_max"] - s(g["f_max"])
    g["f_min_d1"] = g["f_min"] - s(g["f_min"])
    g["f_max_w1"] = g["f_max"] - s(g["f_max"], 7)
    g["f_h10"] = F[10]
    g["f_ramp_7_10"] = F[10] - F[7]
    g["f_mid"] = F[[11, 12, 13, 14, 15]].mean(axis=1)
    g["f_peak_h"] = F.fillna(-1).idxmax(axis=1).where(F.notna().any(axis=1))
    # 태양광 설비 대리지표 (D-2 ~ D-31 한낮 실적 최댓값) — task2 와 같은 방식
    pv_mid = PV[[11, 12, 13, 14, 15]].mean(axis=1)
    g["pv_cap"] = pv_mid.shift(2).rolling(30, min_periods=10).max()
    g["net_mid_proxy"] = g["f_mid"] - g["pv_cap"]
    g["net_mid_r"] = g["net_mid_proxy"] / s(g["net_mid_proxy"]).rolling(REF_DAYS, min_periods=14).median()

    # ---------------- WX : 기상청 단기예보 항목(기온·강수)을 실측으로 대신 — 낙관적 상한
    T = 시간표(d, "temp_land")
    R = 시간표(d, "rain_land")
    g["wx_t_max"] = T.max(axis=1)
    g["wx_t_min"] = T.min(axis=1)
    g["wx_t_mean"] = T.mean(axis=1)
    g["wx_t_d1"] = g["wx_t_mean"] - s(g["wx_t_mean"])
    g["wx_t_min_d1"] = g["wx_t_min"] - s(g["wx_t_min"])
    g["wx_hdd"] = np.clip(18 - g["wx_t_mean"], 0, None)
    g["wx_cdd"] = np.clip(g["wx_t_mean"] - 24, 0, None)
    g["wx_rain_day"] = R[list(range(9, 18))].sum(axis=1)

    # ---------------- ORACLE : 지금은 D-1 에 알 수 없는 실측 — 분석 전용
    S = 시간표(d, "solar_land")
    SU = 시간표(d, "sunshine_land")
    DA = 시간표(d, "demand_actual")
    WD = 시간표(d, "wind_land")
    NL = DA - PV.fillna(0) - WD.fillna(0)
    g["or_solar_day"] = S[list(range(9, 18))].sum(axis=1)
    g["or_sun_day"] = SU[list(range(9, 18))].sum(axis=1)
    g["or_pv_mid"] = pv_mid
    g["or_pv_mid_r"] = pv_mid / g["pv_cap"]
    g["or_dem_max"] = DA.max(axis=1)
    g["or_dem_err_max"] = DA.max(axis=1) - g["f_max"]     # 수요예측 오차(최대)
    g["or_dem_err_h10"] = DA[10] - F[10]
    g["or_net_min"] = NL.min(axis=1)
    g["or_net_max"] = NL.max(axis=1)
    g["or_net_min_r"] = g["or_net_min"] / s(g["or_net_min"]).rolling(REF_DAYS, min_periods=14).median()
    g["or_wind_mean"] = WD.mean(axis=1)
    return d, g


OPER = ["dow", "month", "doy_sin", "doy_cos", "offday", "is_holiday", "prev_offday", "next_offday",
        "off_run_len", "y_max_r", "y_min_r", "y_mean", "y_std", "y_h10_r", "y_mid_min_r", "w1_max_r",
        "w1_min_r", "max7_r", "min7_r", "spike_cnt7", "spike_cnt28", "drop_cnt7", "drop_cnt28",
        "w1_spike", "w1_drop", "ref_max", "ref_min_lvl", "ref_gap", "f_max", "f_min", "f_mean",
        "f_max_r28", "f_min_r28", "f_max_d1", "f_min_d1", "f_max_w1", "f_h10", "f_ramp_7_10", "f_mid",
        "f_peak_h", "pv_cap", "net_mid_proxy", "net_mid_r"]
WX = ["wx_t_max", "wx_t_min", "wx_t_mean", "wx_t_d1", "wx_t_min_d1", "wx_hdd", "wx_cdd", "wx_rain_day"]
ORACLE = ["or_solar_day", "or_sun_day", "or_pv_mid", "or_pv_mid_r", "or_dem_max", "or_dem_err_max",
          "or_dem_err_h10", "or_net_min", "or_net_max", "or_net_min_r", "or_wind_mean"]

if __name__ == "__main__":
    _, g = 만들기()
    g["year"] = g.index.str[:4]
    print(g.groupby("year")[["spike", "drop"]].sum())
    print(g[OPER + WX + ORACLE].isna().mean().sort_values().tail(8))
