import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { InferenceLog } from "../types";

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "error"
      ? "bg-rose-500/20 text-rose-300"
      : status === "cancelled"
        ? "bg-amber-500/20 text-amber-300"
        : "bg-emerald-500/20 text-emerald-300";
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${cls}`}>{status}</span>;
}

export default function TracePanel({
  conversationId,
  refreshKey,
}: {
  conversationId: string;
  refreshKey: number;
}) {
  const [logs, setLogs] = useState<InferenceLog[]>([]);

  useEffect(() => {
    if (!conversationId) return;
    api.conversationLogs(conversationId).then(setLogs).catch(() => setLogs([]));
  }, [conversationId, refreshKey]);

  if (logs.length === 0)
    return <p className="text-xs text-slate-600 px-1">No inference logs yet for this conversation.</p>;

  const maxLatency = Math.max(...logs.map((l) => l.latency_ms), 1);

  return (
    <div className="space-y-2">
      {logs.map((l) => {
        const ttftPct = l.latency_ms ? Math.min(100, (l.ttft_ms / l.latency_ms) * 100) : 0;
        const widthPct = (l.latency_ms / maxLatency) * 100;
        const redactions = Object.entries(l.redaction_counts || {});
        return (
          <div key={l.request_id} className="rounded-md border border-slate-800 bg-slate-900/40 p-2.5">
            <div className="flex items-center justify-between text-xs mb-1.5">
              <div className="flex items-center gap-2">
                <StatusBadge status={l.status} />
                <span className="text-slate-300">{l.model}</span>
                <span className="text-slate-600">{l.provider}</span>
              </div>
              <div className="flex items-center gap-3 text-slate-400 tabular-nums">
                <span>{l.latency_ms} ms</span>
                <span title="time to first token">TTFT {l.ttft_ms} ms</span>
                <span>{l.total_tokens} tok</span>
                <span>${l.cost_usd?.toFixed?.(6) ?? l.cost_usd}</span>
              </div>
            </div>
            {/* latency waterfall: amber = time-to-first-token, indigo = generation */}
            <div className="h-2 rounded-full bg-slate-800 overflow-hidden" style={{ width: `${widthPct}%` }}>
              <div className="h-full bg-amber-400" style={{ width: `${ttftPct}%`, float: "left" }} />
              <div className="h-full bg-indigo-500" style={{ width: `${100 - ttftPct}%`, float: "left" }} />
            </div>
            {redactions.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {redactions.map(([kind, n]) => (
                  <span key={kind} className="rounded bg-fuchsia-500/15 text-fuchsia-300 px-1.5 py-0.5 text-[10px]">
                    redacted {kind} ×{n}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
