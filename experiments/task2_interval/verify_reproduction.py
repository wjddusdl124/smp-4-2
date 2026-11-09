# -*- coding: utf-8 -*-
"""
verify_reproduction.py — 다른 PC 에서 돌린 결과가 원본과 같은지 자동 확인
==============================================================================
확인 순서
  [1] 환경   : 파이썬·핵심 패키지 버전 (다르면 경고만)
  [2] 입력   : 데이터 파일 SHA-256 (다르면 실패 — 데이터가 다르면 결과도 다름)
               Chronos 예측 저장본 SHA-256 (같으면 Chronos 부분은 원본과 완전히 같음)
  [3] 결과   : results/ 의 핵심 수치를 원본 값과 비교 (허용오차 안이면 통과)
  [4] 판정   : 모두 통과하면 종료코드 0, 하나라도 실패하면 1

실행 (task2_interval.py → spike_days.py 를 먼저 실행한 뒤)
  .venv\\Scripts\\python.exe experiments\\task2_interval\\verify_reproduction.py
"""
import hashlib
import os
import platform
import sys
from importlib import metadata

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(HERE, "results")

# =============================================================================
# 원본 결과 (2026-10-26, Windows 11 · Python 3.14.7 에서 생성)
# =============================================================================
EXPECT_PY = "3.14"
EXPECT_PKG = {"numpy": "2.5.4", "pandas": "3.0.6", "lightgbm": "4.7.0", "matplotlib": "3.11.2",
              "torch": "2.14.1", "chronos-forecasting": "2.3.2", "transformers": "5.20.2"}
SHA_DATA = "704431b039d572a66b46f9883163c66b0ba77f2ee353afbdd32776573b29086e"
SHA_CHRONOS = "24e75757d6a7f42684b87c35a455b68ea56e3574cdf2c6463e803ccf537d4a43"

# 방법별 [커버리지(%), 평균 폭(원), Winkler, MAE(원)]
REF_EVAL = {
    "test": {"A_잔차분위수": [74.433, 26.559, 49.801, 9.36], "B_LightGBM분위수": [68.551, 23.588, 46.02, 9.357],
             "C_Chronos2_수요예측": [73.1, 21.749, 38.591, 7.827], "D_Chronos2_단변량": [72.044, 23.628, 44.169, 8.743],
             "E_앙상블": [75.214, 21.901, 38.018, 7.847], "F_앙상블+등각보정(최종)": [79.963, 24.955, 37.701, 7.847]},
    "calib": {"A_잔차분위수": [79.726, 26.532, 40.485, 8.787], "B_LightGBM분위수": [66.518, 21.266, 44.724, 8.775],
              "C_Chronos2_수요예측": [75.057, 20.9, 36.971, 7.483], "D_Chronos2_단변량": [73.63, 21.709, 41.424, 8.01],
              "E_앙상블": [75.947, 21.178, 36.259, 7.397], "F_앙상블+등각보정(최종)": [82.466, 24.232, 35.494, 7.397]},
}
REF_WEIGHTS = {"q10": [0.15, 0.85, 0.0], "q50": [0.15, 0.8, 0.05], "q90": [0.25, 0.75, 0.0]}
REF_CONFORMAL_SUM = [111.789, 72.515]        # 48개 그룹 하한·상한 보정값 합
REF_SPIKE_DAYS = 59
# 최종 모델 급등일/일반일 [일수, 커버리지(%), MAE(원)]
REF_SPIKE_F = {"보정 2025|급등일": [7, 76.786, 9.651], "보정 2025|일반일": [358, 82.577, 7.353],
               "시험 2026|급등일": [6, 84.028, 6.701], "시험 2026|일반일": [267, 79.872, 7.872]}
# 하루 최고가 [일수, 최고가 시간 적중(%), 상한 초과 평균(원)]
REF_PEAK = {"보정 2025|일반일": [358, 58.66, 4.23], "보정 2025|급등일": [7, 0.0, 43.86],
            "시험 2026|일반일": [266, 56.39, 2.86], "시험 2026|급등일": [6, 0.0, 39.4]}

rows = []


def 기록(구분, 항목, 결과, 내용):
    rows.append((구분, 항목, 결과, 내용))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(name):
    return pd.read_csv(os.path.join(RES, name), encoding="utf-8-sig")


def 비교(구분, 항목, got, ref, tol):
    diff = max(abs(g - r) for g, r in zip(got, ref))
    기록(구분, 항목, "통과" if diff <= tol else "실패", f"최대 차이 {diff:.4f} (허용 {tol}) · 값 {[round(float(g), 3) for g in got]}")


# =============================================================================
# [1] 환경
# =============================================================================
py = platform.python_version()
기록("환경", "Python", "통과" if py.startswith(EXPECT_PY) else "경고", f"{py} (원본 {EXPECT_PY}.x)")
for pkg, want in EXPECT_PKG.items():
    try:
        have = metadata.version(pkg)
    except metadata.PackageNotFoundError:
        기록("환경", pkg, "경고", f"설치 안 됨 (원본 {want})")
        continue
    기록("환경", pkg, "통과" if have.split("+")[0] == want else "경고", f"{have} (원본 {want})")

