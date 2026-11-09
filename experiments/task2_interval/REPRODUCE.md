# 과제 2 재현 가이드 — 다른 컴퓨터에서 같은 결과 만들기

이 문서대로 하면 다른 컴퓨터에서도 과제 2의 모든 모델·분석·웹사이트가 **원본과 같은 숫자**로 다시 만들어집니다.
마지막 단계의 검증 스크립트가 원본 결과와 자동으로 비교해 줍니다.

> 원본 환경 : Windows 11 · Python 3.14.7 · CPU만 사용(GPU 불필요) · 2026-10-26 생성
> 이 환경에서 처음부터 다시 실행해 **모든 수치가 원본과 소수점까지 같음**을 확인했습니다(2026-10-28).

---

## 무엇이 재현되나

| 구분 | 내용 | 만드는 코드 |
|---|---|---|
| 모델 A | 잔차 분위수 (LightGBM 중앙값 + 2025년 오차 분위수) | `task2_interval.py` |
| 모델 B | LightGBM 분위수 회귀 (10% · 50% · 90%) | `task2_interval.py` |
| 모델 C | Chronos-2 + 수요예측 공변량 (학습 없음) | `task2_interval.py` |
| 모델 D | Chronos-2 단변량 (학습 없음) | `task2_interval.py` |
| 모델 E | B·C·D 분위수별 가중 앙상블 | `task2_interval.py` |
| **모델 F (최종)** | E + 등각 보정(시간대 × 평일/휴일 48개 그룹) | `task2_interval.py` |
| 급등일 분석 | 급등일 59일 목록, 급등일 vs 일반일, 하루 최고가, D-1 탐지 | `spike_days.py` |
| 웹사이트 | 한눈에 · 상세 분석 · 설명서 3개 페이지 | `web/build_data.py` |
| 검증 | 위 결과가 원본과 같은지 자동 비교 | `verify_reproduction.py` |

---

## 0. 준비물

**폴더 구조** — `student-practice` 폴더를 통째로 받습니다. 최소한 아래 파일이 있어야 합니다.

```
student-practice/
├─ data/processed/smp_dataset_hourly.csv      ← 입력 데이터 (약 10MB)
└─ experiments/task2_interval/
   ├─ task2_interval.py          ← 모델 A~F
   ├─ spike_days.py              ← 급등일 분석
   ├─ verify_reproduction.py     ← 결과 검증
   ├─ requirements-task2.txt     ← 패키지 버전 고정 목록
   ├─ results/chronos_preds.csv  ← Chronos 예측 저장본 (있으면 10분 절약 + 완전히 같은 결과)
   └─ web/                       ← 웹사이트 (index.html, glance.html, guide.html, *.js, *.css, build_data.py)
```

- `data/` 폴더가 없고 `smp_edu_data.zip`만 있다면 압축을 `student-practice` 폴더에 풉니다(또는 `00_실습시작.bat` 실행).
- 데이터 파일이 원본과 같은지는 4단계 검증에서 SHA-256으로 확인합니다.
  원본 값 : `704431b039d572a66b46f9883163c66b0ba77f2ee353afbdd32776573b29086e`

**필요한 것**

| 항목 | 내용 |
|---|---|
| 운영체제 | Windows 10/11 (원본). macOS·Linux도 동작하지만 아래 「OS별 차이」 참고 |
| Python | **3.14.x** (원본 3.14.7). 다른 버전도 동작할 가능성이 높지만 검증되지 않음 |
| 디스크 | 패키지 약 1.5GB + (Chronos 다시 예측 시) 모델 456MB |
| 메모리 | 8GB 이상 권장 |
| 시간 | 저장본 사용 시 약 2~3분 / Chronos 다시 예측 시 +10분 정도(CPU) |
| 인터넷 | 패키지 설치 시 필요. Chronos 다시 예측할 때만 모델 다운로드 필요 |

---

## 1. 파이썬 가상환경 만들기

모든 명령은 **`student-practice` 폴더에서** 실행합니다.

