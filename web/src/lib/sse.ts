// Minimal SSE-over-POST client. The native EventSource only does GET, but /chat
// is a POST, so we read the streaming response body and parse SSE frames by hand.

export interface SSEMessage {
  event: string;
  data: unknown;
}

function parseFrame(frame: string): SSEMessage | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  const raw = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(raw) };
  } catch {
    return { event, data: raw };
  }
}

export interface ChatBody {
  message: string;
  conversation_id?: string | null;
  model?: string;
  session_id?: string;
  guardrails_enabled?: boolean;
}

export async function streamChat(
  body: ChatBody,
  onEvent: (msg: SSEMessage) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!resp.ok || !resp.body) throw new Error(`chat failed: ${resp.status}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r/g, "");
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const msg = parseFrame(frame);
      if (msg) onEvent(msg);
    }
  }
}
