"use client";

import { useEffect, useRef, useState } from "react";
import { getProactive, sendChat } from "@/lib/api";

type Msg = { who: "ai" | "user"; text: string; tag?: string };

const QUICK = [
  "20만원짜리 기타 사도 될까?",
  "이번 달 왜 이렇게 많이 썼지?",
  "시험기간이라 배달 많이 시켰어",
  "다음 카드값 얼마 나와?",
  "구독 뭐뭐 있어?",
];

const tagFor = (kind: string): string | undefined =>
  kind === "coach"
    ? "맥락 이해 완료"
    : kind === "simulation"
      ? "가상 시뮬레이션"
      : undefined;

export default function Chat() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // 최초 진입: AI가 먼저 말을 건다
  useEffect(() => {
    setBusy(true);
    getProactive()
      .then((r) =>
        setMsgs([
          r.should_speak
            ? { who: "ai", text: r.message, tag: "MoneyMate가 먼저 말을 걸었어요" }
            : {
                who: "ai",
                text: "오늘은 특별히 신경 쓸 건 없어 보여 👍 궁금한 거 있으면 물어봐!",
              },
        ])
      )
      .catch(() =>
        setMsgs([{ who: "ai", text: "연결에 문제가 있어. 서버가 켜져 있는지 확인해줘." }])
      )
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setMsgs((m) => [...m, { who: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const r = await sendChat(text);
      setMsgs((m) => [
        ...m,
        { who: "ai", text: r.reply, tag: tagFor(r.kind) },
      ]);
    } catch {
      setMsgs((m) => [...m, { who: "ai", text: "앗, 잠깐 문제가 생겼어. 다시 시도해줘." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col flex-1">
      <div className="text-[13px] text-muted font-bold px-1.5 pt-1.5 pb-0.5">
        💬 MoneyMate와의 대화
      </div>

      {/* 메시지 */}
      <div className="flex flex-col gap-2.5 px-1 pb-3 flex-1">
        {msgs.map((m, i) => (
          <div
            key={i}
            className={
              m.who === "ai"
                ? "self-start max-w-[82%] bg-white border border-line rounded-2xl rounded-bl-[5px] px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap"
                : "self-end max-w-[82%] bg-brand text-white rounded-2xl rounded-br-[5px] px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap"
            }
          >
            {m.tag && (
              <span className="inline-block text-[10px] font-extrabold text-brand bg-[#efeafe] rounded-md px-1.5 py-0.5 mb-1.5">
                {m.tag}
              </span>
            )}
            {m.text}
          </div>
        ))}
        {busy && (
          <div className="self-start text-muted text-[13px] px-2.5 py-1.5">
            MoneyMate가 입력 중…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* 빠른 질문 칩 */}
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

      {/* 입력 바 */}
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
