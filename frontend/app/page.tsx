"use client";

import { useEffect, useState } from "react";
import DashboardView from "@/components/Dashboard";
import Chat from "@/components/Chat";
import IngestPanel from "@/components/IngestPanel";
import Onboarding from "@/components/Onboarding";

const ONBOARD_KEY = "moneymate_onboarded";

export default function Home() {
  const [refresh, setRefresh] = useState(0);
  const [onboarded, setOnboarded] = useState<boolean | null>(null); // null = 판단 전
  const bump = () => setRefresh((k) => k + 1);

  useEffect(() => {
    setOnboarded(localStorage.getItem(ONBOARD_KEY) === "1");
  }, []);

  if (onboarded === null) return null; // localStorage 읽기 전 깜빡임 방지

  if (!onboarded) {
    return (
      <Onboarding
        onDone={() => {
          localStorage.setItem(ONBOARD_KEY, "1");
          setOnboarded(true);
          bump(); // 예산이 바뀌었을 수 있으니 대시보드 갱신
        }}
      />
    );
  }

  return (
    <main className="max-w-phone mx-auto min-h-screen flex flex-col bg-[#f4f4f7]">
      <DashboardView refreshKey={refresh} />
      <div className="px-3.5 pb-2 flex flex-col gap-3 flex-1">
        <IngestPanel onAdded={bump} />
        <Chat onResolved={bump} />
      </div>
    </main>
  );
}
