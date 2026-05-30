"""The run matrix: {models} × {guardrail off, on} × suites.

Every cell runs the identical assistant scaffold (system prompt, memory, params)
through the shared core, so differences are the model's (or the guardrail's),
not the harness's. Generation + dual-judge scoring fan out across a thread pool.
Every raw response and judge rationale is written to a timestamped run dir for
auditability and reproducibility.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import openai

from llmcore import Assistant, Memory, Router, cost_usd
from llmcore.types import Message, ModelBackend, Role

from .config import axis_weights, settings
from .datasets import EVAL_SYSTEM_PROMPT, PromptItem, load_cards, load_suites
from .guardrails import Guardrail, build_guardrail
from .results import FrontierPoint, GuardrailDelta, Scorecard
from .scoring import DualJudge, ItemScore, ModelResult, aggregate_model, combine


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _models_under_test() -> list[str]:
    models = [m.strip() for m in settings.models_under_test.split(",") if m.strip()]
    if settings.modal_oss_url:
        # Run OSS FIRST. The first call doubles as the cold-start warm-up; by the
        # time we move to frontier models, the OSS container's GPU is free for the
        # keep-alive thread to maintain. If we ran OSS last, it would be cold by
        # then and the run would race the GPU reload.
        models.insert(0, settings.oss_model)
    return models


def _spawn_oss_keepalive(router: Router, interval_s: float = 60.0) -> threading.Event:
    """Daemon that pings the OSS container every `interval_s` so the Modal host
    doesn't scale to zero during the long frontier passes. Returns a stop event
    the caller sets when the run completes. No-op when OSS is not configured.
    """
    stop = threading.Event()
    if not settings.modal_oss_url:
        return stop
    try:
        backend = router.backend_for(settings.oss_model)
    except Exception:
        return stop
    if getattr(backend, "provider", "") != "oss":
        return stop

    def loop() -> None:
        # immediate first ping — kicks the cold-start in parallel with run setup
        while True:
            try:
                backend.generate([Message(role=Role.USER, content="ping")], max_tokens=4)
            except Exception:
                pass  # best-effort; main thread's retries handle real failures
            if stop.wait(interval_s):
                return

    threading.Thread(target=loop, daemon=True, name="oss-keepalive").start()
    print(
        f"  [oss] routing {settings.oss_model} via Modal; "
        f"keep-alive every {interval_s:.0f}s"
    )
    return stop


def _resolve_oss_backend(router: Router, model: str) -> tuple[str, ModelBackend]:
    """For the Modal OSS model, ping the endpoint with a tiny prompt; if it raises
    after the backend's own retries are exhausted, swap to the OpenRouter fallback
    so the full eval still completes. No-op for non-OSS models.
    """
    backend = router.backend_for(model)
    if getattr(backend, "provider", "") != "oss" or model != settings.oss_model:
        return model, backend
    try:
        backend.generate([Message(role=Role.USER, content="ping")], max_tokens=4)
        return model, backend
    except Exception as exc:
        fb = settings.oss_fallback_model
        print(
            f"  [oss] Modal endpoint '{model}' unreachable ({type(exc).__name__}); "
            f"falling back to OpenRouter '{fb}' for this run",
            flush=True,
        )
        return fb, router.backend_for(fb)


def _with_rate_limit_retry(fn, max_retries: int = 6, base_delay: float = 15.0):
    """Retry fn on 429 RateLimitError with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return fn()
        except openai.RateLimitError:
            if attempt == max_retries - 1:
                raise
            wait = base_delay * (2 ** attempt)
            print(f"  [rate limit] sleeping {wait:.0f}s before retry {attempt + 1}/{max_retries}")
            time.sleep(wait)


def _run_item(
    backend: ModelBackend,
    item: PromptItem,
    model: str,
    guardrail: Guardrail | None,
    judges: DualJudge,
) -> tuple[ItemScore, float, float]:
    assistant = Assistant(
        backend=backend,
        memory=Memory(EVAL_SYSTEM_PROMPT),
        tools=[],
        guardrail=guardrail,
        gen_params={
            "temperature": settings.gen_temperature,
            "max_tokens": settings.gen_max_tokens,
            "seed": settings.seed,
        },
    )
    latency = cost = 0.0
    final_text = ""
    for turn in item.user_turns():
        reply = _with_rate_limit_retry(lambda t=turn: assistant.chat(t))
        final_text = reply.text
        latency += reply.latency_s
        cost += sum(
            cost_usd(model, r.usage.prompt_tokens, r.usage.completion_tokens) for r in reply.responses
        )
    verdicts = judges.score(item, final_text)
    score = combine(item, final_text, verdicts)
    return score, latency, cost


