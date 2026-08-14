"use client";

import { useState } from "react";
import { updateProfile } from "@/lib/api";

const FEATURES = [
  { emoji: "👀", title: "먼저 말 걸어줘", desc: "소비가 확 늘면 내가 먼저 물어봐. 네가 앱을 안 열어도 돼." },
  { emoji: "🏷️", title: "알아서 정리해줘", desc: "카드 내역만 넣으면 식비·카페·쇼핑… 자동으로 분류해." },
  { emoji: "🧪", title: "사기 전에 물어봐", desc: '"이거 사도 돼?" 하면 지갑 사정을 계산해서 알려줄게.' },
];

const BUDGET_PRESETS = [40, 60, 80, 100];

export default function Onboarding({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [budgetMan, setBudgetMan] = useState(60); // 만원 단위
  const [saving, setSaving] = useState(false);

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
    <main className="max-w-phone mx-auto min-h-screen flex flex-col bg-gradient-to-br from-brand to-brand2 text-white">
      {/* 진행 점 */}
      <div className="flex gap-1.5 justify-center pt-6">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`h-1.5 rounded-full transition-all ${
              i === step ? "w-6 bg-white" : "w-1.5 bg-white/40"
            }`}
          />
        ))}
      </div>

      <div className="flex-1 flex flex-col justify-center px-7">
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

        {step === 2 && (
          <div>
            <h2 className="text-2xl font-extrabold mb-6 leading-snug">
              시작 전에 두 가지만! 🙌
            </h2>

            <label className="block text-sm font-bold mb-2">널 뭐라고 부를까?</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="예) 코니"
              className="w-full rounded-xl px-4 py-3 text-ink outline-none mb-6"
            />

            <label className="block text-sm font-bold mb-2">
              한 달 생활비, 얼마 정도 써?
            </label>
            <div className="flex gap-2 mb-3">
              {BUDGET_PRESETS.map((v) => (
                <button
                  key={v}
                  onClick={() => setBudgetMan(v)}
                  className={`flex-1 rounded-xl py-2.5 text-sm font-bold transition ${
                    budgetMan === v
                      ? "bg-white text-brand"
                      : "bg-white/15 text-white"
                  }`}
                >
                  {v}만원
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 bg-white rounded-xl px-4 py-3 text-ink">
              <input
                type="number"
                value={budgetMan}
                onChange={(e) => setBudgetMan(Math.max(0, Number(e.target.value)))}
                className="flex-1 outline-none text-lg font-extrabold"
              />
              <span className="text-muted font-semibold">만원</span>
            </div>
          </div>
        )}
      </div>

      {/* 하단 버튼 */}
      <div className="px-7 pb-10">
        {step < 2 ? (
          <button
            onClick={() => setStep((s) => s + 1)}
            className="w-full bg-white text-brand font-extrabold rounded-2xl py-4 text-base"
          >
            다음
          </button>
        ) : (
          <button
            onClick={finish}
            disabled={saving}
            className="w-full bg-white text-brand font-extrabold rounded-2xl py-4 text-base disabled:opacity-60"
          >
            {saving ? "준비 중…" : "MoneyMate 시작하기 🚀"}
          </button>
        )}
        {step > 0 && step < 2 && (
          <button
            onClick={onDone}
            className="w-full text-white/70 text-sm font-semibold mt-3"
          >
            건너뛰기
          </button>
        )}
      </div>
    </main>
  );
}
