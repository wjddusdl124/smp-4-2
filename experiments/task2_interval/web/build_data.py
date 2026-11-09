# -*- coding: utf-8 -*-
"""
웹사이트용 데이터 만들기
results/ 의 CSV 를 읽어 web/data.js(window.DATA)로 묶는다.
브라우저에서 파일을 바로 열어도(file://) 동작하도록 JSON 을 JS 변수로 넣는다.

실행: .venv\\Scripts\\python.exe experiments\\task2_interval\\web\\build_data.py
"""
import json
import math
from pathlib import Path

import pandas as pd

# =====================================================================
# [1] 데이터 준비 — 경로와 CSV 읽기
# =====================================================================
WEB = Path(__file__).resolve().parent
RES = WEB.parent / "results"


def read(name):
    # 결과 CSV 는 utf-8-sig(BOM) 로 저장되어 있음
    return pd.read_csv(RES / name, encoding="utf-8-sig")


def num(x, nd=2):
    # NaN 은 JSON null 로, 나머지는 소수 nd 자리로
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), nd)


# 방법 코드(A~F) → 화면에 보일 이름
METHOD_NAME = {
    "A": "잔차 분위수",
    "B": "LightGBM 분위수 회귀",
    "C": "Chronos-2 + 수요예측",
    "D": "Chronos-2 단변량",
    "E": "앙상블 (보정 전)",
    "F": "앙상블 + 등각 보정",
}

# =====================================================================
# [2] 표 형태 결과 정리
# =====================================================================
# MAPE·편의 분모 하한(원/kWh) — 운영 코드(scripts/step4_baseline.py)와 같은 정의
MAPE_FLOOR = 20.0


def point_metrics():
    """시험 구간 중앙값 예측의 MAPE·편의(%) — 방법별.
    MAPE = mean(|예측−실제| / max(실제, 20)) × 100
    편의 = mean((예측−실제) / max(실제, 20)) × 100  (+ 면 실제보다 높게 예측)
    보정 구간(2025)은 시간별 예측이 저장되어 있지 않아 계산하지 않음
    """
    df = read("04_시험구간_예측범위.csv").dropna(subset=["y"])
    den = df["y"].clip(lower=MAPE_FLOOR)
    out = {}
    for col in [c for c in df.columns if c.endswith("_중앙")]:
        err = df[col] - df["y"]
        out[col[0]] = {"mape": num((err.abs() / den).mean() * 100),
                       "bias": num((err / den).mean() * 100)}
    return out


POINT = point_metrics()


def eval_table(name, with_point):
    df = read(name)
    rows = []
    for _, r in df.iterrows():
        code = r["방법"][0]
        pm = POINT[code] if with_point else {"mape": None, "bias": None}
        rows.append({
            "code": code,
            "name": METHOD_NAME[code],
            "picp": num(r["PICP(%)"], 1),
            "mpiw": num(r["MPIW(원)"], 1),
            "winkler": num(r["Winkler"], 1),
            "pb10": num(r["pinball_0.1"]),
            "pb50": num(r["pinball_0.5"]),
            "pb90": num(r["pinball_0.9"]),
            "below": num(r["하한아래(%)"], 1),
            "above": num(r["상한위(%)"], 1),
            "mae": num(r["MAE(중앙값)"]),
            "mae_naive": num(r["MAE(어제같은시각)"]),
            "gain": num(r["개선율(%)"], 1),
            "rmae": num(r["MAE(중앙값)"] / r["MAE(어제같은시각)"], 3),
            "mape": pm["mape"],
            "bias": pm["bias"],
            "n": int(r["n"]),
        })
    return rows


evals = {"test": eval_table("05_평가_시험구간.csv", True),
         "calib": eval_table("05_평가_보정구간_참고.csv", False)}

# 시간대별 커버리지(B, E, F)
hourly = {}
for _, r in read("07_시간대별_커버리지.csv").iterrows():
    hourly.setdefault(r["방법"][0], []).append(
        {"h": int(r["h"]), "picp": num(r["PICP"], 1), "mpiw": num(r["MPIW"], 1)})

# 급등·일반·급락
regimes = []
for _, r in read("06_급등_일반_급락_비교.csv").iterrows():
    regimes.append({
        "code": r["방법"][0], "regime": r["구간"], "n": int(r["시간수"]),
        "actual": num(r["실제_평균가격"], 1), "naive": num(r["어제같은시각_평균"], 1),
        "pred": num(r["예측중앙_평균"], 1), "picp": num(r["PICP(%)"], 1),
        "mpiw": num(r["MPIW(원)"], 1), "mae": num(r["MAE(중앙값)"], 1),
        "above": num(r["상한위(%)"], 1), "below": num(r["하한아래(%)"], 1),
    })

# 앙상블 가중치
weights = []
for _, r in read("02_앙상블_가중치.csv").iterrows():
    weights.append({"q": r["분위수"], "lgb": num(r["lgb"]),
                    "cov": num(r["chr_cov"]), "uni": num(r["chr_uni"]),
                    "pinball": num(r["pinball"], 3)})

# 등각 보정값(시간대 × 평일/휴일)
conformal = []
for _, r in read("03_등각보정값_시간대x평일휴일.csv").iterrows():
    hh, kind = r["그룹"].split("_")
    conformal.append({"h": int(hh.replace("시", "")), "kind": kind,
                      "lo": num(r["하한_보정"]), "hi": num(r["상한_보정"])})

