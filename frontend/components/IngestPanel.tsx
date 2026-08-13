"use client";

import { useEffect, useState } from "react";
import {
  correctCategory,
  getCategories,
  ingest,
  won,
  type IngestItem,
} from "@/lib/api";

const PLACEHOLDER = `카드 내역을 붙여넣어봐 (한 줄에 하나)
예)
스타벅스 강남점 5,500
CU 편의점 8,500
올리브영 32000
동네국밥집 9000`;

const badgeColor: Record<string, string> = {
  rule: "bg-[#eef] text-[#5a5ac0]",
  user: "bg-[#e6f9f0] text-accent",
  llm: "bg-[#fdeede] text-[#c77b1e]",
  fallback: "bg-[#f0f0f4] text-muted",
};

export default function IngestPanel({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState<IngestItem[]>([]);
  const [cats, setCats] = useState<string[]>([]);

  useEffect(() => {
    if (open && cats.length === 0)
      getCategories().then((r) => setCats(r.expense)).catch(() => {});
  }, [open, cats.length]);

  async function run() {
    if (!text.trim() || busy) return;
    setBusy(true);
    try {
      const r = await ingest(text);
      setItems((prev) => [...r.items, ...prev]);
      setText("");
      onAdded();
    } catch {
      /* noop */
    } finally {
      setBusy(false);
    }
  }

  async function fix(id: number, category: string) {
    setItems((prev) =>
      prev.map((it) =>
        it.id === id ? { ...it, category, source: "user", source_label: "내 설정" } : it
      )
    );
    try {
      await correctCategory(id, category);
      onAdded();
    } catch {
      /* noop */
    }
  }

  return (
    <div className="rounded-2xl bg-white p-3.5 shadow-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between text-[13px] font-bold text-ink"
      >
        <span>＋ 카드 내역 추가하면 자동 분류돼</span>
        <span className="text-muted">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="mt-3 flex flex-col gap-2.5">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={PLACEHOLDER}
            rows={5}
            className="w-full border border-line rounded-xl px-3 py-2.5 text-[13px] outline-none focus:border-brand2 resize-none leading-relaxed"
          />
          <button
            onClick={run}
            disabled={busy || !text.trim()}
            className="bg-brand text-white rounded-xl py-2.5 text-sm font-bold disabled:opacity-50"
          >
            {busy ? "분류 중…" : "자동 분류하고 추가"}
          </button>

          {items.length > 0 && (
            <div className="flex flex-col gap-1.5 mt-1">
              {items.map((it) => (
                <div
                  key={it.id}
                  className="flex items-center gap-2 text-[13px] border border-line rounded-xl px-3 py-2"
                >
                  <div className="flex-1 truncate">
                    <span className="font-semibold">{it.merchant}</span>
                    <span className="text-muted ml-1.5">{won(it.amount)}</span>
                  </div>
                  <span
                    className={`text-[10px] font-bold rounded-md px-1.5 py-0.5 ${
                      badgeColor[it.source] ?? badgeColor.fallback
                    }`}
                  >
                    {it.source_label}
                  </span>
                  <select
                    value={it.category}
                    onChange={(e) => fix(it.id, e.target.value)}
                    className="text-[12px] font-semibold border border-line rounded-lg px-1.5 py-1 bg-white outline-none"
                  >
                    {cats.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
              <p className="text-[11px] text-muted mt-0.5 px-1">
                카테고리가 틀리면 바꿔줘 — 다음부터 같은 가맹점은 그렇게 기억할게 🧠
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
