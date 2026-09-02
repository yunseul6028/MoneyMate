"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Widget = {
  today_left_str: string;
  month_left_str: string;
  days_left: number;
  line: string;
};

export default function WidgetPage() {
  const [w, setW] = useState<Widget | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch("/api/widget", { cache: "no-store" })
      .then((r) => r.json())
      .then(setW)
      .catch(() => {});
  }, []);

  async function copyCode() {
    try {
      const code = await fetch("/moneymate-widget.js").then((r) => r.text());
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  }

  return (
    <main
      className="max-w-phone mx-auto h-[100dvh] overflow-y-auto no-scrollbar bg-[#f4f4f7]"
      style={{
        paddingTop: "max(1rem, env(safe-area-inset-top))",
        paddingBottom: "max(1.5rem, env(safe-area-inset-bottom))",
      }}
    >
      <div className="px-4">
        <Link href="/" className="text-brand text-sm font-bold">
          ← 돌아가기
        </Link>
        <h1 className="text-xl font-extrabold mt-2">📱 위젯</h1>
        <p className="text-[13px] text-muted mt-1">
          앱을 안 열어도 홈화면에서 바로 챙겨봐요.
        </p>

        {/* 라이브 위젯 미리보기 (홈화면 Scriptable 위젯과 동일 디자인·데이터) */}
        <div
          className="mt-4 rounded-[22px] p-5 text-white shadow-sm"
          style={{ background: "linear-gradient(135deg,#6c5ce7,#a29bfe)" }}
        >
          <div className="text-[13px] font-bold opacity-85">💸 MoneyMate</div>
          <div className="text-[12px] opacity-80 mt-3">오늘 쓸 수 있는 돈</div>
          <div className="text-[34px] font-extrabold leading-tight">
            {w?.today_left_str ?? "—"}
          </div>
          <div className="text-[12px] opacity-90 mt-1">
            이번 달 남은 돈 {w?.month_left_str ?? "—"} · {w?.days_left ?? "—"}일
          </div>
          <div className="text-[13px] font-semibold mt-3">
            {w?.line ?? "불러오는 중…"}
          </div>
        </div>
        <p className="text-[11px] text-muted mt-2 text-center">
          ↑ 실제 홈화면 위젯에 뜨는 화면 (라이브 데이터)
        </p>

        {/* 홈화면 위젯 만들기 */}
        <div className="mt-5 rounded-2xl bg-white p-4 shadow-sm">
          <h2 className="text-[15px] font-extrabold">홈 화면 위젯으로 만들기</h2>
          <p className="text-[12px] text-muted mt-1 leading-relaxed">
            iOS는 위젯을 앱에서만 제공할 수 있어, 무료 앱 <b>Scriptable</b>로 5초 만에 넣어요.
          </p>
          <ol className="text-[13px] mt-3 flex flex-col gap-2 list-decimal pl-5 leading-relaxed">
            <li>앱스토어에서 <b>Scriptable</b> 설치 (무료)</li>
            <li>아래 <b>코드 복사</b> → Scriptable에서 <b>+</b> → 붙여넣기 → 저장</li>
            <li>홈화면 길게 누르기 → <b>+</b> → Scriptable → 위젯 추가</li>
            <li>위젯 한 번 탭 → <b>Script</b>를 방금 저장한 걸로 선택 → 완료</li>
          </ol>
          <div className="flex gap-2 mt-4">
            <button
              onClick={copyCode}
              className="flex-1 bg-brand text-white font-bold rounded-xl py-2.5 text-sm"
            >
              {copied ? "복사됨 ✓" : "위젯 코드 복사"}
            </button>
            <a
              href="/moneymate-widget.js"
              download
              className="flex-1 text-center bg-white border border-line font-bold rounded-xl py-2.5 text-sm"
            >
              다운로드
            </a>
          </div>
        </div>

        <p className="text-[11px] text-muted mt-4 text-center leading-relaxed">
          위젯은 <code>/api/widget</code> 데이터를 그대로 씁니다 — 앱·위젯이 같은 배포예요.
        </p>
      </div>
    </main>
  );
}
