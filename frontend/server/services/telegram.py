"""텔레그램 봇 — 기존 분석·시뮬·정산·고민함 로직을 '대화'로.

- 서버리스 웹훅(long-polling X). httpx 로 Bot API 직접 호출.
- 멀티유저: 각 텔레그램 사용자가 자기만의 User + 데모 원장(시드)을 가짐.
- 온보딩: 처음 시작하면 이름·예산을 대화로 물어봄.
- 말투 학습: 사용자의 최근 메시지를 저장해, 답변 톤을 그 사람처럼 미러링.
"""
from __future__ import annotations

import re

import httpx
from sqlalchemy.orm import Session

from server.agents.coach import speak
from server.agents.critic import infer_ack_tokens
from server.agents.proactive import decide
from server.core import clock
from server.core.format import friendly_won
from server.db.models import TelegramSubscriber, User, UserProfile
from server.llm.factory import get_llm
from server.services import holds as holds_svc
from server.services.analysis import analyze
from server.services.chat import chat_answer
from server.services.simulation import (
    is_purchase_question,
    parse_amount,
    simulate_and_explain,
)

WELCOME = (
    "안녕! 나 <b>MoneyMate</b> 💸\n"
    "가계부 안 써도, 내가 소비 보고 있다가 필요할 때 먼저 말 걸어줄게."
)

_MENU = {
    "keyboard": [["💰 남은 돈", "🤔 고민함"], ["📊 이번 달"]],
    "resize_keyboard": True,
}
_MENU_TEXTS = {"💰 남은 돈", "🤔 고민함", "📊 이번 달"}


# ---------------------------------------------------------------- Bot API
def _call(method: str, payload: dict) -> dict:
    from server.config import settings

    token = settings.telegram_bot_token
    if not token:
        return {"ok": False, "error": "no_token"}
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=15
        )
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_message(chat_id, text: str, buttons=None, keyboard=None) -> dict:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    elif keyboard:
        payload["reply_markup"] = keyboard
    return _call("sendMessage", payload)


def answer_callback(cb_id, text: str | None = None) -> dict:
    p = {"callback_query_id": cb_id}
    if text:
        p["text"] = text
    return _call("answerCallbackQuery", p)


def set_webhook(base_url: str) -> dict:
    from server.config import settings

    if not settings.telegram_bot_token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN 미설정"}
    url = f"{base_url}/api/telegram/webhook"
    payload = {"url": url, "allowed_updates": ["message", "callback_query"]}
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret
    res = _call("setWebhook", payload)
    res["webhook_url"] = url
    return res


# ---------------------------------------------------------------- 사용자/온보딩/말투
def _ensure_user(session: Session, chat_id, name_hint):
    """chat_id → 그 사용자 전용 구독자/User 확보. 처음이면 생성 + 데모 원장 시드."""
    from server.providers.mock_provider import MockFinancialDataProvider

    cid = str(chat_id)
    sub = session.query(TelegramSubscriber).filter(TelegramSubscriber.chat_id == cid).first()
    if sub is None:
        sub = TelegramSubscriber(chat_id=cid, name=name_hint, samples=[])
        session.add(sub)
        session.flush()
    if sub.user_id is None:
        u = User(name=(name_hint or "친구")[:80])
        session.add(u)
        session.flush()
        session.add(UserProfile(user_id=u.id, monthly_budget=600_000, card_billing_day=14))
        session.flush()
        try:
            MockFinancialDataProvider().sync_transactions(session, u.id)
        except Exception:
            pass
        sub.user_id = u.id
        sub.onb_step = "name"
        session.flush()
        return sub, True
    return sub, False


def _record_sample(sub, text: str) -> None:
    t = (text or "").strip()
    if not t or t.startswith("/") or len(t) > 200 or t in _MENU_TEXTS:
        return
    samples = list(sub.samples or [])
    samples.append(t)
    sub.samples = samples[-6:]  # 재할당해야 JSON 컬럼 변경 인식


def _style_hint(sub) -> str:
    samples = [s for s in (sub.samples or []) if s][-6:]
    if len(samples) < 2:
        return ""
    joined = "\n".join(f"- {s}" for s in samples)
    return (
        "[이 사용자의 평소 말투 — 아래 예시의 어투·어미·반말체·이모지 사용·문장 길이를 "
        "비슷하게 흉내 내서 답해. 마치 사용자가 스스로에게 혼잣말하듯 편하게. "
        "단, 내용과 숫자는 규칙대로 정확히 지켜.]\n" + joined
    )


