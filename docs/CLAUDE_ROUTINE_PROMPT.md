# Claude Code Routine 프롬프트

> Claude Code의 **Routines** 메뉴에 등록할 자율 개발 루프 프롬프트.
> 매일 KST 09:15에 Claude가 깨어나 작업 1개를 진척시킨다.

## 등록 절차

1. Claude Code 사이드바 → **Routines**
2. **+ 새 루틴** 클릭
3. 설정:
   - **이름**: `충북 대기질 - 매일 자율 개발 루프`
   - **스케줄**: 매일 KST 09:15
   - **모드**: 원격 (Remote)
   - **작업 디렉토리**: `C:/Users/xcv54/workspace/Sideproject_260526`
4. **프롬프트**: 아래 [프롬프트 본문] 전체를 복사·붙여넣기
5. **저장 → 활성화**

---

## 프롬프트 본문

```
# 충북 대기질 SPC 모니터링 - 매일 자율 개발 루프 (KST 09:15)

당신은 충북권 대기질 SPC 모니터링 프로젝트의 자율 개발 봇이다.
매일 한 번 깨어나서 Phase 작업 1개를 진척시킨다.

## 작업 디렉토리
C:/Users/xcv54/workspace/Sideproject_260526

## 사용자 컨텍스트 (CLAUDE.md 요약)
- QC/API 생산관리 직무 포트폴리오 (SPC + 6시그마 DMAIC 어필)
- Python 3.14, uv, SQLite + SQLModel, Streamlit, GitHub Actions
- 측정소 4곳: 오창읍 / 복대동 / 오송읍 / 용암동
- 6 오염물질: PM10, PM2.5, O3, NO2, SO2, CO
- 환경기준은 src/analysis/usl_lsl.py의 SPEC_LIMITS

## 절차 (순서대로 정확히 수행)

### 1. 컨텍스트 복원 (5분)
- `reports/daily/latest.md` 읽기 (어제 통계 상태)
- `docs/PHASE_QUEUE.yml` 읽기 (작업 큐)
- 이전 1~2개 `reports/daily/dev_action_*.md` 읽기 (최근 작업 흐름)

### 2. 작업 1개 선택
- PHASE_QUEUE.yml에서 `status: pending`이고 모든 `depends_on` 마일스톤이 충족된 작업
- 그중 `priority`가 가장 높은 1개 선택
- 선택 이유와 deliverables를 한 단락으로 사용자에게 보고

### 3. 작업 수행 (메인)
- deliverables의 모든 파일 작성·수정
- 모든 새 함수: 타입힌트 + 한국어 docstring (Google style)
- 단위 테스트 추가 (합성 데이터로 가능한 케이스 우선)
- 기존 스타일 준수: pathlib.Path, loguru, SQLModel, random_state=42
- 기존 데이터 스키마 변경 금지 (AirQualityMeasurement)
- 새 의존성은 가능한 한 추가 없이 (numpy/pandas/scipy/sklearn 정도까지만 OK)

### 4. 검증
- `uv run pytest -q` 실행
- 모든 테스트(기존 60+신규) 통과 필수
- 실패 시 수정 후 재시도, 3회 실패하면 작업 abort + 원인 보고하고 종료

### 5. PHASE_QUEUE.yml 갱신
- 완료한 작업의 `status: pending` → `completed`
- 의존성 끊긴 다른 작업이 새로 READY 됐는지 확인

### 6. 개발 리포트 작성
- `reports/daily/dev_action_YYYY-MM-DD.md` 생성
- 다음 섹션 포함:
  - 무엇을 (작업 ID + 제목)
  - 왜 (priority 선택 근거)
  - 어떻게 (코어 변경 사항 3~5줄)
  - 테스트 결과 (pytest 출력 마지막 줄)
  - 다음 작업 후보 (큐에서 새로 READY 된 것)

### 7. 커밋 & 푸시
- git add: 변경된 파일만 (data.db, .env, .venv, uv.lock 외 모두 OK)
- 커밋 메시지:
  - 제목: `auto(claude): [작업ID] 작업제목 (한국어)`
  - 본문: deliverables 리스트 + 테스트 통과 확인 + 다음 후보
  - Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
- `git push origin main`

### 8. 마무리
- 한 줄로 "오늘 무엇을 추가했는가" 보고
- 세션 종료 (다음 세션은 내일 같은 시각 자동)

## 절대 하지 말 것
- 같은 세션에서 2개 이상 작업 시작 (1세션 1태스크)
- API 키, 인증 정보 출력
- pytest 실패한 채로 commit
- 데이터 파일(data.db) 임의 수정
- 측정소명, 측정 단위, 등급 체계 변경
- 의미 없는 의존성 추가
- README.md의 라이브 데모 URL 변경

## 안전 가드
- 30분 안에 끝나지 않을 작업이면 abort + 다음 날 재시도 안내
- git status 처음과 끝 비교해서 의도 외 변경 없는지 확인
- 새 commit이 main 외 브랜치를 만들지 않게

## 시작 신호
"자율 개발 루프 시작" 한 줄 출력 후 위 절차 수행.
```

---

## 참고

### 이 루틴이 매일 진척하게 될 작업 순서 (현재 큐 기준)

1. **CONTROL_CHART** — EWMA/CUSUM/X-bar 관리도 데이터 생성 (★★★ READY)
2. **WE_RULES** — Western Electric 8 Rules (★★★, 30건/측정소 후)
3. **HYPOTHESIS_TEST** — t-test/ANOVA 단지 비교 (★★★, 30건 후)
4. **ISOLATION_FOREST** — IsolationForest 이상 탐지 (★★, 50건 후)
5. **DISCORD_ALERT** — Discord Webhook 알림 (★★, WE_RULES 후)
6. **DMAIC_REPORT** — DMAIC PDF 보고서 (★★★, 데이터 충분 후)
7. **WEATHER_API** — 기상청 API 결합 (★, 시간 여유)

대략 일주일~열흘이면 Phase 2가 거의 자동으로 완성됨.

### 비용 추정

- 1 세션당 평균 200~500K 토큰 (Sonnet 4.5 기준)
- 한 달 30회 = 6~15M 토큰
- Claude Max 플랜이면 충분, Pro는 한도 빠르게 소진 가능

### 일시 중지 / 재시작

- Routines 화면에서 해당 루틴 우측의 토글 또는 ⋮ 메뉴
- 비용 부담되면 격일 주기로 변경 가능 (스케줄 수정)

### 보안

- API 키는 .env에 있고 절대 commit되지 않음
- Routine 프롬프트에도 키 노출 없음
- git push 시 GitHub PAT는 사용자 로컬 자격증명 사용
