import { useEffect, useState } from "react";

// Renders the scorecard the Underwriter harness publishes to /eval-scorecard.json
// (web/public/). Falls back to a stub if no run has been published yet.

interface AxisResult {
  axis: string;
  n: number;
  risk: number;
  ci_low: number;
  ci_high: number;
  kappa: number | null;
  fail_rate: number;
  per_judge_risk: Record<string, number>;
  refusal_rate: number | null;
  over_refusal_rate: number | null;
  hard_leak_rate: number | null;
}
interface ModelResult {
  model: string;
  guard: boolean;
  overall_risk: number;
  insurability_index: number;
  premium_tier: string;
  avg_latency_s: number | null;
  avg_cost_usd: number | null;
  axes: Record<string, AxisResult>;
}
interface GuardrailDelta {
  model: string;
  index_off: number;
  index_on: number;
  delta: number;
}
interface Scorecard {
  generated_at: string;
  mode: string;
  manifest: { judges?: string[]; n_items?: number; git_sha?: string };
  models: ModelResult[];
  frontier: { model: string; insurability_index: number; premium_tier: string; overall_risk: number; avg_cost_usd: number; avg_latency_s: number }[];
  guardrail_delta: GuardrailDelta[];
}

const AXIS_ORDER = ["hallucination", "bias", "safety", "sensitive"];
const AXIS_LABEL: Record<string, string> = {
  hallucination: "Hallucination",
  bias: "Bias & Harmful",
  safety: "Content Safety",
  sensitive: "Sensitive-Data",
};
const short = (m: string) => m.split("/").pop() ?? m;

function tierColor(t: string) {
  return t === "Preferred"
    ? "text-emerald-300"
    : t === "Standard"
      ? "text-sky-300"
      : t === "Substandard"
        ? "text-amber-300"
        : "text-rose-300";
}
function riskBar(risk: number) {
  const pct = Math.round(risk * 100);
  const color = risk <= 0.25 ? "bg-emerald-500" : risk <= 0.5 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
      <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function EvaluationView() {
  const [sc, setSc] = useState<Scorecard | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    fetch("/eval-scorecard.json")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setSc)
      .catch(() => setMissing(true));
  }, []);

  if (missing && !sc) {
    return (
      <div className="flex-1 overflow-y-auto p-6">
        <h1 className="text-lg font-semibold">Evaluation — Underwriter</h1>
        <div className="mt-6 rounded-lg border border-dashed border-slate-800 p-10 text-center text-sm text-slate-600">
          No scorecard published yet. Run{" "}
          <code className="text-slate-400">python -m underwriter.cli demo</code> (synthetic) or{" "}
          <code className="text-slate-400">run</code> (live) to populate this view.
        </div>
      </div>
    );
  }
  if (!sc) return <div className="flex-1 p-6 text-slate-500 text-sm">Loading scorecard…</div>;

  const offModels = sc.models.filter((m) => !m.guard);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Evaluation — Underwriter</h1>
          <p className="text-xs text-slate-500">
            Judges: {(sc.manifest.judges ?? []).map(short).join(" + ")} · N={sc.manifest.n_items}/model ·{" "}
            {new Date(sc.generated_at).toLocaleString()}
          </p>
        </div>
        {sc.mode !== "live" && (
          <span className="rounded-md bg-amber-500/20 text-amber-300 px-2.5 py-1 text-xs font-medium">
            ⚠ synthetic demo data
          </span>
        )}
      </div>

      {/* Insurability ranking */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {sc.frontier
          .slice()
          .sort((a, b) => b.insurability_index - a.insurability_index)
          .map((f) => (
            <div key={f.model} className="rounded-lg border border-slate-800 bg-[#0e131c] p-4">
              <div className="flex items-baseline justify-between">
                <span className="text-sm text-slate-300">{short(f.model)}</span>
                <span className={`text-2xl font-semibold tabular-nums ${tierColor(f.premium_tier)}`}>
                  {f.insurability_index}
                </span>
              </div>
              <div className={`text-xs font-medium ${tierColor(f.premium_tier)}`}>{f.premium_tier}</div>
              <div className="mt-2 text-[11px] text-slate-500 tabular-nums">
                risk {f.overall_risk.toFixed(3)} · ${f.avg_cost_usd.toFixed(4)}/req · {f.avg_latency_s.toFixed(2)}s
              </div>
            </div>
          ))}
      </div>

      {/* Per-axis risk (guardrails off) with judge agreement */}
      <div className="rounded-lg border border-slate-800 bg-[#0e131c] p-4">
        <h2 className="text-sm font-medium mb-3 text-slate-300">Risk by axis (guardrails off)</h2>
        <div className="space-y-4">
          {offModels.map((m) => (
            <div key={m.model}>
              <div className="text-xs text-slate-400 mb-1">{short(m.model)}</div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                {AXIS_ORDER.filter((a) => m.axes[a]).map((a) => {
                  const ax = m.axes[a];
                  return (
                    <div key={a} className="rounded-md border border-slate-800 p-2.5">
                      <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                        <span>{AXIS_LABEL[a]}</span>
                        <span className="tabular-nums">{ax.risk.toFixed(2)}</span>
                      </div>
                      {riskBar(ax.risk)}
                      <div className="mt-1 text-[10px] text-slate-600 tabular-nums">
                        95% CI [{ax.ci_low.toFixed(2)}, {ax.ci_high.toFixed(2)}]
                        {ax.kappa != null && <> · κ={ax.kappa.toFixed(2)}</>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Guardrail uplift */}
      {sc.guardrail_delta.length > 0 && (
        <div className="rounded-lg border border-slate-800 bg-[#0e131c] p-4">
          <h2 className="text-sm font-medium mb-3 text-slate-300">
            Guardrail uplift (insurability index off → on)
          </h2>
          <div className="space-y-2">
            {sc.guardrail_delta.map((d) => (
              <div key={d.model} className="flex items-center gap-3 text-sm">
                <span className="w-48 truncate text-slate-300">{short(d.model)}</span>
                <span className="tabular-nums text-slate-500">{d.index_off}</span>
                <span className="text-slate-600">→</span>
                <span className="tabular-nums text-slate-200">{d.index_on}</span>
                <span
                  className={`tabular-nums font-medium ${d.delta >= 0 ? "text-emerald-300" : "text-rose-300"}`}
                >
                  {d.delta >= 0 ? "+" : ""}
                  {d.delta}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
