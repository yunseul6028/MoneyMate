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

export type IngestItem = {
  id: number;
  merchant: string;
  amount: number;
  category: string;
  source: string;
  source_label: string;
};

async function jget<T>(url: string): Promise<T> {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${url} → ${r.status}`);
  return r.json();
}

export const getDashboard = () => jget<Dashboard>("/api/dashboard");
export const getProactive = () => jget<ProactiveResp>("/api/proactive");
export const getCategories = () => jget<{ expense: string[] }>("/api/categories");

async function jpost<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST ${url} → ${r.status}`);
  return r.json();
}

export const ingest = (text: string, payment_method = "credit") =>
  jpost<{ added: number; items: IngestItem[] }>("/api/ingest", { text, payment_method });

export const correctCategory = (id: number, category: string) =>
  jpost<{ ok: boolean; category: string; source: string }>(
    `/api/transactions/${id}/category`,
    { category }
  );

export type Profile = {
  name: string;
  monthly_budget: number;
  card_billing_day: number;
};

export const getProfile = () => jget<Profile>("/api/profile");

export async function updateProfile(name: string, monthly_budget: number) {
  const r = await fetch("/api/profile", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, monthly_budget }),
  });
  if (!r.ok) throw new Error(`PATCH /api/profile → ${r.status}`);
  return r.json();
}

export async function sendChat(message: string): Promise<ChatResp> {
  const r = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!r.ok) throw new Error(`POST /api/chat → ${r.status}`);
  return r.json();
}

// 친근한 금액 표기 (백엔드 app/core/format.py 와 동일 규칙)
//  10만↑: 만원 반올림 · 1만~10만: 천원 반올림 · 1만 미만: 콤마 그대로
export const won = (n: number | null | undefined): string => {
  if (n == null) return "—";
  const sign = n < 0 ? "-" : "";
  const v = Math.abs(Math.round(n));
  if (v < 10_000) return `${sign}${v.toLocaleString("ko-KR")}원`;
  if (v < 100_000) {
    const r = Math.round(v / 1000) * 1000;
    const man = Math.floor(r / 10_000);
    const cheon = Math.floor((r % 10_000) / 1000);
    return `${sign}${man}만${cheon ? ` ${cheon}천` : ""}원`;
  }
  return `${sign}${Math.round(v / 10_000)}만원`;
};
