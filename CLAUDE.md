# CLAUDE.md — SMP(육지) 하루전 예측 · 4-2조

Claude Code가 이 폴더에서 일할 때 먼저 읽는 안내입니다. 사람이 읽는 상세 재현 가이드는 `experiments/spike_drop/REPRODUCE_SPIKE_DROP.md`에 있습니다.

**작업을 시작하기 전에 `docs/HANDOFF.md`도 읽으세요.** 이전 대화에서 사용자가 정한 것(디자인 유지, 급락일 정의 등), 선호, 자주 나온 질문의 답, claude.ai 결과물 링크, 남은 일이 적혀 있습니다.

## 프로젝트 한 줄
SMP(육지, 시간별)를 하루 전에 예측합니다. 모델은 세 가지입니다: ① 평소 가격(예측 범위·중앙값), ② 급락 경보, ③ 급등 대응. 결과는 대시보드와 발표 자료로 정리했습니다.

## 꼭 지킬 규칙
- **설정은 2025년에서만 고르고, 2026-01-01~09-30 시험 구간에는 한 번만 적용합니다.** 2026 결과를 보고 설정을 바꾸면 안 됩니다. 2026은 이미 여러 번 봤기 때문에, 새 규칙은 2026-11 이후 자료로 판정합니다.
- **D-1 정보만 씁니다.** 예측하는 날의 실제값(당일 SMP, 당일 실적)은 변수로 쓰지 않습니다.
- 숫자를 쓸 때는 출처를 표시합니다: [데이터 계산] / [공개 자료] / [추정].
- 설명은 쉬운 한국어로 씁니다. 실험 기록(`docs/work_log.md`)은 보고서가 아니라 한눈에 보는 표 형식입니다.
- 시간 표기: `hour_n`은 거래시간 라벨입니다(거래시간 10시 = 09:00~10:00).
- **API 키·비밀번호를 파일에 넣거나 커밋하지 않습니다.** 공공데이터포털 키는 환경변수(예: `DATA_GO_KR_KEY`)로만 읽습니다.

