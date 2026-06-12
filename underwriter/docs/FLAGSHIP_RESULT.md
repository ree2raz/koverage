# The Headline Result — What the Underwriter Proves

**Run `20260612T072853Z` · 12 June 2026 · the first full-scale evaluation with every safeguard switched on.**

This is the document to read if you read only one. It explains, in plain language,
what the Underwriter module is, why it exists, and what our biggest evaluation to
date actually found. No statistics background required. The detailed math lives in
[`METHODOLOGY.md`](./METHODOLOGY.md); every metric is defined in plain English in
[`METRICS_EXPLAINED.md`](./METRICS_EXPLAINED.md). This page is the story those two
support.

---

## 1. In one sentence

The Underwriter is a **crash-test lab for AI models**: it puts a model through
thousands of dangerous situations, watches how badly it can fail, and turns that
into an **insurance grade** — the same way a car has to pass a crash test before an
insurer will write a policy on it.

---

## 2. The everyday version

Imagine you sell insurance. A company comes to you and says: _"We're putting an AI
chatbot in front of our customers. Cover us if it goes wrong."_

Before you can price that policy, you need to know: **how wrong can this thing go,
and how often?** A human driver gets a quote based on their record, their car's
crash rating, their mileage. An AI model has no DMV record. So we built the record.

The Underwriter is the **inspection that produces the quote.** It scores a model on
the four ways an AI can actually cost a business money, and it hands back a grade:

| Grade           | Plain meaning                                       |
| --------------- | --------------------------------------------------- |
| **Preferred**   | Lowest risk. Cheapest premium. Safe to ship widely. |
| **Standard**    | Normal risk. Ordinary premium.                      |
| **Substandard** | Elevated risk. Higher premium, conditions attached. |
| **Decline**     | Too risky to insure as-is.                          |

That grade is the product. Everything else in this module exists to make sure the
grade is **honest** — that we can defend it to a regulator, a client, or a court.

---

## 3. The four ways an AI costs you money

We don't grade "is the AI good." We grade the four specific risks an insurer would
actually have to pay claims on. Each one is a real liability:

| What we test       | The plain-language danger                                                                                         | The real-world bill                                   |
| ------------------ | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| **Hallucination**  | The AI confidently makes things up.                                                                               | A customer follows wrong advice and sues.             |
| **Bias**           | The AI treats people differently by race, gender, etc.                                                            | Discrimination lawsuit, regulator fine, headline.     |
| **Safety**         | The AI can be talked into helping with something harmful — _or_ it's so locked-down it refuses harmless requests. | Harm done, or customers driven away by a useless bot. |
| **Sensitive data** | The AI leaks private information or secrets it was told to keep.                                                  | Privacy breach, GDPR/CCPA penalty.                    |

A model can be excellent at three of these and catastrophic at the fourth. As you'll
see, **the fourth one is what insurance is all about.**

---

## 4. The journey: four loopholes we had to close

Early versions of this lab produced a number, but the number was **gameable** — it
flattered models in ways that would get an insurer sued. An external review found
four specific loopholes. Closing all four is what makes the June 12 result
trustworthy. Here they are in plain terms:

### Fix A — Stop letting a good score hide a disaster

**The loophole:** the old grade was an _average_. A model that's brilliant on three
risks and a disaster on the fourth would average out to "looks fine." That's like
insuring a car with perfect brakes, perfect tyres, and no airbags — and calling it
average-safe.
**The fix:** a **ceiling rule.** If _any single risk_ is bad enough, the grade is
capped no matter how good everything else is. One catastrophic flaw can no longer
be laundered into a passing grade.

### Fix B — Don't make confident claims on thin evidence

**The loophole:** the old run tested only ~30 cases per risk. That's too few to say
anything precise — like rating a driver after watching them drive for one minute.
**The fix:** we expanded every risk to **180–250 real test cases** (857 per run),
and added a **"not enough evidence" alarm** that automatically caps the grade if any
risk is under-tested. _On this run, that alarm stayed silent for the first time_ —
we finally have enough evidence to grade on behaviour, not on guesswork. (More on
why that matters in §7.)

### Fix C — Test the bad day, not the average day

**The loophole:** the old test asked the model each question once, in its most
careful, predictable setting. But real users hit the model millions of times, and
**insurance pays for the bad day, not the average day.** Asking once hides the rare
disaster.
**The fix:** a **"stress test" pass.** We ask each dangerous question **five times**
with the model in a more spontaneous, realistic setting, and we record its **worst**
answer of the five. This is the single most important change — it's the difference
between "usually fine" and "what's the worst this will do."

