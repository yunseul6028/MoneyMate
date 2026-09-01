# MoneyMate 💸

**🔗 [moneymate-buddy.vercel.app](https://moneymate-buddy.vercel.app)**

> 가계부를 쓰게 만드는 서비스가 아니라, **가계부를 쓰지 않아도 나를 챙겨주는 금융 친구**.

대학생을 위한 Proactive 금융 관리 AI. 사용자가 직접 기록하지 않아도 소비 패턴을 관찰하고,
정말 필요한 순간 AI가 **먼저 말을 건다.**

## 핵심 철학

- AI는 소비를 **통제·심판하지 않는다.** 상황을 설명하고 선택지를 준다. ("사지 마" ❌ → "고민할 시간을 줄게" ✅)
- **금융 계산은 코드가 (deterministic)**, 판단·맥락·대화는 LLM이 담당한다. 숫자를 LLM에게 계산시키지 않는다.
- 모든 거래마다 알림하지 않는다 — Risk/Critic Agent가 "정말 개입이 필요한가"를 먼저 검증한다.

## 주요 기능

**👀 먼저 말 거는 Proactive AI**
소비가 평소보다 튀면 AI가 먼저 말을 건다. 단, Risk/Critic Agent가 개입 가치를 검증한 뒤에만 — 잔소리하지 않는다.

**🏷️ 상호명 기반 자동 분류 + 학습**
카드 내역을 규칙 → AI(Gemini) → 개인화 순으로 분류. 사용자가 고치면 그 가맹점을 기억해 다음부터 자동 반영.

**🤖 '기타'로 남은 결제도 대화로 분류**
규칙·AI로도 애매한 지출은 챗봇이 하나씩 *"이거 어디에 넣을까?"* 물어보고, 답하면 학습한다. (간편결제처럼 상호명이 없는 케이스 대응)

**🤝 친구 정산 netting — 내가 낸 만큼만 내 지출로**
"내가 다 긁고 친구가 입금"하면 **내 몫만** 지출로 잡고, 받은 정산금은 소득으로 안 잡는다.
받은 정산은 *송금 ±3일 내에 그만한 지출이 있을 때만* 인정 → 무관한/옛날 입금 오차감 방지.

**🧪 가상 소비 시뮬레이션**
*"20만원 기타 사도 될까?"* → 실제 결제 없이 지갑 사정(예산·카드값·남은 기간)을 계산해 답한다.

**🤔 고민함 — 충동구매 유예 (cooling-off)**
큰 지출은 바로 사지 않고 **"하루 재워두기"** → 하루 뒤 AI가 다시 물어본다. 접으면 **'고민 끝에 아낀 돈'** 이 쌓인다. (행동경제학의 cooling-off / implementation intention)

**📊 이번 달 지출 자세히 보기**
숫자 옆 *자세히 보기* → 날짜·내용·분류·금액 표로 한눈에.

**📱 홈·잠금화면 위젯**
`/api/widget` + Scriptable 스크립트로 네이티브 앱 없이 홈화면에 *"오늘 쓸 수 있는 돈"* 위젯. 앱을 안 열어도 챙겨본다. → [`widget/moneymate-widget.js`](widget/moneymate-widget.js)

**💬 대화형 온보딩**
설정도 폼이 아니라 친구가 물어보듯 — 이름·이번 달 한도를 대화로 정한다.

## 아키텍처

```
Data Provider Layer (Mock ↔ Real 교체 지점)
      ↓
Classifier (rule → LLM fallback → 개인화 학습)
      ↓
Analysis Engine (순수 계산: 예산·카드값·정산 netting·주간 추세)
      ↓
Financial Analyst → Risk/Critic → Proactive Decision → Financial Coach(LLM)
      ↓
Chat + Tools / Simulation / 고민함 / Widget API
```

## 기술 스택

- **Frontend**: Next.js(App Router) + React + TypeScript + Tailwind CSS — 모바일 앱셸(헤더·입력바 고정, safe-area, 고무줄 바운스 제거)
- **Backend**: Python + FastAPI (분석·Agent·분류·정산·고민함)
- **DB**: SQLite(로컬) ↔ **Neon Postgres**(배포, 상태 영속) — `DATABASE_URL`만으로 전환
- **AI**: Pluggable LLM Provider(OpenAI 호환) — Gemini `gemini-flash-lite-latest`. 키 없어도 규칙기반 mock으로 전체 동작
- **Deploy**: Vercel 단일 프로젝트 (Next.js + Python 서버리스 함수)

## 구조 (단일 프로젝트)

Next.js 프론트 + FastAPI 백엔드가 **한 프로젝트(`frontend/`)** 에 통합돼 있다.
`/api/*` 는 Next.js rewrite 로 같은 프로젝트의 Python 서버리스 함수(`frontend/api/index.py` → `server/`)가 처리한다 — 별도 백엔드 URL·CORS 없음.

```
frontend/
├─ app/ components/ lib/   Next.js (UI · 앱셸 · API 클라이언트)
├─ api/index.py            Vercel Python 진입점 (server.main:app)
├─ server/                 FastAPI
│  ├─ services/            분석 · 분류 · 정산 · 고민함 · 대시보드
│  ├─ agents/              Analyst · Critic · Proactive · Coach
│  ├─ llm/ providers/      LLM 추상화 · 데이터 프로바이더
│  └─ data/                mock/데모 원장 · 가맹점 규칙
└─ requirements.txt
widget/moneymate-widget.js  홈화면 위젯(Scriptable)
```

## 빠른 시작 (모두 frontend/ 에서)

```bash
cd frontend
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                       # LLM 키는 .env 에 (없어도 mock 으로 동작)

# 터미널 1 — API (FastAPI)
uvicorn server.main:app --port 8000
# 터미널 2 — 웹 (Next.js). /api 는 :8000 으로 프록시됨
npm install && npm run dev                 # http://localhost:3000
```

**검증 스크립트** (LLM 키 없이도 실행 가능)

```bash
cd frontend && source .venv/bin/activate
python -m server.scripts.seed_and_check    # DB·데이터
python -m server.scripts.check_agent       # Proactive Agent
python -m server.scripts.check_coach       # LLM Coach
```

## 배포

Vercel 단일 프로젝트 + Neon Postgres(무료). 자세한 내용은 [DEPLOY.md](DEPLOY.md).
데이터가 없어도(LLM=mock, DB=임시) 그대로 뜨고, `DATABASE_URL`(또는 Vercel Storage의 `POSTGRES_URL`)을 붙이면 상태가 영속된다.
