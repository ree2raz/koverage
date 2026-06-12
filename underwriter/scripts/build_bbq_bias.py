"""One-time converter: BBQ → bias_bbq.yaml + SUITES_MANIFEST.json.

Downloads Elfsong/BBQ from HuggingFace via the `hf` CLI (auth: hf auth login),
samples N_ITEMS balanced items across all 11 BBQ categories, and emits:

  underwriter/datasets/suites/bias_bbq.yaml   — PromptItem YAML
  underwriter/datasets/suites/SUITES_MANIFEST.json — provenance record

Run once (or when you want a fresh snapshot):
  uv run --package underwriter python scripts/build_bbq_bias.py

No model in the priced matrix is used here — no circular filtering.
"""

from __future__ import annotations

import json
import random
import re
import subprocess
import tempfile
import textwrap
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

# ── Configuration ──────────────────────────────────────────────────────────────

N_ITEMS = 150
SEED = 7

# Pinned commit on the nyu-mll/BBQ HF repo (datasets viewer branch).
# Update this SHA when you want a fresh snapshot; record it in the manifest.
BBQ_HF_REPO = "Elfsong/BBQ"
# Elfsong/BBQ has 11 splits (one per category); the label field is "answer_label".
# No trust_remote_code needed (Parquet format).

BBQ_SPLITS = [
    "age",
    "disability_status",
    "gender_identity",
    "nationality",
    "physical_appearance",
    "race_ethnicity",
    "race_x_gender",
    "race_x_ses",
    "religion",
    "ses",
    "sexual_orientation",
]

# Human-readable category labels for YAML/manifest (match split names, title-cased).
_SPLIT_TO_CATEGORY = {s: s.replace("_", " ").title() for s in BBQ_SPLITS}

# Each BBQ item has these two dimensions:
CONTEXT_CONDITIONS = ("ambig", "disambig")
QUESTION_POLARITIES = ("neg", "nonneg")

SUITES_DIR = Path(__file__).resolve().parent.parent / "underwriter" / "datasets" / "suites"
MANIFEST_PATH = SUITES_DIR / "SUITES_MANIFEST.json"
OUT_YAML = SUITES_DIR / "bias_bbq.yaml"

# ── Helpers ────────────────────────────────────────────────────────────────────


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def _hf_commit_sha(repo: str) -> str:
    """Resolve the HEAD commit SHA of a HF dataset repo via the API."""
    try:
        import urllib.request
        url = f"https://huggingface.co/api/datasets/{repo}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        return data.get("sha", "unknown")
    except Exception:
        return "unknown"


def _label_to_letter(label: int) -> str:
    return chr(ord("A") + label)


def _format_prompt(context: str, question: str, answers: list[str]) -> str:
    options = "\n".join(f"{_label_to_letter(i)}) {a}" for i, a in enumerate(answers))
    return (
        f"Context: {context}\n"
        f"Question: {question}\n"
        f"{options}\n"
        f"Answer with only the letter ({', '.join(_label_to_letter(i) for i in range(len(answers)))}) "
        f"of the best option."
    )


# ── Main ───────────────────────────────────────────────────────────────────────


_PARQUET_SPLIT_RE = re.compile(r"^(.+)-\d{5}-of-\d{5}\.parquet$")


