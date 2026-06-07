# Suite Expansion Plan: N > 150 per axis

**Goal.** Raise every axis above `min_n_per_axis = 150` with **real, verified-label,
commercially-licensed** items so the power gate stops capping every cell at
Substandard. No synthetic generation, no filtering on a model that's in the priced
matrix (that re-introduces the circularity Fix D removed).

**Current state (the problem):**

| Suite     | Axis          | Items | ≥150? |
| --------- | ------------- | ----- | ----- |
| factual   | hallucination | 30    | ❌    |
| bias      | bias          | 30    | ❌    |
| jailbreak | safety        | 30    | ❌    |
| sensitive | sensitive     | 23    | ❌    |

All four fire `power_warning`. "Preferred"/"Standard" are unreachable today.

---

## Non-negotiable principles

1. **Effective N, not row count.** Counterfactual variants and paraphrase clusters
   count as ~1 independent item. The power gate must see _independent_ items. Where
   a dataset is clustered (Discrim-Eval: 70 scenarios × 135 identities), the unit of
   independence is the scenario.
2. **No circular filtering.** Never select items by "Qwen-8B fails it" — Qwen3-8B is
   priced. Difficulty filtering, if any, uses a model _outside_ the matrix.
3. **License is a hard gate.** Only Apache-2.0 / MIT / CC-BY-4.0 / BSD into the
   priced corpus. (BBQ, OR-Bench, Discrim-Eval, FreshQA, HaluEval, MedMCQA all pass —
   verified.)
4. **Contamination handling, not a made-up discount.** Prefer held-out/rotating;
   pin a dated snapshot per run for reproducibility; if discounting, derive it on
   our own models, don't invent a percentage.
5. **One scoring estimator per axis across the whole matrix** (see logprob note).

---

## The logprob constraint (decides scoring per axis)

Matrix is mixed:

- **Modal-hosted OSS** (gemma, qwen3) → logprobs available.
- **OpenRouter closed** (GPT, Claude) → no reliable logprobs.

Rule: **never mix estimators within an axis.** A metric computed via logits for some
cells and via sampling for others is not comparable, so it can't rank models for
pricing. Consequence: prefer datasets whose scoring is **generation- or
match-based** (works on every cell) for the N-bearing primary set, and treat
logprob-native datasets (Discrim-Eval) as a sampled-decision-rate secondary layer.

---

## Per-axis plan

### Axis: hallucination (suite `factual`) → target ≥ 175

- **Primary: HaluEval** (MIT) — general QA/dialogue/summarization hallucination,
  generation-scored against a reference → works on all cells. Sample a clean,
  deduped subset (~150) + keep the 30 hand-written false-premise traps.
- **Medical layer: MedMCQA** (Apache-2.0) — A/B/C/D, deterministic match, no
  logprobs. Hold out a fresh subset (contamination control). Map liability framing
  (wrong answer = clinical/financial misadvice). ~50 items.
- **Contamination-resistant spike: FreshQA** (Apache-2.0) — rotating; pin a dated
  snapshot per run. ~40 items.
- **Scoring:** judge + reference match (existing dual-judge path); MedMCQA
  deterministic. Keep our existing false-premise detector for the traps.
- **Effective N:** ~240 independent. ✅

### Axis: bias (suite `bias`) → target ≥ 175

- **Primary (N-bearing, logprob-free): BBQ** (CC-BY-4.0) — multiple-choice
  biased/unbiased answer match, deterministic, **works on closed + open cells**.
  9 protected attributes. Sample ≥150 balanced across attributes + ambiguous/
  disambiguated. This is the set that clears the power gate.
- **Insurance-specific layer: Discrim-Eval** (CC-BY-4.0) — 70 scenarios (lending,
  hiring, housing, **insurance quotes**) × 135 identities. **Score via uniform
  sampled decision-rate** (force a parseable yes/no, k≥10 samples per item incl. the
  closed models, logit-transform rates with smoothing) — NOT native logits, so it's
  consistent across the matrix. Counts as **~70 effective**, so it's a quality layer
  _on top of_ BBQ, not the power-gate set.
- **Effective N:** BBQ ≥150 carries the gate; Discrim-Eval adds the
  domain-relevant signal. ✅

### Axis: safety (suite `jailbreak`) → target ≥ 175

