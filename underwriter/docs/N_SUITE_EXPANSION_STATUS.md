# N-Suite Expansion — Status & Progress

**Branch:** `feat/underwriter-n-suite-expansion`
**Base:** `master` at merge `b8e6e23` (risk-pricing hardening already landed)
**HEAD:** `aeb7afd`
**Last updated:** 2026-06-10
**Tests:** 83 passing (offline, no API/judge calls)

---

## 1. The goal

The underwriter module is not a metrics demo — it is the **Insurability Index**,
the live pricing signal Ollive.ai uses to quote AI-insurance premiums. The
hardening branch (already merged) made the priced tier conservative and
non-linear, but it left every axis **under-powered**: each suite had only ~30
items, so the **power gate** (`min_n_per_axis = 150`) fired on all four axes and
capped every model at _Substandard_ — "Preferred" and "Standard" were
unreachable.

**This branch's goal:** raise every axis above the `effective_n ≥ 150` floor with
**real, verified-label, commercially-licensed** data — then make the resulting
suite actually represent the liabilities Ollive.ai underwrites, not just hit a
row count.

### Non-negotiable principles (from `SUITE_EXPANSION.md`)

1. **Effective N, not row count.** Counterfactual/paraphrase clusters count as ~1
   independent item. The power gate counts independent units via
   `meta.effective_unit` — the guard against gaming our own gate.
2. **No circular filtering.** Never select items by "model-under-test fails it"
   (Qwen3-8B is priced — that re-introduces the circularity Fix D removed). All
   sampling is by category/balance with a fixed seed, no in-matrix model.
3. **License is a hard gate.** Only Apache-2.0 / MIT / CC-BY-4.0 / BSD into the
   priced corpus.
4. **One scoring estimator per axis across the whole matrix.** Never mix
   logprob-based and sampling-based scoring within an axis (closed OpenRouter
   models lack reliable logprobs; OSS Modal models have them) — prefer
   generation/match-based scoring that works on every cell.

---

## 2. Where we are — all four axes clear the gate

| Axis              | Built from                                         | rows (`n`) | `effective_n` | det-only | Gate    |
| ----------------- | -------------------------------------------------- | ---------- | ------------- | -------- | ------- |
| **hallucination** | HaluEval 120 + MedMCQA 50 + 30 false-premise traps | 200        | **200**       | 50       | ✅ PASS |
| **bias**          | BBQ 150 + Discrim-Eval 70 scenarios + 30 bespoke   | 250¹       | **250**       | 150      | ✅ PASS |
| **safety**        | OR-Bench 90 benign + 60 toxic + 30 bespoke         | 180        | **180**       | 0        | ✅ PASS |
| **sensitive**     | TensorTrust 140 + synthetic-PII 64 + 23 bespoke    | 227        | **227**       | 0        | ✅ PASS |

¹ Bias `n` is 250 **after** the decision-rate scorer collapses Discrim-Eval's
1,400 identity rows into 70 scenario-level scores (see §4). Before that change it
was 1,580 rows with `effective_n` 250.

**Result:** the power gate no longer caps every cell at Substandard. Preferred /
Standard tiers are now reachable for a model that earns them.

---

## 3. Datasets sourced (provenance in `SUITES_MANIFEST.json`)

Every source is pinned to an HF commit, seeded, and license-recorded.

| Suite file                     | Upstream                      | License       | Items                      | Scoring                                                    |
| ------------------------------ | ----------------------------- | ------------- | -------------------------- | ---------------------------------------------------------- |
| `bias_bbq.yaml`                | BBQ (Parrish 2022)            | CC-BY-4.0     | 150                        | answer-key match (`expected: mcq`, unbiased answer = gold) |
| `bias_discrimeval.yaml`        | Discrim-Eval (Anthropic)      | CC-BY-4.0     | 1,400 rows → 70 scenarios  | **decision-rate disparity** (§4)                           |
| `factual_halueval.yaml`        | HaluEval (Ke 2023)            | MIT           | 120                        | dual-judge vs. reference                                   |
| `factual_medmcqa.yaml`         | MedMCQA (Pal 2022)            | MIT           | 50                         | answer-key match (`expected: mcq`) + MCQ tail pass         |
| `jailbreak_orbench.yaml`       | OR-Bench (Cui 2024)           | CC-BY-4.0     | 150 (90 benign + 60 toxic) | refusal/over-refusal deterministic + judge                 |
| `sensitive_tensortrust.yaml`   | TensorTrust (Toyer 2023)      | BSD-2-Clause  | 140                        | `detect_leak` (sentinel/PII) + judge                       |
| `sensitive_synthetic_pii.yaml` | template-generated (no model) | n/a (bespoke) | 64                         | `planted_pii` leak detection                               |

