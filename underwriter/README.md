# Underwriter: LLM evaluation as AI insurability scoring

Evaluates models on the risks an AI liability insurer underwrites, then prices
an **Insurability Index** and premium tier.

| Axis | What it measures | Suite |
| --- | --- | --- |
| **Hallucination** | factual accuracy + resistance to confabulation (false-premise traps) | `factual` |
| **Bias & Harmful** | stereotyping, harmful generalisations, demeaning content | `bias` |
| **Content Safety** | jailbreak resistance **and over-refusal** (benign controls) | `jailbreak` |
| **Sensitive-Data Disclosure** | system-prompt / token / PII leakage | `sensitive` |

## How it scores (the short version)
- **Hybrid**: deterministic detectors (refusal, false-premise, PII/sentinel leak: leak detection reuses Beacon's `llmobs` redactor) **+** dual cross-provider LLM judges (GPT-4.1 + Gemini). Deterministic signals can override the judge (a leaked card number is a leak regardless of judge opinion).
- **Dual judges + Cohen's κ**: both judges score every item on an anchored 0–4 rubric; we report per-judge risk and inter-rater agreement, and never let a model be its own sole judge.
- **Severity-weighted** risk per axis with **bootstrap 95% CIs**.
- **Guardrail A/B**: every model runs guardrails-off and guardrails-on; the index delta is the risk reduction the guardrail buys.
- **Insurability Index** = 100·(1 − weighted overall risk) → premium tier (Preferred / Standard / Substandard / Decline).
- Full rationale + limitations: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Run it
```bash
uv sync
cp ../.env.example ../.env          # set OPENROUTER_API_KEY (reaches judges + frontier models)

# offline: synthetic scorecard → 1-page PDF + publishes to the web Evaluation view
uv run python -m underwriter.cli demo

# cheap live sanity check (2 prompts/suite, guard off)
uv run python -m underwriter.cli run --smoke

# full live evaluation (all suites, guard off+on, dual judges) → runs/<ts>/{scorecard.json,pdf}
uv run python -m underwriter.cli run
```
The OSS model (Qwen3-8B, self-hosted on Modal/vLLM) joins the run matrix
automatically once `MODAL_OSS_URL` is set; until then the harness runs on the
configured frontier models. If the Modal endpoint is unreachable it falls back to
`qwen/qwen3-8b` on OpenRouter so the run still completes.

## Offline tests (no API)
```bash
uv run pytest underwriter/tests
```
Covers the detectors, the risk-model overrides, and the statistics (weighted mean,
bootstrap CI, Cohen's κ, premium tiers): judge verdicts are fixtures.

## Layout
`datasets/` suites + cards · `scoring/` deterministic + judge + combine + aggregate ·
`guardrails.py` toggleable layer · `runner.py` run matrix · `report.py` PDF + publish · `cli.py`.
