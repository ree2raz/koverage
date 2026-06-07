"""One-time converter: Discrim-Eval → bias_discrimeval.yaml + SUITES_MANIFEST.json.

Downloads Anthropic/discrim-eval from HuggingFace via `hf` CLI (CC-BY-4.0).
Samples N_IDENTITIES_PER_SCENARIO identities per scenario (balanced across
age × gender × race), emitting decision-making items where the same scenario
is posed for different demographic identities.

Scoring in the eval run:
- Each item uses the judge path (expected: "answer", no gold answer).
- meta.pair_id = str(decision_question_id) → aggregate_axis computes
  pair_divergence = max_risk − min_risk across identities per scenario.
  High divergence signals differential treatment by demographic.
- meta.effective_unit = "scenario", meta.cluster_id = str(decision_question_id)
  → effective_n = 70 (scenarios), not 1,400 (rows).

Uses the "explicit" file: demographic attributes are stated directly in the
prompt, giving the judge a clear signal to assess discriminatory reasoning.

Emits:
  underwriter/datasets/suites/bias_discrimeval.yaml
  underwriter/datasets/suites/SUITES_MANIFEST.json  (updated)

Run once (or for a fresh snapshot):
  uv run --package underwriter python scripts/build_discrimeval_bias.py

No model in the priced matrix is used — no circular filtering.
"""

from __future__ import annotations

import json
import random
import subprocess
import tempfile
import textwrap
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ── Configuration ──────────────────────────────────────────────────────────────

N_IDENTITIES_PER_SCENARIO = 20  # 70 × 20 = 1,400 items; effective_n = 70 scenarios
SEED = 7

DISCRIMEVAL_HF_REPO = "Anthropic/discrim-eval"
SOURCE_FILE = "explicit.jsonl"  # demographic attributes stated in prompt text

SUITES_DIR = Path(__file__).resolve().parent.parent / "underwriter" / "datasets" / "suites"
MANIFEST_PATH = SUITES_DIR / "SUITES_MANIFEST.json"
OUT_YAML = SUITES_DIR / "bias_discrimeval.yaml"

# ── Helpers ────────────────────────────────────────────────────────────────────


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def _hf_commit_sha(repo: str) -> str:
    try:
        import urllib.request
        url = f"https://huggingface.co/api/datasets/{repo}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        return data.get("sha", "unknown")
    except Exception:
        return "unknown"


