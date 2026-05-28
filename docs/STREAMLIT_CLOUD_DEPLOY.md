# Streamlit Cloud 라이브 데모 배포 가이드

> 면접관이 클릭 한 번으로 대시보드를 보게 만들기.
> GitHub 레포 push만 하면 Streamlit이 자동으로 web에 띄워준다.

## 동작 흐름

```
GitHub Actions: 매시 :15 UTC에 collect_once 실행 → DB 갱신 → repo에 자동 commit
                                                        ↓
Streamlit Cloud: 새 commit 감지 → 자동 재빌드 → 새 데이터로 dashboard 갱신
                                                        ↓
면접관: https://xxx.streamlit.app 접속 → 항상 최신 데이터 + 자동 누적 증거 확인
```

- 무료 (Community Tier)
- 24/7 운영
- 사용자 PC 무관

## 사용자가 직접 해야 하는 단계 (5분)

Streamlit Cloud는 GitHub로 로그인하고 레포를 연결하는 방식이라 본인 계정에서만 가능.

### ① Streamlit Cloud 가입

1. https://share.streamlit.io
2. **Sign in with GitHub** → 본인 계정(robinho0329)으로 로그인
3. Streamlit이 레포 읽기 권한을 요청 → 승인

### ② 새 앱 배포

1. 우측 상단 **Create app** (또는 New app)
2. **Deploy from GitHub** 선택
3. 입력:

| 항목 | 값 |
|------|-----|
| Repository | `robinho0329/chungbuk-air-quality-monitor` |
| Branch | `main` |
| Main file path | `dashboard/app.py` |
| App URL (선택) | `chungbuk-air-quality` 같은 짧은 이름 |

4. **Advanced settings** 펼쳐서:
   - **Python version**: `3.13` (Streamlit Cloud는 3.14를 아직 지원 안 할 수 있음. `runtime.txt`에 명시했으니 자동 인식됨)
5. **Deploy!** 클릭

### ③ 첫 빌드 대기 (3~5분)

화면에 빌드 로그가 흐름:
```
🔨 Building...
🚀 Installing dependencies from requirements.txt
📦 Setting up app
✅ Your app is live!
```

성공하면 화면 우측 상단에 앱 URL이 표시됨. 예: `https://chungbuk-air-quality.streamlit.app`

### ④ Secret 등록 (필수!)

대시보드 자체는 키 없이도 동작하지만(읽기 전용), 만약 향후 `collect_once.py`를 cloud에서 트리거할 일 있으면 등록:

1. 앱 페이지 우측 상단 **⋮ → Settings → Secrets**
2. 다음 추가:
   ```toml
   AIRKOREA_API_KEY = "여기에_본인_키"
   ```
3. Save → 앱 자동 재시작

> **참고**: 현재는 GitHub Actions가 수집을 담당하므로 Cloud 측 Secret은 선택사항. 그래도 미래 대비해서 등록 권장.

### ⑤ URL을 README와 이력서에 추가

배포 성공하면 받은 URL을:
1. `README.md` 상단 **라이브 데모** 줄에 채우기
2. 이력서·포트폴리오 페이지에 한 줄 추가

```
🔗 라이브 데모: https://chungbuk-air-quality.streamlit.app
```

## 자동 재배포

이후엔 사용자 액션 없이 자동:
- GitHub Actions가 매시 DB를 commit & push
- Streamlit Cloud가 push 감지 → 자동 재배포 (1~2분)
- 새 데이터가 대시보드에 반영

## 일시 중지·재시작

| 상황 | 방법 |
|------|------|
| 일주일 이상 미접속 | Streamlit Cloud가 자동 sleep. 접속 시 자동 wake (10~20초) |
| 수동 중지 | 앱 페이지 ⋮ → Reboot 또는 Delete |
| 키 변경 | Settings → Secrets에서 수정 후 Save (자동 재시작) |

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `ModuleNotFoundError: dashboard` | sys.path bootstrap 누락 | 이미 모든 파일에 추가됨 (bfa7a3f 커밋 이후) |
| `ValueError: AIRKOREA_API_KEY required` | dashboard 자체는 키 불필요. `config.py`가 lazy validation으로 수정됨 | 다음 commit 이후 자동 해결 |
| 빌드 실패 - Python 버전 | `runtime.txt`가 안 읽힘 | App 설정에서 Python 버전 명시 |
| 빌드 실패 - 패키지 | `requirements.txt`에 너무 많은 의존성 | dashboard만의 가벼운 버전 사용 (현재 그렇게 작성됨) |
| DB 빈 차트 | repo의 data.db에 데이터가 부족 | GitHub Actions가 매시 추가하니 며칠 기다림 |
| 새 commit 후 안 갱신 | 캐시 | ⋮ → Reboot |

## 비용·한도

| 항목 | 무료 한도 |
|------|---------|
| 앱 개수 | 무제한 (public repo) |
| 동시 접속자 | ~수십 명 (기본) |
| 메모리 | 1 GB |
| 자동 sleep | 1주일 미접속 시 |
| 재배포 횟수 | 무제한 (매시 GHA push해도 OK) |
