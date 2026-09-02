"""텔레그램 봇 — 기존 분석·시뮬·정산·고민함 로직을 '대화'로 제공.

서버리스 웹훅 방식(long-polling X). httpx 로 Bot API 를 직접 호출한다.
MVP: 모든 사용자가 데모 사용자 데이터를 공유(합성 데이터 데모).
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
from server.db.models import TelegramSubscriber, User
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
    "가계부 안 써도, 내가 소비 보고 있다가 필요할 때 먼저 말 걸어줄게.\n\n"
    "이렇게 해봐:\n"
    "· <b>20만원 기타 사도 될까?</b> — 지갑 사정 계산해서 답해줄게\n"
    "· 아래 버튼으로 <b>남은 돈</b>·<b>고민함</b>도 바로 볼 수 있어"
)

_MENU = {
    "keyboard": [["💰 남은 돈", "🤔 고민함"], ["📊 이번 달"]],
    "resize_keyboard": True,
}


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
    except Exception as e:  # 네트워크 실패해도 웹훅은 200 반환
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


# ---------------------------------------------------------------- helpers
def _demo_uid(session: Session) -> int:
    u = session.query(User).order_by(User.id.asc()).first()
    return u.id if u else 1


def _register(session: Session, chat_id, name) -> None:
    cid = str(chat_id)
    if not session.query(TelegramSubscriber).filter(TelegramSubscriber.chat_id == cid).first():
        session.add(TelegramSubscriber(chat_id=cid, name=name))
        session.flush()


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


def _handle_text(session, chat_id, text) -> None:
    uid = _demo_uid(session)

    if text.startswith("/start"):
        send_message(chat_id, WELCOME, keyboard=_MENU)
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

    # 구매 질문 → 시뮬레이션 (+ 큰 금액이면 재워두기 버튼)
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

    # 맥락 설명 → 코치
    tokens = infer_ack_tokens(text)
    if tokens:
        res = decide(session, uid, report, acknowledged=tokens, now=clock.now())
        if res.should_speak:
            send_message(chat_id, speak(llm, res, report))
            return

    # 일반 질문
    send_message(chat_id, chat_answer(llm, report, text))


def _handle_callback(session, cb) -> None:
    data = cb.get("data", "")
    chat_id = cb["message"]["chat"]["id"]
    cb_id = cb["id"]
    uid = _demo_uid(session)

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
        _handle_callback(session, update["callback_query"])
        return
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if chat_id is None:
        return
    _register(session, chat_id, chat.get("first_name"))
    text = (msg.get("text") or "").strip()
    if text:
        _handle_text(session, chat_id, text)


def nudge_all(session: Session) -> int:
    """먼저 말 걸기 — proactive 판단 후 구독자 전원에게 push (Vercel Cron 용)."""
    uid = _demo_uid(session)
    report = analyze(session, uid, clock.today())
    res = decide(session, uid, report, acknowledged=set(), now=clock.now())
    if not res.should_speak:
        return 0
    msg = speak(get_llm(), res, report)
    subs = session.query(TelegramSubscriber).all()
    for sub in subs:
        send_message(sub.chat_id, f"👀 {msg}")
    return len(subs)