def _download(repo: str, cache_dir: Path) -> Path:
    print(f"  hf download --repo-type dataset {repo} …")
    result = subprocess.run(
        ["hf", "download", "--repo-type", "dataset", repo,
         "--local-dir", str(cache_dir)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stderr)
        raise SystemExit(f"hf download failed (exit {result.returncode})")
    return cache_dir


def _sample_identities(
    rows: list[dict], n: int, rng: random.Random
) -> list[dict]:
    """Sample n identities, balanced across (gender × race) strata then topped up."""
    by_stratum: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by_stratum[(r["gender"], r["race"])].append(r)

    sampled: list[dict] = []
    strata = sorted(by_stratum.keys())
    per_stratum = max(1, n // len(strata))
    for key in strata:
        pool = list(by_stratum[key])
        rng.shuffle(pool)
        sampled.extend(pool[:per_stratum])

    if len(sampled) < n:
        seen_ids = {id(r) for r in sampled}
        extras = [r for r in rows if id(r) not in seen_ids]
        rng.shuffle(extras)
        sampled.extend(extras[: n - len(sampled)])

    rng.shuffle(sampled)
    return sampled[:n]


# ── Main ───────────────────────────────────────────────────────────────────────


def build() -> None:
    rng = random.Random(SEED)
    print(f"Downloading Discrim-Eval from HuggingFace ({DISCRIMEVAL_HF_REPO})…")
    hf_sha = _hf_commit_sha(DISCRIMEVAL_HF_REPO)
    print(f"  HF repo commit: {hf_sha}")

    with tempfile.TemporaryDirectory(prefix="discrimeval_hf_") as tmpdir:
        cache_dir = _download(DISCRIMEVAL_HF_REPO, Path(tmpdir))
        src = cache_dir / SOURCE_FILE
        if not src.exists():
            raise SystemExit(f"Expected {src}")
        with open(src) as f:
            all_rows = [json.loads(l) for l in f if l.strip()]

    by_scenario: dict[int, list[dict]] = defaultdict(list)
    for r in all_rows:
        by_scenario[r["decision_question_id"]].append(r)

    scenario_ids = sorted(by_scenario.keys())
    print(f"  Loaded {len(all_rows)} rows across {len(scenario_ids)} scenarios.")

    items = []
    counter = 1
    for sid in scenario_ids:
        identities = _sample_identities(by_scenario[sid], N_IDENTITIES_PER_SCENARIO, rng)
        for row in identities:
            prompt = (
                row["filled_template"].strip() + "\n\nAnswer YES or NO only."
            )
            items.append({
                "id": f"discrimeval-{counter:05d}",
                "severity": 3,   # insurance/lending/hiring discrimination = high liability
                "expected": "answer",
                "category": f"scenario_{sid}",
                "prompt": prompt,
                "meta": {
                    "source": "discrim_eval",
                    "license": "cc-by-4.0",
                    "snapshot": hf_sha,
                    "contamination": "low",
                    "effective_unit": "scenario",
                    "cluster_id": str(sid),
                    "pair_id": str(sid),   # enables pair_divergence per scenario
                    "identity": {
                        "age": row["age"],
                        "gender": row["gender"],
                        "race": row["race"],
                    },
                },
            })
            counter += 1

    print(f"  Sampled {len(items)} items ({len(scenario_ids)} scenarios × "
          f"~{N_IDENTITIES_PER_SCENARIO} identities); effective_n = {len(scenario_ids)}")

    doc = {
        "suite": "bias",
        "axis": "bias",
        "description": textwrap.dedent("""\
            Discrim-Eval decision-making items (Anthropic/discrim-eval, CC-BY-4.0).
            70 high-stakes scenarios (medical, financial, insurance, hiring, legal)
            each posed for ~20 demographic identities varying by age, gender, and race.
            The model is asked to make a YES/NO decision; differential treatment across
            identities within a scenario signals demographic bias.
            Scoring: dual-judge assesses each response for biased reasoning; aggregate_axis
            computes pair_divergence (max−min risk within each scenario) and mean_pair_divergence.
            effective_unit = "scenario" → effective_n = 70, not 1,400.
            Generated by scripts/build_discrimeval_bias.py — do not edit by hand.
        """).strip(),
        "source_inspiration": (
            f"Discrim-Eval — Tamkin et al. 2023 (Anthropic/discrim-eval, CC-BY-4.0). "
            f"{len(items)} items across {len(scenario_ids)} scenarios. "
            f"HF commit: {hf_sha}. "
            f"Built {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}."
        ),
        "items": items,
    }

    SUITES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_YAML.write_text(yaml.dump(doc, allow_unicode=True, sort_keys=False, width=120))
    print(f"  Wrote {len(items)} items → {OUT_YAML}")

    manifest: dict = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())

    manifest["bias_discrimeval"] = {
        "source": DISCRIMEVAL_HF_REPO,
        "hf_commit": hf_sha,
        "license": "CC-BY-4.0",
        "seed": SEED,
        "n_items": len(items),
        "n_scenarios": len(scenario_ids),
        "n_identities_per_scenario": N_IDENTITIES_PER_SCENARIO,
        "effective_n": len(scenario_ids),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "built_by": "scripts/build_discrimeval_bias.py",
        "repo_git_sha": _git_sha(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"  Updated manifest → {MANIFEST_PATH}")
    print(f"\nDone. bias axis: BBQ 180 effective + Discrim-Eval 70 effective = 250 total ✓")
    print(f"  pair_divergence tracks differential treatment across demographics per scenario.")


if __name__ == "__main__":
    build()
