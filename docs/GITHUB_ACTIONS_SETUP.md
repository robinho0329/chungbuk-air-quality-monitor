# GitHub Actions 자동 수집 설정 가이드

> 컴퓨터를 켜두지 않아도 GitHub 서버가 매시 자동으로 에어코리아 데이터를
> 수집·저장한다. 결과는 레포에 자동 commit되어 영속 보관.

## 동작 개요

| 항목 | 값 |
|------|-----|
| 실행 주기 | 매시 :15 UTC (cron `15 * * * *`) |
| 실행 환경 | `ubuntu-latest` (GitHub 제공) |
| 1회 실행 시간 | 약 1~2분 |
| 영속화 | `src/storage/data.db`를 자동 커밋 |
| 무료 한도 | public repo 무제한 / private 월 2000분 |
| 워크플로우 정의 | `.github/workflows/collect.yml` |

## 사전 준비 (사용자가 직접 해야 함)

### ① GitHub 레포 생성

1. https://github.com/new
2. 레포명: 예) `chungbuk-air-quality-monitor`
3. 공개/비공개: **공개 권장** (Actions 무제한, 포트폴리오 노출 효과)
4. **README 추가 등 옵션은 모두 끄기** (로컬에 이미 있음)
5. Create repository 클릭

### ② 로컬 레포를 GitHub에 연결 & push

```powershell
cd "C:/Users/xcv54/workspace/Sideproject_260526"
git remote add origin https://github.com/<당신_username>/chungbuk-air-quality-monitor.git
git push -u origin main
```

push 시 GitHub 로그인이 필요합니다 (PAT 또는 GitHub CLI).

### ③ GitHub Secrets 등록 (API 키 안전 보관)

1. GitHub 레포 페이지 → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** 클릭
3. 다음 secret 등록:

| Name | Secret (값) |
|------|------------|
| `AIRKOREA_API_KEY` | `.env`에 있는 그 키 (a83fea... 등) |

Secret은 워크플로우 실행 시 환경변수로만 노출되고 로그에는 자동 마스킹됩니다.

### ④ 첫 실행 확인 (수동 트리거)

cron을 기다리지 않고 즉시 동작 확인하려면:

1. GitHub 레포 페이지 → **Actions** 탭
2. 좌측 목록 `🌬️ 충북 대기질 자동 수집` 클릭
3. 우측 `Run workflow` 드롭다운 → `main` 선택 → **Run workflow** 클릭
4. ~10초 후 새 실행이 목록에 뜸. 클릭해서 로그 확인
5. 정상 종료 후 레포 `Code` 탭으로 가면 `auto(collect): airkorea snapshot ...` 커밋이 보임

## 자동 동작 확인

### 며칠 후 누적 확인

GitHub 레포의 **Commits** 페이지로 가면 매시 자동 커밋이 누적된 게 보입니다:
```
auto(collect): airkorea snapshot 2026-05-29T01:18Z (누적 8건)
auto(collect): airkorea snapshot 2026-05-29T02:17Z (누적 12건)
auto(collect): airkorea snapshot 2026-05-29T03:18Z (누적 16건)
...
```

로컬에서도 최신 데이터 받아오려면:
```bash
git pull origin main
uv run python -c "from src.storage.database import query_all; print(f'누적 {len(query_all())}건')"
```

## 자주 묻는 질문

### Q. 매시 cron인데 정확히 :15에 실행되나?
A. **아니요.** GitHub Actions cron은 5~30분 지연이 흔합니다.
   매시 1회 호출만 보장되고 정확한 분 단위 제어는 불가.
   에어코리아 데이터도 시간 단위라 문제 없음.

### Q. private repo면 한도 걱정?
A. 월 2000분 무료. 매시 1회 × 30일 × 2분 = 1440분 → 한도 내.
   더 줄이려면 cron을 `15 */2 * * *` (2시간마다)로 완화.

### Q. 매시 커밋이라 git history가 더러워지는데?
A. 트레이드오프. 깔끔하게 하려면 다음 대안:
   - cron을 1일 1회로 줄이고 `dataTerm=DAILY`로 측정소별 24시간치 한 번에 호출 (코드 추가 필요)
   - 일정 주기로 git history squash
   
   현재는 MVP 우선이라 매시 커밋 그대로.

### Q. 로컬 작업 중 GitHub에서 자동 커밋이 들어오면 충돌?
A. 가능. 작업 시작 전 `git pull --rebase origin main` 습관화.
   또는 로컬 작업 시 워크플로우를 잠시 비활성화:
   - GitHub 레포 → Actions 탭 → 워크플로우 선택 → `...` → **Disable workflow**

### Q. API 키가 GitHub Secrets에 등록됐는지 어떻게 확인?
A. Settings → Secrets and variables → Actions에 이름만 보임 (값은 노출 X).
   동작 여부는 첫 수동 실행 로그에서 확인 — 인증 실패면 500/401 에러로 보임.

## 비활성화 / 일시 정지

- **잠시 멈추기**: Actions 탭 → 워크플로우 → `...` → Disable workflow
- **영구 삭제**: `.github/workflows/collect.yml` 파일 삭제 후 push

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 워크플로우 실행이 안 됨 | Actions 비활성 | Settings → Actions → Allow all |
| "AIRKOREA_API_KEY required" 에러 | Secret 미등록 또는 이름 오타 | Secrets 재등록 |
| 500 Server Error | 키 무효 또는 엔드포인트 변경 | 로컬에서 동일 키로 재현되는지 확인 |
| `Permission denied` push 실패 | `permissions: contents: write` 누락 | 워크플로우 파일 확인 |
| 매시 :15인데 실행 시각이 들쭉날쭉 | GHA cron 지연 (정상) | 신경 쓰지 않음. 매시 1회만 보장 |
