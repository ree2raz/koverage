import type {
  ConversationDetail,
  ConversationSummary,
  InferenceLog,
  MetricSummaryRow,
  ModelInfo,
  TimeseriesRow,
} from "../types";

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return (await r.json()) as T;
}

export const api = {
  models: () => getJSON<ModelInfo[]>("/models"),
  conversations: () => getJSON<ConversationSummary[]>("/api/conversations"),
  conversation: (id: string) => getJSON<ConversationDetail>(`/api/conversations/${id}`),
  conversationLogs: (id: string) => getJSON<InferenceLog[]>(`/api/conversations/${id}/logs`),
  recentLogs: (limit = 50) => getJSON<InferenceLog[]>(`/api/logs?limit=${limit}`),
  summary: (windowMinutes = 1440) =>
    getJSON<MetricSummaryRow[]>(`/api/metrics/summary?window_minutes=${windowMinutes}`),
  timeseries: (windowMinutes = 60) =>
    getJSON<TimeseriesRow[]>(`/api/metrics/timeseries?window_minutes=${windowMinutes}`),
  cancel: (id: string) => fetch(`/api/conversations/${id}/cancel`, { method: "POST" }),
  deleteConversation: (id: string) => fetch(`/api/conversations/${id}`, { method: "DELETE" }),
  renameConversation: (id: string, title: string) =>
    fetch(`/api/conversations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    }),
};
