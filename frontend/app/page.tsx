import DashboardView from "@/components/Dashboard";
import Chat from "@/components/Chat";

export default function Home() {
  return (
    <main className="max-w-phone mx-auto min-h-screen flex flex-col bg-[#f4f4f7]">
      <DashboardView />
      <div className="px-3.5 pb-2 flex flex-col gap-3 flex-1">
        <Chat />
      </div>
    </main>
  );
}
