"use client";

import { useState } from "react";
import { devEvent, devReset } from "@/lib/api";

const EVENTS = [
  { kind: "cafe", label: "☕ 카페 4,500" },
  { kind: "delivery", label: "🍔 배달 21,000" },
  { kind: "shopping", label: "🛍 큰 지출 12만" },
  { kind: "delivery_spike", label: "🔥 배달 폭증" },
  { kind: "friend_in", label: "💸 송금 받음" },
];

export default function TestPanel({ onEvent }: { onEvent: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      onEvent();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-dashed border-line bg-white/50 px-3 py-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between text-[12px] font-bold text-muted"
      >
        <span>🧪 테스트 이벤트 (목업)</span>
        <span>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {EVENTS.map((e) => (
            <button
              key={e.kind}
              disabled={busy}
              onClick={() => run(() => devEvent(e.kind))}
              className="text-[12px] font-semibold border border-line rounded-lg px-2.5 py-1.5 bg-white disabled:opacity-50"
            >
              {e.label}
            </button>
          ))}
          <button
            disabled={busy}
            onClick={() => run(devReset)}
            className="text-[12px] font-semibold border border-warn/50 text-warn rounded-lg px-2.5 py-1.5 bg-white disabled:opacity-50"
          >
            ↩️ 초기화
          </button>
        </div>
      )}
    </div>
  );
}
