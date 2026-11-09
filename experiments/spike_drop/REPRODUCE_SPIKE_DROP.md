# SMP 급등·급락 예측 — 재현 가이드

이 문서대로 하면 다른 컴퓨터에서도 **최종 모델 3개(평소 가격 · 급락 경보 · 급등 대응)의 결과와 대시보드**가 원본과 같은 숫자로 다시 만들어집니다.

> 검증 (2026-11-02) : 결과 파일을 모두 지운 깨끗한 복사본에서 `run_all.py --check` 를 실행 → **대시보드 데이터셋 23/23개가 원본과 바이트 단위로 같음** (Linux · Python 3.13 · CPU, 전체 5.1분)
> 기본 모델(task2_interval)의 원본 환경은 Windows 11 · Python 3.14.7 이며, 그쪽 재현은 `experiments/task2_interval/REPRODUCE.md` 에서 따로 확인됨

---

## 1. 무엇이 재현되나 — 최종 채택 모델

설정은 모두 **2025년(보정 구간)에서만** 고르고, **2026.1.1~9.30 시험 구간에 한 번만** 적용했습니다. 입력은 **D-1에 알 수 있는 값만** 씁니다.

### ① 평소 가격 (예측 범위 · 중앙값)

| 분위 | LightGBM 분위수 | Chronos-2 + 수요예측 | Chronos-2 단변량 |
|---|---|---|---|
| 하한 (10%) | 15% | 85% | 0% |
| 중앙값 (50%) | 15% | 80% | 5% |
| 상한 (90%) | 25% | 75% | 0% |

1. 세 모델 앙상블 (가중치는 2025년 pinball 손실 최소, 0.05 간격)
2. 등각 보정 : 시간대 × 평일/휴일 48그룹, 2025년에 80%가 범위 안에 들도록
3. 방향 넓히기 : 중앙값 > 어제 같은 시각이면 상한 ×2.0, 작으면 하한 ×1.7
4. 위험 시각 : 평일 10·11·15·16시 상한 = max(넓힌 상한, 원래 상한 + 67.8원)

| 2026 결과 | 값 |
|---|---|
| 범위 안에 든 비율 | 80.0% → **89.3%** |
| 평균 범위 폭 | 24.96원 → 42.18원 |
| 중앙값 MAE · rMAE · MAPE · 편의 | 7.85원 · 0.700 · 8.03% · 1.81% (목표 0.65 · 7.0원 · 5.0% · 1.5% 모두 미달) |

### ② 급락 경보

- 모델 : **XGBoost · CatBoost · RandomForest 확률을 1/3씩 평균** (각 시드 3회 평균)
- 입력 : 운영 변수 43개(과거 SMP, 하루전 수요예측, 달력, 태양광 설비 대리값) + 명절 여부 · 연휴 며칠째 · 연휴 남은 날 · 마지막 급락 후 경과일
- 학습 가중 : 2024년 이후 자료 ×3
- 경보 문턱 : **3.894%** (2025년 급락일의 75%를 잡는 값), 단일 단계
- 급락일 채점 : 기업 정의 「거래시간 11~15시 중 1시간이라도 30원 미만」 (2026.11.2 통일, `day_features.drop_corp`). 모델 학습 정답·문턱은 이전 정의(직전 28일 최저가 중앙값의 절반 이하) 그대로 — 2025년은 두 정의의 급락일 19일이 같음
- 2026 결과 : 급락일 **18/20** 잡음, 경보 60일, 적중 30.0%

### ③ 급등 대응 (두 겹)

- 하루 전 경보 : **LightGBM · XGBoost · CatBoost 확률을 1/3씩 평균** (각 시드 3회), 학습 2023-01-08~
  - 입력 : 운영 변수 16개 + 전력거래소 일별 전력수급실적 6개(내일 예상예비율, 전날 예비율, 전날 공급능력, 공급능력 1주 변화 등)
  - 경보 문턱 : **6.79%** (2025년 확률 상위 20일이 되는 값) + 전날 급등이면 경계
- 넓힌 범위 : ①의 3·4단계
- 2026 결과 : 급등일 6일 중 경보 3일(경보 10일, 적중 30%), 범위 안 5일, **둘 중 하나로 6/6** 대비

모든 실험(31개)과 채택 이유는 Claude 문서 「SMP 급등·급락 예측 모델 기록」에 있습니다.

---

## 2. 준비물

### 폴더 구조

`sp` 폴더(원본의 `student-practice`)를 통째로 옮깁니다. 아래 파일이 꼭 있어야 합니다.

