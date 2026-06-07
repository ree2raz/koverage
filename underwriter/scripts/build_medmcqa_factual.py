"""One-time converter: MedMCQA → factual_medmcqa.yaml + SUITES_MANIFEST.json.

Downloads openlifescienceai/medmcqa from HuggingFace via `hf` CLI (MIT license),
samples N_ITEMS from the validation split balanced across medical subjects, and emits:

  underwriter/datasets/suites/factual_medmcqa.yaml
  underwriter/datasets/suites/SUITES_MANIFEST.json  (updated)

Severity 3 throughout: wrong medical advice = clinical/financial misadvice liability.

Run once (or for a fresh snapshot):
  uv run --package underwriter python scripts/build_medmcqa_factual.py

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

import pandas as pd
import yaml

# ── Configuration ──────────────────────────────────────────────────────────────

N_ITEMS = 50
SEED = 7
MEDMCQA_HF_REPO = "openlifescienceai/medmcqa"

# Validation split has all answers (test split does not).
MEDMCQA_SPLIT_FILE = "data/validation-00000-of-00001.parquet"

# cop field: 0→A, 1→B, 2→C, 3→D
_COP_TO_LETTER = {0: "A", 1: "B", 2: "C", 3: "D"}

SUITES_DIR = Path(__file__).resolve().parent.parent / "underwriter" / "datasets" / "suites"
MANIFEST_PATH = SUITES_DIR / "SUITES_MANIFEST.json"
OUT_YAML = SUITES_DIR / "factual_medmcqa.yaml"

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


def _download_parquets(repo: str, cache_dir: Path) -> Path:
    print(f"  hf download --repo-type dataset {repo} …")
    result = subprocess.run(
        ["hf", "download", "--repo-type", "dataset", repo,
         "--local-dir", str(cache_dir), "--include", "*.parquet"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stderr)
        raise SystemExit(f"hf download failed (exit {result.returncode})")
    return cache_dir


def _format_prompt(question: str, opa: str, opb: str, opc: str, opd: str) -> str:
    return (
        f"Question: {question.strip()}\n"
        f"A) {opa.strip()}\n"
        f"B) {opb.strip()}\n"
        f"C) {opc.strip()}\n"
        f"D) {opd.strip()}\n"
        f"Answer with only the letter (A, B, C, D) of the best option."
    )


# ── Main ───────────────────────────────────────────────────────────────────────


def build() -> None:
    rng = random.Random(SEED)
    print(f"Downloading MedMCQA from HuggingFace ({MEDMCQA_HF_REPO})…")
    hf_sha = _hf_commit_sha(MEDMCQA_HF_REPO)
    print(f"  HF repo commit: {hf_sha}")

    with tempfile.TemporaryDirectory(prefix="medmcqa_hf_") as tmpdir:
        cache_dir = _download_parquets(MEDMCQA_HF_REPO, Path(tmpdir))
        pf = cache_dir / MEDMCQA_SPLIT_FILE
        if not pf.exists():
            raise SystemExit(f"Expected parquet at {pf}")
        df = pd.read_parquet(pf)

    # Drop rows with missing gold answer or options.
    df = df.dropna(subset=["cop", "opa", "opb", "opc", "opd", "question"]).reset_index(drop=True)
    df["cop"] = df["cop"].astype(int)
    print(f"  Loaded {len(df)} valid validation rows across {df['subject_name'].nunique()} subjects.")

    # Sample balanced across subjects.
    subjects = df["subject_name"].dropna().unique().tolist()
    n_per_subject = max(1, N_ITEMS // len(subjects))
    buckets: dict[str, list[int]] = defaultdict(list)
    for idx, row in df.iterrows():
        buckets[row["subject_name"]].append(idx)

    sampled_idx: list[int] = []
    for subj in subjects:
        pool = list(buckets[subj])
        rng.shuffle(pool)
        sampled_idx.extend(pool[:n_per_subject])

    # Global top-up to reach exactly N_ITEMS.
    if len(sampled_idx) < N_ITEMS:
        sampled_set = set(sampled_idx)
        extras = [i for i in df.index if i not in sampled_set]
        rng.shuffle(extras)
        sampled_idx.extend(extras[: N_ITEMS - len(sampled_idx)])

    rng.shuffle(sampled_idx)
    sampled_idx = sampled_idx[:N_ITEMS]
    df_sample = df.loc[sampled_idx].reset_index(drop=True)
    print(f"  Sampled {len(df_sample)} items (target {N_ITEMS})")

    subject_counts: dict[str, int] = defaultdict(int)
    for _, row in df_sample.iterrows():
        subject_counts[str(row["subject_name"])] += 1

    # ── Convert to PromptItem YAML ──────────────────────────────────────────
    items = []
    for idx, row in enumerate(df_sample.itertuples(index=False), start=1):
        gold_letter = _COP_TO_LETTER.get(int(row.cop), "A")
        subject = str(row.subject_name) if pd.notna(row.subject_name) else "General"
        item = {
            "id": f"medmcqa-{idx:04d}",
            "severity": 3,   # medical misadvice = highest hallucination liability
            "expected": "mcq",
            "reference": gold_letter,
            "category": subject,
            "prompt": _format_prompt(row.question, row.opa, row.opb, row.opc, row.opd),
            "meta": {
                "source": "medmcqa",
                "license": "mit",
                "source_id": str(row.id),
                "snapshot": hf_sha,
                "contamination": "medium",
                "effective_unit": "item",
            },
        }
        items.append(item)

    # ── Emit YAML ──────────────────────────────────────────────────────────
    doc = {
        "suite": "factual",
        "axis": "hallucination",
        "description": textwrap.dedent("""\
            MedMCQA items (openlifescienceai/medmcqa, MIT). Medical multiple-choice questions
            from Indian entrance exams (AIIMS/NEET-PG). Severity 3: wrong answer = clinical
            misadvice liability. Deterministic answer-key match scoring (no logprobs needed,
            consistent across all matrix cells). Balanced across medical subjects.
            Generated by scripts/build_medmcqa_factual.py — do not edit by hand.
        """).strip(),
        "source_inspiration": (
            f"MedMCQA — Pal et al. 2022 (openlifescienceai/medmcqa, MIT). "
            f"HF commit: {hf_sha}. "
            f"Built {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}."
        ),
        "items": items,
    }

    SUITES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_YAML.write_text(yaml.dump(doc, allow_unicode=True, sort_keys=False, width=120))
    print(f"  Wrote {len(items)} items → {OUT_YAML}")

    # ── Update manifest ────────────────────────────────────────────────────
    manifest: dict = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())

    manifest["factual_medmcqa"] = {
        "source": MEDMCQA_HF_REPO,
        "hf_commit": hf_sha,
        "license": "MIT",
        "seed": SEED,
        "n_items": len(items),
        "effective_n": len(items),
        "per_subject": dict(sorted(subject_counts.items())),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "built_by": "scripts/build_medmcqa_factual.py",
        "repo_git_sha": _git_sha(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"  Updated manifest → {MANIFEST_PATH}")

    print(f"\nSubject breakdown:")
    for subj, n in sorted(subject_counts.items()):
        print(f"  {subj:40s} {n}")
    print(f"\nDone. hallucination axis: existing 30 + HaluEval 120 + MedMCQA {len(items)} = "
          f"{30 + 120 + len(items)} total (effective_n ≥ 175 ✓)")


if __name__ == "__main__":
    build()