## 실행
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r experiments/task2_interval/requirements-task2.txt
pip install -r experiments/spike_drop/requirements-spike_drop.txt
python experiments/spike_drop/run_all.py --check       # 15단계 실행 후 reference/와 23개 CSV 비교 → 23/23 같으면 성공
python experiments/spike_drop/dashboard/build_standalone.py   # 내 컴퓨터에서 여는 대시보드 HTML
```
- torch는 OS마다 설치 방법이 달라 requirements에서 뺐습니다(REPRODUCE.md 2단계 참고). 단, 저장된 `experiments/task2_interval/results/chronos_preds.csv`를 쓰기 때문에 **run_all.py에는 torch·Chronos가 필요 없습니다.** 이 파일은 지우지 마세요.
- 확인된 환경: Linux, Python 3.13에서 23/23이 같았습니다. 원본은 Windows 11, Python 3.14.7에서 만들었습니다.
- 한 단계가 실패하면 `cd experiments/spike_drop && python <파일>.py`로 직접 실행해 오류를 봅니다.
- 코드는 루트를 `experiments/spike_drop/../..`로 찾습니다. **`data/`와 `experiments/`는 항상 최상위에 두어야 합니다.**

### run_all.py 순서
1. `task2_interval.py`
2. `hour_ranges.py`
3. `spike_level.py`
4. `combined.py`
5. `drop_final.py`
6. `spike_supply.py`
7. `median_adjust.py`
8. `point_improve.py`
9. `make_dashboard_data.py`
10. `day_causes.py`
11. `merit_order.py`
12. `spike_height_mo.py`
13. `fuel_tests.py`
14. `common_period.py --end 2026-09-30`
15. `drop_weekday.py`

출력은 `experiments/spike_drop/dash_export/`(대시보드 데이터 23개)와 `results/`에 생깁니다.

## 최종 모델

### ① 평소 가격 (구간 모델 F)

| 분위 | LightGBM | Chronos-2 + 수요예측 | Chronos-2 단변량 |
|---|---|---|---|
| q10 | 0.15 | 0.85 | 0 |
| q50 | 0.15 | 0.80 | 0.05 |
| q90 | 0.25 | 0.75 | 0 |

여기에 다음 보정을 차례로 적용합니다.
- CQR 보정(48그룹)
- G1 방향 넓힘: 위 ×2.0, 아래 ×1.7
- 평일 10·11·15·16시: 상한 = max(Ug, U + 67.8)

### ② 급락 경보
- 모델: XGB + Cat + RF를 1/3씩, 시드 3개
- 변수: OPER 43개 + EXTRA
- 2024년 이후 자료에 가중치 ×3
- 경보 문턱: 3.894% (2025 급락의 75%를 잡는 값)
- **급락일 정의(채점·표시):** 거래시간 11~15시 중 1시간이라도 30원 미만 (기업 정의, `day_features.drop_corp`, 11/2 통일). 학습 정답·문턱은 이전 정의(직전 28일 최저가 중앙값의 절반 이하, `drop`) 그대로이며, 2025년은 두 정의의 급락일 19일이 같습니다.

### ③ 급등 대응
- 모델: LGB + XGB + Cat을 1/3씩
- 변수: FEATS 16개 + 공급 변수 6개
- 경보 문턱: 6.79% (2025 상위 20일)
- 보조 규칙: 「전날 급등」 주의
- 공급 변수는 「공급 여유(전날 공급능력 − 수요예측)」로만 해석합니다. 기업 10/28 정정으로 예비력 가설은 철회했습니다.

## 2026 시험 결과 (2026-01-01~09-30) [데이터 계산]

| 항목 | 결과 |
|---|---|
| 평소 가격 | MAE 7.85 / rMAE 0.700 / MAPE 8.03% / 편의 1.81% — 목표 4개 모두 미달 |
| 예측 범위 커버리지 | 80.0% → 89.3% |
| 예측 범위 폭 | 24.96원 → 42.18원 |
| 급락 (기업 정의) | 20일 중 18일 잡음, 경보 60일, 정밀도 30.0% (이전 정의로는 21일 중 19일 — 6/7 차이) |
| 급등 | 경보 3/6, 범위 5/6, 둘 중 하나 6/6 |
| 후보 규칙 | 평일 급락 가격 문턱(11~15시 중앙값 < 85원): 2026 평일 급락 2/2, 결합 규칙 20/20·경보 65일. 미채택 후보이며 11월 이후 자료로 확인 예정 |

## 해 봤지만 채택하지 않은 것 (다시 하지 않기)
- **평소 가격 모델 개선 E1~E6:** 효과가 MAE 0.03 이하이거나 더 나빠졌습니다(results/41).
- **기업 편의 보정:** MAE 8.34로 더 나빠졌습니다(results/42, `corp_bias.py`).
- **변동비 순위·공급곡선 변수:** 급등·급락 경보 모두 개선이 없었습니다(results/43~46).
  - 급등 최고가는 그 달 일반 LNG 순위의 약 94% 자리에 있었지만, 이 자리가 해마다 올라가서(2023년 0.85 → 2026년 0.94) 상한으로는 쓰지 않습니다.
- **예비력 계열 변수 빼기:** 2026 급등을 잡은 날이 3/6 → 1/6으로 줄어 모델을 유지했습니다.

## 파일 지도

| 경로 | 내용 |
|---|---|
| `data/processed/smp_dataset_hourly.csv` | 기본 시간별 데이터셋 |
| `data/external/` | 공급능력(cp949), 연료비, SMP 결정 연료, 발전원별(`powersource/*.xlsx` → `powersource_hourly.csv`), 캐시 pkl, `fuel_2026/` 변동비 순위 |
| `data/raw_uploads/` | 사용자가 처음 올린 원본(참고용, 코드는 읽지 않음). 발전원별 xlsx, HOME_*.csv, 비중앙발전 zip·csv(실험 #11), 과제2 원본 zip, 기업 모델 예측 CSV |
| `experiments/task2_interval/` | 평소 가격 구간 모델. `results/chronos_preds.csv` 필수 |
| `experiments/spike_drop/` | 급락·급등·대시보드 데이터 스크립트, `reference/`(정답 CSV 23개), `dash_export/`, `results/`(번호 = 실험 기록 번호) |
| `experiments/spike_drop/dashboard/` | `page.html`(대시보드 v10), `d3.min.js` 7.9.0, `build_standalone.py` → `dashboard.html` |
| `dashboard_platform/` | claude.ai 대시보드 원본. `body_v10.html` + `script_v9.js` → `python build_v10.py` → `page_v10.html` / `index_v10.json` |
| `docs/HANDOFF.md` | 대화에서만 정해진 결정·선호·질문과 답·남은 일 (먼저 읽기) |
| `docs/work_log.md` | 실험 기록 「SMP 급등·급락 예측 모델 기록」 전체(40항목) |
| `docs/presentation/` | 발표 자료 22장(`deck.json` + `slides/*.html`, 발표 대본은 각 `<aside>`) |
| `docs/company/` | 기업 문서: PRD v2.12, 실행계획서 v1.7, 공표경계 v1.2, 감쇠진동 v1.0, 1028 피드백 v1.1, 연료비자료 zip. 4-2조 피드백만 기준 |

2026 급락일·급등일 원인 문구는 `experiments/spike_drop/day_causes.py`에 손으로 적어 두었습니다. 모두 「추정」입니다.

## 알려진 한계
- **네트워크:** 이 프로젝트를 만든 환경에서는 data.go.kr, kpx.or.kr, epsis, huggingface가 막혀 있었습니다. Claude Code 로컬에서는 열려 있을 수 있습니다.
- **Chronos 10/1~10/2:** 이 기간 예측은 huggingface 접속과 torch가 있어야 만들 수 있습니다(`common_period.py` 기본 `--end 2026-10-02`).
- **발전원별 태양광:** 2026년 6월 이후 자료는 비어 있습니다.
- **다음에 넣고 싶은 자료:** 시간별 가격결정발전기, 지역 송전제약, 정비·기동 계획, 출력제어 이력. 넣을 때도 같은 규칙(2025에서 고르고 2026에 한 번 적용)을 지킵니다.
