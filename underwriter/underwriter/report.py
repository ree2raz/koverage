"""Report generation: a one-page PDF scorecard with infographics, and
publishing the scorecard JSON to the web Evaluation view.

Also builds a clearly-labelled SYNTHETIC scorecard so the PDF and the dashboard
can be demonstrated end-to-end before spending a cent on real API calls. The
synthetic numbers are flagged mode="synthetic-demo" everywhere.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

from .config import AXES, AXIS_LABELS, axis_weights  # noqa: E402
from .results import FrontierPoint, GuardrailDelta, Scorecard  # noqa: E402
from .scoring import AxisResult, ModelResult  # noqa: E402

_PLATFORM = Path(__file__).resolve().parents[2]
_SHORT = {a: AXIS_LABELS[a].split(" (")[0].split(" & ")[0].split(" ")[0] for a in AXES}
_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#38bdf8"]


def _short_model(m: str) -> str:
    return m.split("/")[-1]


def recommendation(scorecard: Scorecard) -> str:
    if not scorecard.frontier:
        return "No results."
    best = max(scorecard.frontier, key=lambda f: f.insurability_index)
    lines = [
        f"Recommendation: {_short_model(best.model)} is the most insurable model under test "
        f"(index {best.insurability_index}/100, tier '{best.premium_tier}'), balancing risk "
        f"against ${best.avg_cost_usd:.4f}/req and {best.avg_latency_s:.2f}s latency."
    ]
    if scorecard.guardrail_delta:
        avg_uplift = sum(d.delta for d in scorecard.guardrail_delta) / len(scorecard.guardrail_delta)
        lines.append(
            f"Enabling the guardrail layer raises the insurability index by {avg_uplift:+.0f} points "
            "on average — the premium reduction a safety layer buys."
        )
    return " ".join(lines)


def generate_pdf(scorecard: Scorecard, out_path: Path) -> Path:
    off = [m for m in scorecard.models if not m.guard]
    on_by_model = {m.model: m for m in scorecard.models if m.guard}

    fig = plt.figure(figsize=(8.5, 11))
    gs = GridSpec(4, 2, figure=fig, height_ratios=[0.7, 1.1, 1.1, 0.9], hspace=0.55, wspace=0.3)
    fig.suptitle("AI Insurability Scorecard", fontsize=18, fontweight="bold", x=0.5, y=0.975)

    # header / manifest
    ax_h = fig.add_subplot(gs[0, :])
    ax_h.axis("off")
    m = scorecard.manifest
    badge = "  ⚠ SYNTHETIC DEMO DATA" if scorecard.mode != "live" else ""
    ax_h.text(
        0, 0.85,
        f"Generated {scorecard.generated_at[:19]}Z{badge}\n"
        f"Models: {', '.join(_short_model(x) for x in m.get('models_under_test', []))}    "
        f"Judges: {', '.join(_short_model(x) for x in m.get('judges', []))}\n"
        f"N={m.get('n_items','?')} prompts/model · seed {m.get('seed','?')} · "
        f"gen T={m.get('gen_temperature','?')} · {m.get('bootstrap_iterations','?')} bootstraps · "
        f"git {m.get('git_sha','?')}",
        fontsize=8.5, va="top", family="monospace",
    )

    # Panel 1: risk per axis per model (guard off), severity-weighted
    ax1 = fig.add_subplot(gs[1, 0])
    _grouped_axis_bars(ax1, off)
    ax1.set_title("Risk by axis (guardrails off)", fontsize=10, fontweight="bold")

    # Panel 2: insurability index, guard off vs on
    ax2 = fig.add_subplot(gs[1, 1])
    _index_bars(ax2, off, on_by_model)
    ax2.set_title("Insurability index (0–100)", fontsize=10, fontweight="bold")

    # Panel 3: guardrail risk reduction per axis
    ax3 = fig.add_subplot(gs[2, 0])
    _guardrail_delta_bars(ax3, scorecard.guardrail_delta)
    ax3.set_title("Guardrail risk reduction (off − on)", fontsize=10, fontweight="bold")

    # Panel 4: cost × latency × risk frontier
    ax4 = fig.add_subplot(gs[2, 1])
    _frontier_scatter(ax4, scorecard.frontier)
    ax4.set_title("Cost × latency × risk", fontsize=10, fontweight="bold")

    # footer: recommendation + threats to validity
    ax_f = fig.add_subplot(gs[3, :])
    ax_f.axis("off")
    ax_f.text(0, 0.95, recommendation(scorecard), fontsize=9, va="top", wrap=True,
              bbox=dict(boxstyle="round", fc="#eef2ff", ec="#c7d2fe"))
    ax_f.text(
        0, 0.30,
        "Threats to validity: LLM-judge scores carry bias (esp. self-preference when a judge grades "
        "its own provider — see per-judge columns and Cohen's κ); N is modest, so CIs are wide; prompts "
        "are English-only and indicative, not a certification.",
        fontsize=7.2, va="top", style="italic", color="#475569", wrap=True,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="pdf", bbox_inches="tight")
    plt.close(fig)
    return out_path


def _grouped_axis_bars(ax, models: list[ModelResult]) -> None:
    import numpy as np

    x = np.arange(len(AXES))
    width = 0.8 / max(1, len(models))
    for i, mr in enumerate(models):
        vals = [mr.axes[a].risk if a in mr.axes else 0 for a in AXES]
        errs = [
            [max(0, mr.axes[a].risk - mr.axes[a].ci_low) if a in mr.axes else 0 for a in AXES],
            [max(0, mr.axes[a].ci_high - mr.axes[a].risk) if a in mr.axes else 0 for a in AXES],
        ]
        ax.bar(x + i * width, vals, width, yerr=errs, capsize=2,
               label=_short_model(mr.model), color=_COLORS[i % len(_COLORS)])
    ax.set_xticks(x + width * (len(models) - 1) / 2)
    ax.set_xticklabels([_SHORT[a] for a in AXES], fontsize=7.5, rotation=15)
    ax.set_ylabel("risk (0–1, ↓ better)", fontsize=8)
    ax.set_ylim(0, 1)
    ax.legend(fontsize=7)


def _index_bars(ax, off: list[ModelResult], on_by_model: dict[str, ModelResult]) -> None:
    import numpy as np

    labels = [_short_model(m.model) for m in off]
    x = np.arange(len(off))
    ax.bar(x - 0.2, [m.insurability_index for m in off], 0.4, label="guard off", color="#94a3b8")
    ax.bar(x + 0.2, [on_by_model[m.model].insurability_index if m.model in on_by_model else 0 for m in off],
           0.4, label="guard on", color="#6366f1")
    for tier, y in [("Preferred", 85), ("Standard", 70), ("Substandard", 55)]:
        ax.axhline(y, ls="--", lw=0.6, color="#cbd5e1")
        ax.text(len(off) - 0.5, y + 0.5, tier, fontsize=6, color="#64748b", ha="right")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.5, rotation=15)
    ax.set_ylim(0, 100)
    ax.legend(fontsize=7)


def _guardrail_delta_bars(ax, deltas: list[GuardrailDelta]) -> None:
    import numpy as np

    if not deltas:
        ax.axis("off")
        ax.text(0.5, 0.5, "no guardrail comparison", ha="center", fontsize=8, color="#94a3b8")
        return
    x = np.arange(len(AXES))
    width = 0.8 / max(1, len(deltas))
    for i, d in enumerate(deltas):
        vals = [d.axis_risk_delta.get(a, 0) for a in AXES]
        ax.bar(x + i * width, vals, width, label=_short_model(d.model), color=_COLORS[i % len(_COLORS)])
    ax.axhline(0, lw=0.6, color="#475569")
    ax.set_xticks(x + width * (len(deltas) - 1) / 2)
    ax.set_xticklabels([_SHORT[a] for a in AXES], fontsize=7.5, rotation=15)
    ax.set_ylabel("risk reduction ↑", fontsize=8)
    ax.legend(fontsize=7)


def _frontier_scatter(ax, frontier: list[FrontierPoint]) -> None:
    if not frontier:
        ax.axis("off")
        return
    for i, p in enumerate(frontier):
        ax.scatter(p.avg_latency_s, p.avg_cost_usd, s=120 + 600 * p.overall_risk,
                   color=_COLORS[i % len(_COLORS)], alpha=0.65, edgecolors="white")
        ax.annotate(f"{_short_model(p.model)}\n{p.insurability_index} · {p.premium_tier}",
                    (p.avg_latency_s, p.avg_cost_usd), fontsize=6.5,
                    textcoords="offset points", xytext=(6, 6))
    ax.set_xlabel("avg latency (s)", fontsize=8)
    ax.set_ylabel("avg cost ($/req)", fontsize=8)
    ax.text(0.98, 0.02, "bubble size ∝ risk", transform=ax.transAxes, fontsize=6.5,
            ha="right", color="#64748b")


def publish_scorecard(scorecard: Scorecard, web_public: Path | None = None) -> Path:
    target = (web_public or (_PLATFORM / "web" / "public")) / "eval-scorecard.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(scorecard.model_dump_json(indent=2))
    return target


# ── synthetic demo data (clearly flagged; for pipeline/UI verification only) ──
def _axis(axis: str, risk: float, kappa: float, judges: dict[str, float], **extra) -> AxisResult:
    return AxisResult(
        axis=axis, n=15, risk=risk, ci_low=max(0, risk - 0.08), ci_high=min(1, risk + 0.08),
        fail_rate=round(risk * 0.9, 3), kappa=kappa, per_judge_risk=judges, **extra,
    )


def synthetic_scorecard() -> Scorecard:
    j = ["openai/gpt-4.1", "google/gemini-2.5-pro"]

    def model(name, guard, profile, lat, cost):
        axes = {
            "hallucination": _axis("hallucination", profile[0], 0.71, {j[0]: profile[0] - 0.03, j[1]: profile[0] + 0.03}),
            "bias": _axis("bias", profile[1], 0.64, {j[0]: profile[1], j[1]: profile[1] + 0.02}),
            "safety": _axis("safety", profile[2], 0.78, {j[0]: profile[2], j[1]: profile[2] + 0.01},
                            refusal_rate=round(1 - profile[2], 2), over_refusal_rate=0.2 if guard else 0.0),
            "sensitive": _axis("sensitive", profile[3], 0.82, {j[0]: profile[3], j[1]: profile[3]},
                               hard_leak_rate=round(profile[3] * 0.5, 2)),
        }
        w = axis_weights()
        risk = round(sum(axes[a].risk * w[a] for a in axes), 4)
        idx = round(100 * (1 - risk))
        from .scoring import premium_tier

        return ModelResult(model=name, guard=guard, n_items=60, axes=axes, overall_risk=risk,
                           insurability_index=idx, premium_tier=premium_tier(idx),
                           avg_latency_s=lat, avg_cost_usd=cost)

    models = [
        model("openai/gpt-4.1", False, [0.12, 0.10, 0.18, 0.09], 1.9, 0.0042),
        model("openai/gpt-4.1", True, [0.10, 0.08, 0.06, 0.03], 2.0, 0.0044),
        model("google/gemma-3n-e4b-it", False, [0.34, 0.27, 0.41, 0.30], 0.8, 0.0),
        model("google/gemma-3n-e4b-it", True, [0.30, 0.22, 0.18, 0.10], 0.9, 0.0),
    ]
    sc = Scorecard(
        generated_at=datetime.now(timezone.utc).isoformat(), mode="synthetic-demo",
        manifest={"models_under_test": ["openai/gpt-4.1", "google/gemma-3n-e4b-it"], "judges": j,
                  "n_items": 60, "seed": 7, "gen_temperature": 0.0, "bootstrap_iterations": 1000,
                  "git_sha": "demo"},
        axis_weights=axis_weights(), models=models,
    )
    by_off = {m.model: m for m in models if not m.guard}
    by_on = {m.model: m for m in models if m.guard}
    sc.frontier = [FrontierPoint(model=m.model, avg_cost_usd=m.avg_cost_usd or 0,
                                 avg_latency_s=m.avg_latency_s or 0, overall_risk=m.overall_risk,
                                 insurability_index=m.insurability_index, premium_tier=m.premium_tier)
                   for m in by_off.values()]
    sc.guardrail_delta = [
        GuardrailDelta(model=mm, index_off=by_off[mm].insurability_index,
                       index_on=by_on[mm].insurability_index,
                       delta=by_on[mm].insurability_index - by_off[mm].insurability_index,
                       risk_off=by_off[mm].overall_risk, risk_on=by_on[mm].overall_risk,
                       axis_risk_delta={a: round(by_off[mm].axes[a].risk - by_on[mm].axes[a].risk, 4)
                                        for a in by_off[mm].axes})
        for mm in by_off
    ]
    return sc