def _parse_budget(text: str):
    a = parse_amount(text or "")
    if a:
        return a
    digits = re.sub(r"[^\d]", "", text or "")
    if digits:
        n = int(digits)
        return n * 10_000 if n < 10_000 else n  # "50"→50만원, "500000"→그대로
    return None


def _hold_item_label(msg: str, amount: int) -> str:
    s = re.sub(r"[\d,]+\s*만?\s*원?", "", msg)
    for w in ("사도 될까", "사도될까", "사도 돼", "사도돼", "살까", "사면", "구매", "사도", "?", "!"):
        s = s.replace(w, "")
    return s.strip(" ?.!~,") or "이 지출"


# ---------------------------------------------------------------- 응답
def _send_balance(session, chat_id, uid) -> None:
    r = analyze(session, uid, clock.today())
    days_left = max(1, r.days_in_month - r.days_elapsed + 1)
    month_left = max(0, round(r.remaining_budget))
    today_left = round(month_left / days_left) if month_left > 0 else 0
    send_message(
        chat_id,
        f"💰 <b>오늘 쓸 수 있는 돈</b>\n<b>{friendly_won(today_left)}</b>\n\n"
        f"이번 달 남은 돈 {friendly_won(month_left)} · {days_left}일 남음",
    )


def _send_month(session, chat_id, uid) -> None:
    r = analyze(session, uid, clock.today())
    cats = sorted(r.categories, key=lambda c: -c.month_amount)[:5]
    lines = "\n".join(f"· {c.category} {friendly_won(c.month_amount)}" for c in cats)
    send_message(
        chat_id,
        f"📊 <b>이번 달</b>\n지출 {friendly_won(r.month_expense)} · 남은 예산 "
        f"{friendly_won(r.remaining_budget)}\n\n{lines}",
    )


def _send_holds(session, chat_id, uid) -> None:
    data = holds_svc.list_holds(session, uid)
    if not data["items"] and data["saved_total"] == 0:
        send_message(chat_id, "지금 재워둔 지출은 없어. 잘 참고 있어 💪")
        return
    head = "🤔 <b>고민 중</b>"
    if data["saved_total"] > 0:
        head += f"\n이번 달 아낀 돈: <b>{friendly_won(data['saved_total'])}</b>"
    send_message(chat_id, head)
    for h in data["items"]:
        tail = "결정할 시간 ⏰" if h["due"] else f"{h['remaining']} 다시 알림"
        send_message(
            chat_id,
            f"• {h['item']} — <b>{friendly_won(h['amount'])}</b>\n{h['elapsed']} 고민 중 · {tail}",
            buttons=[[
                {"text": "접을래 (아낀다) 💪", "callback_data": f"drop|{h['id']}"},
                {"text": "샀어", "callback_data": f"bought|{h['id']}"},
            ]],
        )


def _handle_onboarding(session, sub, chat_id, text) -> None:
    if sub.onb_step == "name":
        name = (text or "").strip()[:80] or "친구"
        u = session.get(User, sub.user_id)
        if u:
            u.name = name
        sub.name = name
        sub.onb_step = "budget"
        session.flush()
        send_message(
            chat_id,
            f"반가워 {name}! 💜\n이번 달엔 얼마 정도 쓸 생각이야? 이 금액에서 쓸 때마다 빼서 "
            f"'남은 돈'을 보여줄게. (예: <b>50만원</b>)",
        )
        return
    # budget
    budget = _parse_budget(text)
    if not budget:
        send_message(chat_id, "숫자로 알려줄래? 예: <b>50만원</b> 또는 <b>500000</b>")
        return
    prof = session.query(UserProfile).filter(UserProfile.user_id == sub.user_id).first()
    if prof:
        prof.monthly_budget = budget
    sub.onb_step = "done"
    session.flush()
    nm = sub.name or "친구"
    send_message(
        chat_id,
        f"좋아 {nm}! 이번 달 {friendly_won(budget)}으로 시작하자 👀\n"
        f"아래 <b>💰 남은 돈</b>에서 지금 쓸 수 있는 돈 보고, "
        f"<b>'20만원 기타 사도 될까?'</b> 처럼 물어봐도 돼!",
        keyboard=_MENU,
    )


