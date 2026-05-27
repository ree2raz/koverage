// Placeholder shell for the Underwriter evaluation module (Phase 3). Once the
// eval harness writes its scorecard JSON, this view renders the per-model risk
// scores (hallucination / bias / safety), the insurability index, and the
// cost × latency × risk frontier. Kept as a clear stub so the navigation and
// product story are complete now.

const AXES = [
  ["Hallucination", "Does the model state false facts with confidence?"],
  ["Bias & harmful output", "Does it produce biased or harmful content?"],
  ["Content safety", "Does it resist jailbreaks and refuse unsafe requests?"],
];

export default function EvaluationView() {
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Evaluation — Underwriter</h1>
        <p className="text-xs text-slate-500">
          Scores the same models on the risks an AI insurer underwrites, then prices an
          insurability index. Wired in Phase 3.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {AXES.map(([title, desc]) => (
          <div key={title} className="rounded-lg border border-slate-800 bg-[#0e131c] p-4">
            <div className="text-sm font-medium text-slate-200">{title}</div>
            <p className="mt-1 text-xs text-slate-500">{desc}</p>
            <div className="mt-3 h-2 rounded-full bg-slate-800 overflow-hidden">
              <div className="h-full w-0 bg-emerald-500" />
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-dashed border-slate-800 p-10 text-center text-sm text-slate-600">
        Run the Underwriter harness (Phase 3) to populate the scorecard, dual-judge agreement,
        guardrail risk-delta, and the cost × latency × risk frontier.
      </div>
    </div>
  );
}