Build scripts (one per source, re-runnable) live in `underwriter/scripts/`.

---

## 4. The headline fix — Discrim-Eval decision-rate disparity (Gap 1)

This is the most important code change on the branch and the only **methodology
deviation** that needed correcting.

### The problem

Discrim-Eval poses the _same_ high-stakes YES/NO decision (lending, hiring,
housing, **insurance**, medical) for ~20 demographic identities per scenario.
Bias here is **differential treatment across identities**, not anything in a
single answer.

The first build routed all 1,400 items through the **dual-judge path** at k=1.
Two flaws:

- The judge scored each identity's response _in isolation_ — where bias does not
  live. The actual disparate-treatment metric (`pair_divergence`) was computed in
  the aggregator but **never folded into the priced bias risk**. Demographic
  discrimination had **zero effect on the price**.
- It paid ~2,800 judge calls on 1,400 mechanically-scorable items.

### The fix (built exactly as the plan specified — sampled decisions, no logprobs)

- **`extract_yes_no()`** (`scoring/deterministic.py`) — deterministic YES/NO
  extraction from a forced-choice response; ambiguous → excluded from the rate.
- **`decision_rate_disparity()`** (`scoring/fairness.py`, new) — per scenario,
  compute the smoothed favorable-decision rate for every protected group
  (age **bucket** × gender × race), take the largest gap (**demographic-parity
  difference**) as the scenario's bias risk in [0,1]. Max log-odds ratio is kept
  as the plan's "logit" diagnostic.
- **`PromptItem.is_decision_rate`** — routes items (via
  `meta.scoring="decision_rate"`, or a scenario+identity heuristic for
  already-built suites) away from the judge path.
- **`runner._run_decision_pass`** — samples each (scenario × identity) **k=5 @
  T=0.7** (a rate is meaningless at T=0), groups by `cluster_id`, emits **one
  scenario-level `ItemScore`** (`effective_unit="scenario"`).

### Why it matters for pricing

1. **Cross-matrix comparable** — uses sampled decisions, never log-probs, so
   closed (OpenRouter) and OSS (Modal) cells are measured identically (honours the
   §logprob constraint).
2. **It actually moves the price** — the disparity is the bias-axis risk now,
   instead of a reported-but-unused side metric.
3. **Honest N** — bias `n` drops 1,580 → 250; `effective_n` stays 250.

Verified offline against the real suite (induced race bias → bias risk 0.17, gate
PASS). `k=5` reuses the existing tail config by design.

---

## 5. Anti-gaming & supporting scorer changes (from the N-suite commits)

- **MCQ scoring** (`combine.py`, `deterministic.py`): `expected="mcq"` + a
  `reference` → `extract_mcq_choice()` answer-key match (0.0 correct / 1.0 wrong).
  No judge calls. Powers BBQ (bias) and MedMCQA (hallucination).
- **`effective_n`** (`aggregate.py`): unique `cluster_id`s for
  `effective_unit="scenario"` items count as one; the power gate reads
  `effective_n`, not raw `n`.
- **`deterministic_only`** property: True only when `expected=="mcq"` **and** a
  reference exists — so judge calls are skipped only when there is a real oracle.
- **MCQ hallucination tail pass** (`tail_risk`): MedMCQA MCQ items get the k=5
  worst-of-k stress pass; HaluEval open-answer items are **excluded** from the
  tail (no deterministic oracle → would false-zero-inflate the tail risk).

---

## 6. Commits on this branch (oldest → newest)

| SHA       | Summary                                                                                                                                                          |
| --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `4bef6a9` | N-suite expansion — all four axes clear the 150 power gate (BBQ, HaluEval, MedMCQA, OR-Bench, TensorTrust + MCQ/effective_n/`deterministic_only` scorer changes) |
| `c8881de` | License hygiene — NOTICE, third-party licenses, suite attributions                                                                                               |
| `410a6dc` | Gap-fill — Discrim-Eval suite, synthetic PII, hallucination MCQ tail pass                                                                                        |
| `0e3a2ba` | Cosmetic — normalize suite YAML quoting + README table alignment (removes working-tree drift)                                                                    |
| `aeb7afd` | **Discrim-Eval decision-rate disparity scorer (Gap 1)** + doc reconciliation                                                                                     |

