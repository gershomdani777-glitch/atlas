import type { AgentStatus, Decision, DecisionReceipt, MarketAsset, Metrics, Portfolio, RiskConfig } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`${options?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  getStatus: () => request<AgentStatus>("/agent/status"),
  killAgent: () => request<{ status: string }>("/agent/kill", { method: "POST" }),
  resumeAgent: () => request<{ status: string }>("/agent/resume", { method: "POST" }),
  getDecisions: (params?: { limit?: number; offset?: number; accepted?: boolean }) => {
    const qs = new URLSearchParams();
    if (params?.limit != null) qs.set("limit", String(params.limit));
    if (params?.offset != null) qs.set("offset", String(params.offset));
    if (params?.accepted != null) qs.set("accepted", String(params.accepted));
    const query = qs.toString();
    return request<Decision[]>(`/agent/decisions${query ? `?${query}` : ""}`);
  },
  getDecisionReceipt: (id: number) => request<DecisionReceipt>(`/agent/decisions/${id}/receipt`),
  getPortfolio: () => request<Portfolio>("/portfolio"),
  getMarket: () => request<MarketAsset[]>("/market"),
  getMetrics: () => request<Metrics>("/metrics"),
  getRiskConfig: () => request<RiskConfig>("/config/risk"),
  putRiskConfig: (updates: Partial<RiskConfig>) =>
    request<RiskConfig>("/config/risk", { method: "PUT", body: JSON.stringify(updates) }),
};
