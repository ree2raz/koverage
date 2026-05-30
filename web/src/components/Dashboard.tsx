import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { InferenceLog, MetricSummaryRow, TimeseriesRow } from "../types";

const WINDOWS: [string, number][] = [
  ["1h", 60],
  ["24h", 1440],
  ["7d", 10080],
];

const AXIS = { stroke: "#94a3b8", fontSize: 12 };
const GRID = "#1e293b";

function Card({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-100 tabular-nums">{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function shortModel(m: string) {
  return m.includes("/") ? m.split("/")[1] : m;
}

export default function Dashboard() {
  const [summary, setSummary] = useState<MetricSummaryRow[]>([]);
  const [series, setSeries] = useState<TimeseriesRow[]>([]);
  const [recentLogs, setRecentLogs] = useState<InferenceLog[]>([]);
  const [expandedSpan, setExpandedSpan] = useState<string | null>(null);
  const [windowMin, setWindowMin] = useState(60);

  useEffect(() => {
    let alive = true;
    const load = () => {
      api.summary(windowMin).then((s) => alive && setSummary(s)).catch(() => {});
      api.timeseries(Math.min(windowMin, 360)).then((s) => alive && setSeries(s)).catch(() => {});
      api.recentLogs(30).then((l) => alive && setRecentLogs(l)).catch(() => {});
    };
    load();
    const t = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [windowMin]);

  const totalReq = summary.reduce((a, r) => a + Number(r.requests), 0);
  const totalErr = summary.reduce((a, r) => a + Number(r.errors), 0);
  const totalCost = summary.reduce((a, r) => a + Number(r.cost_usd), 0);
  const totalTok = summary.reduce((a, r) => a + Number(r.tokens), 0);
  const errRate = totalReq ? (totalErr / totalReq) * 100 : 0;

  const latencyData = summary.map((r) => ({
    model: shortModel(r.model),
    p50: Number(r.p50_ms),
    p95: Number(r.p95_ms),
    p99: Number(r.p99_ms),
    ttft_p95: Number(r.ttft_p95_ms),
  }));
  const costData = summary.map((r) => ({ model: shortModel(r.model), cost: Number(r.cost_usd) }));
  const seriesData = series.map((r) => ({
    t: new Date(r.bucket).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    requests: Number(r.requests),
    errors: Number(r.errors),
    p95: Number(r.p95_ms),
  }));

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Observability</h1>
          <p className="text-xs text-slate-400">Latency, throughput, errors, and cost per model.</p>
        </div>
        <div className="flex gap-1">
          {WINDOWS.map(([label, mins]) => (
            <button
              key={mins}
              onClick={() => setWindowMin(mins)}
              className={`rounded-md px-2.5 py-1 text-xs ${
                windowMin === mins ? "bg-slate-700 text-white" : "text-slate-400 hover:bg-slate-800"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card label="Requests" value={totalReq.toLocaleString()} />
        <Card label="Error rate" value={`${errRate.toFixed(1)}%`} sub={`${totalErr} errors`} />
        <Card label="Total cost" value={`$${totalCost.toFixed(4)}`} />
        <Card label="Tokens" value={totalTok.toLocaleString()} />
      </div>

      {summary.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-800 p-10 text-center text-sm text-slate-400">
          No inference logs in this window yet. Start a chat and the metrics will stream in.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <h2 className="text-sm font-medium mb-3 text-slate-300">Latency by model (ms)</h2>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={latencyData}>
                  <CartesianGrid stroke={GRID} vertical={false} />
                  <XAxis dataKey="model" tick={AXIS} />
                  <YAxis tick={AXIS} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
                  <Legend wrapperStyle={{ fontSize: 12, color: "#cbd5e1" }} />
                  <Bar dataKey="p50" fill="#34d399" />
                  <Bar dataKey="p95" fill="#60a5fa" />
                  <Bar dataKey="p99" fill="#f472b6" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <h2 className="text-sm font-medium mb-3 text-slate-300">Throughput & errors</h2>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={seriesData}>
                  <CartesianGrid stroke={GRID} vertical={false} />
                  <XAxis dataKey="t" tick={AXIS} />
                  <YAxis tick={AXIS} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
                  <Legend wrapperStyle={{ fontSize: 12, color: "#cbd5e1" }} />
                  <Line type="monotone" dataKey="requests" stroke="#818cf8" dot={false} />
                  <Line type="monotone" dataKey="errors" stroke="#fb7185" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h2 className="text-sm font-medium mb-3 text-slate-300">Cost by model (USD)</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={costData}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="model" tick={AXIS} />
                <YAxis tick={AXIS} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
                <Bar dataKey="cost" fill="#fbbf24" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60 text-slate-400 text-xs">
                <tr>
                  {["Provider", "Model", "Req", "Err", "p50", "p95", "p99", "TTFT p95", "Tokens", "Cost"].map(
                    (h) => (
                      <th key={h} className="px-3 py-2 text-left font-medium">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {summary.map((r) => (
                  <tr key={`${r.provider}/${r.model}`} className="border-t border-slate-800">
                    <td className="px-3 py-2 text-slate-400">{r.provider}</td>
                    <td className="px-3 py-2 text-slate-200">{shortModel(r.model)}</td>
                    <td className="px-3 py-2">{r.requests}</td>
                    <td className="px-3 py-2 text-rose-300">{r.errors}</td>
                    <td className="px-3 py-2">{Math.round(Number(r.p50_ms))}</td>
                    <td className="px-3 py-2">{Math.round(Number(r.p95_ms))}</td>
                    <td className="px-3 py-2">{Math.round(Number(r.p99_ms))}</td>
                    <td className="px-3 py-2">{Math.round(Number(r.ttft_p95_ms))}</td>
                    <td className="px-3 py-2">{Number(r.tokens).toLocaleString()}</td>
                    <td className="px-3 py-2">${Number(r.cost_usd).toFixed(6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Recent spans / trace log */}
      <div className="rounded-lg border border-slate-800 bg-slate-900 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-800">
          <h2 className="text-sm font-medium text-slate-300">Recent Spans</h2>
          <p className="text-xs text-slate-400 mt-0.5">Last 30 inference traces — click any row to expand</p>
        </div>
        {recentLogs.length === 0 ? (
          <p className="px-4 py-6 text-sm text-slate-400 text-center">No traces yet. Start a chat to see spans here.</p>
        ) : (
          <div className="divide-y divide-slate-800">
            {recentLogs.map((l) => {
              const isOpen = expandedSpan === l.request_id;
              const maxLat = Math.max(...recentLogs.map((x) => x.latency_ms), 1);
              const ttftPct = l.latency_ms ? Math.min(100, (l.ttft_ms / l.latency_ms) * 100) : 0;
              const barPct = (l.latency_ms / maxLat) * 100;
              const statusColor =
                l.status === "error" ? "text-rose-400"
                : l.status === "cancelled" ? "text-amber-400"
                : l.status === "refused" ? "text-fuchsia-300"
                : "text-emerald-400";
              const redactions = Object.entries(l.redaction_counts || {});
              return (
                <div key={l.request_id}>
                  <button
                    onClick={() => setExpandedSpan(isOpen ? null : l.request_id)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-800/40 text-left transition-colors"
                  >
                    <span className={`text-xs font-bold uppercase w-20 shrink-0 truncate ${statusColor}`}>{l.status}</span>
                    <span className="text-xs text-slate-300 w-28 shrink-0 truncate">{shortModel(l.model)}</span>
                    <span className="text-xs text-slate-400 w-16 shrink-0 truncate">{l.provider}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div style={{ width: `${barPct}%` }} className="h-full flex">
                        <div className="h-full bg-amber-400" style={{ width: `${ttftPct}%` }} />
                        <div className="h-full bg-indigo-500 flex-1" />
                      </div>
                    </div>
                    <span className="text-xs text-slate-400 w-16 text-right shrink-0">{(l.latency_ms / 1000).toFixed(2)}s</span>
                    <span className="text-xs text-slate-400 w-16 text-right shrink-0">${(l.cost_usd ?? 0).toFixed(5)}</span>
                    {redactions.length > 0 && (
                      <span className="text-xs rounded bg-fuchsia-500/15 text-fuchsia-300 px-1.5 py-0.5 shrink-0">PII</span>
                    )}
                    <span className="text-slate-400 text-xs ml-1">{isOpen ? "▲" : "▼"}</span>
                  </button>
                  {isOpen && (
                    <div className="px-4 pb-4 pt-2 bg-slate-900/40 space-y-3 text-xs border-t border-slate-800">
                      {/* metrics row */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div><span className="text-slate-400">TTFT </span><span className="text-slate-200 tabular-nums">{l.ttft_ms ?? 0} ms</span></div>
                        <div><span className="text-slate-400">Latency </span><span className="text-slate-200 tabular-nums">{(l.latency_ms / 1000).toFixed(2)}s</span></div>
                        <div><span className="text-slate-400">Tokens </span><span className="text-slate-200 tabular-nums">{l.prompt_tokens ?? 0}↑ {l.completion_tokens ?? 0}↓</span></div>
                        <div><span className="text-slate-400">Cost </span><span className="text-slate-200 tabular-nums">${(l.cost_usd ?? 0).toFixed(5)}</span></div>
                        <div className="col-span-2"><span className="text-slate-400">Request ID </span><span className="text-slate-400 font-mono">{l.request_id}</span></div>
                        <div className="col-span-2"><span className="text-slate-400">Model </span><span className="text-slate-400 font-mono">{l.model}</span></div>
                      </div>
                      {/* redaction badges */}
                      {redactions.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {redactions.map(([kind, n]) => (
                            <span key={kind} className="rounded bg-fuchsia-500/15 text-fuchsia-300 px-1.5 py-0.5">
                              redacted {kind} ×{n}
                            </span>
                          ))}
                        </div>
                      )}
                      {/* request payload */}
                      {l.input_preview && (
                        <div>
                          <div className="text-slate-400 mb-1 uppercase tracking-wide">Request (redacted)</div>
                          <pre className="whitespace-pre-wrap break-words rounded bg-slate-800 border border-slate-700 px-3 py-2 text-slate-300 font-mono leading-relaxed max-h-64 overflow-y-auto">
                            {l.input_preview}
                          </pre>
                        </div>
                      )}
                      {/* response payload */}
                      {l.output_preview && (
                        <div>
                          <div className="text-slate-400 mb-1 uppercase tracking-wide">Response (redacted)</div>
                          <pre className="whitespace-pre-wrap break-words rounded bg-slate-800 border border-slate-700 px-3 py-2 text-slate-300 font-mono leading-relaxed max-h-64 overflow-y-auto">
                            {l.output_preview}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
