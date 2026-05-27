export interface ModelInfo {
  id: string;
  label: string;
  provider: string;
  gateway: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  status: string;
  default_model: string;
  updated_at: string | null;
}

export type Role = "user" | "assistant" | "system" | "tool";

export interface ChatMessage {
  id?: string;
  role: Role;
  content: string;
  sequence?: number;
  created_at?: string | null;
  streaming?: boolean;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ChatMessage[];
}

export interface InferenceLog {
  request_id: string;
  conversation_id?: string;
  message_id?: string;
  provider: string;
  model: string;
  status: string;
  error_type?: string;
  latency_ms: number;
  ttft_ms: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens: number;
  cost_usd: number;
  input_preview: string;
  output_preview: string;
  redaction_counts: Record<string, number>;
  ts: string;
}

export interface MetricSummaryRow {
  provider: string;
  model: string;
  requests: number;
  errors: number;
  cancelled: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  ttft_p95_ms: number;
  tokens: number;
  cost_usd: number;
}

export interface TimeseriesRow {
  bucket: string;
  requests: number;
  errors: number;
  p95_ms: number;
  tokens: number;
  cost_usd: number;
}

export interface DoneEvent {
  conversation_id: string;
  status: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  request_id: string;
}
