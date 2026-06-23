# 포트폴리오 발표 덱 (디자인본)

`reports/portfolio/포트폴리오_충북대기질_SPC.pptx` 의 소스.
자동 생성되는 `reports/portfolio/latest.pptx`(주 1회 GHA)와 별개의 **발표용 디자인 덱**(17슬라이드).

## 구성
- `gen_charts.py` — 실데이터(SQLite)로 matplotlib 차트 6종 PNG + **stats.json**(핵심 수치) 생성
- `deck.js` — pptxgenjs로 17슬라이드 덱 빌드. 헤드라인 수치는 stats.json을 읽어 차트와 일치(드리프트 방지)
- 슬라이드: 표지 · **훅(반전 메시지)** · 목차 · DMAIC 13장 · 결론 · **Q&A 백업(Appendix)**
- 발표 스크립트: `docs/PRESENTATION_SCRIPT.md`, 프롬프트: `docs/PRESENTATION_PROMPTS.md`

## 재생성 방법 (OS 무관 · in-place)
```bash
uv run python scripts/portfolio_deck/gen_charts.py        # 차트 PNG + stats.json (한글폰트 자동탐색)
cd scripts/portfolio_deck && npm install --no-save pptxgenjs sharp react react-dom react-icons  # 최초 1회
node deck.js                                              # → 포트폴리오_충북대기질_SPC_v2.pptx
cp 포트폴리오_충북대기질_SPC_v2.pptx ../../reports/portfolio/포트폴리오_충북대기질_SPC.pptx
```
> `img/`·`node_modules/`·`stats.json`·`*.pptx`는 .gitignore. Pretendard 경로는 `PORTFOLIO_FONT_DIR`로 지정(없으면 맑은고딕/나눔 폴백).

## 디자인 레퍼런스
클린 코발트블루 + Pretendard 헤비, 실제 차트 이미지, Governing Message 바·라운드 카드·알약 배지·프로세스 셰브론 (데이터 분석 발표 덱 컨벤션).
