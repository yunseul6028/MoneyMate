"use client";

import { useEffect, useRef, useState } from "react";
import { updateProfile } from "@/lib/api";

const FEATURES = [
  { emoji: "👀", title: "먼저 말 걸어줘", desc: "소비가 확 늘면 내가 먼저 물어봐. 네가 앱을 안 열어도 돼." },
  { emoji: "🏷️", title: "알아서 정리해줘", desc: "카드 내역만 넣으면 식비·카페·쇼핑… 자동으로 분류해." },
  { emoji: "🧪", title: "사기 전에 물어봐", desc: '"이거 사도 돼?" 하면 지갑 사정을 계산해서 알려줄게.' },
];

const BUDGET_PRESETS = [40, 60, 80, 100];

type Msg = { who: "ai" | "user"; text: string };
type Phase = "name" | "budget" | "ready";

export default function Onboarding({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);

  // 대화형 기초 설정 상태
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [phase, setPhase] = useState<Phase>("name");
  const [name, setName] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [budgetMan, setBudgetMan] = useState(60);
  const [thinking, setThinking] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  // AI 메시지를 잠깐 '생각 중' 후 띄워서 대화 느낌
  const pushAI = (text: string, delay = 450) => {
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      setMsgs((m) => [...m, { who: "ai", text }]);
    }, delay);
  };

  // step 2(대화형 설정) 진입 시 첫 질문
  useEffect(() => {
    if (step === 2 && !started.current) {
      started.current = true;
      pushAI("좋아, 시작 전에 딱 두 개만 물어볼게 🙌\n먼저 — 널 뭐라고 부를까?", 300);
    }
  }, [step]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, thinking]);

  function submitName() {
    const n = nameInput.trim() || "친구";
    setName(n);
    setMsgs((m) => [...m, { who: "user", text: n }]);
    setPhase("budget");
    pushAI(
      `반가워 ${n}! 💜\n이번 달엔 얼마 정도 쓸 생각이야?\n이 금액에서 쓸 때마다 빼서, 지금 '남은 돈'을 딱 보여줄게 💳`
    );
  }

  function submitBudget() {
    setMsgs((m) => [...m, { who: "user", text: `${budgetMan}만원` }]);
    setPhase("ready");
    pushAI(`좋아! 이번 달은 ${budgetMan}만원으로 시작하자.\n남은 돈이 얼마인지 항상 보이게 해줄게 👀`);
  }

  async function finish() {
    setSaving(true);
    try {
      await updateProfile(name.trim() || "친구", budgetMan * 10_000);
    } catch {
      /* 실패해도 온보딩은 통과 (기본값 유지) */
    } finally {
      onDone();
    }
  }

  return (
    <main
      className="max-w-phone mx-auto h-[100dvh] flex flex-col overflow-hidden bg-gradient-to-br from-brand to-brand2 text-white"
      style={{ paddingTop: "max(1.5rem, env(safe-area-inset-top))" }}
    >
      {/* 진행 점 */}
      <div className="flex gap-1.5 justify-center pb-2 shrink-0">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`h-1.5 rounded-full transition-all ${
              i === step ? "w-6 bg-white" : "w-1.5 bg-white/40"
            }`}
          />
        ))}
      </div>

      {step < 2 ? (
        <>
          <div className="flex-1 min-h-0 overflow-y-auto flex flex-col justify-center px-7">
            {step === 0 && (
              <div className="text-center">
                <div className="text-[64px] mb-2">💸</div>
                <h1 className="text-3xl font-extrabold tracking-tight">MoneyMate</h1>
                <p className="mt-4 text-lg font-semibold leading-relaxed">
                  가계부, 안 써도 돼.
                  <br />
                  내가 알아서 챙겨줄게.
                </p>
                <p className="mt-3 text-sm text-white/80">
                  소비 잔소리 대신, 진짜 필요할 때만
                  <br />
                  먼저 말 걸어주는 금융 친구야.
                </p>
              </div>
            )}

            {step === 1 && (
              <div>
                <h2 className="text-2xl font-extrabold mb-6 leading-snug">
                  이런 걸 도와줄게 👇
                </h2>
                <div className="flex flex-col gap-4">
                  {FEATURES.map((f) => (
                    <div
                      key={f.title}
                      className="bg-white/15 backdrop-blur rounded-2xl p-4 flex gap-3.5 items-start"
                    >
                      <div className="text-[28px] leading-none">{f.emoji}</div>
                      <div>
                        <div className="font-extrabold">{f.title}</div>
                        <div className="text-[13px] text-white/85 mt-1 leading-relaxed">
                          {f.desc}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div
            className="px-7 shrink-0"
            style={{ paddingBottom: "max(2.5rem, env(safe-area-inset-bottom))" }}
          >
            <button
              onClick={() => setStep((s) => s + 1)}
              className="w-full bg-white text-brand font-extrabold rounded-2xl py-4 text-base"
            >
              다음
            </button>
            {step > 0 && (
              <button
                onClick={onDone}
                className="w-full text-white/70 text-sm font-semibold mt-3"
              >
                건너뛰기
              </button>
            )}
          </div>
        </>
      ) : (
        /* step 2 — 대화형 기초 설정 */
        <>
          <div className="flex-1 min-h-0 overflow-y-auto px-5 flex flex-col gap-2.5 pt-2">
            {msgs.map((m, i) => (
              <div
                key={i}
                className={
                  m.who === "ai"
                    ? "self-start max-w-[85%] bg-white/15 backdrop-blur rounded-2xl rounded-bl-[5px] px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap"
                    : "self-end max-w-[85%] bg-white text-brand font-bold rounded-2xl rounded-br-[5px] px-4 py-2.5 text-[15px]"
                }
              >
                {m.text}
              </div>
            ))}
            {thinking && (
              <div className="self-start bg-white/15 rounded-2xl rounded-bl-[5px] px-4 py-3 text-white/70 text-sm">
                …
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* phase 별 입력 */}
          <div
            className="px-5 pt-3 shrink-0"
            style={{ paddingBottom: "max(2rem, env(safe-area-inset-bottom))" }}
          >
            {phase === "name" && !thinking && (
              <div className="flex gap-2">
                <input
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      submitName();
                    }
                  }}
                  placeholder="예) 코니"
                  autoFocus
                  className="flex-1 rounded-full px-4 py-3 text-ink outline-none"
                />
                <button
                  onClick={submitName}
                  className="bg-white text-brand rounded-full px-5 font-extrabold"
                >
                  확인
                </button>
              </div>
            )}

            {phase === "budget" && !thinking && (
              <div>
                <div className="flex gap-2 mb-2.5">
                  {BUDGET_PRESETS.map((v) => (
                    <button
                      key={v}
                      onClick={() => setBudgetMan(v)}
                      className={`flex-1 rounded-xl py-2.5 text-sm font-bold transition ${
                        budgetMan === v ? "bg-white text-brand" : "bg-white/15 text-white"
                      }`}
                    >
                      {v}만원
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <div className="flex-1 flex items-center gap-2 bg-white rounded-full px-4 py-2.5 text-ink">
                    <input
                      type="number"
                      value={budgetMan}
                      onChange={(e) => setBudgetMan(Math.max(0, Number(e.target.value)))}
                      className="flex-1 w-full outline-none text-lg font-extrabold"
                    />
                    <span className="text-muted font-semibold">만원</span>
                  </div>
                  <button
                    onClick={submitBudget}
                    className="bg-white text-brand rounded-full px-5 font-extrabold"
                  >
                    확인
                  </button>
                </div>
              </div>
            )}

            {phase === "ready" && !thinking && (
              <button
                onClick={finish}
                disabled={saving}
                className="w-full bg-white text-brand font-extrabold rounded-2xl py-4 text-base disabled:opacity-60"
              >
                {saving ? "준비 중…" : "MoneyMate 시작하기 🚀"}
              </button>
            )}
          </div>
        </>
      )}
    </main>
  );
}
