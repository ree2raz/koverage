"""Shared helpers for the dataset-builder scripts (`build_*.py`).

These were copy-pasted verbatim across every builder; keeping one copy here means
a change to how we capture provenance (git/HF SHAs) or pull a HF dataset happens
in exactly one place. Builders import the names they need:

    from _common import git_sha, hf_commit_sha, hf_download

(The scripts run directly — `python scripts/build_x.py` — so their own directory
is on sys.path and this bare import resolves.)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def hf_commit_sha(repo: str) -> str:
    """Resolve the HEAD commit SHA of a HF dataset repo via the API."""
    try:
        import urllib.request
        url = f"https://huggingface.co/api/datasets/{repo}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        return data.get("sha", "unknown")
    except Exception:
        return "unknown"


def hf_download(repo: str, cache_dir: Path) -> Path:
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