**Windows (PowerShell)**
```powershell
cd C:\경로\student-practice
py -3.14 -m venv .venv
.venv\Scripts\python.exe --version        # Python 3.14.x 확인
```
`py` 명령이 없으면 [python.org](https://www.python.org/downloads/)에서 Python 3.14를 설치하고 「Add python.exe to PATH」를 체크합니다.

**macOS / Linux**
```bash
cd /경로/student-practice
python3.14 -m venv .venv
.venv/bin/python --version
```

> 이 문서의 명령은 Windows 기준(`.venv\Scripts\python.exe`)입니다. macOS·Linux에서는 `.venv/bin/python`으로 바꾸고 경로의 `\`를 `/`로 바꿉니다.

---

## 2. 패키지 설치 (버전 고정)

**순서가 중요합니다.** torch를 먼저 CPU 판으로 설치해야 합니다. 그렇지 않으면 3번째 줄에서 2GB가 넘는 GPU 판이 설치됩니다.

**Windows / Linux**
```powershell
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python.exe -m pip install -r experiments\task2_interval\requirements-task2.txt
```

**macOS** (Mac용 torch는 기본 판이 CPU 판)
```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install torch==2.14.1
.venv/bin/python -m pip install -r experiments/task2_interval/requirements-task2.txt
```

핵심 패키지 버전 (`requirements-task2.txt`에 79개 전체가 고정되어 있음)

| 패키지 | 버전 | 쓰는 곳 |
|---|---|---|
| numpy | 2.5.4 | 전체 |
| pandas | 3.0.6 | 전체 |
| lightgbm | 4.7.0 | 모델 A·B |
| matplotlib | 3.11.2 | 그래프 |
| torch | 2.14.1 (CPU) | 모델 C·D |
| chronos-forecasting | 2.3.2 | 모델 C·D |
| transformers | 5.20.2 | 모델 C·D |

---

## 3. 실행

### 3-A. 빠른 재현 (권장) — Chronos 저장본 사용

`results/chronos_preds.csv`가 있으면 Chronos 예측을 다시 하지 않고 저장본을 씁니다. 이 경우 **결과가 원본과 완전히 같습니다.**

```powershell
# ① 모델 A~F 학습·예측·평가 (약 1분)
.venv\Scripts\python.exe experiments\task2_interval\task2_interval.py

# ② 급등일 vs 일반일 분석 (약 1분)
.venv\Scripts\python.exe experiments\task2_interval\spike_days.py

# ③ 웹사이트 데이터 만들기 (수 초)
.venv\Scripts\python.exe experiments\task2_interval\web\build_data.py

# ④ 원본과 비교 검증
.venv\Scripts\python.exe experiments\task2_interval\verify_reproduction.py
```

정상이면 ①의 출력 마지막 부분에 이런 줄이 보입니다.
```
  · Chronos 저장본 사용 : experiments\task2_interval\results\chronos_preds.csv
  · 앙상블 가중치 (2025년 pinball 최소)
분위수  lgb  chr_cov  chr_uni  pinball
  q10 0.15     0.85     0.00    1.740
  q50 0.15     0.80     0.05    3.698
  q90 0.25     0.75     0.00    1.886
```
②의 출력에는 반드시 아래 줄이 있어야 합니다(①과 같은 예측을 다시 만들었는지 스스로 확인함).
```
  · 급등일(최고가 ≥ 직전 28일 일 최고가 중앙값 × 1.25) : 2021년 이후 59일
  · 재현 확인 : 시험 구간 6개 방법 예측이 04 결과와 일치
```

### 3-B. 완전 재현 — Chronos까지 처음부터 다시 예측

```powershell
.venv\Scripts\python.exe experiments\task2_interval\task2_interval.py --rerun-chronos
```

- Hugging Face에서 `amazon/chronos-2` 모델(456MB)을 내려받습니다. 처음 한 번만 받고 이후에는 캐시를 씁니다.
- 모델 버전은 원본과 같은 커밋 `29ec3766d36d6f73f0696f85560a422f50e8498c`로 **코드에 고정**되어 있어, 나중에 모델이 업데이트되어도 같은 가중치를 씁니다.
- CPU 종류·스레드 수에 따라 Chronos 출력이 소수점 아래에서 아주 조금 다를 수 있습니다. 이 경우 검증 스크립트가 자동으로 허용오차를 0.5로 넓혀 비교합니다.
- 그 뒤 ②~④를 똑같이 실행합니다.

**인터넷이 막힌 컴퓨터**에서는 인터넷이 되는 컴퓨터의 아래 폴더를 같은 위치에 복사한 뒤 실행합니다.
```
Windows : C:\Users\<사용자>\.cache\huggingface\hub\models--amazon--chronos-2\
macOS   : ~/.cache/huggingface/hub/models--amazon--chronos-2/
```
```powershell
$env:HF_HUB_OFFLINE = "1"      # macOS/Linux: export HF_HUB_OFFLINE=1
.venv\Scripts\python.exe experiments\task2_interval\task2_interval.py --rerun-chronos
```

---

## 4. 결과 검증

`verify_reproduction.py`가 아래를 확인하고 「통과/경고/실패」를 출력합니다.

| 단계 | 확인 내용 | 다르면 |
|---|---|---|
| 환경 | Python·핵심 패키지 버전 | 경고만 (결과가 같으면 문제없음) |
| 입력 | 데이터 SHA-256 | **실패** — 데이터가 다르면 결과도 다름 |
| 입력 | Chronos 저장본 SHA-256 | 경고 — 다시 예측한 경우. 허용오차를 넓혀 비교 |
| 결과 | 6개 방법 × 2기간의 커버리지·폭·Winkler·MAE | 실패 |
| 결과 | 앙상블 가중치, 등각 보정값 합 | 실패 |
| 결과 | 급등일 59일, 급등일/일반일 비교, 최고가 분석 | 실패 |

성공하면 마지막 줄이 이렇게 나오고 종료코드가 0입니다.
```
재현 성공 — 모든 결과가 원본과 같습니다.
```

**원본 핵심 수치** (검증 스크립트와 같은 값)

| 시험 2026 | 커버리지 | 평균 폭 | Winkler | MAE |
|---|---|---|---|---|
| A 잔차 분위수 | 74.433% | 26.559원 | 49.801 | 9.360원 |
| B LightGBM 분위수 | 68.551% | 23.588원 | 46.020 | 9.357원 |
| C Chronos-2 + 수요예측 | 73.100% | 21.749원 | 38.591 | 7.827원 |
| D Chronos-2 단변량 | 72.044% | 23.628원 | 44.169 | 8.743원 |
| E 앙상블 | 75.214% | 21.901원 | 38.018 | 7.847원 |
| **F 앙상블 + 등각 보정** | **79.963%** | **24.955원** | **37.701** | **7.847원** |

---

## 5. 웹사이트 열기

서버는 필요 없습니다. 파일을 더블클릭하면 브라우저에서 열립니다.

| 파일 | 내용 |
|---|---|
| `web/glance.html` | 한눈에 — 처음 보는 사람용 요약 |
| `web/index.html` | 상세 분석 — 방법 비교·급등일·시간대 |
| `web/guide.html` | 설명서 — 용어·읽는 법·해석·근거 |

- 세 페이지 모두 `web/data.js` 하나를 읽습니다. 결과가 바뀌면 3-A의 ③만 다시 실행하면 됩니다.
- 글꼴(Pretendard)은 인터넷에서 받아옵니다. 오프라인이면 맑은 고딕 등 기본 글꼴로 보이고 내용은 같습니다.
- `guide.html` 문장 속 숫자는 손으로 쓴 값이라 결과가 바뀌어도 자동으로 바뀌지 않습니다.

---

## 6. 만들어지는 결과물

**`results/` (CSV)**

| 파일 | 내용 | 코드 |
|---|---|---|
| `01_오차분위수_2025_시간대x평일휴일.csv` | 모델 A가 쓰는 2025년 오차 분위수 | task2 |
| `02_앙상블_가중치.csv` | 분위수별 가중치 | task2 |
| `03_등각보정값_시간대x평일휴일.csv` | 48개 그룹 보정값 | task2 |
| `04_시험구간_예측범위.csv` | 6개 방법 시험 구간 예측 전체 | task2 |
| `05_평가_시험구간.csv` · `05_평가_보정구간_참고.csv` | 평가표 | task2 |
| `06_급등_일반_급락_비교.csv` | 시간 단위 급변 비교(참고) | task2 |
| `07_시간대별_커버리지.csv` | 시간대별 | task2 |
| `08_최종모델_예측범위.csv` | 최종 모델만 | task2 |
| `chronos_preds.csv` | Chronos 예측 저장본 | task2 |
| `09_급등일_목록.csv` ~ `13_급등일_시간대별_모양.csv` | 급등일 분석 | spike_days |

**`plots/` (PNG)** — `01`~`05` task2, `06`~`08` spike_days

---

## 7. 같은 결과가 나오는 이유

| 바뀔 수 있는 것 | 고정한 방법 |
|---|---|
| 입력 데이터 | 같은 파일 + SHA-256 확인 |
| 기간 분할 | 코드 상수 (학습 ~2024 / 보정 2025 / 시험 2026.1~9) |
| 패키지 버전 | `requirements-task2.txt`에 전체 79개 + torch 버전 고정 |
| LightGBM 무작위성 | `random_state=9` 고정, 하이퍼파라미터 코드에 고정 |
| Chronos 모델 | Hugging Face 커밋 고정 + 예측 저장본(`chronos_preds.csv`) 제공 |
| 앙상블 가중치·등각 보정 | 2025년 자료로 정해진 규칙에 따라 계산(무작위 없음) |
| 급등일 정의 | 그날 최고 SMP ≥ 직전 28일 일 최고가 중앙값 × 1.25 (코드 상수) |

---

## 8. 문제 해결

| 증상 | 해결 |
|---|---|
| `py -3.14` 를 찾을 수 없음 | Python 3.14 설치. 다른 버전을 쓰면 검증에서 「경고」가 나오지만 결과가 같으면 괜찮음 |
| pip 가 torch 를 2GB 넘게 받음 | 2단계 순서대로 torch CPU 판을 **먼저** 설치 |
| `[중단] results/chronos_preds.csv 없음` (spike_days) | task2_interval.py 를 먼저 실행 |
| `[중단] 시험 구간 예측이 04 결과와 다름` | task2_interval.py 를 다시 실행한 뒤 spike_days.py 실행(둘을 같은 환경에서 연달아) |
| 검증에서 「데이터 SHA-256 실패」 | 데이터 파일이 다름. 원본 `smp_edu_data.zip`을 다시 풀거나 원본 파일을 받음 |
| 검증에서 결과 수치 실패 + 패키지 버전 경고 | 2단계를 그대로 다시 실행해 버전을 맞춤 |
| 그래프 한글이 □로 나옴 (Linux) | 코드는 Windows=맑은 고딕, 그 외=AppleGothic 을 씀. Linux 는 한글 글꼴을 설치해야 그림 글자가 보임(숫자 결과에는 영향 없음) |
| 한글이 깨져서 출력됨 (Windows 콘솔) | `$env:PYTHONUTF8 = "1"` 후 다시 실행 |
| Chronos 다운로드 실패 | 회사·학교망 차단일 수 있음 → 3-B의 오프라인 방법 사용 |

---

## 9. 다른 사람에게 전달할 때

`student-practice` 폴더를 통째로 압축해서 보내는 것이 가장 간단합니다. **`.venv` 폴더는 빼고** 보냅니다(컴퓨터마다 새로 만들어야 함).

꼭 포함해야 하는 것
- `data/processed/smp_dataset_hourly.csv`
- `experiments/task2_interval/` 전체 — 특히 `results/chronos_preds.csv`(완전히 같은 결과 + 10분 절약)

받은 사람은 1 → 2 → 3-A → 4 순서로 실행하면 됩니다.
