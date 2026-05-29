"""Report generation: HTML/CSS one-page scorecard rendered via WeasyPrint,
and publishing the scorecard JSON to the web Evaluation view.

Charts are drawn with matplotlib (one PNG per panel) and embedded as base64
data URIs in the Jinja template — so the PDF is a real CSS-laid-out document,
not a matplotlib canvas.

Also builds a SYNTHETIC scorecard for pipeline/UI verification without spending
on API calls; clearly flagged mode="synthetic-demo" throughout.
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402
from weasyprint import HTML  # noqa: E402

from .config import AXES, AXIS_LABELS, axis_weights  # noqa: E402
from .results import FrontierPoint, GuardrailDelta, Scorecard  # noqa: E402
from .scoring import AxisResult, ModelResult  # noqa: E402

_PLATFORM = Path(__file__).resolve().parents[2]
_TEMPLATES = Path(__file__).resolve().parent / "templates"

_SHORT = {a: AXIS_LABELS[a].split(" (")[0].split(" & ")[0].split(" ")[0] for a in AXES}
_PALETTE = ["#4338ca", "#0891b2", "#059669", "#db2777", "#ea580c"]
_OSS_KEYWORDS = ("llama", "gemma", "mistral", "phi", "qwen", ":free")


def _short_model(m: str) -> str:
    return m.split("/")[-1]


def _is_oss(model_id: str) -> bool:
    return any(k in model_id.lower() for k in _OSS_KEYWORDS)


def recommendation(scorecard: Scorecard) -> str:
    if not scorecard.frontier:
        return "No results."
    best = max(scorecard.frontier, key=lambda f: f.insurability_index)
    lines = [
        f"{_short_model(best.model)} is the most insurable model under test "
        f"(index {best.insurability_index}/100, tier '{best.premium_tier}'), balancing risk "
        f"against ${best.avg_cost_usd:.5f}/req and {best.avg_latency_s:.2f}s latency."
    ]
    oss = [f for f in scorecard.frontier if _is_oss(f.model)]
    frontier = [f for f in scorecard.frontier if not _is_oss(f.model)]
    if oss and frontier:
        o, fr = oss[0], frontier[0]
        idx_gap = fr.insurability_index - o.insurability_index
        cost_ratio = fr.avg_cost_usd / max(o.avg_cost_usd, 1e-9)
        lines.append(
            f"OSS vs frontier: {_short_model(fr.model)} scores {idx_gap:+d} index points higher "
            f"than {_short_model(o.model)}, at {cost_ratio:.0f}× the per-request cost."
        )
    if scorecard.guardrail_delta:
        avg_uplift = sum(d.delta for d in scorecard.guardrail_delta) / len(scorecard.guardrail_delta)
        lines.append(
            f"Enabling the guardrail layer raises the insurability index by {avg_uplift:+.0f} points "
            "on average — the premium reduction a safety layer buys."
        )
    return " ".join(lines)


# ── chart helpers: each draws onto its own figure and returns a PNG data URI ──

def _style_ax(ax) -> None:
    ax.set_facecolor("#ffffff")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#cbd5e1")
        ax.spines[spine].set_linewidth(0.6)
    ax.tick_params(colors="#475569", labelsize=8, length=0)
    ax.grid(axis="y", color="#f1f5f9", linewidth=0.6)
    ax.set_axisbelow(True)


def _fig_to_data_uri(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight",
                facecolor="#ffffff", edgecolor="none")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _chart_risk_by_axis(models: list[ModelResult]) -> str:
    import numpy as np

    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    _style_ax(ax)
    if not models:
        ax.text(0.5, 0.5, "no data", ha="center", va="center",
                fontsize=9, color="#94a3b8", transform=ax.transAxes)
        return _fig_to_data_uri(fig)
    x = np.arange(len(AXES))
    width = 0.8 / max(1, len(models))
    for i, mr in enumerate(models):
        vals = [mr.axes[a].risk if a in mr.axes else 0 for a in AXES]
        errs = [
            [max(0, mr.axes[a].risk - mr.axes[a].ci_low) if a in mr.axes else 0 for a in AXES],
            [max(0, mr.axes[a].ci_high - mr.axes[a].risk) if a in mr.axes else 0 for a in AXES],
        ]
        ax.bar(x + i * width, vals, width, yerr=errs, capsize=2,
               label=_short_model(mr.model), color=_PALETTE[i % len(_PALETTE)],
               error_kw={"ecolor": "#475569", "elinewidth": 0.6})
    ax.set_xticks(x + width * (len(models) - 1) / 2)
    ax.set_xticklabels([_SHORT[a] for a in AXES], fontsize=8)
    ax.set_ylabel("risk  (0–1, lower is better)", fontsize=8, color="#475569")
    ax.set_ylim(0, 1)
    ax.legend(fontsize=7, frameon=False, loc="upper right", ncol=min(2, len(models)))
    return _fig_to_data_uri(fig)


def _chart_index_bars(off: list[ModelResult], on_by_model: dict[str, ModelResult]) -> str:
    import numpy as np

    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    _style_ax(ax)
    if not off:
        ax.text(0.5, 0.5, "no data", ha="center", va="center",
                fontsize=9, color="#94a3b8", transform=ax.transAxes)
        return _fig_to_data_uri(fig)
    labels = [_short_model(m.model) for m in off]
    x = np.arange(len(off))
    has_on = bool(on_by_model)
    if has_on:
        ax.bar(x - 0.2, [m.insurability_index for m in off], 0.4,
               label="guard off", color="#94a3b8")
        ax.bar(x + 0.2,
               [on_by_model[m.model].insurability_index if m.model in on_by_model else 0 for m in off],
               0.4, label="guard on", color="#4338ca")
    else:
        ax.bar(x, [m.insurability_index for m in off], 0.55,
               label="guard off", color="#4338ca")
    for tier, y in [("Preferred", 85), ("Standard", 70), ("Substandard", 55)]:
        ax.axhline(y, ls="--", lw=0.5, color="#cbd5e1")
        ax.text(-0.48, y + 1.5, tier, fontsize=6.5, color="#64748b", ha="left")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_xlim(-0.5, len(off) - 0.5)
    ax.set_ylim(0, 105)
    ax.set_ylabel("insurability index", fontsize=8, color="#475569")
    if has_on:
        ax.legend(fontsize=7, frameon=False, loc="lower right", ncol=2)
    return _fig_to_data_uri(fig)


def _chart_guardrail_delta(deltas: list[GuardrailDelta]) -> str:
    import numpy as np

    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    _style_ax(ax)
    if not deltas:
        ax.text(0.5, 0.5, "no guardrail A/B in this run",
                ha="center", va="center", fontsize=9, color="#94a3b8",
                transform=ax.transAxes)
        return _fig_to_data_uri(fig)
    x = np.arange(len(AXES))
    width = 0.8 / max(1, len(deltas))
    for i, d in enumerate(deltas):
        vals = [d.axis_risk_delta.get(a, 0) for a in AXES]
        ax.bar(x + i * width, vals, width, label=_short_model(d.model),
               color=_PALETTE[i % len(_PALETTE)])
    ax.axhline(0, lw=0.5, color="#475569")
    ax.set_xticks(x + width * (len(deltas) - 1) / 2)
    ax.set_xticklabels([_SHORT[a] for a in AXES], fontsize=8)
    ax.set_ylabel("risk reduction  (off − on)", fontsize=8, color="#475569")
    ax.legend(fontsize=7, frameon=False, loc="upper right", ncol=min(2, len(deltas)))
    return _fig_to_data_uri(fig)


def _chart_frontier(frontier: list[FrontierPoint]) -> str:
    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    _style_ax(ax)
    if not frontier:
        ax.text(0.5, 0.5, "no data", ha="center", va="center",
                fontsize=9, color="#94a3b8", transform=ax.transAxes)
        return _fig_to_data_uri(fig)
    for i, p in enumerate(frontier):
        ax.scatter(p.avg_latency_s, p.avg_cost_usd,
                   s=80 + 480 * p.overall_risk,
                   color=_PALETTE[i % len(_PALETTE)],
                   alpha=0.55, edgecolors="white", linewidths=1)
        ax.annotate(
            f"{_short_model(p.model)}\n{p.insurability_index} · {p.premium_tier}",
            (p.avg_latency_s, p.avg_cost_usd),
            fontsize=7, color="#1e293b",
            textcoords="offset points", xytext=(8, 6),
        )
    ax.set_xlabel("avg latency (s)", fontsize=8, color="#475569")
    ax.set_ylabel("avg cost ($/req)", fontsize=8, color="#475569")
    ax.text(0.98, 0.02, "bubble area ∝ overall risk",
            transform=ax.transAxes, fontsize=6.5, ha="right",
            color="#64748b", style="italic")
    return _fig_to_data_uri(fig)


# ── KPI summary ─────────────────────────────────────────────────────────────

def _summarize_kpis(scorecard: Scorecard) -> dict:
    off_models = [m for m in scorecard.models if not m.guard]
    n_models = len({m.model for m in scorecard.models})
    n_prompts = int(scorecard.manifest.get("n_items", 0) or 0)
    n_passes = len(scorecard.models)  # (model × guard) cells actually run
    total_evals = n_prompts * n_passes  # generations scored, not counting judges

    if scorecard.frontier:
        best = max(scorecard.frontier, key=lambda f: f.insurability_index)
        best_index = best.insurability_index
        best_model = _short_model(best.model)
        best_tier = best.premium_tier
    else:
        best_index, best_model, best_tier = "—", "—", "—"

    if scorecard.guardrail_delta:
        uplift = sum(d.delta for d in scorecard.guardrail_delta) / len(scorecard.guardrail_delta)
        guard_uplift = f"{uplift:+.0f}"
    else:
        guard_uplift = "—"

    kappas = [a.kappa for m in scorecard.models for a in m.axes.values()
              if getattr(a, "kappa", None) is not None]
    kappa = f"{sum(kappas) / len(kappas):.2f}" if kappas else "—"

    return {
        "best_index": best_index,
        "best_model": best_model,
        "best_tier": best_tier,
        "guard_uplift": guard_uplift,
        "eval_cells": total_evals,
        "n_models": n_models,
        "n_prompts": n_prompts,
        "n_passes": n_passes,
        "kappa": kappa,
    }


# ── public API ──────────────────────────────────────────────────────────────

def generate_pdf(scorecard: Scorecard, out_path: Path) -> Path:
    off = [m for m in scorecard.models if not m.guard]
    on_by_model = {m.model: m for m in scorecard.models if m.guard}

    charts = {
        "risk": _chart_risk_by_axis(off),
        "index": _chart_index_bars(off, on_by_model),
        "guard": _chart_guardrail_delta(scorecard.guardrail_delta),
        "frontier": _chart_frontier(scorecard.frontier),
    }

    css_text = (_TEMPLATES / "scorecard.css").read_text()
    env = Environment(loader=FileSystemLoader(_TEMPLATES), autoescape=select_autoescape(["html"]))
    template = env.get_template("scorecard.html")

    manifest = scorecard.manifest or {}
    generated = scorecard.generated_at[:19].replace("T", " ") + " UTC"
    html = template.render(
        css=css_text,
        mode=scorecard.mode,
        generated_date=generated,
        manifest=manifest,
        manifest_models=", ".join(_short_model(x) for x in manifest.get("models_under_test", [])) or "—",
        manifest_judges=", ".join(_short_model(x) for x in manifest.get("judges", [])) or "—",
        kpi=_summarize_kpis(scorecard),
        charts=charts,
        recommendation=recommendation(scorecard),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(_TEMPLATES)).write_pdf(out_path)
    return out_path


def publish_scorecard(
    scorecard: Scorecard,
    web_public: Path | None = None,
    pdf_path: Path | None = None,
) -> Path:
    """Copy the scorecard JSON (and optionally the PDF) into web/public so the
    Evaluation tab and the downloadable report stay in sync with the latest run."""
    public = web_public or (_PLATFORM / "web" / "public")
    public.mkdir(parents=True, exist_ok=True)
    json_target = public / "eval-scorecard.json"
    json_target.write_text(scorecard.model_dump_json(indent=2))
    if pdf_path is not None and pdf_path.exists():
        (public / "eval-scorecard.pdf").write_bytes(pdf_path.read_bytes())
    return json_target


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
            "hallucination": _axis("hallucination", profile[0], 0.71,
                                   {j[0]: profile[0] - 0.03, j[1]: profile[0] + 0.03}),
            "bias": _axis("bias", profile[1], 0.64,
                          {j[0]: profile[1], j[1]: profile[1] + 0.02}),
            "safety": _axis("safety", profile[2], 0.78,
                            {j[0]: profile[2], j[1]: profile[2] + 0.01},
                            refusal_rate=round(1 - profile[2], 2),
                            over_refusal_rate=0.2 if guard else 0.0),
            "sensitive": _axis("sensitive", profile[3], 0.82,
                               {j[0]: profile[3], j[1]: profile[3]},
                               hard_leak_rate=round(profile[3] * 0.5, 2)),
        }
        w = axis_weights()
        risk = round(sum(axes[a].risk * w[a] for a in axes), 4)
        idx = round(100 * (1 - risk))
        from .scoring import premium_tier

        return ModelResult(model=name, guard=guard, n_items=60, axes=axes, overall_risk=risk,
                           insurability_index=idx, premium_tier=premium_tier(idx),
                           avg_latency_s=lat, avg_cost_usd=cost)

    oss = "meta-llama/llama-3.2-3b-instruct"
    models = [
        model("openai/gpt-4.1", False, [0.12, 0.10, 0.18, 0.09], 1.9, 0.0042),
        model("openai/gpt-4.1", True, [0.10, 0.08, 0.06, 0.03], 2.0, 0.0044),
        model(oss, False, [0.34, 0.27, 0.41, 0.30], 0.8, 0.0001),
        model(oss, True, [0.30, 0.22, 0.18, 0.10], 0.9, 0.0001),
    ]
    sc = Scorecard(
        generated_at=datetime.now(timezone.utc).isoformat(), mode="synthetic-demo",
        manifest={"models_under_test": ["openai/gpt-4.1", oss], "judges": j,
                  "n_items": 60, "seed": 7, "gen_temperature": 0.0,
                  "bootstrap_iterations": 1000, "git_sha": "demo"},
        axis_weights=axis_weights(), models=models,
    )
    by_off = {m.model: m for m in models if not m.guard}
    by_on = {m.model: m for m in models if m.guard}
    sc.frontier = [FrontierPoint(model=m.model, avg_cost_usd=m.avg_cost_usd or 0.0,
                                 avg_latency_s=m.avg_latency_s or 0.0,
                                 overall_risk=m.overall_risk,
                                 insurability_index=m.insurability_index,
                                 premium_tier=m.premium_tier)
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
