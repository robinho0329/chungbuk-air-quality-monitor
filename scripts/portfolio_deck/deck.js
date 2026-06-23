// 충북권 대기질 SPC 모니터링 — 포트폴리오 덱 v2 (레퍼런스 컨설팅 스타일)
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const path = require("path");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const fa = require("react-icons/fa6");

const fs = require("fs");
const IMG = path.join(__dirname, "img");
// 핵심 수치는 gen_charts.py가 만든 stats.json에서 읽어 차트와 항상 일치시킨다(드리프트 방지).
const S = JSON.parse(fs.readFileSync(path.join(__dirname, "stats.json"), "utf-8"));
const TOTAL = Number(S.total).toLocaleString("en-US");  // "13,685"
const BA = `${S.resid_before_pct}% → ${S.resid_after_pct}%`;

// ── 팔레트 ──────────────────────────────────────────────
const COBALT = "1F40E6";
const COBALT_DK = "1730A8";
const INK = "151B2E";      // 헤더 검정
const BODY = "44506A";     // 본문
const MUTE = "8A94A6";     // 캡션
const LAV = "EEF1FB";      // 카드/거버닝 배경
const LAV2 = "E2E8FB";
const BORDER = "DCE3F2";
const RED = "E04646";
const GREEN = "2E7D32";
const TEAL = "0E9488";
const ORANGE_BG = "FFF6E9";
const ORANGE = "C77B16";
const WHITE = "FFFFFF";
const F = "Pretendard";
const W = 13.33, H = 7.5;

const pres = new pptxgen();
pres.defineLayout({ name: "WIDE", width: W, height: H });
pres.layout = "WIDE";
pres.author = "유호빈";
pres.title = "충북권 산업단지 대기질 SPC 모니터링";

const shadow = () => ({ type: "outer", color: "8794B5", blur: 8, offset: 2, angle: 90, opacity: 0.22 });

// ── 아이콘 → base64 ─────────────────────────────────────
async function icon(Comp, color = COBALT, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Comp, { color: "#" + color, size: String(size) })
  );
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}
let IC = {};
async function buildIcons() {
  const map = {
    industry: fa.FaIndustry, chartLine: fa.FaChartLine, shield: fa.FaShieldHalved,
    server: fa.FaServer, clock: fa.FaRegClock, sync: fa.FaArrowsRotate,
    grid: fa.FaTableCells, bell: fa.FaBell, robot: fa.FaRobot,
    ruler: fa.FaListCheck, trophy: fa.FaTrophy, check: fa.FaCircleCheck,
    bullseye: fa.FaBullseye, database: fa.FaDatabase, cloud: fa.FaCloud,
    flask: fa.FaFlask, gauge: fa.FaGaugeHigh, wind: fa.FaWind,
  };
  for (const [k, C] of Object.entries(map)) IC[k] = await icon(C, COBALT);
  IC.check_w = await icon(fa.FaCircleCheck, "FFFFFF");
  IC.trophy_w = await icon(fa.FaTrophy, "FFFFFF");
}

// ── 이미지 비율 유지 삽입 ───────────────────────────────
async function addChart(slide, file, x, y, w, opts = {}) {
  const meta = await sharp(path.join(IMG, file)).metadata();
  const h = w * (meta.height / meta.width);
  slide.addImage({ path: path.join(IMG, file), x, y, w, h, ...opts });
  return h;
}

// ── 공통 크롬 ───────────────────────────────────────────
function spine(s) {
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.16, h: H, fill: { color: COBALT } });
}
function header(s, title, subtitle) {
  s.addText(title, { x: 0.55, y: 0.3, w: 11.5, h: 0.62, fontSize: 27, bold: true, color: INK, fontFace: F, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.58, y: 1.04, w: 0.07, h: 0.26, fill: { color: COBALT } });
  s.addText(subtitle, { x: 0.75, y: 1.0, w: 11, h: 0.34, fontSize: 13, color: MUTE, fontFace: F, margin: 0, valign: "middle" });
}
function pageNum(s, n) {
  s.addText(String(n).padStart(2, "0"), { x: W - 0.95, y: H - 0.46, w: 0.6, h: 0.3, fontSize: 10, color: MUTE, align: "right", fontFace: F });
}
function govBar(s, msg, y = 1.55) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.55, y, w: 12.25, h: 0.62, fill: { color: LAV }, rectRadius: 0.06 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.72, y: y + 0.13, w: 2.05, h: 0.36, fill: { color: COBALT }, rectRadius: 0.18 });
  s.addText("Governing Message", { x: 0.72, y: y + 0.13, w: 2.05, h: 0.36, fontSize: 11, bold: true, color: WHITE, align: "center", valign: "middle", fontFace: F, margin: 0 });
  s.addText(msg, { x: 2.95, y, w: 9.7, h: 0.62, fontSize: 13.5, bold: true, color: INK, valign: "middle", fontFace: F, margin: 0 });
}
function pill(s, x, y, w, h, text, fill, color, fs = 12) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, rectRadius: h / 2 });
  s.addText(text, { x, y, w, h, fontSize: fs, bold: true, color, align: "center", valign: "middle", fontFace: F, margin: 0 });
}
function card(s, x, y, w, h, topAccent) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: WHITE }, line: { color: BORDER, width: 1 }, rectRadius: 0.08, shadow: shadow() });
  if (topAccent) s.addShape(pres.shapes.RECTANGLE, { x: x + 0.18, y: y + 0.16, w: w - 0.36, h: 0.07, fill: { color: topAccent } });
}

