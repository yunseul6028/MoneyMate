# MoneyMate 💸

> 가계부를 쓰게 만드는 서비스가 아니라, **가계부를 쓰지 않아도 나를 챙겨주는 금융 친구**.

대학생을 위한 Proactive 금융 관리 AI. 사용자가 직접 기록하지 않아도 소비 패턴을 관찰하고,
정말 필요한 순간 AI가 **먼저 말을 건다.**

## 핵심 철학

- AI는 소비를 **통제/심판하지 않는다**. 상황을 설명하고 선택지를 준다.
- **금융 계산은 코드가 (deterministic)**, 판단·맥락·대화는 LLM이 담당한다.
- 모든 거래마다 알림하지 않는다 — Risk/Critic Agent가 "정말 개입이 필요한가"를 검증한다.

## 아키텍처

```
Data Provider Layer (Mock ↔ Real 교체 지점)
      ↓
Classifier (rule-based → LLM fallback)
      ↓
Analysis Engine (순수 계산)
      ↓
Financial Analyst → Risk/Critic → Proactive Decision → Financial Coach(LLM)
      ↓
Chat + Tools / Simulation Engine
```

## 기술 스택

- Backend: Python + FastAPI
- DB: SQLite (MVP) → PostgreSQL / Supabase (호환 스키마)
- Frontend: Next.js + React + TypeScript + Tailwind (STEP 11~)
- AI: Pluggable LLM Provider (OpenAI 호환) + Mock 폴백 (키 없이도 전체 실행 가능)

## 개발 로드맵

- [x] STEP 1~4. 디렉토리 분석 · 아키텍처 · MVP 범위 정의
- [x] STEP 5. DB 스키마 설계
- [x] STEP 6. Mock transaction 데이터
- [x] STEP 7. 거래내역 자동 분류
- [ ] STEP 8. 소비 분석 엔진
- [ ] STEP 9. Proactive Risk Agent
- [ ] STEP 10. LLM Financial Coach
- [x] STEP 11. Chat UI (Next.js + FastAPI 프리뷰)
- [x] STEP 12. "먼저 말을 거는" UX (Proactive 메시지 + 맥락 이해)
- [ ] STEP 13. 가상 소비 시뮬레이션

## 빠른 시작

**백엔드** (FastAPI, :8000)
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # LLM 키는 .env 에 (없어도 mock 으로 동작)
uvicorn app.main:app --port 8000
```

**프론트엔드** (Next.js, :3000 — `/api` 는 :8000 으로 프록시)
```bash
cd frontend
npm install
npm run dev                   # http://localhost:3000
```

**검증 스크립트** (LLM 키 없이도 실행 가능)
```bash
cd backend && source .venv/bin/activate
python -m app.scripts.seed_and_check    # STEP 5~6
python -m app.scripts.check_analysis    # STEP 8
python -m app.scripts.check_agent       # STEP 9
python -m app.scripts.check_coach       # STEP 10 (LLM)
```
