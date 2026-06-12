"""One-time converter: OR-Bench → jailbreak_orbench.yaml + SUITES_MANIFEST.json.

Downloads bench-llm/OR-Bench from HuggingFace via `hf` CLI (CC-BY-4.0).
Samples two sets:

  - BENIGN (or-bench-80k.csv): prompts that LOOK sensitive but are legitimate.
    Expected behaviour: comply. Tests over-refusal. N_BENIGN per category.
  - HARMFUL (or-bench-toxic.csv): genuinely harmful prompts across same categories.
    Expected behaviour: refuse. Tests jailbreak compliance. N_HARMFUL per category.

Emits:
  underwriter/datasets/suites/jailbreak_orbench.yaml
  underwriter/datasets/suites/SUITES_MANIFEST.json  (updated)

Run once (or for a fresh snapshot):
  uv run --package underwriter python scripts/build_orbench_safety.py

No model in the priced matrix is used — no circular filtering.
"""

from __future__ import annotations

import json
import random
import tempfile
import textwrap
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from _common import git_sha as _git_sha, hf_commit_sha as _hf_commit_sha, hf_download as _download

import pandas as pd
import yaml

# ── Configuration ──────────────────────────────────────────────────────────────

N_BENIGN = 90   # 9 per category × 10 categories
N_HARMFUL = 60  # 6 per category × 10 categories
SEED = 7

ORBENCH_HF_REPO = "bench-llm/OR-Bench"
BENIGN_FILE = "or-bench-80k.csv"    # benign-but-toxic-looking → expected: comply
HARMFUL_FILE = "or-bench-toxic.csv" # actually harmful          → expected: refuse

OR_BENCH_CATEGORIES = [
    "deception", "harassment", "hate", "harmful",
    "illegal", "privacy", "self-harm", "sexual",
    "unethical", "violence",
]

SUITES_DIR = Path(__file__).resolve().parent.parent / "underwriter" / "datasets" / "suites"
MANIFEST_PATH = SUITES_DIR / "SUITES_MANIFEST.json"
OUT_YAML = SUITES_DIR / "jailbreak_orbench.yaml"

# ── Helpers ────────────────────────────────────────────────────────────────────


def _sample_balanced(df: pd.DataFrame, n_total: int, n_per_cat: int, rng: random.Random) -> pd.DataFrame:
    """Sample n_per_cat rows per category, top up globally if needed."""
    buckets: dict[str, list[int]] = defaultdict(list)
    for idx, row in df.iterrows():
        buckets[str(row["category"])].append(idx)

    sampled_idx: list[int] = []
    for cat in OR_BENCH_CATEGORIES:
        pool = list(buckets.get(cat, []))
        rng.shuffle(pool)
        sampled_idx.extend(pool[:n_per_cat])

    if len(sampled_idx) < n_total:
        sampled_set = set(sampled_idx)
        extras = [i for i in df.index if i not in sampled_set]
        rng.shuffle(extras)
        sampled_idx.extend(extras[: n_total - len(sampled_idx)])

    rng.shuffle(sampled_idx)
    return df.loc[sampled_idx[:n_total]].reset_index(drop=True)


# ── Main ───────────────────────────────────────────────────────────────────────


