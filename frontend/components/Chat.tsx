"use client";

import { useEffect, useRef, useState } from "react";
import {
  getCategories,
  getProactive,
  getTransfers,
  resolvePerson,
  sendChat,
  won,
  type TransferTx,
} from "@/lib/api";

type Action = { tx: TransferTx; mode: "ask" | "pick" };
type Msg = { who: "ai" | "user"; text: string; tag?: string; action?: Action };

const QUICK = [
  "20만원짜리 기타 사도 될까?",
  "이번 달 왜 이렇게 많이 썼지?",
  "다음 카드값 얼마 나와?",
  "구독 뭐뭐 있어?",
];

const tagFor = (kind: string): string | undefined =>
  kind === "coach" ? "맥락 이해 완료" : kind === "simulation" ? "가상 시뮬레이션" : undefined;

export default function Chat({ onResolved }: { onResolved?: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [cats, setCats] = useState<string[]>([]);
  const queue = useRef<TransferTx[]>([]);       // 개별 거래 큐
  const resolved = useRef<Set<string>>(new Set()); // 이번 세션에 이미 정리한 사람
  const endRef = useRef<HTMLDivElement>(null);
  const didInit = useRef(false);

  const push = (m: Msg) => setMsgs((prev) => [...prev, m]);
  const clearAction = (idx: number) =>
    setMsgs((prev) => prev.map((m, i) => (i === idx ? { ...m, action: undefined } : m)));

  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    getCategories().then((r) => setCats(r.expense)).catch(() => {});
    (async () => {
      setBusy(true);
      try {
        const r = await getProactive();
        push(
          r.should_speak
            ? { who: "ai", text: r.message, tag: "MoneyMate가 먼저 말을 걸었어요" }
            : { who: "ai", text: "오늘은 특별히 신경 쓸 건 없어 👍 궁금한 거 있으면 물어봐!" }
        );
      } catch {
        push({ who: "ai", text: "연결에 문제가 있어. 서버가 켜져 있는지 확인해줘." });
      }
      setBusy(false);
      try {
        const t = await getTransfers();
        queue.current = t.queue;
        if (t.queue.length) {
          const people = new Set(t.queue.map((x) => x.person)).size;
          push({ who: "ai", text: `아 맞다, 처음 보는 송금이 좀 있던데(${people}명) 하나씩만 확인해도 돼? 🙏` });
          askNext();
        }
      } catch {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  function txLine(tx: TransferTx): string {
    const [, mm, dd] = tx.date.split("-");
    const when = `${Number(mm)}/${Number(dd)}`;
    const body =
      tx.direction === "out"
        ? `${tx.person}한테 ${won(tx.amount)} 보냈`
        : `${tx.person}한테서 ${won(tx.amount)} 받았`;
    return `${when}에 ${body}네. 이거 친구랑 N빵한 거야? 🤔`;
  }

  function askNext() {
    let tx = queue.current.shift();
    while (tx && resolved.current.has(tx.person)) tx = queue.current.shift(); // 이미 정리한 사람 건너뜀
    if (!tx) {
      push({ who: "ai", text: "좋아, 송금들 이제 다 정리했다! 앞으로 알아서 분류해둘게 👍" });
      return;
    }
    push({ who: "ai", text: txLine(tx), action: { tx, mode: "ask" } });
  }

  async function onFriend(idx: number, tx: TransferTx) {
    clearAction(idx);
    push({ who: "user", text: "응, 친구 N빵이야" });
    resolved.current.add(tx.person);
    setBusy(true);
    try {
      await resolvePerson(tx.person, "friend", "식음료");
      onResolved?.();
    } catch {}
    setBusy(false);
    push({ who: "ai", text: `오케이! ${tx.person}는 친구로 기억할게 🧠 이 사람 송금은 앞으로 식음료로 정리해둘게.` });
    askNext();
  }

  function onNotFriend(idx: number, tx: TransferTx) {
    clearAction(idx);
    push({ who: "user", text: "아니, 다른 거야" });
    push({ who: "ai", text: `그렇구나! 그럼 ${tx.person}랑 오간 건 어디에 넣을까?`, action: { tx, mode: "pick" } });
  }

  async function onPick(idx: number, tx: TransferTx, cat: string) {
    clearAction(idx);
    push({ who: "user", text: cat });
    resolved.current.add(tx.person);
    setBusy(true);
    try {
      await resolvePerson(tx.person, "other", cat);
      onResolved?.();
    } catch {}
    setBusy(false);
    push({ who: "ai", text: `알겠어, ${tx.person}는 '${cat}'로 기억할게 🧠` });
    askNext();
  }

  async function send(text: string) {
    if (!text.trim() || busy) return;
    push({ who: "user", text });
    setInput("");
    setBusy(true);
    try {
      const r = await sendChat(text);
      push({ who: "ai", text: r.reply, tag: tagFor(r.kind) });
    } catch {
      push({ who: "ai", text: "앗, 잠깐 문제가 생겼어. 다시 시도해줘." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col flex-1">
      <div className="text-[13px] text-muted font-bold px-1.5 pt-1.5 pb-0.5">
        💬 MoneyMate와의 대화
      </div>

      <div className="flex flex-col gap-2.5 px-1 pb-3 flex-1">
        {msgs.map((m, i) => (
          <div
            key={i}
            className={
              m.who === "ai"
                ? "self-start max-w-[86%] flex flex-col gap-2"
                : "self-end max-w-[82%] bg-brand text-white rounded-2xl rounded-br-[5px] px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap"
            }
          >
            {m.who === "ai" ? (
              <div className="bg-white border border-line rounded-2xl rounded-bl-[5px] px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap">
                {m.tag && (
                  <span className="inline-block text-[10px] font-extrabold text-brand bg-[#efeafe] rounded-md px-1.5 py-0.5 mb-1.5">
                    {m.tag}
                  </span>
                )}
                {m.text}
              </div>
            ) : (
              m.text
            )}

            {m.action?.mode === "ask" && (
              <div className="flex gap-2">
                <button
                  disabled={busy}
                  onClick={() => onFriend(i, m.action!.tx)}
                  className="flex-1 bg-brand text-white text-[13px] font-bold rounded-xl py-2 disabled:opacity-50"
                >
                  응, 친구 N빵 🍚
                </button>
                <button
                  disabled={busy}
                  onClick={() => onNotFriend(i, m.action!.tx)}
                  className="flex-1 bg-white border border-line text-[13px] font-bold rounded-xl py-2 disabled:opacity-50"
                >
                  아니, 다른 거야
                </button>
              </div>
            )}
            {m.action?.mode === "pick" && (
              <div className="flex flex-wrap gap-1.5">
                {cats.map((c) => (
                  <button
                    key={c}
                    disabled={busy}
                    onClick={() => onPick(i, m.action!.tx, c)}
                    className="text-[12px] font-semibold border border-line rounded-lg px-2.5 py-1.5 bg-white disabled:opacity-50"
                  >
                    {c}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && (
          <div className="self-start text-muted text-[13px] px-2.5 py-1.5">
            MoneyMate가 입력 중…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="flex gap-1.5 overflow-x-auto no-scrollbar px-1 py-1.5">
        {QUICK.map((q) => (
          <button
            key={q}
            onClick={() => send(q)}
            disabled={busy}
            className="whitespace-nowrap bg-white border border-line text-[#5a5a6e] text-xs font-semibold px-3 py-1.5 rounded-full disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>

      <div className="sticky bottom-0 bg-[#f4f4f7] pt-2 pb-4 flex gap-2 border-t border-line">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          placeholder="금융 관련 뭐든 물어봐…"
          className="flex-1 border border-line rounded-full px-4 py-3 text-sm outline-none bg-white focus:border-brand2"
        />
        <button
          onClick={() => send(input)}
          disabled={busy}
          className="bg-brand text-white rounded-full w-[46px] text-lg disabled:opacity-50"
        >
          ➤
        </button>
      </div>
    </div>
  );
}
