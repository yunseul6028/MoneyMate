"use client";

import { useEffect, useRef, useState } from "react";
import {
  categorizePurchase,
  categorizeTransfer,
  getCategories,
  getProactive,
  getTransfers,
  getUnresolvedPurchases,
  resolvePerson,
  sendChat,
  won,
  type PurchaseTx,
  type TransferTx,
} from "@/lib/api";

type Action =
  | { kind: "transfer"; tx: TransferTx; mode: "ask" | "pick" }
  | { kind: "purchase"; purchase: PurchaseTx };
type Msg = { who: "ai" | "user"; text: string; tag?: string; action?: Action };

const QUICK = [
  "20만원짜리 기타 사도 될까?",
  "이번 달 왜 이렇게 많이 썼지?",
  "다음 카드값 얼마 나와?",
  "구독 뭐뭐 있어?",
];

const tagFor = (kind: string): string | undefined =>
  kind === "coach" ? "맥락 이해 완료" : kind === "simulation" ? "가상 시뮬레이션" : undefined;

export default function Chat({
  onResolved,
  pokeKey = 0,
}: {
  onResolved?: () => void;
  pokeKey?: number;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [cats, setCats] = useState<string[]>([]);
  const queue = useRef<TransferTx[]>([]);       // 개별 거래 큐
  const resolved = useRef<Set<string>>(new Set()); // 이번 세션에 이미 정리한 사람
  const seenIds = useRef<Set<number>>(new Set()); // 이미 큐에 넣은 거래
  const pendingAsk = useRef(false);             // 현재 질문 대기 중인지
  const pQueue = useRef<PurchaseTx[]>([]);      // '기타' 카드결제 질문 큐 (송금 다음 차례)
  const seenMerch = useRef<Set<string>>(new Set());   // 이미 큐에 넣은 가맹점
  const resolvedMerch = useRef<Set<string>>(new Set()); // 이번 세션에 이미 정리한 가맹점
  const endRef = useRef<HTMLDivElement>(null);
  const didInit = useRef(false);
  const composing = useRef(false); // 한글 IME 조합 중 여부

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
        if (t.queue.length) {
          const people = new Set(t.queue.map((x) => x.person)).size;
          push({ who: "ai", text: `아 맞다, 처음 보는 송금이 좀 있던데(${people}명) 하나씩만 확인해도 돼? 🙏` });
          queueTransfers(t.queue);
        }
      } catch {}
      // 규칙/AI 로도 못 정한 '기타' 카드결제도 하나씩 물어봄 (송금 다음 차례)
      try {
        const pr = await getUnresolvedPurchases();
        if (pr.queue.length) queuePurchases(pr.queue);
      } catch {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 테스트 이벤트(poke) → AI가 방금 발생한 상황에 반응 + 새 송금 있으면 이어서 확인
  useEffect(() => {
    if (pokeKey === 0) return; // 최초 마운트는 위 init 이 처리
    (async () => {
      setBusy(true);
      try {
        const r = await getProactive();
        if (r.should_speak) push({ who: "ai", text: r.message, tag: "방금 이벤트 반응" });
      } catch {}
      setBusy(false);
      try {
        const t = await getTransfers();
        queueTransfers(t.queue);
      } catch {}
      try {
        const pr = await getUnresolvedPurchases();
        queuePurchases(pr.queue);
      } catch {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pokeKey]);

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
    return `${when}에 ${body}네. 이거 친구랑 정산한 거야? 🤔`;
  }

  function askNext() {
    let tx = queue.current.shift();
    while (tx && resolved.current.has(tx.person)) tx = queue.current.shift(); // 이미 정리한 사람 건너뜀
    if (tx) {
      pendingAsk.current = true;
      push({ who: "ai", text: txLine(tx), action: { kind: "transfer", tx, mode: "ask" } });
      return;
    }
    // 사람 송금 다 끝났으면 → '기타' 카드결제 질문 차례
    askNextPurchase();
  }

  function purchaseLine(p: PurchaseTx): string {
    const [, mm, dd] = p.date.split("-");
    const when = `${Number(mm)}/${Number(dd)}`;
    const many = p.count > 1 ? ` (여기서 그동안 총 ${p.count}건 ${won(p.total)})` : "";
    return `${when}에 '${p.merchant}'에서 ${won(p.amount)} 썼는데${many}, 여긴 아직 분류가 안 됐어. 어디에 넣을까? 🧐`;
  }

  function askNextPurchase() {
    let p = pQueue.current.shift();
    while (p && resolvedMerch.current.has(p.merchant)) p = pQueue.current.shift(); // 이미 정리한 가맹점 건너뜀
    if (!p) {
      if (pendingAsk.current)
        push({ who: "ai", text: "좋아, 이제 다 정리했다! 앞으로 알아서 분류해둘게 👍" });
      pendingAsk.current = false;
      return;
    }
    pendingAsk.current = true;
    push({ who: "ai", text: purchaseLine(p), action: { kind: "purchase", purchase: p } });
  }

  // 새 '기타' 카드결제를 큐에 넣고, 대기 중 질문이 없으면 물어보기 시작
  function queuePurchases(list: PurchaseTx[]) {
    let added = 0;
    for (const p of list) {
      if (seenMerch.current.has(p.merchant)) continue;
      seenMerch.current.add(p.merchant);
      if (resolvedMerch.current.has(p.merchant)) continue;
      pQueue.current.push(p);
      added++;
    }
    if (added && !pendingAsk.current) askNextPurchase();
  }

  // '기타' 카드결제를 사용자가 고른 카테고리로 확정 → 개인화 학습 + 같은 가맹점 전부 반영
  async function onPickPurchase(idx: number, p: PurchaseTx, cat: string) {
    clearAction(idx);
    push({ who: "user", text: cat });
    resolvedMerch.current.add(p.merchant);
    setBusy(true);
    try {
      await categorizePurchase(p.merchant, cat);
      onResolved?.();
    } catch {}
    setBusy(false);
    push({ who: "ai", text: `오케이! '${p.merchant}'는 앞으로 ${cat}로 분류할게 👍` });
    askNext();
  }

  // 새 송금 거래를 큐에 넣고, 대기 중인 질문이 없으면 물어보기 시작
  function queueTransfers(list: TransferTx[]) {
    let added = 0;
    for (const tx of list) {
      if (seenIds.current.has(tx.id)) continue;
      seenIds.current.add(tx.id);
      if (resolved.current.has(tx.person)) continue;
      queue.current.push(tx);
      added++;
    }
    if (added && !pendingAsk.current) askNext();
  }

  async function onFriend(idx: number, tx: TransferTx) {
    clearAction(idx);
    push({ who: "user", text: "응, 친구랑 정산한 거야" });
    resolved.current.add(tx.person);
    setBusy(true);
    try {
      await resolvePerson(tx.person, "friend", "식음료");
      onResolved?.();
    } catch {}
    setBusy(false);
    push({ who: "ai", text: `오케이! ${tx.person}랑은 식음료로 정리해둘게 🍚` });
    askNext();
  }

  function onNotFriend(idx: number, tx: TransferTx) {
    clearAction(idx);
    push({ who: "user", text: "아니, 다른 거야" });
    push({ who: "ai", text: "그렇구나! 그럼 이건 어디에 넣을까?", action: { kind: "transfer", tx, mode: "pick" } });
  }

  // 일회성: 이 건만 분류하고 사람은 기억하지 않음 (친구 정산만 기억)
  async function onPick(idx: number, tx: TransferTx, cat: string) {
    clearAction(idx);
    push({ who: "user", text: cat });
    setBusy(true);
    try {
      await categorizeTransfer(tx.id, cat);
      onResolved?.();
    } catch {}
    setBusy(false);
    push({ who: "ai", text: `알겠어, 이번 건은 '${cat}'에 넣어둘게 👍` });
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
        {msgs.map((m, i) => {
          const act = m.action; // const 로 잡아야 아래 onClick 클로저까지 타입 좁혀짐
          return (
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

            {act?.kind === "transfer" && act.mode === "ask" && (
              <div className="flex gap-2">
                <button
                  disabled={busy}
                  onClick={() => onFriend(i, act.tx)}
                  className="flex-1 bg-brand text-white text-[13px] font-bold rounded-xl py-2 disabled:opacity-50"
                >
                  응, 친구랑 정산 🤝
                </button>
                <button
                  disabled={busy}
                  onClick={() => onNotFriend(i, act.tx)}
                  className="flex-1 bg-white border border-line text-[13px] font-bold rounded-xl py-2 disabled:opacity-50"
                >
                  아니, 다른 거야
                </button>
              </div>
            )}
            {act?.kind === "transfer" && act.mode === "pick" && (
              <div className="flex flex-wrap gap-1.5">
                {cats.map((c) => (
                  <button
                    key={c}
                    disabled={busy}
                    onClick={() => onPick(i, act.tx, c)}
                    className="text-[12px] font-semibold border border-line rounded-lg px-2.5 py-1.5 bg-white disabled:opacity-50"
                  >
                    {c}
                  </button>
                ))}
              </div>
            )}
            {act?.kind === "purchase" && (
              <div className="flex flex-wrap gap-1.5">
                {cats.map((c) => (
                  <button
                    key={c}
                    disabled={busy}
                    onClick={() => onPickPurchase(i, act.purchase, c)}
                    className="text-[12px] font-semibold border border-line rounded-lg px-2.5 py-1.5 bg-white disabled:opacity-50"
                  >
                    {c}
                  </button>
                ))}
              </div>
            )}
          </div>
          );
        })}
        {busy && (
          <div className="self-start text-muted text-[13px] px-2.5 py-1.5">
            MoneyMate가 입력 중…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* 하단 고정 바 (빠른질문 + 입력) */}
      <div className="sticky bottom-0 z-30 bg-[#f4f4f7]">
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

        <div className="pt-2 pb-4 flex gap-2 border-t border-line">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onCompositionStart={() => (composing.current = true)}
          onCompositionEnd={() => (composing.current = false)}
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            // 한글 IME 조합 중 Enter는 '글자 확정'이지 '전송'이 아님 → 3중 가드로 무시
            if (e.nativeEvent.isComposing || composing.current || e.keyCode === 229) return;
            e.preventDefault();
            send(input);
          }}
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
    </div>
  );
}
