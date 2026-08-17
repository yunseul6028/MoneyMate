# Vercel 배포 (단일 프로젝트)

Next.js 프론트 + FastAPI 백엔드가 **한 프로젝트**에 통합돼 있다.
`/api/*` 요청은 Next.js rewrite 로 같은 프로젝트의 **Python 서버리스 함수**(`api/index.py` → `server/`)가 처리한다 — 별도 백엔드 URL·CORS 없음.

```
frontend/  ← Vercel 프로젝트 루트
├─ app/ components/ lib/   Next.js
├─ api/index.py            Python 진입점 (from server.main import app)
├─ server/                 FastAPI 앱
├─ requirements.txt        Python 의존성
├─ next.config.mjs         /api → (배포) /api 함수 / (로컬) :8000 프록시
└─ vercel.json 없음        Vercel 이 Next.js + api/*.py 자동 감지
```

> 데이터: `server/data/demo_ledger.py`(실 은행내역 기반)는 git·배포 제외 → 배포엔 **합성 mock 데이터**로 뜬다(개인정보 없음).

## 대시보드로 배포 (권장)
Vercel → **Add New… → Project** → 저장소 `MoneyMate` import
- **Root Directory**: `frontend`
- **Framework**: Next.js (자동)
- Deploy → URL 하나로 프론트+API 다 동작

## CLI 로 배포
```bash
cd frontend
vercel deploy --prod --yes --scope <계정슬러그>
```

## 환경변수 (선택)
없어도 동작한다(LLM=mock, DB=/tmp 자동). **진짜 AI(Gemini)** 를 켜려면 프로젝트 **Settings → Environment Variables**:

| Key | Value |
|---|---|
| `LLM_PROVIDER` | `gemini` |
| `GEMINI_API_KEY` | (본인 키) |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` |

> 공개 데모면 아무나 써서 Gemini 쿼터가 소진될 수 있음 — 원치 않으면 `LLM_PROVIDER=mock` 유지.

## ⚠️ 서버리스 특성
- 백엔드가 서버리스 SQLite(`/tmp`)라 콜드스타트 때 초기화된다 → 정산 기억·테스트 이벤트 등 사용자 변경이 유지 안 될 수 있음(둘러보기 데모엔 충분).
- 상태 영속이 필요하면 Neon/Vercel Postgres 무료 티어 → `DATABASE_URL` 만 바꾸면 됨(SQLAlchemy).

## 로컬 실행
```bash
cd frontend
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
uvicorn server.main:app --port 8000    # 터미널 1
npm install && npm run dev             # 터미널 2 → http://localhost:3000
```
