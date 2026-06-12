# Red-Team Landscape for the Koverage Underwriter

**Purpose.** Map the people, orgs, and artifacts in AI red-teaming that are usable
for koverage's underwriter — with an explicit bias toward work in the _same angle
as Ollive.ai_ (validate a model's risk → translate it into an insurance price).
For each source: what it is, what we can actually take, the license/contamination
catch, and whether it may touch the **priced corpus** or only the adaptive/stress
layer.

All external facts here were web-verified June 2026 (assistant knowledge cutoff is
Jan 2026, so anything dated later was checked live). Sources at the bottom.

---

## 1. The direct peers — companies that already price AI risk

These are the closest analogs to Ollive.ai. We are building the _signal_; they are
the _market_ that consumes a signal like it. Study how they frame it.

### Armilla AI — the closest mirror

Third-party AI/LLM validation + red-teaming **wrapped in an insurance-backed
warranty**. Lloyd's coverholder; reinsured by Swiss Re, Greenlight Re, Chaucer,
Axis Capital. "Armilla Guaranteed" pays out if a validated model's accuracy drops
below verified thresholds; cover reported up to ~$25M for hallucinations, model
drift, and regulatory breaches. Healthcare precedent: BUDDI AI (medical coding,
warranty on accuracy). Bank co-pilot precedent: warranty explicitly conditioned on
_jailbreak resistance and sensitive-data-disclosure resistance_.

**What we take:** their loss taxonomy maps almost 1:1 onto our axes —
hallucination, bias (they sell NYC Local Law 144 bias assessments), jailbreak,
sensitive-data disclosure. The warranty-trigger framing ("compensation if accuracy
drops below a _verified threshold_") is exactly what our ceiling ladder + priced
tier should produce: a defensible threshold, not a vibe. This is the reference for
how rigorous our `priced_tier` has to be.

### Munich Re — aiSure

Performance-guarantee insurance since 2018; model-agnostic (covers GenAI and
agentic). A dedicated research-scientist team does **technical due diligence**
before a model is insurable, and "model quality + performance stability determine
the premium." 2026: Mosaic partnership, up to ~$15M, **parametric-like claims
settled on measurable performance data**. Defines AI broadly to avoid "silent AI
risk" (the cyber-insurance analogy).

**What we take:** "premium determined by quality + _stability_" validates our dual
index — the tail/variance pass (T=0.7, worst-of-k) is the stability term Munich Re
prices on, not just the modal point estimate. Their parametric claims model is an
argument for keeping scoring deterministic and replayable where possible.

### The market read (why our guardrail-delta design is right)

2026 industry analysis describes a shift from pricing _the technology_ to **pricing
the security program behind it** ("control-based underwriting", following the cyber
curve). That is precisely our guardrail A/B delta: the guardrail is the control;
the guard-on vs guard-off delta is the loss-mitigation credit. Keep that framing
front and center in the scorecard — it's where the market is going.

### Lakera — runtime guardrails + an injection benchmark

Lakera Guard (runtime firewall) + Lakera Red (pre-launch testing) + **PINT**
benchmark (prompt-injection detection, MIT) + the Gandalf game corpus. Adjacent to
our guardrail layer rather than our scorer.

**What we take:** PINT as a secondary check on the sensitive/injection axis;
Gandalf as a _technique_ reference for the adaptive round (not priced data).

### Adversa AI

AI red-teaming firm that also publishes analysis of **AI-insurance exclusions** —
useful for understanding what carriers are carving _out_ of coverage (i.e., the
risks our signal most needs to quantify, because they're where disputes land).

---

## 2. The researchers & red-teamers worth tracking

### Pliny the Liberator (@elder_plinius) — technique source, not data source

The most prolific public jailbreaker (TIME 100 in AI, 2025; SANS AI Cybersecurity
Summit keynote, April 2026). Maintains **L1B3RT4S** (vendor-organized jailbreak
prompts, a portable four-stage pipeline, GODMODE-style meta-commands) and
**CL4R1T4S** (leaked system prompts). Runs the BASI PROMPT1NG community.

**What we can use — and the hard limits:**

- ✅ **Technique taxonomy for the adaptive/rewrite layer.** His categories (see §4)
  are the closest public proxy for how real attackers _adapt_ after a guardrail
  blocks them. Use them to design rewrite operators for a future adaptive tail
  pass.
- ✅ **Tooling on-ramp:** Promptfoo ships a "Pliny" red-team plugin that pulls
  from L1B3RT4S dynamically — the productized way to exercise these, rather than
  hand-copying strings.
- ❌ **Not priced data.** Public + heavily scraped → same contamination disease as
  AdvBench; measured risk on these exact strings is understated.
- ❌ **License:** Promptfoo states the L1B3RT4S prompts are **AGPL-3.0** (copyleft,
  network clause) — cannot be baked into a proprietary pricing corpus without
  legal review.
- ⚠️ **Axis fit is partial:** mostly content-safety jailbreaks; little on
  tool-mediated cross-record extraction, which is our hardest sensitive-data case.

### Gray Swan AI — the ART benchmark + a contamination-resistant arena

Runs the largest red-teaming **Arena** (fresh challenges weekly across chat, image,
agents, indirect injection — inherently contamination-resistant). Produced the
**Agent Red Teaming (ART) benchmark** (arXiv:2507.20526): ~2,000 participants,
**1.8M prompt-injection attacks against 22 frontier agents across 44 realistic
deployment scenarios** (customer service, web search, financial tools). Headline:
near-100% attack success within 10–100 queries; high transferability. Co-authored
AgentHarm with UK AISI.

**What we take:** ART is the state of the art for _agentic_ risk and is the model
to follow when koverage adds a tool-misuse axis — realistic deployment scenarios,
multi-query budgets, transfer. The Arena's weekly rotation is a template for a
contamination-resistant attack stream. (AgentHarm itself is license-blocked for us
— MIT + safety-only clause — so use it for design, not as priced data.)

### Center for AI Safety (Mazeika, Hendrycks et al.) — HarmBench

Standardized red-teaming eval, MIT, 400 expert-curated behaviors + a classifier.
Usable but public/contaminated — secondary signal with a discount, never sole.

### Berkeley (StrongREJECT), Oxford/Bocconi (XSTest), UMD (PHTest), MLCommons

(AILuminate) — covered in `ai_insurance_datasets_report.md`. AILuminate's hazard
taxonomy is the citable severity framework for the safety/sensitive axes (it
**excludes bias** — don't use it there).

### Standards to map axes onto (for liability defensibility)

- **OWASP LLM Top 10** — prompt injection ranked #1 two years running ("the new SQL
  injection"). Map each of our axes to an OWASP category so the scorecard speaks
  the language an underwriter/regulator already uses.
- **NIST AI RMF / AI 600-1**, **EU AI Act risk tiers**, **NAIC** (Spring 2026:
  proposed EU-style four-tier taxonomy, AI Systems Evaluation Tool pilot Jan–Sep
  2026, and a **third-party vendor registry + model law** anticipated 2026 — which
  may put Ollive.ai itself in scope as a vendor of a pricing signal).

### Tooling (build vs. buy for the harness)

Promptfoo (red-team plugins incl. Pliny), DeepEval/Confident AI, Enkrypt AI. Useful
as attack _generators_ for the adaptive layer; our scoring/stats stay in-house.

---

## 3. Usable-artifacts cheat sheet

| Source                     | What we take                                                  | License           | Contamination     | Priced corpus?   |
| -------------------------- | ------------------------------------------------------------- | ----------------- | ----------------- | ---------------- |
| Armilla / Munich Re        | Loss taxonomy, threshold + control-based framing              | n/a (concepts)    | n/a               | n/a              |
| Pliny L1B3RT4S             | Rewrite-operator taxonomy (§4); Promptfoo plugin as generator | AGPL-3.0 ⚠️       | High (public)     | ❌ adaptive only |
| Gray Swan ART (2507.20526) | Agentic scenario design, multi-query budgets                  | check paper terms | Low (recent)      | ⚠️ design ref    |
| Gray Swan Arena            | Rotating attack-stream template                               | platform          | Low (rotating)    | ❌ stress only   |
| Lakera PINT / Gandalf      | Injection detection check; technique ref                      | MIT / game        | Med               | ⚠️ secondary     |
| HarmBench                  | Harmful behaviors, with discount                              | MIT               | Moderate          | ⚠️ discounted    |
| AILuminate                 | Severity taxonomy (safety/sensitive only)                     | CC-BY-4.0         | Low (12k private) | ✅ taxonomy      |
| OWASP LLM Top 10           | Axis→liability mapping                                        | open              | n/a               | n/a              |

---

## 4. Adaptive-round rewrite operators (technique taxonomy, defensive use)

For an authorized eval, the value of Pliny/Gray Swan is the _category of move_ an
attacker makes after a guardrail blocks the literal probe — the assignment's
"adaptive round" and a capability koverage's tail pass currently lacks. Described
at the taxonomy level (no working strings):

1. **Paraphrase / synonym substitution** — restate the blocked request without the
   trigger tokens the guardrail keys on.
2. **Reframing** — wrap the ask in a fictional, role-play, hypothetical, or
   "for safety research" frame.
3. **Encoding / obfuscation** — base64/leetspeak/translation/character-splitting to
   slip past surface filters.
4. **Multi-turn build-up** — establish benign context over several turns, then pivot
   (the "trust-building" then "authority confusion" pattern).
5. **Injection through a data field** — hide the instruction inside content the agent
   is asked to _process_ (a patient record, a document) — the OWASP #1 pattern and
   the most relevant to tool-using agents.
6. **Splitting across turns/fields** — distribute the payload so no single message
   trips the guardrail.

**Use:** these define the rewrite functions for an adaptive tail pass. The break
rate that survives rewriting (not the literal-probe rate) is the real robustness
number — exactly the point both the assignment and Gray Swan's ART make.

---

## 5. Standing caveats

- **Contamination:** anything public and popular (AdvBench, L1B3RT4S, XSTest)
  understates risk on models trained after its release. Prefer held-out/private
  (AILuminate 12k private), rotating (Gray Swan Arena), or counterfactual structure
  (Discrim-Eval). Cite Intent Laundering (arXiv:2602.16729) and arXiv:2511.22047 for
  the magnitude — not the fabricated "Failure-First / 83pp" claim from the dataset
  report.
- **License is a hard gate** for a commercial pricing product. AGPL (Pliny),
  safety-only clauses (AgentHarm), and custom/NC licenses (SORRY-Bench, FELM) are
  out of the priced corpus regardless of fit.
- **Axis fit:** most public jailbreak corpora are content-safety; our hardest axis
  (tool-mediated sensitive-data disclosure) is under-served — that gap is where
  bespoke, real-label work pays off most.

---

## Sources

- Armilla AI — https://www.armilla.ai/ , https://www.armilla.ai/ai-insurance
- Munich Re aiSure — https://www.munichre.com/en/solutions/for-industry-clients/insure-ai.html
- Mosaic × Munich Re (2026) — https://www.reinsurancene.ws/mosaic-and-munich-re-introduce-ai-specific-insurance-for-developers/
- Gray Swan ART benchmark — https://arxiv.org/pdf/2507.20526 ; Arena — https://app.grayswan.ai/arena
- Pliny L1B3RT4S — https://github.com/elder-plinius/L1B3RT4S ; Promptfoo plugin (AGPL note) — https://www.promptfoo.dev/docs/red-team/plugins/pliny/
- Lakera PINT — https://github.com/lakeraai/pint-benchmark
- Adversa AI insurance-exclusions analysis — https://adversa.ai/blog/ai-risk-management-insurance-what-the-new-exclusions-mean/
- Intent Laundering — https://arxiv.org/pdf/2602.16729 ; guardrail robustness — https://www.arxiv.org/pdf/2511.22047