```
sp/
├─ data/
│  ├─ processed/smp_dataset_hourly.csv          ← 기본 데이터 (2021.1~2026.10.6)
│  └─ external/
│     ├─ supply_daily_raw.csv                   ← 전력거래소 일별 전력수급실적 (cp949)
│     ├─ fuel_cost.csv                          ← EPSIS 연료비용 (월별)
│     ├─ smp_fuel_set.csv                       ← EPSIS 연료원별 SMP결정 (월별)
│     └─ fuel_2026/                             ← 기업 제공 연료비 자료 (변동비 순위 발전기별·연료별 요약, 열량단가, 안내문)
└─ experiments/
   ├─ task2_interval/
   │  ├─ task2_interval.py                      ← 평소 가격 기본 모델 A~F
   │  ├─ requirements-task2.txt
   │  └─ results/chronos_preds.csv              ← Chronos-2 예측 저장본 (꼭 함께 옮기기)
   └─ spike_drop/
      ├─ run_all.py                             ← 전체 실행 (이것 하나만 실행하면 됨)
      ├─ make_dashboard_data.py                 ← 대시보드 데이터셋 20개
      ├─ requirements-spike_drop.txt
      ├─ reference/                             ← 원본 대시보드 데이터셋 23개 (비교용)
      ├─ dashboard/                             ← 대시보드 페이지 · d3 · 오프라인 빌더
      └─ *.py                                   ← 모델·실험 코드
```

### 입력 파일 확인 (SHA-256)

같은 결과가 나오려면 입력이 같아야 합니다. 아래 값과 다르면 데이터가 바뀐 것입니다.

| 파일 | SHA-256 |
|---|---|
| data/processed/smp_dataset_hourly.csv | `704431b039d572a66b46f9883163c66b0ba77f2ee353afbdd32776573b29086e` |
| data/external/supply_daily_raw.csv | `4517e0c782ac78848d41845a8ea0ca5b052fe433a3b65e9e467b9128a4836dfb` |
| data/external/fuel_cost.csv | `e9bd003b912a442d6b7046407575633190c92b71b7e0888898b6573c6404518c` |
| data/external/smp_fuel_set.csv | `d88a9bc78931b9b980006fa7d2d46df57c889d365a5dbad38627cac6dce8371a` |
| data/external/fuel_2026/변동비순위_발전기별_202203-202611.csv | `17f355021a8bc99a6732cda722cfc615c2cef458baa4c62482b28566cc742228` |
| data/external/fuel_2026/변동비_연료별_월별요약_202203-202611.csv | `71384e4a4cebe7a1187bce41238580249a8bcd268dda473812c54252f5541f75` |
| experiments/task2_interval/results/chronos_preds.csv | `24e75757d6a7f42684b87c35a455b68ea56e3574cdf2c6463e803ccf537d4a43` |

확인 방법 : Windows `certutil -hashfile 파일 SHA256` / macOS·Linux `shasum -a 256 파일`

### 환경

| 항목 | 내용 |
|---|---|
| Python | 3.13 또는 3.14 (검증 : 3.13 Linux, 기본 모델 원본 3.14.7 Windows) |
| GPU | 필요 없음 (CPU만) |
| 시간 | 약 5분 (Chronos 저장본 사용 시, 검증 5.1분) |
| 인터넷 | 패키지 설치할 때만 |

---

## 3. 설치

```bash
cd sp
python -m venv .venv
# Windows : .venv\Scripts\activate      macOS·Linux : source .venv/bin/activate
pip install -r experiments/task2_interval/requirements-task2.txt
pip install -r experiments/spike_drop/requirements-spike_drop.txt
```

핵심 패키지 버전 (검증 환경)

| 패키지 | 버전 |
|---|---|
| pandas | 3.0.5 ~ 3.0.6 |
| numpy | 2.5.3 ~ 2.5.4 |
| lightgbm | 4.7.0 |
| xgboost | 3.4.1 |
| catboost | 1.2.10 |
| scikit-learn | 1.9.1 |
| scipy | 1.18.1 |

torch · chronos-forecasting 은 Chronos 예측을 **다시 계산할 때만** 필요합니다. `chronos_preds.csv` 저장본이 있으면 설치하지 않아도 됩니다.

---

## 4. 실행

```bash
python experiments/spike_drop/run_all.py --check
```

마지막 줄에 `원본과 비교 : 23/23 같음` 이 나오면 재현 성공입니다.

`run_all.py` 가 순서대로 실행하는 것 :

