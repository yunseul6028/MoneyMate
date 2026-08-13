"use client";

import { useEffect, useState } from "react";
import { getDashboard, won, type Dashboard } from "@/lib/api";

export default function DashboardView() {
  const [d, setD] = useState<Dashboard | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    getDashboard().then(setD).catch(() => setErr(true));
  }, []);

  return (
    <>
      {/* 헤더 */}
      <div className="bg-gradient-to-br from-brand to-brand2 text-white px-5 pt-5 pb-7 rounded-b-[22px]">
        <div className="flex justify-between items-baseline">
          <h1 className="text-xl font-extrabold tracking-tight">MoneyMate 💸</h1>
          <span className="text-xs opacity-80">{d?.today ?? "—"}</span>
        </div>
        <p className="mt-2.5 text-[13px] opacity-95">
          {d ? `${d.user}야, 오늘도 내가 지켜보고 있어 👀` : "불러오는 중…"}
        </p>
      </div>

      {/* 금융 상태 카드 */}
      <div className="mx-3.5 mt-3 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="text-[13px] text-muted font-bold mb-2.5">이번 달 금융 상태</h2>

        {err ? (
          <p className="text-sm text-warn">
            백엔드에 연결하지 못했어. 서버(:8000)가 켜져 있는지 확인해줘.
          </p>
        ) : !d ? (
          <p className="text-sm text-muted">불러오는 중…</p>
        ) : (
          <>
            <div className="text-[30px] font-extrabold tracking-tight">
              {won(d.month_expense)}
              <span className="text-sm font-semibold text-muted ml-1">
                이번 달 지출
              </span>
            </div>

            <div className="flex gap-2.5 mt-3">
              <Box k="남은 예산" v={won(d.remaining_budget)} />
              <Box k="다음 카드 결제" v={won(d.upcoming_card_bill)} warn />
            </div>

            <div className="flex flex-col gap-2.5 mt-3.5">
              {d.categories.slice(0, 5).map((c) => {
                const max = Math.max(...d.categories.map((x) => x.month_amount), 1);
                return (
                  <div key={c.category} className="flex items-center gap-2.5 text-[13px]">
                    <div className="w-16 font-semibold">{c.category}</div>
                    <div className="flex-1 h-2 bg-[#f0f0f6] rounded-md overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-brand to-brand2 rounded-md"
                        style={{ width: `${Math.round((c.month_amount / max) * 100)}%` }}
                      />
                    </div>
                    <div className="w-[78px] text-right font-bold tabular-nums">
                      {won(c.month_amount)}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-3 bg-[#f0eefe] rounded-xl px-3 py-2.5 text-[13px] font-semibold text-[#4b3fb0] flex gap-2 items-center">
              <span>🤖</span>
              <span>{d.one_liner}</span>
            </div>
          </>
        )}
      </div>
    </>
  );
}

function Box({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div className="flex-1 bg-[#fafaff] border border-line rounded-xl px-3 py-2.5">
      <div className="text-[11px] text-muted">{k}</div>
      <div className={`text-[15px] font-extrabold mt-0.5 ${warn ? "text-warn" : ""}`}>
        {v}
      </div>
    </div>
  );
}
