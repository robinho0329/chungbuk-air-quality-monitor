# Prefect 운영급 스케줄링 설정 가이드

> 매시 5분에 자동으로 에어코리아 데이터를 수집·저장하기 위한
> Prefect 3 정식 서버 + 워커 구성.

## 왜 정식 서버가 필요한가

`flow.serve()`만 실행하면 임시(ephemeral) 서버가 뜨는데,
이 모드에서는 **스케줄러가 동작하지 않습니다**. 즉:

| 구성 | 워커 (작업 폴링) | 스케줄러 (cron 트리거) |
|------|----------------|----------------------|
| `serve()`만 (ephemeral) | ✅ | ❌ 없음 |
| 정식 server + serve | ✅ | ✅ |

수동 트리거(`prefect deployment run ...`)는 두 구성 모두 가능하지만,
매시 자동 실행은 정식 서버가 필수.

## 실행 절차 (3 터미널)

### 사전 정리

이전에 `serve()`로 띄운 ephemeral 서버가 돌고 있다면 그 터미널에서 **Ctrl+C로 중단**.

### 터미널 1: Prefect 서버 띄우기

```bash
cd "C:/Users/xcv54/workspace/Sideproject_260526"
.venv\Scripts\activate
prefect server start
```

초기화 로그 후 `Check out the dashboard at http://127.0.0.1:4200` 메시지가 뜨면 준비 완료.
**이 터미널은 계속 켜두세요.** Ctrl+C로 종료하면 서버가 죽습니다.

브라우저에서 http://127.0.0.1:4200 열면 Prefect UI에서 deployment, flow run, 로그를 시각적으로 확인할 수 있습니다.

### 터미널 2: Deployment 등록 + 워커 띄우기

새 터미널을 열고:

```bash
cd "C:/Users/xcv54/workspace/Sideproject_260526"
.venv\Scripts\activate
uv run python -c "from flows.collect_flow import deploy; deploy()"
```

이번에는 ephemeral 서버 경고가 뜨지 않고 정식 서버(127.0.0.1:4200)에 연결됩니다.
출력에 다음이 보이면 성공:

```
Your flow 'airkorea-collect' is being served and polling for scheduled runs!
```

**이 터미널도 계속 켜두세요.** 워커 역할이라 종료하면 스케줄이 와도 실행할 사람이 없습니다.

### 터미널 3: 즉시 검증 (선택)

스케줄을 기다리지 않고 바로 한 번 트리거하려면:

```bash
cd "C:/Users/xcv54/workspace/Sideproject_260526"
.venv\Scripts\activate
prefect deployment run "airkorea-collect/hourly-airkorea-collect"
```

터미널 2에서 flow가 즉시 시작되는 로그가 보입니다.

## 동작 검증

### 1. UI 확인
http://127.0.0.1:4200 → 좌측 **Deployments**에 `airkorea-collect/hourly-airkorea-collect`가 보이고 다음 실행 시각(매시 :05)이 표시됨.

### 2. 누적 진행 확인
다음 매시 :05를 지나고 별도 터미널에서:
```bash
uv run python -c "from src.storage.database import query_all; from collections import Counter; rows = query_all(); print(f'총 {len(rows)}건'); [print(f'  {k}: {v}건') for k, v in Counter(r.station_name for r in rows).items()]"
```
측정소당 건수가 1씩 증가하면 성공.

## 중단 절차

- 터미널 2 (워커): Ctrl+C
- 터미널 1 (서버): Ctrl+C

deployment 자체는 서버 DB(`~/.prefect/prefect.db`)에 남아 있어서, 다음에 서버를 다시 켜면 그대로 보입니다.

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `Cannot schedule flows on an ephemeral server` | 정식 서버가 안 켜져있음 | 터미널 1에서 `prefect server start` |
| `Failed to connect to 127.0.0.1:4200` | 서버가 아직 부팅 중 | 1~2분 기다리고 재시도 |
| 워커는 살아있는데 flow가 안 도는 시각 | 시계가 정시:05 지났는지 확인 | 매시 5분에 트리거. UI에서 다음 실행시각 확인 |
| 측정값이 모두 None | 측정소 통신장애 (정상 흐름) | 다음 정시에 자동 복구 |

## Windows 작업스케줄러 우회 옵션 (참고)

Prefect 3 터미널을 항상 두 개 켜놓는 게 부담스러우면 OS 기본 도구로 우회 가능.
`scripts/collect_once.py`를 매시 :05에 실행하는 작업을 등록:

1. 시작 메뉴 → "작업 스케줄러"
2. 작업 만들기 → 트리거: 매일, 반복: 1시간, 무기한
3. 동작: 프로그램 시작
   - 프로그램: `C:\Users\xcv54\workspace\Sideproject_260526\.venv\Scripts\python.exe`
   - 인수: `scripts/collect_once.py`
   - 시작 위치: `C:\Users\xcv54\workspace\Sideproject_260526`

이 방식은 Prefect UI/재시도/메타데이터를 잃지만 가장 단순.
포트폴리오 면접에서는 정식 Prefect 구성이 더 어필됩니다.