| 순서 | 파일 | 하는 일 | 만드는 것 | 시간 |
|---|---|---|---|---|
| 1 | task2_interval/task2_interval.py | 평소 가격 기본 모델 A~F (앙상블 + 등각 보정) | task2_interval/results/02~08 | 25초 |
| 2 | hour_ranges.py | 방향 넓히기 비교 | results/24 | 23초 |
| 3 | spike_level.py | 위험 시각 상한 확대, 최종 범위 L·M·U | results/32, `_spike_level.pkl` | 24초 |
| 4 | combined.py | 방향 넓히기 + 위험 시각 결합 | results/33 | 2초 |
| 5 | drop_final.py | 급락 경보 V2, 문턱 75~95% | results/29~31 | 31초 |
| 6 | spike_supply.py | 급등 경보 + 전력수급실적 | results/34, `_spike_supply_probs.pkl` | 9초 |
| 7 | median_adjust.py | 경보를 중앙값에 반영 실험 | results/40, `_median_adjust.pkl` | 17초 |
| 8 | point_improve.py | 평소 가격 개선 실험 | results/41 | 86초 |
| 9 | make_dashboard_data.py | 대시보드 데이터셋 20개 (안에서 final_spike.py · price_targets.py 실행) | dash_export/*.csv | 29초 |
| 9-1 | day_causes.py | 2026 급락일·급등일 표에 「원인 (추정)」 열 추가 | dash_export/drop_days_final · spike_days_final | 3초 |
| 10 | merit_order.py | 기업 변동비 순위 변수로 급등·급락 경보 시험 | results/43 | 37초 |
| 11 | spike_height_mo.py | 급등 높이를 변동비 순위로 정하기 시험 | results/44·45 | 2초 |
| 12 | fuel_tests.py | 연료비 자료·10/28 피드백 시험 정리 (예비력 계열 변수 빼기 포함) | dash_export/fuel_tests.csv | 4초 |
| 13 | common_period.py --end 2026-09-30 | 3차 피드백 ① 가격 모델 7안 같은 기간·같은 지표 | results/47, dash_export/common_period.csv | 약 20초 |
| 14 | drop_weekday.py | 3차 피드백 ③ 급락 평일·휴일 따로 + 가격 문턱(85원) 비교 | results/48, dash_export/drop_weekday.csv | 약 5초 |

한 단계가 실패하면 그 파일을 직접 실행하면 오류가 보입니다 (`cd experiments/spike_drop && python 파일.py`).

---

## 5. 대시보드 보기

### (가) 내 컴퓨터에서 바로 보기 — 인터넷·서버 필요 없음

```bash
python experiments/spike_drop/dashboard/build_standalone.py
```

`experiments/spike_drop/dashboard/dashboard.html` 이 생깁니다. 브라우저로 열면(더블클릭) claude.ai 대시보드와 같은 화면이 나옵니다.
페이지 원본(`page.html`), 차트 라이브러리 d3 7.9.0(`d3.min.js`), 데이터셋 23개가 파일 하나에 들어가며, 라이트·다크 모드를 모두 지원합니다.

### (나) claude.ai 대시보드로 다시 올리기

Claude에게 `dashboard/page.html` 과 `dash_export/` 폴더를 주고 "Dashboard 유형으로 올려 줘"라고 요청합니다. 데이터셋 이름은 CSV 파일 이름과 같아야 합니다.

| 데이터셋 | 만드는 코드 | 쓰는 구역 |
|---|---|---|
| price_targets · price_regimes · price_adjust | price_targets.py | 평소 가격 |
| price_experiments | make_dashboard_data.py (results/41) | 평소 가격 |
| drop_daily · drop_perf · drop_compare · drop_missed · drop_missed_ref · drop_days_final | make_dashboard_data.py (results/30·31 + drop_final 모델) | 급락 경보 |
| spike_daily · spike_days_final · spike_summary | final_spike.py | 급등 대응 |
| spike_alarm · spike_actions | make_dashboard_data.py (results/24·33 + 경보 확률) | 급등 대응 · 요약 |
| fuel_tests | fuel_tests.py (results/43·45 + 예비력 계열 빼기 시험) | SMP 정보 |
| common_period | common_period.py | 예측 범위 |
| drop_weekday | drop_weekday.py | 급락 경보 |
| metrics · series · hourly · weights · regimes | task2_interval/results 05·08·07·02·06 그대로 | 예측 범위 |

---

## 6. 눈으로 확인할 숫자

`dash_export` 를 열어 아래 값이 나오면 맞게 재현된 것입니다.

| 파일 | 항목 | 값 |
|---|---|---|
| price_targets.csv | 2026 전체 시간 rMAE · MAE · MAPE · 편의 | 0.700 · 7.85 · 8.03 · 1.81 |
| drop_perf.csv | 75% 행 : 문턱 · 2025 잡은 날 · 2026 잡은 날 · 경보일 · 적중률 | 3.894 · 15/19 · 18/20 · 60 · 30.0 |
| spike_summary.csv | 2026 행 : 급등일 · 경보로 잡음 · 경보일 · 범위로 담음 · 둘 중 하나 · 문턱 | 6 · 3 · 10 · 5 · 6 · 6.79 |
| spike_actions.csv | [모두 적용] 범위 안 비율 · 평균 폭 | 80.0 → 89.3 · 24.96 → 42.18 |
| spike_alarm.csv | 지금 방식 2026 잡은 급등일 | 01-22 · 01-23 · 03-16 |

---

## 7. 알아둘 점

- **기업 요청 기간(2026.1.1~10.2)으로 비교표 만들기** : `python experiments/spike_drop/common_period.py` (기본값 `--end 2026-10-02`). 10월 1~2일 Chronos-2 예측이 필요해 torch·chronos-forecasting 설치와 인터넷(HuggingFace)이 있어야 합니다. 없으면 Chronos 가 있는 9/30 까지만 계산하고 표에 실제 기간을 적습니다. 이 결과는 `reference/` 와 비교 대상이 아닙니다.

- **Chronos 저장본** : `chronos_preds.csv` 를 지우면 Chronos-2를 다시 돌립니다(모델 456MB 다운로드, CPU 약 10분). 부동소수점 차이로 끝자리가 달라질 수 있으니 저장본을 쓰는 것을 권장합니다.
- **다른 OS** : 트리 모델(LightGBM·XGBoost·CatBoost·RandomForest)은 시드를 고정했지만, CPU·OS·스레드 수에 따라 확률의 아주 작은 끝자리가 달라질 수 있습니다. 그래도 경보 판정과 표의 숫자(반올림된 값)는 같게 나오는 것이 정상입니다. `--check` 에서 다르게 나오면 그 파일만 열어 숫자를 비교해 보세요.
- **글꼴 경고** : Linux·macOS에서 `findfont: Font family 'AppleGothic' not found` 경고가 나올 수 있습니다. 그림(PNG) 글꼴만의 문제로 결과 숫자와는 상관없습니다.
- **전력수급실적 D-1 가정** : 급등 경보는 전날 수급실적을 예측 시점에 안다고 가정했습니다. 실제 운영 전에 전력거래소 공표 시각을 확인해야 합니다. 이틀 전 실적만 쓰면 2026년에 잡은 급등일이 0일이 됩니다(실험 #22).
- **데이터 빈칸** : 2026년 수요 실적·풍력은 없고 태양광은 6월부터 없습니다. 7/31 SMP가 비어 있어 7/31~8/28은 급락 판정을 하지 못합니다.
- **새 데이터로 다시 학습할 때** : 기간을 늘리면 결과가 달라지는 것이 정상입니다. 그때는 `reference/` 를 새 결과로 바꿔 두세요.

---

## 8. 코드 ↔ 실험 기록 번호

| 코드 | 실험 기록 # | 최종 사용 |
|---|---|---|
| task2_interval.py | 1, 31 | ✓ (평소 가격 기본) |
| day_alarm.py | 2, 3 | |
| hour_ranges.py | 4, 5, 6 | ✓ (방향 넓히기) |
| drop_models.py · drop_ensemble.py | 7, 10, 11 | |
| drop_final.py | 12, 30 | ✓ (급락 경보) |
| spike_prob.py | 8 | |
| standing_buffer.py · spike_level.py · combined.py | 9, 14~17 | ✓ (위험 시각) |
| spike_supply.py | 18, 19, 22 | ✓ (급등 경보) |
| spike_fuel.py · spike_monthly.py | 20, 21 | |
| powersource.py (+ 발전원별 실시간 xlsx) | 23~26 | |
| final_spike.py | 27 | ✓ (급등 대응 결과) |
| median_adjust.py · price_targets.py | 28 | |
| point_improve.py | 29 | |
| corp_bias.py | 32 | |
| merit_order.py · spike_height_mo.py · fuel_tests.py | 33~35 | |
| common_period.py · drop_weekday.py | 36, 37 | |
| day_causes.py | 38, 39 | ✓ (대시보드 원인 열) |
| make_dashboard_data.py · run_all.py · dashboard/ | — | ✓ (대시보드) |

`day_alarm.py` 처럼 최종에 쓰지 않은 실험 코드도 각각 따로 실행하면 해당 결과(results/21~41)를 다시 만들 수 있습니다. 실험 #23~26은 `data/external/powersource/` 의 전력거래소 발전원별 실시간 xlsx 파일을 씁니다(패키지에 포함).
