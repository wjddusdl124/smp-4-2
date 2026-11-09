# 대시보드 배포 (GitHub + Render 무료)

대시보드는 HTML 파일 하나(`public/index.html`)라서 Render **Static Site**(무료, 잠들지 않음)로 올립니다.

| 파일 | 역할 |
|---|---|
| `deploy/build_site.py` | `build_standalone.py` 실행 → `public/index.html` 생성 (표준 라이브러리만 사용) |
| `render.yaml` | Render 설정: 빌드 명령, 공개 폴더 `public`, 보안 헤더 |
| `.gitignore` | `public/`, `.venv/`, `.env` 등은 올리지 않음 |

## 1. GitHub 저장소 만들기
1. github.com → 오른쪽 위 **+** → **New repository**
2. 이름: `smp-4-2` (예시) / **Private** 선택 (기업 문서·데이터가 들어 있음)
3. README·.gitignore·license는 **추가하지 않음** (빈 저장소여야 push가 깔끔함) → **Create repository**

## 2. 올리기 (PowerShell, 이 폴더에서)
```powershell
git remote add origin https://github.com/<내아이디>/smp-4-2.git
git push -u origin main
```
처음 push하면 브라우저 로그인 창이 뜹니다(Git Credential Manager). 로그인하면 끝.

## 3. Render에 배포
1. dashboard.render.com → **New +** → **Blueprint**
2. **Connect GitHub** → "Only select repositories"로 `smp-4-2`만 허용
3. 저장소 선택 → `render.yaml`을 읽어 `smp-dashboard`(Static Site) 생성 → **Apply**
4. 빌드 로그에 `public/index.html 생성 완료`가 나오면 성공
5. 주소: `https://smp-dashboard.onrender.com` (이름이 이미 있으면 뒤에 글자가 붙음)

Blueprint 대신 수동으로 만들 때: **New + → Static Site** → Build Command `python deploy/build_site.py`, Publish Directory `public`.

## 4. 대시보드 업데이트
```powershell
python experiments/spike_drop/run_all.py --check   # 데이터를 다시 만들 때만
git add -A
git commit -m "대시보드 데이터 갱신"
git push
```
push하면 Render가 자동으로 다시 빌드합니다(대시보드 관련 파일이 바뀐 경우만).

## 주의
- 저장소는 Private이어도 **Render 주소는 누구나 열 수 있습니다.** 대시보드에 들어간 숫자는 공개된다고 생각하세요.
- API 키는 파일에 넣지 않습니다. 정적 사이트에는 키가 필요 없습니다.
