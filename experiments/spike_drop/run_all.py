# -*- coding: utf-8 -*-
"""
run_all.py — 최종 모델과 대시보드 데이터를 처음부터 다시 만듦 (순서 고정)
  python experiments/spike_drop/run_all.py            # 전체 (약 5분, CPU)
  python experiments/spike_drop/run_all.py --check    # 다 만든 뒤 reference/ 와 비교
"""
import os, sys, subprocess, time, filecmp
# Windows 콘솔(cp949)에서 한글·특수문자 출력 오류가 나지 않도록 UTF-8 모드로 실행 (Linux 결과와 같게)
ENV = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
T2 = os.path.join(HERE, '..', 'task2_interval')
STEPS = [
    (T2, 'task2_interval.py', '평소 가격 기본 모델 A~F (Chronos 예측은 results/chronos_preds.csv 재사용)'),
    (HERE, 'hour_ranges.py', '방향 넓히기 비교 → results/24'),
    (HERE, 'spike_level.py', '위험 시각 확대 → results/32, _spike_level.pkl'),
    (HERE, 'combined.py', '방향 넓히기 + 위험 시각 결합 → results/33'),
    (HERE, 'drop_final.py', '급락 경보 V2 (XGB·Cat·RF) → results/29~31'),
    (HERE, 'spike_supply.py', '급등 경보 + 전력수급실적 → results/34, _spike_supply_probs.pkl'),
    (HERE, 'median_adjust.py', '경보를 중앙값에 반영 → results/40, _median_adjust.pkl'),
    (HERE, 'point_improve.py', '평소 가격 개선 실험 → results/41'),
    (HERE, 'make_dashboard_data.py', '대시보드 데이터셋 20개 → dash_export/'),
    (HERE, 'day_causes.py', '2026 급락일·급등일 표에 원인 (추정) 열 추가'),
    (HERE, 'merit_order.py', '기업 변동비 순위로 급등·급락 경보 → results/43'),
    (HERE, 'spike_height_mo.py', '급등 높이 = 변동비 순위 → results/44·45'),
    (HERE, 'fuel_tests.py', '연료비 자료·피드백 시험 정리 → dash_export/fuel_tests.csv'),
    (HERE, 'common_period.py --end 2026-09-30', '피드백 ① 가격 모델 7안 같은 기간·같은 지표 → dash_export/common_period.csv'),
    (HERE, 'drop_weekday.py', '피드백 ③ 급락 평일·휴일 따로 + 가격 문턱 비교 → dash_export/drop_weekday.csv'),
]

def main():
    t0 = time.time()
    for cwd, py, what in STEPS:
        print(f'\n=== {py} : {what}', flush=True); t = time.time()
        r = subprocess.run([sys.executable] + py.split(), cwd=cwd, stdout=subprocess.DEVNULL, env=ENV)
        if r.returncode: sys.exit(f'실패 : {py} (코드 {r.returncode}) — 이 파일을 직접 실행해 오류를 확인하세요')
        print(f'    완료 {time.time() - t:.0f}초', flush=True)
    print(f'\n전체 {(time.time() - t0) / 60:.1f}분')
    if '--check' in sys.argv:
        ref = os.path.join(HERE, 'reference'); out = os.path.join(HERE, 'dash_export')
        bad = [f for f in sorted(os.listdir(ref)) if not os.path.exists(os.path.join(out, f)) or not filecmp.cmp(os.path.join(ref, f), os.path.join(out, f), shallow=False)]
        print(f'원본과 비교 : {len(os.listdir(ref)) - len(bad)}/{len(os.listdir(ref))} 같음' + (f' · 다름 {bad}' if bad else ''))
        sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