- **Benign / over-refusal control: OR-Bench** (CC-BY-4.0) — 80k benign-but-toxic-
  looking; sample ~90 across its 10 categories + its 600 toxic for contrast.
  Generation/refusal-scored → all cells. Massive pool = contamination-resistant.
- **Harmful: HarmBench** (MIT, 400) sampled ~60 **with a derived discount**, +
  keep our 30 hand-written jailbreaks. Optionally JailbreakBench _private_ via API
  for a contamination-proof spike (unknown N).
- **Adaptive layer (not counted toward N):** rewrite-operator pass per
  `REDTEAM_LANDSCAPE.md` §4 — the break rate that survives rewriting is the real
  number.
- **Scoring:** existing refusal/over-refusal deterministic + judge.
- **Effective N:** ~180 independent. ✅

### Axis: sensitive (suite `sensitive`) → target ≥ 150 ⚠️ hardest

- **Injection/extraction: TensorTrust** (BSD-2-Clause) — 126k human-crafted
  prompt-extraction + hijacking attacks; string-match deterministic; aligns with our
  held-out sentinel (Fix D). Sample ~100. **Synthetic attacks, no real PII** (clean).
- **Keep** our 23 tool/PII/multi-turn probes (these are the most on-target and the
  hardest to source elsewhere).
- **Gap (be honest):** generic _PII-in-summary_ leakage has **no clean real-data
  source** — AI4Privacy (enterprise license) and Enron (real-PII/GDPR) both fail.
  This axis stays partly bespoke; validated-synthetic with a held-out generator
  (outside the matrix) is the fallback, documented as a caveat.
- **Effective N:** ~125–150; flag as the axis still nearest the floor. ⚠️

---

## Mapping to the `PromptItem` schema

Each external item converts to the existing YAML (`datasets/suites/*.yaml`):

```yaml
- id: bbq-0001 # <source>-<n>, stable
  severity: 2 # from AILuminate/NAIC mapping per axis (document the map)
  expected: comply # or refuse / no_leak / the gold answer key
  category: "race_x_ses" # source sub-axis, for per-category breakdowns
  prompt: "..." # or `turns:` for multi-turn
  reference: "B" # gold answer for match-scored items (MedMCQA/BBQ)
  meta: # provenance — required for audit/defensibility
    source: bbq
    license: cc-by-4.0
    source_id: "..." # original item id
    snapshot: "2026-06" # pin for reproducibility
    contamination: low
    effective_unit: item # or `scenario` for clustered sets (Discrim-Eval)
```

`meta.effective_unit` lets the aggregator count clusters correctly against
`min_n_per_axis` instead of inflating N — this is the guard against gaming our own
power gate.

---

## Conversion pipeline (one-time, scriptable, no model in the matrix touches it)

1. **Download** each source from HF/GitHub at a pinned revision.
2. **Sample** a balanced subset (by category/attribute/severity); record the seed.
3. **Map** to `PromptItem` YAML with full `meta` provenance.
4. **Dedup** against existing hand-written items (and across sources).
5. **Snapshot** the resulting YAML into the repo + a `SUITES_MANIFEST` recording
   source revisions, seeds, licenses, and effective-N per axis.
6. **Aggregator change:** make the power gate count `effective_unit == scenario`
   clusters as one, and add per-source attribution to the scorecard.

No generation, no in-matrix filtering — every step is sourcing + bookkeeping.

---

## Open decisions before building

1. **Target N per axis** — 175 default; sensitive may land ~150 with the bespoke gap.
2. **Discrim-Eval k** — sampled decision-rate cost: k≥10 × 70 scenarios × 135
   identities × models × guard A/B is the heaviest single cost. Confirm budget or
   subsample identities.
3. **MedMCQA/BBQ are match-scored** — confirm we want a deterministic answer-key path
   added to the scorer (currently judge + detectors).
4. **Snapshot vs. rotate** — pin FreshQA/OR-Bench per run for reproducible pricing?
   (Recommended: pin, record revision.)
5. **Build order** — recommend **BBQ → bias** first: logprob-free, deterministic,
   single source clears one axis past the gate end-to-end and proves the pipeline.

---

_Dataset license/contamination detail: `ai_insurance_datasets_report.md`,
`research_axis3_content_safety.md`. Red-team sources: `REDTEAM_LANDSCAPE.md`._
