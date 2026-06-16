# 포트폴리오 발표 덱 (디자인본)

`reports/portfolio/포트폴리오_충북대기질_SPC.pptx` 의 소스.
자동 생성되는 `reports/portfolio/latest.pptx`(주 1회 GHA)와 별개의 **발표용 디자인 덱**(13슬라이드).

## 구성
- `gen_charts.py` — 실데이터(SQLite)로 matplotlib 차트 6종 PNG 생성 (Cpk 히트맵·바, 박스플롯, 잔차 관리도 Before/After, 누적 추세)
- `deck.js` — pptxgenjs로 13슬라이드 덱 빌드 (Pretendard, 코발트 테마, 차트 이미지·아이콘 임베드)

## 재생성 방법
```bash
# 사전: Pretendard 폰트 설치(~/Library/Fonts), Node + pptxgenjs/sharp/react-icons, uv
mkdir -p build/deck/img
uv run python scripts/portfolio_deck/gen_charts.py     # 차트 PNG → build/deck/img/
cd build/deck && cp ../../scripts/portfolio_deck/deck.js . && node deck.js
```
> 경로는 `gen_charts.py`/`deck.js` 상단 상수 기준. `build/`는 .gitignore 처리됨(node_modules·중간 PNG 제외).

## 디자인 레퍼런스
클린 코발트블루 + Pretendard 헤비, 실제 차트 이미지, Governing Message 바·라운드 카드·알약 배지·프로세스 셰브론 (데이터 분석 발표 덱 컨벤션).