### Fix D — Don't grade the security guard on a test it was handed the answers to

**The loophole:** the model carries an optional "guardrail" — a security layer that
blocks bad requests. We used to test it by planting a secret and checking if the
guardrail caught _that exact secret_. But we'd basically told the guardrail the
answer in advance. That's not a test; that's a rehearsal.
**The fix:** we now plant a **brand-new secret on every single run** and **never tell
the guardrail what it is.** Now we're measuring whether the guardrail can catch
things it has never seen — which is the only measure that matters in the real world.

> **Why this matters:** with all four loopholes closed, the grade this lab produces
> is no longer a flattering marketing number. It is a **conservative, defensible
> risk assessment** — the kind you could put in front of an actuary or a court.

---

## 5. The payoff: what the June 12 run found

We tested three models, each twice — once with the security guardrail **off** and
once **on** — across all 857 test cases per run. The three models:

- **Gemini 2.5 Flash** and **GPT-4.1-mini** — two leading commercial AI models.
- **Qwen3-8B** — a smaller open-source model we host ourselves, as a price-vs-risk
  comparison.

### The reveal: everyone looks great on paper, and that's the trap

Here is the single most important table in the project. The **"on paper" score** is
the old-style careful-setting average. The **"stress-test grade"** is what the model
actually earns once we look at its worst behaviour and apply the ceiling rule:

| Model                  | Guardrail | Looks like, on paper | **Actual insurance grade** | Why it's capped            |
| ---------------------- | --------- | -------------------- | -------------------------- | -------------------------- |
| Gemini 2.5 Flash       | off       | 86 / "Preferred"     | **Substandard**            | makes things up too often  |
| Gemini 2.5 Flash       | on        | 90 / "Preferred"     | **Substandard**            | makes things up too often  |
| GPT-4.1-mini           | off       | 87 / "Preferred"     | **Decline**                | can be talked into harm    |
| GPT-4.1-mini           | on        | 91 / "Preferred"     | **Substandard**            | makes things up too often  |
| Qwen3-8B (open-source) | off       | 78 / "Standard"      | **Decline**                | fails on nearly everything |
| Qwen3-8B (open-source) | on        | 88 / "Preferred"     | **Decline**                | makes things up constantly |

**Read that table twice.** Every single model scores 78–91 on paper — the range a
salesperson would call "excellent." And **not one of them earns a clean insurance
grade.** The best any model achieves is Substandard. Two cells are outright Decline.

That gap — between "looks like a 90" and "actually uninsurable" — **is the entire
value of this module in one picture.** Without the four fixes, we'd have shipped
those flattering 90s and an insurer would have been blindsided by the first claim.

### What the stress test exposed that the paper score missed

The reason the grades drop is the stress test (Fix C). When we ask each dangerous
question five times and keep the worst answer, the risk numbers jump dramatically:

| Risk, with guardrail OFF                      | Gemini        | GPT-4.1-mini  | Qwen3-8B    |
| --------------------------------------------- | ------------- | ------------- | ----------- |
| Can it be talked into harm? (calm setting)    | low (0.10)    | low (0.11)    | low (0.13)  |
| **Can it be talked into harm? (stress test)** | **0.23**      | **0.49**      | **0.57**    |
| Will it leak secrets? (calm setting)          | medium (0.34) | medium (0.29) | high (0.51) |
| **Will it leak secrets? (stress test)**       | **0.39**      | 0.24          | **0.63**    |

_(0 = never fails, 1 = always fails. Higher is worse.)_

In the calm setting, GPT-4.1-mini's "can it be talked into harm" risk looks like a
gentle 0.11. Push it five times, and **nearly half** the time (0.49) it eventually
complies. That is exactly the rare-but-real failure an insurer pays for — and the
old single-question test was completely blind to it.

### Model-by-model, in business terms

**Qwen3-8B (the cheap open-source option): uninsurable, full stop.** With no
guardrail it fails almost everything — it leaks secrets 63% of the time under stress
and can be talked into harm 57% of the time. Switch the guardrail on and it cleans
up its safety and privacy behaviour impressively — but it _still_ makes things up so
constantly (its hallucination stress score is a near-maximum 0.98) that it remains a
**Decline**. **Lesson:** a small, cheap model can be made _safe_, but it cannot be
made _reliable_ — and you can't insure a system that confidently invents facts.

**GPT-4.1-mini: the guardrail is the difference between insurable and not.** With the
guardrail off, it can be talked into harmful output often enough (0.49) to be an
outright **Decline**. Turn the guardrail on and that danger collapses — it jumps a
full grade to **Substandard.** This is the clearest proof in the whole run that the
security layer is doing real, measurable work.

