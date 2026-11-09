# -*- coding: utf-8 -*-
"""
build_site.py — Render(정적 사이트) 배포용 빌드
  python deploy/build_site.py
  1) experiments/spike_drop/dashboard/build_standalone.py 로 dashboard.html 생성
     (page.html + d3.min.js + dash_export/*.csv 23개를 파일 하나로 합침)
  2) public/index.html 로 복사 → Render 가 public/ 폴더를 그대로 공개
표준 라이브러리만 사용하므로 Render 빌드에서 pip 설치가 필요 없습니다.
"""
import os, shutil, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
DASH = os.path.join(ROOT, 'experiments', 'spike_drop', 'dashboard')
OUT = os.path.join(ROOT, 'public')

sys.path.insert(0, DASH)
import build_standalone  # noqa: E402

build_standalone.main()
os.makedirs(OUT, exist_ok=True)
shutil.copyfile(os.path.join(DASH, 'dashboard.html'), os.path.join(OUT, 'index.html'))
print('public/index.html 생성 완료')