def run(
    *,
    models: list[str] | None = None,
    guard_options: tuple[bool, ...] = (False, True),
    suites: list[str] | None = None,
    n_per_suite: int | None = None,
    out_dir: Path | None = None,
) -> tuple[Scorecard, Path]:
    models = models or _models_under_test()
    items = load_suites(suites, n_per_suite)
    router = Router()
    judges = DualJudge(settings.judge_a, settings.judge_b, router=router,
                       temperature=settings.judge_temperature)
    weights = axis_weights()

    ts = datetime.now(timezone.utc)
    run_dir = out_dir or (Path(__file__).resolve().parent.parent / "runs" / ts.strftime("%Y%m%dT%H%M%SZ"))
    run_dir.mkdir(parents=True, exist_ok=True)
    gen_f = (run_dir / "scores.jsonl").open("w")

    # background keep-alive so the Modal endpoint doesn't go cold mid-run
    keepalive_stop = _spawn_oss_keepalive(router)

    results: list[ModelResult] = []
    resolved_models: list[str] = []
    for original_model in models:
        model, backend = _resolve_oss_backend(router, original_model)
        resolved_models.append(model)
        for guard in guard_options:
            guardrail = build_guardrail() if guard else None
            scores: list[ItemScore] = []
            latencies: list[float] = []
            costs: list[float] = []
            t0 = time.perf_counter()
            with ThreadPoolExecutor(max_workers=settings.concurrency) as ex:
                futures = [
                    ex.submit(_run_item, backend, item, model, guardrail, judges) for item in items
                ]
                for fut in as_completed(futures):
                    score, lat, cost = fut.result()
                    scores.append(score)
                    latencies.append(lat)
                    costs.append(cost)
                    rec = score.model_dump()
                    rec.update({"model": model, "guard": guard})
                    gen_f.write(json.dumps(rec, default=str) + "\n")
            mr = aggregate_model(
                model, guard, scores, axis_weights=weights,
                iterations=settings.bootstrap_iterations, seed=settings.seed,
                latencies=latencies, costs=costs,
            )
            results.append(mr)
            print(
                f"  {model:32} guard={'on ' if guard else 'off'}  "
                f"index={mr.insurability_index:3d} ({mr.premium_tier})  "
                f"risk={mr.overall_risk:.3f}  {time.perf_counter() - t0:.1f}s"
            )
    gen_f.close()
    keepalive_stop.set()

    scorecard = _build_scorecard(results, weights, ts, resolved_models, judges, items)
    (run_dir / "scorecard.json").write_text(scorecard.model_dump_json(indent=2))
    _write_manifest(run_dir, scorecard)
    print(f"\nrun written → {run_dir}")
    return scorecard, run_dir


def _build_scorecard(results, weights, ts, models, judges, items) -> Scorecard:
    by_off = {r.model: r for r in results if not r.guard}
    by_on = {r.model: r for r in results if r.guard}

    frontier = [
        FrontierPoint(
            model=r.model, avg_cost_usd=r.avg_cost_usd or 0.0, avg_latency_s=r.avg_latency_s or 0.0,
            overall_risk=r.overall_risk, insurability_index=r.insurability_index,
            premium_tier=r.premium_tier,
        )
        for r in by_off.values()
    ]

    deltas = []
    for model, off in by_off.items():
        on = by_on.get(model)
        if not on:
            continue
        axis_delta = {
            ax: round(off.axes[ax].risk - on.axes[ax].risk, 4)
            for ax in off.axes
            if ax in on.axes
        }
        deltas.append(GuardrailDelta(
            model=model, index_off=off.insurability_index, index_on=on.insurability_index,
            delta=on.insurability_index - off.insurability_index,
            risk_off=off.overall_risk, risk_on=on.overall_risk, axis_risk_delta=axis_delta,
        ))

    manifest = {
        "generated_at": ts.isoformat(),
        "git_sha": _git_sha(),
        "models_under_test": models,
        "judges": list(judges.names),
        "n_items": len(items),
        "gen_temperature": settings.gen_temperature,
        "judge_temperature": settings.judge_temperature,
        "seed": settings.seed,
        "bootstrap_iterations": settings.bootstrap_iterations,
    }
    return Scorecard(
        generated_at=ts.isoformat(), mode="live", manifest=manifest,
        cards=[c.model_dump() for c in load_cards()], axis_weights=weights,
        models=results, frontier=frontier, guardrail_delta=deltas,
    )


def _write_manifest(run_dir: Path, scorecard: Scorecard) -> None:
    (run_dir / "manifest.json").write_text(json.dumps(scorecard.manifest, indent=2, default=str))