# 급등일 vs 일반일 (spike_days.py 결과) — 급등일 = 그날 최고 SMP ≥ 직전 28일 일 최고가 중앙값 × 1.25
spike = None
if (RES / "10_급등일_일반일_비교.csv").exists():
    cmp_ = read("10_급등일_일반일_비교.csv")
    spike_cmp = []
    for _, r in cmp_.iterrows():
        spike_cmp.append({
            "period": "test" if r["기간"].startswith("시험") else "calib",
            "code": r["방법"][0], "kind": r["구분"], "days": int(r["일수"]), "n": int(r["n"]),
            "picp": num(r["PICP(%)"], 1), "mpiw": num(r["MPIW(원)"], 1), "winkler": num(r["Winkler"], 1),
            "below": num(r["하한아래(%)"], 1), "above": num(r["상한위(%)"], 1),
            "mae": num(r["MAE(중앙값)"]), "rmae": num(r["rMAE"], 3),
            "mape": num(r["MAPE(%)"]), "bias": num(r["편의(%)"]),
        })
    peak = []
    for _, r in read("12_피크_D-1탐지_요약.csv").iterrows():
        peak.append({
            "period": "test" if r["기간"].startswith("시험") else "calib", "kind": r["구분"], "days": int(r["일수"]),
            "actualMax": num(r["실제_최고_평균(원)"], 1), "medMax": num(r["예측중앙_최고_평균(원)"], 1),
            "upMax": num(r["예측상한_최고_평균(원)"], 1), "under": num(r["최고가_과소예측_평균(원)"], 1),
            "peakHit": num(r["피크시_범위적중(%)"], 1), "shortfall": num(r["피크시_부족분_평균(원)"], 1),
            "timing": num(r["피크시각_일치(±1시간,%)"], 1),
            "sigMed": num(r["D-1신호_중앙(%)"], 1), "sigUp": num(r["D-1신호_상한(%)"], 1),
        })
    days = []
    for _, r in read("11_일별_피크_최종모델.csv").iterrows():
        if not r["급등일"]:
            continue
        days.append({
            "period": "test" if r["기간"].startswith("시험") else "calib", "date": r["date"],
            "ref": num(r["기준_28일중앙(원)"], 1), "actualMax": num(r["실제_최고(원)"], 1),
            "ratio": num(r["실제_배율"], 2), "peakHour": int(r["실제_피크시"]),
            "medMax": num(r["예측중앙_최고(원)"], 1), "upAtPeak": num(r["피크시_상한(원)"], 1),
            "shortfall": num(r["피크시_부족분(원)"], 1), "dayCov": num(r["하루_커버리지(%)"], 1),
            "dayMae": num(r["하루_MAE(원)"], 2), "predPeakHour": int(r["예측중앙_피크시"]),
        })
    lst = read("09_급등일_목록.csv")
    all59 = {
        "n": len(lst),
        "byYear": lst["date"].str[:4].value_counts().sort_index().to_dict(),
        "byMonth": {int(k): int(v) for k, v in lst["date"].str[5:7].value_counts().sort_index().items()},
        "byHour": {int(k): int(v) for k, v in lst["피크시"].value_counts().sort_index().items()},
        "oneHour": int((lst["기준초과_시간수"] == 1).sum()),
        "ratioMedian": num(lst["배율"].median(), 2),
        "ratioMax": num(lst["배율"].max(), 2),
    }
    shape = read("13_급등일_시간대별_모양.csv")
    shp = {k: {c: [num(v, 1) for v in g.sort_values("hour_n")[c]] for c in ("실제", "중앙", "하한", "상한")}
           for k, g in shape.groupby("구분")}
    spike = {"cmp": spike_cmp, "peak": peak, "days": days, "all": all59,
             "shape": {"spike": shp["급등일"], "normal": shp["일반일"]}}

# =====================================================================
# [3] 시계열(최종 모델) — 1시간 간격 연속 배열로 압축
# =====================================================================
ts = read("08_최종모델_예측범위.csv")
ts["datetime"] = pd.to_datetime(ts["datetime"])
series = {
    "start": ts["datetime"].iloc[0].strftime("%Y-%m-%dT%H:%M"),
    "actual": [num(v) for v in ts["actual"]],
    "lower": [num(v) for v in ts["lower"]],
    "median": [num(v) for v in ts["median"]],
    "upper": [num(v) for v in ts["upper"]],
    "naive": [num(v) for v in ts["naive"]],
}
# 1시간 간격이 끊기지 않았는지 확인(끊기면 배열 인덱스로 시각을 복원할 수 없음)
assert (ts["datetime"].diff().dropna() == pd.Timedelta("1h")).all()

# =====================================================================
# [4] 저장
# =====================================================================
data = {"evals": evals, "hourly": hourly, "regimes": regimes,
        "weights": weights, "conformal": conformal, "series": series, "spike": spike}
out = WEB / "data.js"
out.write_text("window.DATA = " + json.dumps(data, ensure_ascii=False,
                                               separators=(",", ":")) + ";\n",
               encoding="utf-8")
print(f"저장: {out}  ({out.stat().st_size / 1024:.0f} KB, 시계열 {len(ts)}시간)")