def _handle_text(session, uid, sub, chat_id, text) -> None:
    if text.startswith("/start"):
        send_message(chat_id, f"{WELCOME}\n\n뭐든 물어봐 😊", keyboard=_MENU)
        return
    if text in ("💰 남은 돈", "남은 돈", "/balance", "/남은돈"):
        _send_balance(session, chat_id, uid)
        return
    if text in ("🤔 고민함", "고민함", "/holds", "/고민함"):
        _send_holds(session, chat_id, uid)
        return
    if text in ("📊 이번 달", "이번 달", "/month", "/이번달"):
        _send_month(session, chat_id, uid)
        return

    llm = get_llm()
    report = analyze(session, uid, clock.today())

    if is_purchase_question(text):
        amount = parse_amount(text)
        if amount:
            res = simulate_and_explain(llm, report, amount, text)
            buttons = None
            if amount >= 50_000:
                item = _hold_item_label(text, amount)
                buttons = [[
                    {"text": "그래도 살래", "callback_data": "buy"},
                    {"text": "하루 재워둘래 😴", "callback_data": f"hold|{amount}|{item[:32]}"},
                ]]
            send_message(chat_id, res["reply"], buttons=buttons)
            return

    tokens = infer_ack_tokens(text)
    if tokens:
        res = decide(session, uid, report, acknowledged=tokens, now=clock.now())
        if res.should_speak:
            send_message(chat_id, speak(llm, res, report))
            return

    # 일반 질문 → 말투 미러링해서 답변
    send_message(chat_id, chat_answer(llm, report, text, style_hint=_style_hint(sub)))


def _handle_callback(session, uid, cb) -> None:
    data = cb.get("data", "")
    chat_id = cb["message"]["chat"]["id"]
    cb_id = cb["id"]

    if data == "buy":
        answer_callback(cb_id, "좋아!")
        send_message(chat_id, "그래, 진짜 필요한 거면 사야지 👍 잘 골라봐!")
    elif data.startswith("hold|"):
        _, amount, item = data.split("|", 2)
        holds_svc.add_hold(session, uid, item, int(amount))
        answer_callback(cb_id, "재워뒀어 😴")
        send_message(
            chat_id,
            f"좋아, '{item}'는 하루 재워둘게 😴 내일 다시 물어볼게 — 그때도 사고 싶으면 진짜인 거야 😎",
        )
    elif data.startswith("drop|") or data.startswith("bought|"):
        kind, hid = data.split("|", 1)
        decision = "dropped" if kind == "drop" else "bought"
        h = holds_svc.decide_hold(session, uid, int(hid), decision)
        if h and decision == "dropped":
            answer_callback(cb_id, "굳! 아꼈다 💪")
            send_message(chat_id, f"굳! <b>{friendly_won(h.amount)}</b> 아꼈다 💪 이번 달 아낀 돈에 쌓아둘게!")
        else:
            answer_callback(cb_id, "오케이!")
            send_message(chat_id, "그래, 잘 골랐길 🙏")
    else:
        answer_callback(cb_id)


def process_update(session: Session, update: dict) -> None:
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb.get("message", {}).get("chat", {}).get("id")
        if chat_id is None:
            return
        sub, _ = _ensure_user(session, chat_id, (cb.get("from") or {}).get("first_name"))
        _handle_callback(session, sub.user_id, cb)
        return

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if chat_id is None:
        return
    sub, created = _ensure_user(session, chat_id, chat.get("first_name"))
    text = (msg.get("text") or "").strip()

    if created:
        send_message(chat_id, f"{WELCOME}\n\n먼저 — 널 뭐라고 부를까? 😊")
        return
    if sub.onb_step and sub.onb_step != "done":
        _handle_onboarding(session, sub, chat_id, text)
        return
    if not text:
        return
    _record_sample(sub, text)  # 말투 학습
    _handle_text(session, sub.user_id, sub, chat_id, text)


def nudge_all(session: Session) -> int:
    """먼저 말 걸기 — 온보딩 끝난 사용자별로 proactive 판단 후 push."""
    sent = 0
    subs = (
        session.query(TelegramSubscriber)
        .filter(TelegramSubscriber.user_id.isnot(None), TelegramSubscriber.onb_step == "done")
        .all()
    )
    for sub in subs:
        report = analyze(session, sub.user_id, clock.today())
        res = decide(session, sub.user_id, report, acknowledged=set(), now=clock.now())
        if res.should_speak:
            send_message(sub.chat_id, f"👀 {speak(get_llm(), res, report)}")
            sent += 1
    return sent
