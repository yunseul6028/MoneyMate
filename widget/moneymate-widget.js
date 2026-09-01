// ===== MoneyMate 위젯 (Scriptable 용) =====
// 사용법:
//  1) 앱스토어에서 "Scriptable"(무료) 설치
//  2) Scriptable 열고 + → 이 코드 전체 붙여넣기 → 이름 저장(예: MoneyMate)
//  3) 홈화면 길게 눌러 위젯 추가 → Scriptable → 이 스크립트 선택
//  ※ 잠금화면 위젯도 같은 방식(Scriptable 지원 크기: 작게/중간 권장)

const API = "https://moneymate-buddy.vercel.app/api/widget";

// 친근한 금액 표기 (백엔드 friendly_won 과 동일 규칙, 폴백용)
function won(n) {
  if (n == null) return "—";
  const sign = n < 0 ? "-" : "";
  const v = Math.abs(Math.round(n));
  if (v < 10000) return `${sign}${v.toLocaleString()}원`;
  if (v < 100000) {
    const r = Math.round(v / 1000) * 1000;
    const man = Math.floor(r / 10000);
    const cheon = Math.floor((r % 10000) / 1000);
    return `${sign}${man}만${cheon ? ` ${cheon}천` : ""}원`;
  }
  return `${sign}${Math.round(v / 10000)}만원`;
}

async function loadData() {
  try {
    const req = new Request(API);
    req.timeoutInterval = 10;
    return await req.loadJSON();
  } catch (e) {
    return null;
  }
}

const data = await loadData();
const w = new ListWidget();

// 배경: 브랜드 보라 그라데이션
const g = new LinearGradient();
g.colors = [new Color("#6c5ce7"), new Color("#a29bfe")];
g.locations = [0, 1];
w.backgroundGradient = g;
w.setPadding(16, 16, 16, 16);

if (!data) {
  const t = w.addText("💸 MoneyMate\n연결 실패 😢\n잠시 후 다시");
  t.textColor = Color.white();
  t.font = Font.mediumSystemFont(14);
} else {
  const head = w.addText("💸 MoneyMate");
  head.textColor = new Color("#ffffff", 0.85);
  head.font = Font.semiboldSystemFont(12);

  w.addSpacer(6);

  const label = w.addText("오늘 쓸 수 있는 돈");
  label.textColor = new Color("#ffffff", 0.8);
  label.font = Font.mediumSystemFont(11);

  const big = w.addText(data.today_left_str || won(data.today_left));
  big.textColor = Color.white();
  big.font = Font.boldSystemFont(30);
  big.minimumScaleFactor = 0.7;

  w.addSpacer(4);

  const sub = w.addText(
    `이번 달 남은 돈 ${data.month_left_str || won(data.month_left)} · ${data.days_left}일`
  );
  sub.textColor = new Color("#ffffff", 0.85);
  sub.font = Font.systemFont(11);
  sub.minimumScaleFactor = 0.7;

  w.addSpacer(8);

  const line = w.addText(data.line || "");
  line.textColor = Color.white();
  line.font = Font.mediumSystemFont(12);
  line.minimumScaleFactor = 0.8;
}

// 약 15분마다 갱신 시도 (iOS가 실제 주기는 조절함)
w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);

if (config.runsInWidget) {
  Script.setWidget(w);
} else {
  // 앱에서 직접 실행 시 미리보기
  w.presentMedium();
}
Script.complete();