def _download_bbq_parquets(cache_dir: Path) -> Path:
    """Download Elfsong/BBQ parquet files via hf CLI; return the data directory."""
    print(f"  hf download --repo-type dataset {BBQ_HF_REPO} …")
    result = subprocess.run(
        ["hf", "download", "--repo-type", "dataset", BBQ_HF_REPO,
         "--local-dir", str(cache_dir), "--include", "*.parquet"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stderr)
        raise SystemExit(f"hf download failed (exit {result.returncode})")
    data_dir = cache_dir / "data"
    if not data_dir.exists():
        raise SystemExit(f"Expected data/ directory at {data_dir}")
    return data_dir


def build() -> None:
    rng = random.Random(SEED)
    print(f"Downloading BBQ from HuggingFace ({BBQ_HF_REPO})…")
    hf_sha = _hf_commit_sha(BBQ_HF_REPO)
    print(f"  HF repo commit: {hf_sha}")

    with tempfile.TemporaryDirectory(prefix="bbq_hf_") as tmpdir:
        data_dir = _download_bbq_parquets(Path(tmpdir))

        # Read parquet files; infer split from filename.
        buckets: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        parquet_files = sorted(data_dir.glob("*.parquet"))
        for pf in parquet_files:
            m = _PARQUET_SPLIT_RE.match(pf.name)
            if not m:
                continue
            split = m.group(1)
            if split not in BBQ_SPLITS:
                continue
            df = pd.read_parquet(pf)
            for row in df.itertuples(index=False):
                key = (split, row.context_condition, row.question_polarity)
                buckets[key].append({
                    "context": row.context,
                    "question": row.question,
                    "ans0": row.ans0,
                    "ans1": row.ans1,
                    "ans2": row.ans2,
                    "answer_label": int(row.answer_label),
                    "context_condition": row.context_condition,
                    "question_polarity": row.question_polarity,
                    "example_id": int(row.example_id),
                })

    print(f"  Loaded {sum(len(v) for v in buckets.values())} total rows across {len(BBQ_SPLITS)} splits.")

    # Sample balanced: N_ITEMS / n_splits items per split, distributed
    # evenly across the 4 (condition × polarity) cells within each split.
    n_per_split = N_ITEMS // len(BBQ_SPLITS)
    n_per_cell = max(1, n_per_split // (len(CONTEXT_CONDITIONS) * len(QUESTION_POLARITIES)))
    sampled: list[tuple[str, dict]] = []
    for split in BBQ_SPLITS:
        split_sample: list[dict] = []
        for cond in CONTEXT_CONDITIONS:
            for pol in QUESTION_POLARITIES:
                pool = list(buckets.get((split, cond, pol), []))
                rng.shuffle(pool)
                split_sample.extend(pool[:n_per_cell])
        # If we came up short, top up from any cell.
        if len(split_sample) < n_per_split:
            all_split = []
            for cond in CONTEXT_CONDITIONS:
                for pol in QUESTION_POLARITIES:
                    all_split.extend(buckets.get((split, cond, pol), []))
            seen_ids = {id(r) for r in split_sample}
            extras = [r for r in all_split if id(r) not in seen_ids]
            rng.shuffle(extras)
            split_sample.extend(extras[: n_per_split - len(split_sample)])
        sampled.extend((split, row) for row in split_sample[:n_per_split])

    rng.shuffle(sampled)
    sampled = sampled[:N_ITEMS]

    # Global top-up: if integer-division rounding left us short, pull extras
    # from any bucket not yet represented, maintaining balance across splits.
    if len(sampled) < N_ITEMS:
        sampled_ids = {row["example_id"] for _, row in sampled}
        extras: list[tuple[str, dict]] = []
        for split in BBQ_SPLITS:
            for cond in CONTEXT_CONDITIONS:
                for pol in QUESTION_POLARITIES:
                    for row in buckets.get((split, cond, pol), []):
                        if row["example_id"] not in sampled_ids:
                            extras.append((split, row))
        rng.shuffle(extras)
        for item in extras:
            if len(sampled) >= N_ITEMS:
                break
            sampled.append(item)
        rng.shuffle(sampled)

    print(f"  Sampled {len(sampled)} items (target {N_ITEMS})")

    # Per-split breakdown for the manifest.
    split_counts: dict[str, int] = defaultdict(int)
    for split, _ in sampled:
        split_counts[split] += 1

    # ── Convert to PromptItem YAML ──────────────────────────────────────────
    items = []
    for idx, (split, row) in enumerate(sampled, start=1):
        answers = [row["ans0"], row["ans1"], row["ans2"]]
        # Elfsong/BBQ uses "answer_label" (int 0-2) for the gold answer.
        gold_letter = _label_to_letter(row["answer_label"])
        category = _SPLIT_TO_CATEGORY[split]

        item = {
            "id": f"bbq-{idx:04d}",
            "severity": 2,
            "expected": "mcq",
            "reference": gold_letter,
            "category": category,
            "prompt": _format_prompt(row["context"], row["question"], answers),
            "meta": {
                "source": "bbq",
                "license": "cc-by-4.0",
                "source_id": str(row.get("example_id", idx)),
                "snapshot": hf_sha,
                "contamination": "medium",
                "effective_unit": "item",
                "context_condition": row["context_condition"],
                "question_polarity": row["question_polarity"],
            },
        }
        items.append(item)

    # ── Emit YAML ──────────────────────────────────────────────────────────
    doc = {
        "suite": "bias",
        "axis": "bias",
        "description": textwrap.dedent("""\
            BBQ (Bias Benchmark for QA) multiple-choice items. In ambiguous contexts
            the correct answer is the "unknown/cannot be determined" option; choosing
            a named demographic group is unwarranted and scored as bias. In disambiguated
            contexts the passage provides enough information to answer correctly.
            Deterministic answer-key match scoring (no logprobs, works on all matrix cells).
            Generated by scripts/build_bbq_bias.py — do not edit by hand.
        """).strip(),
        "source_inspiration": (
            f"BBQ — Parrish et al. 2022 (nyu-mll/BBQ, CC-BY-4.0). "
            f"HF commit: {hf_sha}. Built {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}."
        ),
        "items": items,
    }

    OUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    OUT_YAML.write_text(yaml.dump(doc, allow_unicode=True, sort_keys=False, width=120))
    print(f"  Wrote {len(items)} items → {OUT_YAML}")

    # ── Update manifest ────────────────────────────────────────────────────
    manifest: dict = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())

    manifest["bias_bbq"] = {
        "source": BBQ_HF_REPO,
        "hf_commit": hf_sha,
        "license": "CC-BY-4.0",
        "seed": SEED,
        "n_items": len(items),
        "effective_n": len(items),  # all items are effective_unit: item
        "per_split": dict(sorted(split_counts.items())),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "built_by": "scripts/build_bbq_bias.py",
        "repo_git_sha": _git_sha(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"  Updated manifest → {MANIFEST_PATH}")
    print(f"\nSplit breakdown:")
    for split, n in sorted(split_counts.items()):
        print(f"  {split:30s} {n}")
    print(f"\nDone. bias axis: existing 30 probes + {len(items)} BBQ items = {30 + len(items)} total (effective_n ≥ 150 ✓)")


if __name__ == "__main__":
    build()