---

## 7. Realism gaps — assessed, partly closed

A web-research pass checked the suite against real AI-insurance liability (NAIC
enforcement focus; Munich Re / Geneva Association liability categories). Three
gaps were identified; status below.

| Gap                                   | What it was                                                                                                  | Status                                                                                            |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| **Insurance-specific discrimination** | No NAIC-style unfair-discrimination testing                                                                  | ✅ **Closed** — Discrim-Eval + the decision-rate scorer (§4)                                      |
| **PII-in-context leakage**            | Sensitive axis had injection attacks but not real "model summarises a doc and leaks the PII in it" liability | ✅ **Closed** — synthetic-PII multi-turn scenarios with `planted_pii`                             |
| **Single-run reliability**            | Pricing on one T=0 pass hides tail behaviour                                                                 | ✅ **Mitigated** — tail pass (k=5 @ T=0.7) already from hardening; MCQ hallucination now included |

### Known substitutions / remaining caveats (documented for audit)

- **FreshQA dropped** — `freshllms/freshqa` was not resolvable on HF at build
  time. Hallucination clears its target without it; the hand-written
  false-premise traps remain the contamination-resistant element. _(Gap 3, not
  fixed — by scope choice.)_
- **HarmBench → OR-Bench-toxic** — HarmBench's repo was gated. The toxic subset
  keeps the license clean but harmful items are **softer** (a moderation set, same
  source family as the benign control) than HarmBench's behaviour-elicitation
  prompts. Candidate upgrade: **JailbreakBench / StrongREJECT**. _(Gap 2, not
  fixed — by scope choice.)_
- **Synthetic-PII fill** — within plan bounds: the documented validated-synthetic
  fallback for the PII-in-context gap (template-based, seeded, no in-matrix
  model). Carried as a caveat in METHODOLOGY §11.
- **Open-answer hallucination tail** — HaluEval open answers still reuse modal
  risk in the tail (no judge-free oracle). MCQ hallucination and bias now have
  deterministic estimators.

---

## 8. Regulatory context (material to Ollive.ai)

NAIC Spring 2026 proposed a 4-tier (EU-style) risk taxonomy, an AI Systems
Evaluation Tool (pilot Jan–Sep 2026, 12 states), and a third-party vendor
registry + model law (anticipated 2026). As a third-party vendor selling a
pricing signal to insurers, Ollive.ai may be in scope — which is why the
Discrim-Eval insurance-discrimination axis and the decision-rate disparity metric
(a standard demographic-parity fairness measure) directly target the NAIC
unfair-discrimination focus.

---

## 9. What's next

- **Push branch + open PR to `master`** (not yet done).
- **Gap 2 (optional):** swap soft OR-Bench-toxic harmful items for JailbreakBench
  / StrongREJECT for a genuinely adversarial safety harmful set.
- **Gap 3 (optional):** source a FreshQA substitute for a contamination-resistant
  hallucination spike.
- **Live smoke run:** confirm `scorecard.json` carries the new bias decision-rate
  scores and that a fresh run reprices off `priced_tier` end-to-end (needs API
  keys).
- **Open-answer hallucination oracle:** a lightweight reference-based factual-error
  detector would close the last tail-oracle gap.

---

## 10. Key files (map)

```
underwriter/
├── docs/
│   ├── SUITE_EXPANSION.md          # the plan + "Implementation status (as built)"
│   ├── METHODOLOGY.md              # §3 scoring pipeline incl. decision-rate pass; §11/§12 caveats
│   └── N_SUITE_EXPANSION_STATUS.md # this file
├── scripts/build_*.py              # one converter per source (re-runnable, pinned)
└── underwriter/
    ├── datasets/
    │   ├── __init__.py             # PromptItem; deterministic_only + is_decision_rate
    │   └── suites/                 # the priced corpus YAML + SUITES_MANIFEST.json
    ├── scoring/
    │   ├── deterministic.py        # extract_mcq_choice, extract_yes_no, tail_risk, detect_leak
    │   ├── fairness.py             # decision_rate_disparity  (NEW)
    │   ├── combine.py              # per-item risk; MCQ branch
    │   └── aggregate.py            # effective_n, power gate, price()
    └── runner.py                   # modal pass + tail pass + _run_decision_pass
```
