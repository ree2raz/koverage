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
import type { MetricSummaryRow, TimeseriesRow } from "../types";

const WINDOWS: [string, number][] = [
  ["1h", 60],
  ["24h", 1440],
  ["7d", 10080],
];

const AXIS = { stroke: "#475569", fontSize: 11 };
const GRID = "#1e293b";

function Card({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-[#0e131c] px-4 py-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-100 tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-slate-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function shortModel(m: string) {
  return m.includes("/") ? m.split("/")[1] : m;
}

export default function Dashboard() {
  const [summary, setSummary] = useState<MetricSummaryRow[]>([]);
  const [series, setSeries] = useState<TimeseriesRow[]>([]);
  const [windowMin, setWindowMin] = useState(1440);

  useEffect(() => {
    let alive = true;
    const load = () => {
      api.summary(windowMin).then((s) => alive && setSummary(s)).catch(() => {});
      api
        .timeseries(Math.min(windowMin, 360))
        .then((s) => alive && setSeries(s))
        .catch(() => {});
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
          <p className="text-xs text-slate-500">Latency, throughput, errors, and cost per model.</p>
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
        <div className="rounded-lg border border-dashed border-slate-800 p-10 text-center text-sm text-slate-600">
          No inference logs in this window yet. Start a chat and the metrics will stream in.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-lg border border-slate-800 bg-[#0e131c] p-4">
              <h2 className="text-sm font-medium mb-3 text-slate-300">Latency by model (ms)</h2>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={latencyData}>
                  <CartesianGrid stroke={GRID} vertical={false} />
                  <XAxis dataKey="model" tick={AXIS} />
                  <YAxis tick={AXIS} />
                  <Tooltip contentStyle={{ background: "#0b0e14", border: "1px solid #1e293b" }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="p50" fill="#34d399" />
                  <Bar dataKey="p95" fill="#60a5fa" />
                  <Bar dataKey="p99" fill="#f472b6" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="rounded-lg border border-slate-800 bg-[#0e131c] p-4">
              <h2 className="text-sm font-medium mb-3 text-slate-300">Throughput & errors</h2>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={seriesData}>
                  <CartesianGrid stroke={GRID} vertical={false} />
                  <XAxis dataKey="t" tick={AXIS} />
                  <YAxis tick={AXIS} />
                  <Tooltip contentStyle={{ background: "#0b0e14", border: "1px solid #1e293b" }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="requests" stroke="#818cf8" dot={false} />
                  <Line type="monotone" dataKey="errors" stroke="#fb7185" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-[#0e131c] p-4">
            <h2 className="text-sm font-medium mb-3 text-slate-300">Cost by model (USD)</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={costData}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="model" tick={AXIS} />
                <YAxis tick={AXIS} />
                <Tooltip contentStyle={{ background: "#0b0e14", border: "1px solid #1e293b" }} />
                <Bar dataKey="cost" fill="#fbbf24" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-lg border border-slate-800 bg-[#0e131c] overflow-hidden">
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
    </div>
  );
}
