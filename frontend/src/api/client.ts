const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }

  return (await res.json()) as T;
}

export const api = {
  health: () => request<{ status: string; app: string; env: string }>("/api/v1/health"),
  runAnalysis: (payload: unknown, notify: boolean) =>
    request("/api/v1/analysis/run" + (notify ? "?notify=true" : ""), {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  runBacktest: (payload: unknown) =>
    request("/api/v1/backtest/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  analyzePortfolio: (payload: unknown) =>
    request("/api/v1/portfolio/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  placeOrder: (payload: unknown) =>
    request("/api/v1/trading/order", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  askChat: (payload: unknown) =>
    request("/api/v1/chat/query", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