# =============================================================================
# [2] 입력 파일
# =============================================================================
data = os.path.join(BASE, "data", "processed", "smp_dataset_hourly.csv")
if not os.path.exists(data):
    기록("입력", "데이터", "실패", "data/processed/smp_dataset_hourly.csv 없음")
else:
    ok = sha256(data) == SHA_DATA
    기록("입력", "데이터 SHA-256", "통과" if ok else "실패",
         "원본과 같음" if ok else "원본과 다름 → 같은 데이터 파일을 받아야 같은 결과가 나옴")

ch = os.path.join(RES, "chronos_preds.csv")
same_chronos = os.path.exists(ch) and sha256(ch) == SHA_CHRONOS
if not os.path.exists(ch):
    기록("입력", "Chronos 저장본", "실패", "results/chronos_preds.csv 없음 → task2_interval.py 를 먼저 실행")
else:
    기록("입력", "Chronos 저장본", "통과" if same_chronos else "경고",
         "원본 저장본 그대로 사용" if same_chronos
         else "이 PC 에서 다시 예측함 → CPU·스레드 차이로 소수점이 조금 다를 수 있어 허용오차를 넓힘")

# Chronos 저장본이 같으면 LightGBM 부분만 달라질 수 있음 → 좁은 허용오차
TOL = 0.01 if same_chronos else 0.5

# =============================================================================
# [3] 결과 수치
# =============================================================================
try:
    for tag, f in (("test", "05_평가_시험구간.csv"), ("calib", "05_평가_보정구간_참고.csv")):
        d = read(f).set_index("방법")
        for k, ref in REF_EVAL[tag].items():
            r = d.loc[k]
            비교("결과", f"{'시험' if tag == 'test' else '보정'} {k[0]} 커버리지·폭·Winkler·MAE",
                 [round(r["PICP(%)"], 3), round(r["MPIW(원)"], 3), round(r["Winkler"], 3),
                  round(r["MAE(중앙값)"], 3)], ref, TOL)

    w = read("02_앙상블_가중치.csv").set_index("분위수")
    got = {q: [float(w.loc[q, c]) for c in ("lgb", "chr_cov", "chr_uni")] for q in REF_WEIGHTS}
    기록("결과", "앙상블 가중치", "통과" if got == REF_WEIGHTS else "실패", str(got))

    c = read("03_등각보정값_시간대x평일휴일.csv")
    비교("결과", "등각 보정값 합(하한·상한)", [round(c["하한_보정"].sum(), 3), round(c["상한_보정"].sum(), 3)],
         REF_CONFORMAL_SUM, TOL * 10)
except FileNotFoundError as e:
    기록("결과", "task2_interval.py 결과", "실패", f"{os.path.basename(e.filename)} 없음 → 먼저 실행")

try:
    n = len(read("09_급등일_목록.csv"))
    기록("결과", "급등일 수(2021~)", "통과" if n == REF_SPIKE_DAYS else "실패", f"{n}일 (원본 {REF_SPIKE_DAYS}일)")
    s = read("10_급등일_일반일_비교.csv")
    s = s[s["방법"].str.startswith("F")]
    for _, r in s.iterrows():
        key = f"{r['기간']}|{r['구분']}"
        비교("결과", f"급등일 비교 {key}", [int(r["일수"]), round(r["PICP(%)"], 3), round(r["MAE(중앙값)"], 3)],
             REF_SPIKE_F[key], TOL)
    p = read("12_피크_D-1탐지_요약.csv")
    for _, r in p.iterrows():
        key = f"{r['기간']}|{r['구분']}"
        비교("결과", f"최고가 분석 {key}",
             [int(r["일수"]), round(r["피크시_범위적중(%)"], 2), round(r["피크시_부족분_평균(원)"], 2)],
             REF_PEAK[key], max(TOL, 0.01) * 10)
except FileNotFoundError as e:
    기록("결과", "spike_days.py 결과", "실패", f"{os.path.basename(e.filename)} 없음 → 먼저 실행")

# =============================================================================
# [4] 판정
# =============================================================================
w1 = max(len(r[1]) for r in rows) + 2
for 구분, 항목, 결과, 내용 in rows:
    mark = {"통과": "OK  ", "경고": "WARN", "실패": "FAIL"}[결과]
    print(f"[{mark}] {구분:<3} {항목:<{w1}} {내용}")
fails = sum(r[2] == "실패" for r in rows)
warns = sum(r[2] == "경고" for r in rows)
print("-" * 70)
if fails:
    print(f"재현 실패 — 실패 {fails}개, 경고 {warns}개. REPRODUCE.md 의 「문제 해결」을 보세요.")
    sys.exit(1)
print("재현 성공 — 모든 결과가 원본과 같습니다." + (f" (경고 {warns}개: 버전·저장본 차이 안내)" if warns else ""))
