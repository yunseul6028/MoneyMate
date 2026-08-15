"use client";

import { useEffect, useState } from "react";
import DashboardView from "@/components/Dashboard";
import Chat from "@/components/Chat";
import TestPanel from "@/components/TestPanel";
import Onboarding from "@/components/Onboarding";

const ONBOARD_KEY = "moneymate_onboarded";

export default function Home() {
  const [refresh, setRefresh] = useState(0);
  const [poke, setPoke] = useState(0);
  const [onboarded, setOnboarded] = useState<boolean | null>(null);
  const bump = () => setRefresh((k) => k + 1);
  // 테스트 이벤트 발생 시: 대시보드 갱신 + 채팅이 반응하도록 poke
  const onEvent = () => {
    setRefresh((k) => k + 1);
    setPoke((k) => k + 1);
  };

  useEffect(() => {
    setOnboarded(localStorage.getItem(ONBOARD_KEY) === "1");
  }, []);

  if (onboarded === null) return null;

  if (!onboarded) {
    return (
      <Onboarding
        onDone={() => {
          localStorage.setItem(ONBOARD_KEY, "1");
          setOnboarded(true);
          bump();
        }}
      />
    );
  }

  return (
    <main className="max-w-phone mx-auto min-h-screen flex flex-col bg-[#f4f4f7]">
      <DashboardView refreshKey={refresh} />
      <div className="px-3.5 pb-2 flex flex-col gap-3 flex-1">
        <TestPanel onEvent={onEvent} />
        <Chat onResolved={bump} pokeKey={poke} />
      </div>
    </main>
  );
}