// =====================================================================
async function build() {
  await buildIcons();

  // ───────────────────────── S1 표지
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 3.55, h: H, fill: { color: COBALT } });
    s.addShape(pres.shapes.RECTANGLE, { x: 3.55, y: 0, w: 0.08, h: H, fill: { color: COBALT_DK } });
    // 좌측 패널 아이콘 클러스터
    s.addImage({ data: IC.gauge, x: 1.15, y: 2.5, w: 1.25, h: 1.25 });
    s.addText("AIR QUALITY · SPC", { x: 0.55, y: 4.1, w: 2.9, h: 0.4, fontSize: 13, bold: true, color: "C9D4FF", align: "center", charSpacing: 2, fontFace: F, margin: 0 });
    // 우측 본문
    s.addText("DATA PORTFOLIO  |  품질데이터 · SPC 엔지니어 (QC · API 생산관리)", { x: 4.1, y: 1.55, w: 8.8, h: 0.4, fontSize: 13, bold: true, color: COBALT, charSpacing: 1, fontFace: F, margin: 0 });
    s.addText("충북권 산업단지\n대기질 SPC 모니터링 시스템", { x: 4.1, y: 2.15, w: 8.8, h: 1.9, fontSize: 40, bold: true, color: INK, lineSpacingMultiple: 1.05, fontFace: F, margin: 0 });
    s.addText("통계적 공정관리(SPC) · 6시그마 DMAIC · 데이터 파이프라인 자동화", { x: 4.12, y: 4.25, w: 8.6, h: 0.5, fontSize: 16, color: BODY, fontFace: F, margin: 0 });
    s.addShape(pres.shapes.LINE, { x: 4.12, y: 5.15, w: 8.4, h: 0, line: { color: BORDER, width: 1.5 } });
    s.addText([
      { text: "분석 기간  ", options: { color: MUTE } },
      { text: `${S.period_start} ~ ${S.period_end}`, options: { color: INK, bold: true } },
      { text: "      누적  ", options: { color: MUTE } },
      { text: `${TOTAL}건 · 측정소 5곳 · 1시간 해상도`, options: { color: INK, bold: true } },
    ], { x: 4.12, y: 5.35, w: 8.6, h: 0.4, fontSize: 12.5, fontFace: F, margin: 0 });
    pill(s, 4.12, 6.05, 1.4, 0.46, "유호빈", COBALT, WHITE, 14);
    s.addText("개인 프로젝트  ·  github.com/robinho0329/chungbuk-air-quality-monitor", { x: 5.7, y: 6.05, w: 7, h: 0.46, fontSize: 11.5, color: MUTE, valign: "middle", fontFace: F, margin: 0 });
  }

  // ───────────────────────── S1.5 훅 (반전 메시지 · 단일 핵심 메시지)
  {
    const s = pres.addSlide();
    s.background = { color: INK };
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.16, h: H, fill: { color: COBALT } });
    s.addText("HOOK", { x: 0.9, y: 1.5, w: 4, h: 0.4, fontSize: 13, bold: true, color: "9DB2FF", charSpacing: 3, fontFace: F, margin: 0 });
    s.addText("측정소 5곳, PM2.5 공정능력이\n전부 ‘규격 미달’이었다.", { x: 0.9, y: 2.05, w: 11.6, h: 1.7, fontSize: 34, bold: true, color: WHITE, lineSpacingMultiple: 1.08, fontFace: F, margin: 0 });
    s.addText([
      { text: "Cpk < 1.0", options: { color: "FF8A8A", bold: true } },
      { text: "  —  그런데 진짜 문제는 ", options: { color: "C9D4FF" } },
      { text: "‘위치’가 아니었다.", options: { color: WHITE, bold: true } },
    ], { x: 0.9, y: 3.95, w: 11.6, h: 0.7, fontSize: 23, fontFace: F, margin: 0 });
    s.addShape(pres.shapes.LINE, { x: 0.92, y: 4.95, w: 7.5, h: 0, line: { color: "3A476A", width: 1.5 } });
    s.addText("변동의 95%는 측정소(위치)가 아니라 시간·기상에서 왔다.\n관리할 산포와 그냥 둘 변동을 통계로 가르는 것 — 그것이 이 프로젝트의 핵심이자, 내가 증명한 QC 역량이다.", { x: 0.92, y: 5.15, w: 11.4, h: 1.3, fontSize: 15, color: "AEB9DA", lineSpacingMultiple: 1.45, fontFace: F, margin: 0, valign: "top" });
  }

  // ───────────────────────── S2 목차
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    s.addText("목차", { x: 0.55, y: 0.4, w: 4, h: 0.7, fontSize: 30, bold: true, color: INK, fontFace: F, margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.58, y: 1.2, w: 0.07, h: 0.26, fill: { color: COBALT } });
    s.addText("DMAIC 흐름으로 본 프로젝트 구성", { x: 0.75, y: 1.16, w: 8, h: 0.34, fontSize: 13, color: MUTE, fontFace: F, margin: 0, valign: "middle" });
    const items = [
      ["01", "문제 정의", "산단 대기질 vs 거주지, SPC 상시 감시"],
      ["02", "측정 시스템", "측정 지표·측정소, 무중단 수집 아키텍처"],
      ["03", "데이터 수집·점검", "108일 누적, 결측·이상치 점검"],
      ["04", "관리 기준 설정", "전통 관리도 vs 자기상관 보정 잔차 관리도"],
      ["05", "통계 분석", "Cp/Cpk · 잔차 관리도 · 단지 비교 검정"],
      ["06", "이상탐지·알림 · 현업 전이", "WE Rules·IForest·Discord → GMP 품질관리 전이·결론"],
    ];
    const colX = [0.7, 6.95], cw = 5.65, ch = 1.35, gy = 0.32, y0 = 2.05;
    items.forEach((it, i) => {
      const c = Math.floor(i / 3), r = i % 3;
      const x = colX[c], y = y0 + r * (ch + gy);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: ch, fill: { color: WHITE }, line: { color: BORDER, width: 1 }, rectRadius: 0.1, shadow: shadow() });
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.28, y: y + 0.32, w: 0.72, h: 0.72, fill: { color: COBALT }, rectRadius: 0.1 });
      s.addText(it[0], { x: x + 0.28, y: y + 0.32, w: 0.72, h: 0.72, fontSize: 20, bold: true, color: WHITE, align: "center", valign: "middle", fontFace: F, margin: 0 });
      s.addText(it[1], { x: x + 1.2, y: y + 0.34, w: cw - 1.4, h: 0.46, fontSize: 17, bold: true, color: INK, fontFace: F, margin: 0 });
      s.addText(it[2], { x: x + 1.2, y: y + 0.78, w: cw - 1.4, h: 0.4, fontSize: 12, color: BODY, fontFace: F, margin: 0 });
    });
    pageNum(s, 2);
  }

  // ───────────────────────── S2.5 분석 배경 & 동기
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "분석 배경 & 동기", "왜 이 분석을 시작했는가");
    govBar(s, "공개 대기질 데이터를 ‘제조 공정’에 빗대어, QC·생산관리 직무 역량을 실데이터로 증명하기 위해 시작했다");
    const motives = [
      [IC.bullseye, "직무 역량 입증", "QC/API 생산관리 직무 지원 — SPC·6시그마·데이터 자동화 역량을 ‘말’이 아닌 실데이터·실코드로 증명", COBALT],
      [IC.flask, "메타포로 끝까지 구현", "사내 생산 데이터가 없어도, 공개 대기질 API를 공정·품질특성·규격에 매핑해 공정관리 기법을 완주", TEAL],
      [IC.wind, "지역 문제의식", "충북 청주 산단(오창·오송 등) 인근 대기질이 거주지보다 실제로 나쁜지, 데이터로 직접 검증하고 싶었다", ORANGE],
      [IC.cloud, "자동화 파이프라인 경험", "수집→분석→알림까지 무중단·무비용으로 돌아가는 엔드투엔드 데이터 파이프라인을 직접 설계·운영", "6D4AE0"],
    ];
    const mx = [0.7, 6.85], mw = 5.95, mh = 1.92, my = [2.4, 4.5];
    motives.forEach(([ic, t, d, ac], i) => {
      const x = mx[i % 2], y = my[Math.floor(i / 2)];
      card(s, x, y, mw, mh, ac);
      s.addShape(pres.shapes.OVAL, { x: x + 0.35, y: y + 0.55, w: 0.95, h: 0.95, fill: { color: LAV } });
      s.addImage({ data: ic, x: x + 0.59, y: y + 0.79, w: 0.47, h: 0.47 });
      s.addText(t, { x: x + 1.55, y: y + 0.42, w: mw - 1.8, h: 0.45, fontSize: 16.5, bold: true, color: INK, valign: "middle", fontFace: F, margin: 0 });
      s.addText(d, { x: x + 1.55, y: y + 0.92, w: mw - 1.8, h: 0.85, fontSize: 12, color: BODY, lineSpacingMultiple: 1.28, fontFace: F, margin: 0, valign: "top" });
    });
    pageNum(s, 3);
  }

  // ───────────────────────── S3 문제 정의
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "문제 정의", "주제 · 분석 배경 · 분석 목표");
    govBar(s, "산단 인근 대기질이 거주지보다 통계적으로 나쁜지, 어느 지표를 우선 관리해야 하는지 규명한다");
    const cards = [
      [IC.industry, "분석 주제", "측정소=공정 라인, 오염물질=품질특성(CQA), 환경기준=규격(USL)으로 매핑한 메타포 프로젝트", COBALT],
      [IC.chartLine, "분석 목표", "산단 영향군 vs 거주지 평균차 통계 검정, 공정능력(Cpk) 산출, 우선 관리 지표 도출", TEAL],
      [IC.shield, "분석 배경", "산단 대기질 상시 감시 필요. 단순 농도 비교만으로는 ‘관리 우선순위’ 판단이 어려움", ORANGE],
    ];
    let x = 0.7;
    cards.forEach(([ic, t, d, ac]) => {
      card(s, x, 2.45, 3.9, 2.05, ac);
      s.addImage({ data: ic, x: x + 0.32, y: 2.78, w: 0.62, h: 0.62 });
      s.addText(t, { x: x + 1.1, y: 2.82, w: 2.6, h: 0.5, fontSize: 17, bold: true, color: INK, valign: "middle", fontFace: F, margin: 0 });
      s.addText(d, { x: x + 0.34, y: 3.55, w: 3.25, h: 0.85, fontSize: 12.5, color: BODY, lineSpacingMultiple: 1.25, fontFace: F, margin: 0, valign: "top" });
      x += 4.05;
    });
    // 하단 2 와이드 카드
    card(s, 0.7, 4.75, 5.95, 1.75);
    s.addImage({ data: IC.bullseye, x: 1.0, y: 5.05, w: 0.5, h: 0.5 });
    s.addText("문제 정의", { x: 1.62, y: 5.05, w: 4.5, h: 0.5, fontSize: 15, bold: true, color: COBALT, valign: "middle", fontFace: F, margin: 0 });
    s.addText("산단 인근 대기질은 거주지보다 통계적으로 유의하게 나쁜가?\n어느 지표·어느 측정소를 우선 관리해야 하는가?", { x: 1.0, y: 5.6, w: 5.4, h: 0.85, fontSize: 13.5, bold: true, color: INK, lineSpacingMultiple: 1.25, fontFace: F, margin: 0, valign: "top" });
    card(s, 6.85, 4.75, 5.95, 1.75);
    s.addImage({ data: IC.check, x: 7.15, y: 5.05, w: 0.5, h: 0.5 });
    s.addText("핵심 결과", { x: 7.77, y: 5.05, w: 4.5, h: 0.5, fontSize: 15, bold: true, color: TEAL, valign: "middle", fontFace: F, margin: 0 });
    s.addText([
      { text: "PM2.5·PM10 전 측정소 ‘불량 위험’ 식별", options: { color: INK, bold: true, breakLine: true } },
      { text: `잔차 관리도로 거짓경보 ${BA} 개선`, options: { color: INK, bold: true } },
    ], { x: 7.15, y: 5.6, w: 5.4, h: 0.85, fontSize: 13.5, lineSpacingMultiple: 1.25, fontFace: F, margin: 0, valign: "top" });
    pageNum(s, 4);
  }

  // ───────────────────────── S4 측정 시스템 — 대상
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "측정 시스템 — 대상", "측정 지표 6종 · 측정소 5곳");
    // 좌: 지표 6종 그리드
    s.addText("측정 지표 (품질특성 CQA)", { x: 0.7, y: 1.65, w: 5, h: 0.4, fontSize: 15, bold: true, color: COBALT, fontFace: F, margin: 0 });
    const polls = [
      ["PM2.5", "초미세먼지 · 우선관리"], ["PM10", "미세먼지 · 우선관리"],
      ["NO₂", "이산화질소"], ["O₃", "오존"],
      ["SO₂", "아황산가스"], ["CO", "일산화탄소"],
    ];
    const px = [0.7, 2.78, 4.86], pw = 1.95, ph = 1.15;
    polls.forEach((p, i) => {
      const c = i % 3, r = Math.floor(i / 3);
      const x = px[c], y = 2.15 + r * (ph + 0.28);
      const warn = p[1].includes("우선");
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: pw, h: ph, fill: { color: warn ? "FDEDED" : LAV }, rectRadius: 0.08 });
      s.addText(p[0], { x, y: y + 0.16, w: pw, h: 0.5, fontSize: 20, bold: true, color: warn ? RED : COBALT, align: "center", fontFace: F, margin: 0 });
      s.addText(p[1], { x: x + 0.1, y: y + 0.68, w: pw - 0.2, h: 0.38, fontSize: 10.5, color: BODY, align: "center", fontFace: F, margin: 0 });
    });
    s.addText("USL=대기환경보전법 환경기준 · LSL=0 (단측 규격). 실제 배치공정 양측 규격(USL+LSL)에도 동일 Cpk 산식 적용 가능.", { x: 0.7, y: 4.95, w: 6.3, h: 0.55, fontSize: 10.5, italic: true, color: MUTE, lineSpacingMultiple: 1.15, fontFace: F, margin: 0, valign: "top" });
    // 우: 측정소 그룹
    s.addText("측정소 (공정 라인)", { x: 7.15, y: 1.65, w: 5, h: 0.4, fontSize: 15, bold: true, color: COBALT, fontFace: F, margin: 0 });
    card(s, 7.15, 2.15, 5.65, 1.5, COBALT);
    s.addText("산단 영향군 · 4곳", { x: 7.45, y: 2.42, w: 5, h: 0.4, fontSize: 15, bold: true, color: INK, fontFace: F, margin: 0 });
    s.addText("오창(반도체) · 복대 · 봉명(SK하이닉스 청주캠퍼스 권역) · 오송(바이오)", { x: 7.45, y: 2.85, w: 5.1, h: 0.7, fontSize: 12.5, color: BODY, lineSpacingMultiple: 1.2, fontFace: F, margin: 0, valign: "top" });
    card(s, 7.15, 3.8, 5.65, 1.5, "9AA5B1");
    s.addText("베이스라인 · 1곳 (대조군)", { x: 7.45, y: 4.07, w: 5, h: 0.4, fontSize: 15, bold: true, color: INK, fontFace: F, margin: 0 });
    s.addText("용암동 — 거주지 기준선. 산단 영향군과의 평균차를 Welch t-test로 검정", { x: 7.45, y: 4.5, w: 5.1, h: 0.7, fontSize: 12.5, color: BODY, lineSpacingMultiple: 1.2, fontFace: F, margin: 0, valign: "top" });
    // 하단 인사이트
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: 5.6, w: 12.1, h: 0.95, fill: { color: LAV }, rectRadius: 0.08 });
    pill(s, 0.95, 5.83, 1.5, 0.48, "인사이트", COBALT, WHITE, 12);
    s.addText("6종 × 5측정소 = 30개 ‘공정-품질특성’ 조합을 1시간 해상도로 상시 모니터링", { x: 2.65, y: 5.6, w: 10, h: 0.95, fontSize: 13.5, bold: true, color: INK, valign: "middle", fontFace: F, margin: 0 });
    pageNum(s, 5);
  }

  // ───────────────────────── S5 아키텍처
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "측정 시스템 — 아키텍처", "무중단 · 무비용 · 무누락 자동 파이프라인");
    govBar(s, "외부 스케줄러가 GitHub Actions를 트리거 → 수집·저장·배포·알림까지 서버리스 무중단 운영");
    // 프로세스 셰브론
    const steps = [["cron-job.org", "외부 스케줄러"], ["GitHub Actions", "서버리스 수집"], ["에어코리아 API", "시간당 측정"], ["SQLite", "중복 안전 저장"], ["Streamlit", "대시보드 배포"]];
    const icons = [IC.clock, IC.cloud, IC.wind, IC.database, IC.chartLine];
    const n = steps.length, bw = 2.05, gap = 0.42, x0 = 0.75, y = 2.55, bh = 1.35;
    steps.forEach((st, i) => {
      const x = x0 + i * (bw + gap);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: bw, h: bh, fill: { color: i === 1 ? COBALT : LAV }, rectRadius: 0.1 });
      s.addImage({ data: i === 1 ? IC.cloud_w || icons[i] : icons[i], x: x + bw / 2 - 0.28, y: y + 0.2, w: 0.56, h: 0.56 });
      s.addText(st[0], { x: x + 0.04, y: y + 0.78, w: bw - 0.08, h: 0.32, fontSize: 12.5, bold: true, color: i === 1 ? WHITE : INK, align: "center", fontFace: F, margin: 0 });
      s.addText(st[1], { x: x + 0.04, y: y + 1.06, w: bw - 0.08, h: 0.26, fontSize: 10, color: i === 1 ? "D6DEFF" : BODY, align: "center", fontFace: F, margin: 0 });
      if (i < n - 1) s.addText("›", { x: x + bw, y: y + 0.2, w: gap, h: bh - 0.4, fontSize: 30, bold: true, color: COBALT, align: "center", valign: "middle", fontFace: F, margin: 0 });
    });
    // 분석 도구 표
    s.addText("분석 도구 및 방법", { x: 0.75, y: 4.35, w: 6, h: 0.4, fontSize: 15, bold: true, color: COBALT, fontFace: F, margin: 0 });
    const rows = [
      [{ text: "구분", options: { fill: { color: COBALT }, color: WHITE, bold: true, align: "center" } }, { text: "내용", options: { fill: { color: COBALT }, color: WHITE, bold: true, align: "center" } }],
      ["수집 · 저장", "requests(지수 백오프) · SQLite + SQLModel · self-healing 백필"],
      ["통계 · 분석", "Cp/Cpk · 관리도(I/EWMA/CUSUM) · 잔차 관리도 · WE Rules · scipy(t-test/ANOVA)"],
      ["이상탐지 · 알림", "scikit-learn IsolationForest · Discord Webhook"],
      ["자동화 · 품질", "GitHub Actions · pytest 220건 · uv · Streamlit Cloud"],
    ];
    s.addTable(rows, {
      x: 0.75, y: 4.8, w: 12.05, colW: [2.6, 9.45], rowH: 0.42,
      fontSize: 12, fontFace: F, color: BODY, valign: "middle",
      border: { type: "solid", color: BORDER, pt: 1 },
      align: "left",
    });
    pageNum(s, 6);
  }

  // ───────────────────────── S6 수집 성과
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "데이터 수집 성과 & 농도 추세", `${S.days}일 무중단 ${TOTAL}건 · PM2.5 일별 추세`);
    const stats = [[TOTAL, "총 누적 건수"], [`${S.days}일`, "연속 무중단 수집"], [`${S.exceed_days}일`, "산단 USL 초과"], ["220", "회귀 테스트"]];
    let sx = 0.7;
    stats.forEach(([b, l]) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: sx, y: 1.6, w: 2.9, h: 1.35, fill: { color: LAV }, rectRadius: 0.08 });
      s.addText(b, { x: sx, y: 1.74, w: 2.9, h: 0.8, fontSize: 36, bold: true, color: COBALT, align: "center", fontFace: F, margin: 0 });
      s.addText(l, { x: sx, y: 2.55, w: 2.9, h: 0.35, fontSize: 12.5, color: BODY, align: "center", fontFace: F, margin: 0 });
      sx += 3.04;
    });
    await addChart(s, "ts_pm25.png", 0.7, 3.2, 7.8);
    // 우측 설명
    card(s, 8.7, 3.2, 4.1, 3.0);
    s.addText("수집을 넘어 ‘신호’까지", { x: 9.0, y: 3.45, w: 3.6, h: 0.4, fontSize: 15, bold: true, color: COBALT, fontFace: F, margin: 0 });
    s.addText([
      { text: "산단 > 거주지", options: { bold: true, color: INK } },
      { text: ` — 산단 영향군 일평균이 대부분 거주지보다 높고, 환경기준(USL 35)을 ${S.ind_days}일 중 `, options: { color: BODY } },
      { text: `${S.exceed_days}일 초과`, options: { bold: true, color: RED } },
      { text: ".", options: { color: BODY }, breakLine: true },
    ], { x: 9.0, y: 3.95, w: 3.55, h: 1.3, fontSize: 12.5, lineSpacingMultiple: 1.3, fontFace: F, margin: 0, valign: "top" });
    s.addText([
      { text: "self-healing", options: { bold: true, color: INK } },
      { text: " — cron 드롭이 나도 다음 실행이 직전 24h 갭을 멱등 복구해 ", options: { color: BODY } },
      { text: "최종 데이터는 무결", options: { bold: true, color: TEAL } },
      { text: ".", options: { color: BODY } },
    ], { x: 9.0, y: 5.25, w: 3.55, h: 1.0, fontSize: 12.5, lineSpacingMultiple: 1.3, fontFace: F, margin: 0, valign: "top" });
    pageNum(s, 7);
  }

  // ───────────────────────── S7 데이터 점검
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "데이터 점검 — 전처리", "6종 오염물질 분포 · 결측/이상치 확인");
    await addChart(s, "box_grid.png", 1.35, 1.65, 10.6);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: 6.5, w: 12.1, h: 0.72, fill: { color: LAV }, rectRadius: 0.08 });
    pill(s, 0.92, 6.64, 1.5, 0.44, "전처리 결과", COBALT, WHITE, 12);
    s.addText("결측 0건 · 측정값 범위 정상 — 측정시각(data_time)·수집시각(created_at) 분리 기록 = audit trail·ALCOA+ 데이터 무결성 원칙", { x: 2.6, y: 6.5, w: 10, h: 0.72, fontSize: 12.5, bold: true, color: INK, valign: "middle", fontFace: F, margin: 0 });
  }

  // ───────────────────────── S8 관리 기준 (3σ vs 잔차)
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "관리 기준 설정", "전통 관리도 vs 자기상관 보정 잔차 관리도");
    // 좌 부적합
    card(s, 0.7, 1.7, 5.95, 4.6);
    s.addText("전통 I-Chart (i.i.d. 가정)", { x: 1.0, y: 2.0, w: 4.0, h: 0.5, fontSize: 18, bold: true, color: INK, valign: "middle", fontFace: F, margin: 0 });
    pill(s, 5.25, 2.05, 1.15, 0.42, "부적합", "9AA5B1", WHITE, 12);
    s.addText([
      { text: "대기질은 강한 시계열 자기상관(PM2.5 lag-1 ACF ≈ 0.93)을 가진다.", options: { color: BODY, breakLine: true } },
    ], { x: 1.0, y: 2.7, w: 5.35, h: 0.9, fontSize: 13, lineSpacingMultiple: 1.3, fontFace: F, margin: 0, valign: "top" });
    [["독립 가정 붕괴", "인접 관측치가 강하게 상관 → MR 기반 σ 과소추정"],
     ["관리한계 협소", "한계선이 좁아져 정상 변동도 이탈로 오판"],
     ["거짓경보 폭증", `실측 이탈률 ${S.resid_before_pct}% — 특수원인 식별 불가`]].forEach((it, i) => {
      const y = 3.6 + i * 0.85;
      s.addShape(pres.shapes.OVAL, { x: 1.0, y: y + 0.05, w: 0.16, h: 0.16, fill: { color: RED } });
      s.addText(it[0], { x: 1.3, y, w: 5.0, h: 0.3, fontSize: 13, bold: true, color: INK, fontFace: F, margin: 0 });
      s.addText(it[1], { x: 1.3, y: y + 0.3, w: 5.1, h: 0.45, fontSize: 11.5, color: BODY, fontFace: F, margin: 0, valign: "top" });
    });
    // 우 채택
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.85, y: 1.7, w: 5.95, h: 4.6, fill: { color: "F0F8F6" }, line: { color: "B9E0D8", width: 1 }, rectRadius: 0.08, shadow: shadow() });
    s.addText("잔차 관리도 (자기상관 보정)", { x: 7.15, y: 2.0, w: 4.0, h: 0.5, fontSize: 18, bold: true, color: "0B6B61", valign: "middle", fontFace: F, margin: 0 });
    pill(s, 11.4, 2.05, 1.15, 0.42, "채택", TEAL, WHITE, 12);
    s.addText("일주기(시간대) 효과 제거 + AR(1) 잔차에 관리도를 적용해 독립성을 회복.", { x: 7.15, y: 2.7, w: 5.35, h: 0.9, fontSize: 13, color: BODY, lineSpacingMultiple: 1.3, fontFace: F, margin: 0, valign: "top" });
    [["백색화 성공", "ACF 0.93 → ≈0(−0.03), 잔차가 독립에 근접"],
     ["관리한계 정상화", "명목 거짓경보율(0.27%) 수준으로 복원"],
     ["진짜 신호만 탐지", `실측 이탈률 ${BA}, 특수원인 후보만 남김`]].forEach((it, i) => {
      const y = 3.6 + i * 0.85;
      s.addImage({ data: IC.check, x: 7.15, y: y, w: 0.22, h: 0.22 });
      s.addText(it[0], { x: 7.5, y, w: 5.0, h: 0.3, fontSize: 13, bold: true, color: INK, fontFace: F, margin: 0 });
      s.addText(it[1], { x: 7.5, y: y + 0.3, w: 5.1, h: 0.45, fontSize: 11.5, color: BODY, fontFace: F, margin: 0, valign: "top" });
    });
    pageNum(s, 9);
  }

  // ───────────────────────── S9 Cpk 분석
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "통계 분석 — 공정능력지수 Cpk", "측정소 × 오염물질 30개 조합 진단");
    await addChart(s, "cpk_heatmap.png", 0.55, 2.35, 7.7);
    s.addText("USL=대기환경보전법 일평균 환경기준(PM2.5 35㎍/㎥ 등) · LSL=0 · Cpk<1.0=불량 위험 · Cpk≥1.33=양호", { x: 0.7, y: 6.05, w: 8.1, h: 0.35, fontSize: 10.5, italic: true, color: MUTE, fontFace: F, margin: 0 });
    // 우측 인사이트
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.85, y: 1.95, w: 3.95, h: 2.25, fill: { color: "FDEDED" }, rectRadius: 0.08 });
    s.addText("우선 관리 — PM2.5 · PM10", { x: 9.1, y: 2.2, w: 3.5, h: 0.4, fontSize: 14.5, bold: true, color: RED, fontFace: F, margin: 0 });
    s.addText(`전 측정소 Cpk < 1.0 ‘불량 위험’. 특히 ${S.cpk_pm25_min_station} PM2.5 Cpk ${S.cpk_pm25_min}로 최저 → 1순위 관리 대상. 미세먼지가 구조적 핵심 인자.`, { x: 9.1, y: 2.68, w: 3.5, h: 1.45, fontSize: 12.5, color: BODY, lineSpacingMultiple: 1.3, fontFace: F, margin: 0, valign: "top" });
    card(s, 8.85, 4.45, 3.95, 2.25);
    s.addText("관리 양호 — SO₂ · CO", { x: 9.1, y: 4.72, w: 3.5, h: 0.4, fontSize: 14.5, bold: true, color: TEAL, fontFace: F, margin: 0 });
    s.addText("Cpk ≥ 1.2로 규격 대비 여유. Cp/Cpk·USL은 대기환경보전법 환경기준(일·연평균) 기반으로 산출.", { x: 9.1, y: 5.2, w: 3.5, h: 1.4, fontSize: 12.5, color: BODY, lineSpacingMultiple: 1.3, fontFace: F, margin: 0, valign: "top" });
    pageNum(s, 10);
  }

  // ───────────────────────── S10 잔차 관리도 결과
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "통계 분석 — 자기상관 보정 성과", `잔차 관리도로 거짓경보율 ${BA} 정상화`);
    await addChart(s, "residual_ba.png", 0.7, 1.7, 8.3);
    // 우측 before/after 콜아웃
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.35, y: 1.9, w: 3.45, h: 1.7, fill: { color: WHITE }, line: { color: BORDER, width: 1 }, rectRadius: 0.08, shadow: shadow() });
    s.addText("BEFORE", { x: 9.35, y: 2.08, w: 3.45, h: 0.32, fontSize: 12, bold: true, color: MUTE, align: "center", charSpacing: 1, fontFace: F, margin: 0 });
    s.addText(`${S.resid_before_pct}%`, { x: 9.35, y: 2.35, w: 3.45, h: 0.85, fontSize: 50, bold: true, color: RED, align: "center", fontFace: F, margin: 0 });
    s.addText("전통 I-Chart 거짓경보율", { x: 9.35, y: 3.2, w: 3.45, h: 0.32, fontSize: 11.5, color: BODY, align: "center", fontFace: F, margin: 0 });
    s.addText("▼", { x: 9.35, y: 3.66, w: 3.45, h: 0.32, fontSize: 16, bold: true, color: TEAL, align: "center", fontFace: F, margin: 0 });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.35, y: 4.05, w: 3.45, h: 1.7, fill: { color: "F0F8F6" }, rectRadius: 0.08 });
    s.addText("AFTER", { x: 9.35, y: 4.23, w: 3.45, h: 0.32, fontSize: 12, bold: true, color: "0B6B61", align: "center", charSpacing: 1, fontFace: F, margin: 0 });
    s.addText(`${S.resid_after_pct}%`, { x: 9.35, y: 4.5, w: 3.45, h: 0.85, fontSize: 50, bold: true, color: TEAL, align: "center", fontFace: F, margin: 0 });
    s.addText("잔차 관리도 거짓경보율", { x: 9.35, y: 5.35, w: 3.45, h: 0.32, fontSize: 11.5, color: "0B6B61", align: "center", fontFace: F, margin: 0 });
    // 하단 인사이트
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: 6.4, w: 12.1, h: 0.82, fill: { color: COBALT }, rectRadius: 0.08 });
    s.addText([
      { text: "핵심 성과   ", options: { color: "C9D4FF", bold: true } },
      { text: "|   원시 관리도의 이탈은 대부분 자기상관에 의한 거짓경보 — 잔차에 남는 이탈만이 진짜 특수원인 후보", options: { color: WHITE, bold: true } },
    ], { x: 1.05, y: 6.4, w: 11.6, h: 0.82, fontSize: 13.5, valign: "middle", fontFace: F, margin: 0 });
  }

  // ───────────────────────── S11 단지 비교
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "통계 분석 — 단지 비교 검정", "산단 영향군 vs 거주지 (Welch t-test)");
    await addChart(s, "group_box.png", 0.7, 1.75, 7.0);
    s.addText(`※ 전체 누적 ${TOTAL}건. PM2.5 결측 제외 측정치로 산단 4측정소(합산) vs 거주지 1측정소를 Welch t-test 비교.`,
      { x: 0.7, y: 6.35, w: 7.2, h: 0.6, fontSize: 9.5, italic: true, color: MUTE, lineSpacingMultiple: 1.15, fontFace: F, margin: 0, valign: "top" });
    // 우측 검정 결과
    s.addImage({ data: IC.check, x: 8.3, y: 1.95, w: 0.45, h: 0.45 });
    s.addText("검증 결과", { x: 8.85, y: 1.95, w: 4, h: 0.45, fontSize: 17, bold: true, color: COBALT, valign: "middle", fontFace: F, margin: 0 });
    s.addShape(pres.shapes.LINE, { x: 8.3, y: 2.6, w: 4.5, h: 0, line: { color: BORDER, width: 1 } });
    s.addText("가설", { x: 8.3, y: 2.8, w: 4.5, h: 0.35, fontSize: 12, bold: true, color: MUTE, fontFace: F, margin: 0 });
    s.addText("“산단 영향군의 PM2.5 평균이 거주지보다 높을 것이다”", { x: 8.3, y: 3.15, w: 4.55, h: 0.8, fontSize: 14, bold: true, color: INK, lineSpacingMultiple: 1.25, fontFace: F, margin: 0, valign: "top" });
    s.addText([
      { text: "Welch t-test", options: { bold: true, color: COBALT } },
      { text: "로 두 군 평균차의 통계적 유의성을 검정. Cohen’s d로 효과크기를 함께 산출해 실질적 차이를 확인.", options: { color: BODY } },
    ], { x: 8.3, y: 4.05, w: 4.55, h: 1.3, fontSize: 12.5, lineSpacingMultiple: 1.3, fontFace: F, margin: 0, valign: "top" });
    pill(s, 8.3, 5.55, 2.0, 0.5, "가설 검정 자동화", COBALT, WHITE, 12.5);
    s.addText("daily 루프가 MD·Word 리포트 자동 생성", { x: 8.3, y: 6.12, w: 4.55, h: 0.4, fontSize: 11, italic: true, color: MUTE, fontFace: F, margin: 0 });
    pageNum(s, 12);
  }

  // ───────────────────────── S12 이상탐지 & 알림
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "이상 탐지 자동화 & 실시간 알림", "Western Electric Rules · IsolationForest · Discord");
    const items = [
      [IC.ruler, "Western Electric Rules", "추세·쏠림·허깅·지그재그 등 8개 비랜덤 패턴 자동 판정. 3σ 이탈만 보던 한계를 넘어 특수원인 신호를 조기 포착.", COBALT],
      [IC.robot, "IsolationForest", "6개 오염물질을 동시에 보는 다변량 이상 탐지. 단변량 관리도가 놓치는 복합 이상 패턴을 비지도 학습으로 식별.", TEAL],
      [IC.bell, "Discord 실시간 알림", "매 수집 후 Cpk 미달·룰 위반을 점검해 Webhook 전송. 위험/주의/정상 색상 코드로 즉시 인지.", ORANGE],
    ];
    let x = 0.7;
    items.forEach(([ic, t, d, ac], i) => {
      card(s, x, 1.85, 3.9, 4.0, ac);
      s.addShape(pres.shapes.OVAL, { x: x + 0.32, y: 2.5, w: 1.0, h: 1.0, fill: { color: LAV } });
      s.addImage({ data: ic, x: x + 0.57, y: 2.75, w: 0.5, h: 0.5 });
      s.addText(`0${i + 1}`, { x: x + 0.34, y: 3.65, w: 3.2, h: 0.4, fontSize: 13, bold: true, color: ac, fontFace: F, margin: 0 });
      s.addText(t, { x: x + 0.34, y: 3.98, w: 3.3, h: 0.7, fontSize: 16.5, bold: true, color: INK, lineSpacingMultiple: 1.05, fontFace: F, margin: 0, valign: "top" });
      s.addText(d, { x: x + 0.34, y: 4.72, w: 3.25, h: 1.05, fontSize: 12, color: BODY, lineSpacingMultiple: 1.3, fontFace: F, margin: 0, valign: "top" });
      x += 4.05;
    });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: 6.1, w: 12.1, h: 0.82, fill: { color: LAV }, rectRadius: 0.08 });
    pill(s, 0.92, 6.27, 1.5, 0.48, "Control", COBALT, WHITE, 12);
    s.addText("DMAIC의 Control 단계 — 탐지에서 알림까지 완전 자동화로 지속 모니터링 체계 완성", { x: 2.6, y: 6.1, w: 10, h: 0.82, fontSize: 13, bold: true, color: INK, valign: "middle", fontFace: F, margin: 0 });
    pageNum(s, 13);
  }

  // ───────────────────────── S13.5 현업 전이 (GMP·품질관리)
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "현업 전이 — GMP · 품질관리로의 확장", "SPC 역량이 실제 제조·품질 업무로 어떻게 이어지는가");
    govBar(s, "대기질로 검증한 SPC·통계·자동화 역량은 GMP 환경의 공정능력·일탈관리·밸리데이션으로 그대로 전이된다");
    const rows = [
      [{ text: "본 프로젝트에서 구현", options: { fill: { color: COBALT }, color: WHITE, bold: true, align: "center", valign: "middle" } },
       { text: "GMP · 품질관리 현업 적용", options: { fill: { color: COBALT }, color: WHITE, bold: true, align: "center", valign: "middle" } }],
      ["Cp / Cpk 공정능력 산출", "공정밸리데이션(PPQ) 공정능력 평가 · 규격(spec) 대비 여유 판정"],
      ["관리도 + Western Electric Rules", "공정 모니터링 · 일탈(deviation)·OOT 조기 탐지 · CAPA 연계"],
      ["자기상관 보정 잔차 관리도", "자기상관 있는 연속공정 변수의 올바른 관리한계 설정 (거짓경보 억제)"],
      ["Welch t-test · ANOVA", "배치 간·라인 간 비교 · 동등성은 TOST로 확장(p·Cohen’s d 산출 완료, 임계 ±δ만 추가)"],
      ["IsolationForest 다변량 탐지", "다변량 공정이상(MSPC) 탐지 · OOS/OOT 조사 트리거 · 원인변수 스크리닝"],
      ["수집→분석→알림 자동화", "MES / LIMS 품질데이터 모니터링 · ALCOA+ · Part 11 audit trail"],
    ];
    s.addTable(rows, {
      x: 0.7, y: 2.4, w: 11.95, colW: [4.35, 7.6], rowH: [0.48, 0.56, 0.56, 0.56, 0.56, 0.56, 0.56],
      fontSize: 12, fontFace: F, color: INK, valign: "middle",
      border: { type: "solid", color: BORDER, pt: 1 },
      align: "left",
    });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: 6.6, w: 11.95, h: 0.62, fill: { color: LAV }, rectRadius: 0.08 });
    pill(s, 0.92, 6.74, 1.7, 0.34, "생산관리 확장", COBALT, WHITE, 11);
    s.addText("연속공정 SPC를 배치공정으로 확장 — 골든배치 대비 Mahalanobis 거리 · 배치 간 변동 ANOVA/혼합효과모형 · 수율 모니터링", { x: 2.8, y: 6.6, w: 9.85, h: 0.62, fontSize: 11.5, bold: true, color: INK, valign: "middle", fontFace: F, margin: 0 });
  }

  // ───────────────────────── S13 결론
  {
    const s = pres.addSlide();
    s.background = { color: COBALT };
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: W, h: 0.14, fill: { color: COBALT_DK } });
    s.addImage({ data: IC.trophy_w, x: 0.7, y: 0.82, w: 0.55, h: 0.55 });
    s.addText("핵심 성과 & 입증 역량", { x: 1.4, y: 0.78, w: 11, h: 0.65, fontSize: 28, bold: true, color: WHITE, valign: "middle", fontFace: F, margin: 0 });
    const kpis = [[`${TOTAL}건`, `${S.days}일 무중단 수집`], [BA, "PM2.5 거짓경보율"], ["8 + 다변량", "WE Rules · IForest"], ["220 / 220", "회귀 테스트 통과"]];
    let x = 0.7;
    kpis.forEach(([b, l]) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.95, w: 2.9, h: 2.1, fill: { color: "2E4DEA" }, rectRadius: 0.1 });
      s.addShape(pres.shapes.RECTANGLE, { x: x + 0.25, y: 2.2, w: 2.4, h: 0.06, fill: { color: "9DB2FF" } });
      s.addText(b, { x: x + 0.05, y: 2.5, w: 2.8, h: 0.8, fontSize: 24, bold: true, color: WHITE, align: "center", fontFace: F, margin: 0 });
      s.addText(l, { x: x + 0.1, y: 3.35, w: 2.7, h: 0.5, fontSize: 12.5, color: "D6DEFF", align: "center", lineSpacingMultiple: 1.1, fontFace: F, margin: 0 });
      x += 3.04;
    });
    s.addShape(pres.shapes.LINE, { x: 0.7, y: 4.55, w: 11.95, h: 0, line: { color: "5A73EE", width: 1 } });
    s.addText("입증한 역량", { x: 0.7, y: 4.75, w: 11, h: 0.4, fontSize: 14, bold: true, color: "C9D4FF", charSpacing: 1, fontFace: F, margin: 0 });
    [["SPC · 6시그마 DMAIC 실데이터 적용", "Cp/Cpk·관리도·가설검정을 직접 구현"],
     ["데이터 파이프라인 무중단 자동화", "GitHub Actions로 수집→분석→알림 무인 운영"],
     ["통계적 엄밀성", "자기상관 보정으로 거짓경보를 정량 개선"]].forEach((it, i) => {
      const cx = 0.7 + i * 4.0;
      s.addImage({ data: IC.check_w, x: cx, y: 5.25, w: 0.32, h: 0.32 });
      s.addText(it[0], { x: cx + 0.45, y: 5.2, w: 3.5, h: 0.7, fontSize: 13.5, bold: true, color: WHITE, lineSpacingMultiple: 1.1, fontFace: F, margin: 0, valign: "top" });
      s.addText(it[1], { x: cx + 0.45, y: 5.85, w: 3.5, h: 0.7, fontSize: 11, color: "BCC8F5", lineSpacingMultiple: 1.15, fontFace: F, margin: 0, valign: "top" });
    });
    s.addText([
      { text: "→ ", options: { color: "9DB2FF", bold: true } },
      { text: "이 역량은 GMP 환경의 공정능력(PPQ)·일탈관리·밸리데이션으로 그대로 전이됩니다", options: { color: WHITE, bold: true } },
    ], { x: 0.7, y: 6.62, w: 11.95, h: 0.4, fontSize: 13, fontFace: F, margin: 0 });
    s.addText("github.com/robinho0329/chungbuk-air-quality-monitor   ·   라이브 대시보드 6페이지 운영 중", { x: 0.7, y: 7.05, w: 12, h: 0.35, fontSize: 11, color: "7E93D6", fontFace: F, margin: 0 });
  }

  // ───────────────────────── APPENDIX 예상 질문 & 대응
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    spine(s);
    header(s, "예상 질문 & 대응", "Appendix — 면접 Q&A 핵심");
    const rows = [
      [{ text: "예상 질문", options: { fill: { color: COBALT }, color: WHITE, bold: true, align: "center", valign: "middle" } },
       { text: "대응 요지", options: { fill: { color: COBALT }, color: WHITE, bold: true, align: "center", valign: "middle" } }],
      ["왜 제조 데이터가 아니라 대기질인가?", "공정과 통계 구조가 같은 ‘실시간 실데이터’라 일부러 선택. 더미는 SPC가 잡아야 할 결측·이상·드리프트가 사라져 무의미."],
      ["대기질은 통제 불가인데 Improve는?", "공정 조작 불가가 한계. Improve를 ‘방법론 개선(잔차 보정 거짓경보 44%→2%)’ + alert/action 정책으로 매핑."],
      ["효과크기가 작은데(d≈0.2~0.3) 의미 있나?", "표본 1만이라 유의는 당연. 그래서 효과크기·η²로 ‘실질 차이는 작다’를 정직히 보고 — 통계적 유의 ≠ 실질적 중요."],
      ["자기상관이 왜 그렇게 중요한가?", "lag-1 ACF 0.93 → 유효표본 n_eff≈75로 명목 n의 1/27. p값이 과대평가됨. 잔차 관리도로 보정해 신호를 분리."],
      ["위치 차이가 작으면 결론은 뭔가?", "산포의 출처를 시간·기상(공통원인)으로 분리 → ‘라인별 관리’가 아니라 ‘공통원인 관리’가 답이라는 진단."],
    ];
    s.addTable(rows, {
      x: 0.7, y: 1.7, w: 11.95, colW: [4.2, 7.75],
      rowH: [0.45, 0.92, 0.92, 0.92, 0.92, 0.92],
      fontSize: 12, fontFace: F, color: INK, valign: "middle",
      border: { type: "solid", color: BORDER, pt: 1 }, align: "left",
    });
  }

  await pres.writeFile({ fileName: "포트폴리오_충북대기질_SPC_v2.pptx" });
  console.log("✅ 생성 완료: 포트폴리오_충북대기질_SPC_v2.pptx (17 슬라이드)");
}

build().catch((e) => { console.error(e); process.exit(1); });
