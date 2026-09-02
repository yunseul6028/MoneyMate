"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  decideHold,
  getDashboard,
  getHolds,
  getTransactions,
  won,
  type Dashboard,
  type HoldsResp,
  type TxList,
} from "@/lib/api";

export default function DashboardView({ refreshKey = 0 }: { refreshKey?: number }) {
  const [d, setD] = useState<Dashboard | null>(null);
  const [err, setErr] = useState(false);
  const [showDetail, setShowDetail] = useState(false);
  const [holds, setHolds] = useState<HoldsResp | null>(null);

  const loadHolds = () => getHolds().then(setHolds).catch(() => {});

  useEffect(() => {
    getDashboard().then(setD).catch(() => setErr(true));
    loadHolds();
  }, [refreshKey]);

  async function decide(id: number, decision: "bought" | "dropped") {
    try {
      await decideHold(id, decision);
    } catch {}
    loadHolds();
  }

  return (
    <>
      {/* 헤더 (상단 고정) */}
      <div
        className="sticky top-0 z-30 bg-gradient-to-br from-brand to-brand2 text-white px-5 pb-7 rounded-b-[22px] shadow-sm"
        style={{ paddingTop: "max(1.25rem, env(safe-area-inset-top))" }}
      >
        <div className="flex justify-between items-baseline">
          <h1 className="text-xl font-extrabold tracking-tight">MoneyMate 💸</h1>
          <span className="text-xs opacity-80">{d?.today ?? "—"}</span>
        </div>
        <div className="flex justify-between items-center mt-2.5 gap-2">
          <p className="text-[13px] opacity-95">
            {d ? `${d.user}야, 오늘도 내가 지켜보고 있어 👀` : "불러오는 중…"}
          </p>
          <Link
            href="/widget"
            className="shrink-0 text-[12px] font-bold bg-white/20 rounded-full px-3 py-1 whitespace-nowrap"
          >
            📱 위젯
          </Link>
        </div>
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
            <div className="flex items-start justify-between">
              <div className="text-[30px] font-extrabold tracking-tight">
                {won(d.month_expense)}
                <span className="text-sm font-semibold text-muted ml-1">
                  이번 달 지출
                </span>
              </div>
              <button
                onClick={() => setShowDetail(true)}
                className="mt-1.5 shrink-0 text-[12px] font-bold text-brand bg-[#efeafe] rounded-full px-3 py-1.5"
              >
                자세히 보기 ›
              </button>
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

      {/* 고민함 (충동구매 유예) */}
      {holds && (holds.items.length > 0 || holds.saved_total > 0) && (
        <div className="mx-3.5 mt-3 rounded-2xl bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2.5">
            <h2 className="text-[13px] text-muted font-bold">🤔 고민 중</h2>
            {holds.saved_total > 0 && (
              <span className="text-[12px] font-bold text-brand">
                이번 달 아낀 돈 {won(holds.saved_total)}
              </span>
            )}
          </div>

          {holds.items.length === 0 ? (
            <p className="text-[13px] text-muted">지금 재워둔 지출은 없어. 잘 참았어 💪</p>
          ) : (
            <div className="flex flex-col gap-2.5">
              {holds.items.map((h) => (
                <div key={h.id} className="border border-line rounded-xl p-3">
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="font-bold text-sm truncate">{h.item}</div>
                    <div className="font-extrabold tabular-nums shrink-0">{won(h.amount)}</div>
                  </div>
                  <div className="text-[11px] text-muted mt-0.5">
                    {h.elapsed} 고민 중 · {h.due ? "이제 결정할 시간 ⏰" : `${h.remaining} 다시 알림`}
                  </div>
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => decide(h.id, "dropped")}
                      className="flex-1 bg-brand text-white text-[12px] font-bold rounded-lg py-1.5"
                    >
                      접을래 (아낀다) 💪
                    </button>
                    <button
                      onClick={() => decide(h.id, "bought")}
                      className="flex-1 bg-white border border-line text-[12px] font-bold rounded-lg py-1.5"
                    >
                      샀어
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {showDetail && <TxDetailModal onClose={() => setShowDetail(false)} />}
    </>
  );
}

function TxDetailModal({ onClose }: { onClose: () => void }) {
  const [data, setData] = useState<TxList | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    getTransactions().then(setData).catch(() => setErr(true));
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-end justify-center"
      onClick={onClose}
    >
      <div
        className="w-full max-w-phone bg-white rounded-t-2xl flex flex-col max-h-[85dvh]"
        style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 pt-4 pb-2 shrink-0">
          <div>
            <div className="text-[15px] font-extrabold">이번 달 지출 내역</div>
            <div className="text-[12px] text-muted mt-0.5">
              {data ? `${data.count}건 · 합계 ${won(data.total)}` : "불러오는 중…"}
            </div>
          </div>
          <button onClick={onClose} className="text-muted text-xl px-2 -mr-2 leading-none">
            ✕
          </button>
        </div>

        <div className="overflow-y-auto no-scrollbar px-2 pb-2">
          {err ? (
            <p className="text-sm text-warn px-2 py-8 text-center">내역을 불러오지 못했어.</p>
          ) : !data ? (
            <p className="text-sm text-muted px-2 py-8 text-center">불러오는 중…</p>
          ) : data.items.length === 0 ? (
            <p className="text-sm text-muted px-2 py-8 text-center">이번 달 지출 내역이 아직 없어.</p>
          ) : (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-[11px] text-muted text-left border-b border-line">
                  <th className="font-semibold py-2 pl-2 w-12">날짜</th>
                  <th className="font-semibold py-2">내용</th>
                  <th className="font-semibold py-2 w-14">분류</th>
                  <th className="font-semibold py-2 pr-2 text-right w-20">금액</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((t) => {
                  const [, mm, dd] = t.date.split("-");
                  return (
                    <tr key={t.id} className="border-b border-[#f2f2f6]">
                      <td className="py-2 pl-2 text-muted tabular-nums whitespace-nowrap">
                        {Number(mm)}/{Number(dd)}
                      </td>
                      <td className="py-2 pr-2 font-semibold truncate max-w-0">{t.merchant}</td>
                      <td className="py-2 text-muted whitespace-nowrap">{t.category}</td>
                      <td className="py-2 pr-2 text-right font-bold tabular-nums whitespace-nowrap">
                        {won(t.amount)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
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