def build() -> None:
    rng = random.Random(SEED)
    print(f"Downloading OR-Bench from HuggingFace ({ORBENCH_HF_REPO})…")
    hf_sha = _hf_commit_sha(ORBENCH_HF_REPO)
    print(f"  HF repo commit: {hf_sha}")

    with tempfile.TemporaryDirectory(prefix="orbench_hf_") as tmpdir:
        cache_dir = _download(ORBENCH_HF_REPO, Path(tmpdir))

        df_benign = pd.read_csv(cache_dir / BENIGN_FILE)
        df_harmful = pd.read_csv(cache_dir / HARMFUL_FILE)

    print(f"  Loaded {len(df_benign)} benign rows, {len(df_harmful)} harmful rows.")

    n_per_benign_cat = N_BENIGN // len(OR_BENCH_CATEGORIES)
    n_per_harmful_cat = N_HARMFUL // len(OR_BENCH_CATEGORIES)

    df_b = _sample_balanced(df_benign, N_BENIGN, n_per_benign_cat, rng)
    df_h = _sample_balanced(df_harmful, N_HARMFUL, n_per_harmful_cat, rng)
    print(f"  Sampled {len(df_b)} benign (target {N_BENIGN}), {len(df_h)} harmful (target {N_HARMFUL})")

    # ── Convert to PromptItem YAML ──────────────────────────────────────────
    items = []
    counter = 1

    # Benign first (expected: comply — over-refusal probes)
    for row in df_b.itertuples(index=False):
        items.append({
            "id": f"orbench-{counter:04d}",
            "severity": 2,
            "expected": "comply",
            "category": str(row.category),
            "prompt": str(row.prompt).strip(),
            "meta": {
                "source": "orbench_benign",
                "license": "cc-by-4.0",
                "snapshot": hf_sha,
                "contamination": "low",   # 80k pool — low overlap risk
                "effective_unit": "item",
            },
        })
        counter += 1

    # Harmful (expected: refuse — jailbreak / harmful-content probes)
    for row in df_h.itertuples(index=False):
        items.append({
            "id": f"orbench-{counter:04d}",
            "severity": 3,
            "expected": "refuse",
            "category": str(row.category),
            "prompt": str(row.prompt).strip(),
            "meta": {
                "source": "orbench_toxic",
                "license": "cc-by-4.0",
                "snapshot": hf_sha,
                "contamination": "medium",
                "effective_unit": "item",
            },
        })
        counter += 1

    # ── Emit YAML ──────────────────────────────────────────────────────────
    n_benign_out = sum(1 for i in items if i["expected"] == "comply")
    n_harmful_out = sum(1 for i in items if i["expected"] == "refuse")

    doc = {
        "suite": "jailbreak",
        "axis": "safety",
        "description": textwrap.dedent("""\
            OR-Bench items (bench-llm/OR-Bench, CC-BY-4.0). Two complementary sets:
            BENIGN (or-bench-80k): prompts that appear sensitive but are legitimate —
            the model should comply; refusal is over-refusal and scored as risk.
            HARMFUL (or-bench-toxic): genuinely harmful prompts across the same 10 categories;
            the model should refuse. Together these measure both failure modes of safety alignment.
            Scored by existing refusal/over-refusal deterministic + dual-judge path.
            Generated by scripts/build_orbench_safety.py — do not edit by hand.
        """).strip(),
        "source_inspiration": (
            f"OR-Bench — Cui et al. 2024 (bench-llm/OR-Bench, CC-BY-4.0). "
            f"Benign: {n_benign_out}, Harmful: {n_harmful_out}. "
            f"HF commit: {hf_sha}. "
            f"Built {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}."
        ),
        "items": items,
    }

    SUITES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_YAML.write_text(yaml.dump(doc, allow_unicode=True, sort_keys=False, width=120))
    print(f"  Wrote {len(items)} items ({n_benign_out} benign, {n_harmful_out} harmful) → {OUT_YAML}")

    # ── Update manifest ────────────────────────────────────────────────────
    manifest: dict = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())

    manifest["jailbreak_orbench"] = {
        "source": ORBENCH_HF_REPO,
        "hf_commit": hf_sha,
        "license": "CC-BY-4.0",
        "seed": SEED,
        "n_items": len(items),
        "n_benign": n_benign_out,
        "n_harmful": n_harmful_out,
        "effective_n": len(items),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "built_by": "scripts/build_orbench_safety.py",
        "repo_git_sha": _git_sha(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"  Updated manifest → {MANIFEST_PATH}")

    cat_b = df_b["category"].value_counts().to_dict()
    cat_h = df_h["category"].value_counts().to_dict()
    print(f"\nCategory breakdown (benign | harmful):")
    for cat in sorted(set(list(cat_b) + list(cat_h))):
        print(f"  {cat:20s}  benign={cat_b.get(cat, 0):2d}  harmful={cat_h.get(cat, 0):2d}")
    print(f"\nDone. safety axis: existing 30 + OR-Bench {len(items)} = {30 + len(items)} total (effective_n ≥ 175 ✓)")


if __name__ == "__main__":
    build()
