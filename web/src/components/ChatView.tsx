import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { streamChat, type SSEMessage } from "../lib/sse";
import { useStore } from "../store";
import type { ChatMessage, DoneEvent, ModelInfo } from "../types";
import MessageBubble from "./MessageBubble";
import ModelSelector from "./ModelSelector";
import TracePanel from "./TracePanel";

export default function ChatView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { refresh, sessionId } = useStore();

  const [models, setModels] = useState<ModelInfo[]>([]);
  const [model, setModel] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastTurn, setLastTurn] = useState<DoneEvent | null>(null);
  const [showTrace, setShowTrace] = useState(true);
  const [traceKey, setTraceKey] = useState(0);
  const [guardrailsEnabled, setGuardrailsEnabled] = useState(
    () => typeof window !== "undefined" && localStorage.getItem("guardrails_enabled") !== "false",
  );

  useEffect(() => {
    localStorage.setItem("guardrails_enabled", String(guardrailsEnabled));
  }, [guardrailsEnabled]);

  const convIdRef = useRef<string | null>(id ?? null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // load model catalog once
  useEffect(() => {
    api.models().then((ms) => {
      setModels(ms);
      setModel((cur) => cur || ms[0]?.id || "");
    });
  }, []);

  // load (or reset) the conversation when the route changes
  useEffect(() => {
    convIdRef.current = id ?? null;
    setError(null);
    setLastTurn(null);
    if (!id) {
      setMessages([]);
      return;
    }
    api.conversation(id).then((c) => {
      setMessages(c.messages.map((m) => ({ ...m })));
      if (c.default_model) setModel(c.default_model);
      setTraceKey((k) => k + 1);
    });
  }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function onEvent(msg: SSEMessage) {
    if (msg.event === "meta") {
      convIdRef.current = (msg.data as { conversation_id: string }).conversation_id;
    } else if (msg.event === "token") {
      const text = (msg.data as { text: string }).text;
      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        copy[copy.length - 1] = { ...last, content: last.content + text };
        return copy;
      });
    } else if (msg.event === "done") {
      setLastTurn(msg.data as DoneEvent);
    } else if (msg.event === "error") {
      setError((msg.data as { detail: string }).detail ?? "stream error");
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    setError(null);
    const wasNew = !convIdRef.current;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", streaming: true },
    ]);
    setStreaming(true);

    const abort = new AbortController();
    abortRef.current = abort;
    try {
      await streamChat(
        {
          message: text,
          conversation_id: convIdRef.current,
          model,
          session_id: sessionId,
          guardrails_enabled: guardrailsEnabled,
        },
        onEvent,
        abort.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError(String(e));
    } finally {
      setStreaming(false);
      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        if (last?.streaming) copy[copy.length - 1] = { ...last, streaming: false };
        return copy;
      });
      setTraceKey((k) => k + 1);
      refresh();
      if (wasNew && convIdRef.current) navigate(`/c/${convIdRef.current}`, { replace: true });
    }
  }

  async function cancel() {
    if (convIdRef.current) await api.cancel(convIdRef.current);
    abortRef.current?.abort();
    setStreaming(false);
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="flex h-full min-h-0">
      <div className="flex-1 min-w-0 flex flex-col">
        {/* header */}
        <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-5 py-3">
          <h1 className="text-sm font-medium text-slate-300 truncate">
            {id ? "Conversation" : "New chat"}
          </h1>
          <div className="flex items-center gap-2">
            <ModelSelector models={models} value={model} onChange={setModel} disabled={streaming} />
            <button
              onClick={() => setGuardrailsEnabled((v) => !v)}
              title={
                guardrailsEnabled
                  ? "Guardrails on — jailbreak attempts are refused before reaching the model"
                  : "Guardrails off — every prompt reaches the model"
              }
              className={`rounded-md border px-2.5 py-1.5 text-xs transition-colors ${
                guardrailsEnabled
                  ? "border-emerald-600/50 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25"
                  : "border-slate-700 text-slate-400 hover:bg-slate-800"
              }`}
            >
              Guardrails {guardrailsEnabled ? "on" : "off"}
            </button>
            <button
              onClick={() => setShowTrace((s) => !s)}
              className="rounded-md border border-slate-700 px-2.5 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
            >
              {showTrace ? "Hide trace" : "Show trace"}
            </button>
          </div>
        </div>

        {/* messages */}
        <div className="flex-1 min-h-0 overflow-y-auto px-5 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-slate-600 mt-20 text-sm">
              Ask anything. Every turn is instrumented — open the trace panel to watch latency,
              tokens, cost, and PII redaction per call.
            </div>
          )}
          {messages.map((m, i) => (
            <MessageBubble key={m.id ?? i} message={m} />
          ))}
          {error && (
            <div className="text-rose-400 text-sm bg-rose-500/10 rounded-md px-3 py-2">{error}</div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* input */}
        <div className="border-t border-slate-800 px-5 py-3">
          {lastTurn && (
            <div className="mb-2 text-xs text-slate-500 tabular-nums">
              last turn · {lastTurn.completion_tokens} tok · ${lastTurn.cost_usd.toFixed(6)} ·{" "}
              {lastTurn.status}
            </div>
          )}
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Message…  (Enter to send, Shift+Enter for newline)"
              className="flex-1 resize-none rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            {streaming ? (
              <button
                onClick={cancel}
                className="rounded-lg bg-rose-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-rose-500"
              >
                Cancel
              </button>
            ) : (
              <button
                onClick={send}
                disabled={!input.trim()}
                className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
              >
                Send
              </button>
            )}
          </div>
        </div>
      </div>

      {/* trace side panel */}
      {showTrace && (
        <div className="w-[360px] shrink-0 border-l border-slate-800 bg-[#0e131c] overflow-y-auto p-3">
          <p className="px-1 pb-2 text-xs uppercase tracking-wide text-slate-600">
            Inference trace
          </p>
          {convIdRef.current ? (
            <TracePanel conversationId={convIdRef.current} refreshKey={traceKey} />
          ) : (
            <p className="text-xs text-slate-600 px-1">Send a message to see its trace.</p>
          )}
        </div>
      )}
    </div>
  );
}