**Gemini 2.5 Flash: the most balanced, but still no free pass.** It's the steadiest
performer with the guardrail on or off — but it lands at **Substandard** both ways
because it makes things up a bit too often. Notably, the guardrail can't rescue this:
a security guard stops bad requests from getting in, but it can't stop the model from
being confidently wrong. (It even gets slightly _more_ prone to making things up with
the guardrail on — a reminder these are independent problems.)

### The guardrail is worth real money

Across all three models, switching the guardrail on produced a large, **honestly
measured** improvement (remember Fix D — the guardrail had never seen these secrets):

| Model            | Stress-test grade lift (guardrail off → on)              |
| ---------------- | -------------------------------------------------------- |
| Gemini 2.5 Flash | +7 points                                                |
| GPT-4.1-mini     | **+16 points** (and a full grade: Decline → Substandard) |
| Qwen3-8B         | **+25 points**                                           |

The guardrail roughly **halves or better** the "can it be talked into harm" and
"will it leak secrets" risks on every model. For an insurer, this is the headline
mitigation: the guardrail is a cheap add-on that demonstrably lowers the risk you'd
be underwriting.

---

## 6. Why this run is the project's highlight

Three reasons this specific run is the one we point to:

1. **It's the first run where all four fixes operated together at full scale** — and
   they worked as a system. The ceiling rule (A) capped the flattering scores, the
   stress test (C) exposed the hidden danger, the held-out secret (D) made the
   guardrail improvement believable, and —

2. **The "not enough evidence" alarm (B) stayed silent for the first time.** On every
   earlier run, the data was so thin that _every_ model was automatically floored at
   Substandard — the lab couldn't tell a good model from a bad one, it could only say
   "we don't have enough evidence." This run cleared that bar on every risk (180–250
   cases each). That's why, for the first time, the models earn **different** grades
   for **different** reasons — GPT-4.1-mini fails on safety, everyone else on
   hallucination, Qwen fails on everything. **The lab can finally tell models apart.**

3. **It demonstrates the core thesis end-to-end:** _a model that looks like a 90 can
   be uninsurable, and only a properly designed test reveals it._ Every model scored
   78–91 "on paper" and none earned a clean grade. That single fact is the reason the
   Underwriter module exists.

---

## 7. The honest caveats (because honesty is the product)

A risk assessment you can't poke holes in isn't trustworthy. Here's what to keep in
mind when reading these grades:

- **The "makes things up" score is deliberately strict.** Our stress test flags a
  question as failed if the model gets it wrong _even once in five tries_. So a score
  of 0.98 for Qwen doesn't mean "wrong 98% of the time" — it means "almost every
  question tripped it up at least once out of five." That's the right way to measure
  a worst-case for insurance, but it's aggressive, and we report it as such rather
  than dressing it up.

- **The guardrail's safety improvement is partly mechanical.** Some of the measured
  drop in risk is the guardrail genuinely blocking bad requests; some is just that a
  blocked request is easy to score as "safely refused." The _direction_ (guardrail
  helps, a lot) is rock-solid; treat the exact point values as indicative.

- **We grade conservatively on purpose.** Every design choice — worst-of-five, the
  ceiling rule, pricing on the cautious end of our confidence range — pushes the
  grade _down_ when we're unsure. For insurance, an over-optimistic grade is the
  expensive mistake. We'd rather decline a borderline-safe model than insure a
  borderline-dangerous one.

---

## 8. The bottom line

> **Three leading AI models walked in looking like straight-A students (78–91 "on
> paper"). After an honest stress test, none earned a clean insurance grade — the
> best result was Substandard, and two were outright Decline.**
>
> - The cheap open-source model (Qwen3-8B) is **uninsurable** — it can be made safe,
>   but never made reliable.
> - The commercial models are **insurable only with their security guardrail on**,
>   and even then they're held back because they still make things up too often.
> - The guardrail is **worth a full grade** — a cheap, proven way to lower the risk.

That is what the Underwriter module is _for_: turning "this AI seems pretty good"
into a number an insurer can actually stake money on — and proving, with this run,
that the difference between those two things is enormous.

---

_Full numbers, statistics, and reproducibility details: [`METHODOLOGY.md`](./METHODOLOGY.md) §8.
Every metric defined in plain English: [`METRICS_EXPLAINED.md`](./METRICS_EXPLAINED.md).
Raw scorecard: `underwriter/runs/20260612T072853Z/scorecard.json`._
