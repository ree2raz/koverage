import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { InferenceLog } from "../types";

const short = (m: string) => m.split("/").pop() ?? m;

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
      <span className="text-xs tabular-nums text-slate-200">{value}</span>
    </div>
  );
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
    return <p className="text-xs text-slate-400 px-1">No inference logs yet.</p>;

  const maxLatency = Math.max(...logs.map((l) => l.latency_ms), 1);

  return (
    <div className="space-y-2">
      {logs.map((l, i) => {
        const ttftPct = l.latency_ms ? Math.min(100, (l.ttft_ms / l.latency_ms) * 100) : 0;
        const barPct = (l.latency_ms / maxLatency) * 100;
        const latS = (l.latency_ms / 1000).toFixed(2);
        const ttftMs = l.ttft_ms ?? 0;
        const redactions = Object.entries(l.redaction_counts || {});
        const statusColor =
          l.status === "error"
            ? "text-rose-400"
            : l.status === "cancelled"
              ? "text-amber-400"
              : "text-emerald-400";

        return (
          <div key={l.request_id} className="rounded-md border border-slate-800 bg-slate-900/50 p-3 space-y-2.5">
            {/* turn header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium text-slate-400">#{i + 1}</span>
                <span className="text-xs font-medium text-slate-300">{short(l.model)}</span>
              </div>
              <span className={`text-xs font-semibold uppercase ${statusColor}`}>{l.status}</span>
            </div>

            {/* waterfall bar: amber = TTFT, indigo = generation */}
            <div className="space-y-1">
              <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                <div style={{ width: `${barPct}%` }} className="h-full flex">
                  <div className="h-full bg-amber-400" style={{ width: `${ttftPct}%` }} />
                  <div className="h-full bg-indigo-500 flex-1" />
                </div>
              </div>
              <div className="flex gap-3 text-xs text-slate-400">
                <span className="flex items-center gap-1"><span className="inline-block w-2 h-1.5 rounded-sm bg-amber-400" />TTFT</span>
                <span className="flex items-center gap-1"><span className="inline-block w-2 h-1.5 rounded-sm bg-indigo-500" />generation</span>
              </div>
            </div>

            {/* key metrics grid */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-slate-800 pt-2">
              <Stat label="TTFT" value={ttftMs ? `${ttftMs} ms` : "—"} />
              <Stat label="Total latency" value={`${latS} s`} />
              <Stat label="Tokens" value={`${l.prompt_tokens ?? 0}↑ ${l.completion_tokens ?? 0}↓`} />
              <Stat label="Cost" value={`$${(l.cost_usd ?? 0).toFixed(5)}`} />
            </div>

            {/* provider */}
            <div className="text-xs text-slate-400 truncate">{l.provider} · {l.model}</div>

            {/* redaction badges */}
            {redactions.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-1 border-t border-slate-800">
                {redactions.map(([kind, n]) => (
                  <span key={kind} className="rounded bg-fuchsia-500/15 text-fuchsia-300 px-1.5 py-0.5 text-xs">
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
