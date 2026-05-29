# 외부 스케줄러로 시간당 수집 보장 (cron-job.org)

> **왜 필요한가**: GitHub Actions의 내장 `schedule` cron은 best-effort라 무료/public 레포에서
> 트리거를 대량 드롭한다. 실측 결과 우리 레포는 `:07/:27/:47`(시간당 3회) 설정에도
> **24시간 동안 6회만** 실행되고 분(分)도 안 지켜졌다(약 89% 누락).
> 반면 `workflow_dispatch` API 호출은 throttling 없이 **즉시 실행**된다.
> → 외부 cron이 매시 정각 이 API를 호출하면 **진짜 시간당 수집**이 보장된다.

검증 완료: 아래 엔드포인트는 `gh api`로 호출 시 204(성공) 확인됨.

---

## 호출할 API (cron-job.org가 매시 실행할 요청)

```
POST https://api.github.com/repos/robinho0329/chungbuk-air-quality-monitor/actions/workflows/collect.yml/dispatches

Headers:
  Authorization: Bearer <GITHUB_PAT>
  Accept: application/vnd.github+json
  X-GitHub-Api-Version: 2022-11-28

Body (JSON):
  {"ref": "main"}
```

응답 204 No Content = 성공(본문 없음이 정상).

---

## 1단계: GitHub Personal Access Token 발급 (최소 권한)

> ⚠️ PAT는 비밀키다. **레포·코드에 절대 넣지 말 것.** cron-job.org에만 저장한다.

1. GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate new token
2. 설정:
   - **Repository access**: Only select repositories → `chungbuk-air-quality-monitor`
   - **Permissions** → Repository permissions:
     - **Actions**: Read and write  ← 워크플로 dispatch에 필수
     - (Metadata: Read-only는 자동 포함)
   - **Expiration**: 90일 등(만료 후 재발급)
3. 생성된 토큰 문자열을 복사(이때만 보임).

(클래식 토큰을 쓴다면 `repo` + `workflow` 스코프.)

---

## 2단계: cron-job.org 작업 생성

1. https://cron-job.org 무료 가입 → **Create cronjob**
2. **URL**: `https://api.github.com/repos/robinho0329/chungbuk-air-quality-monitor/actions/workflows/collect.yml/dispatches`
3. **Schedule**: Every hour, 분은 `5`(정각 회피) 등 — 예: 매시 :05
4. **Advanced / Request** 설정:
   - **Request method**: `POST`
   - **Request headers** 추가:
     - `Authorization`: `Bearer <복사한_PAT>`
     - `Accept`: `application/vnd.github+json`
     - `X-GitHub-Api-Version`: `2022-11-28`
   - **Request body**: `{"ref": "main"}`
5. 저장.

---

## 3단계: 검증

- 저장 후 cron-job.org의 "Run now"로 즉시 테스트.
- GitHub Actions 탭에서 **event가 `workflow_dispatch`인 실행**이 매시 뜨면 성공.
- cron-job.org 실행 로그에서 HTTP **204** 확인.

---

## 보안·운영 메모

- PAT는 cron-job.org에만 저장(레포 커밋 금지). 만료 시 재발급·교체.
- 최소 권한(해당 레포 Actions write)만 부여.
- **이중 안전망**: 내장 `schedule` cron은 그대로 둔다(fallback). 외부 트리거가 죽어도
  GitHub이 가끔이라도 실행하면 **self-heal**(`src/collectors/self_heal.py`)이 직전 24h 갭을
  자동 복구하므로 데이터 완결성은 유지된다.
- 즉 **외부 cron = 실시간성 보장**, **self-heal = 완결성 보장**의 2중 구조.

---

## 대안 (참고)

- **EasyCron / Google Cloud Scheduler / 본인 상시구동 서버 crontab** 도 동일하게 dispatch API 호출 가능.
- GitHub Actions `repository_dispatch` 이벤트로 바꿔도 되나, `workflow_dispatch`가 가장 간단.
