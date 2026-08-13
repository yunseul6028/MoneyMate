// 백엔드 FastAPI API 클라이언트 + 타입.
// next.config 의 rewrites 로 /api → http://localhost:8000 프록시됨.

export type CategoryStat = {
  category: string;
  month_amount: number;
  share: number;
  week_amount: number;
  baseline_week_avg: number;
  increase_rate: number | null;
};

export type Dashboard = {
  user: string;
  today: string;
  one_liner: string;
  month_expense: number;
  month_income: number;
  remaining_budget: number;
  monthly_budget: number;
  upcoming_card_bill: number;
  next_billing_date: string;
  week_expense: number;
  avg_weekly_expense: number;
  categories: CategoryStat[];
  subscriptions: { merchant: string; amount: number; date: string }[];
};

export type ProactiveResp = {
  should_speak: boolean;
  message: string;
  decision: string | null;
  trigger?: string;
};

export type ChatResp = { reply: string; kind: "coach" | "chat"; decision?: string };

async function jget<T>(url: string): Promise<T> {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${url} → ${r.status}`);
  return r.json();
}

export const getDashboard = () => jget<Dashboard>("/api/dashboard");
export const getProactive = () => jget<ProactiveResp>("/api/proactive");

export async function sendChat(message: string): Promise<ChatResp> {
  const r = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!r.ok) throw new Error(`POST /api/chat → ${r.status}`);
  return r.json();
}

export const won = (n: number | null | undefined) =>
  n == null ? "—" : Number(n).toLocaleString("ko-KR") + "원";
