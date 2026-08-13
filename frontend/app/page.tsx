"use client";

import { useState } from "react";
import DashboardView from "@/components/Dashboard";
import Chat from "@/components/Chat";
import IngestPanel from "@/components/IngestPanel";

export default function Home() {
  const [refresh, setRefresh] = useState(0);
  const bump = () => setRefresh((k) => k + 1);

  return (
    <main className="max-w-phone mx-auto min-h-screen flex flex-col bg-[#f4f4f7]">
      <DashboardView refreshKey={refresh} />
      <div className="px-3.5 pb-2 flex flex-col gap-3 flex-1">
        <IngestPanel onAdded={bump} />
        <Chat />
      </div>
    </main>
  );
}
