✅ Phase 3 — Underwriter: done, committed (1eaa0d7), pushed. Stopping here as asked.

  How to test what's built so far

  1. The evaluation harness — fully offline, no keys, no spend

  cd /home/rituraj/projects/olive-jd-assignment/platform && uv sync

  uv run pytest                              # 26 tests (core + Beacon SDK +
  Underwriter scoring)
  uv run python -m underwriter.cli demo      # synthetic scorecard → 1-page PDF +
  publishes to web
  open underwriter/runs/demo/scorecard.pdf   # the infographic scorecard
  The demo proves the whole pipeline (risk model → severity-weighted stats → bootstrap
  CIs → Cohen's κ → Insurability Index → PDF → web JSON) without an API call.

  2. The web app — see all three areas

  cd web && npm install && npm run dev       # http://localhost:5173
  - Evaluation tab → renders the demo scorecard live (insurability ranking, per-axis
  risk + 95% CI + κ, guardrail uplift, "⚠ synthetic demo" badge).
  - Chat / Observability → UI renders; live data needs the gateway (below).

  3. Live evaluation (needs your OPENROUTER_API_KEY in .env)

  uv run python -m underwriter.cli run --smoke   # 2 prompts/suite, guard off — cheap
  sanity (~spends a little)
  uv run python -m underwriter.cli run           # full: all suites × guard on/off ×
  dual judges
  Then refresh the web Evaluation tab — the real scorecard replaces the synthetic one.

  4. Full Beacon pipeline live (Docker + key) — from Phase 1, unchanged

  docker compose -f deploy/docker-compose.yml up -d
  cd beacon && uv run alembic upgrade head && cd ..
  # 3 terminals: ingestion (:8088), worker, gateway (:8000) — see beacon/README.md
  Chat through the UI → watch redacted inference logs + the trace waterfall +
  dashboards populate.

  What I can't do for you

  The live Underwriter run and the live Beacon pipeline need your OPENROUTER_API_KEY
  (and Docker for Beacon) — those are yours to run. Everything else (tests, demo
  scorecard, PDF, the whole UI) runs offline right now.

  Two open items for later (not blocking): drop in OSS_SPACE_URL when your HF Space is
  up so Underwriter does the OSS-vs-frontier comparison, and GEMINI_API_KEY isn't
  needed since the second judge routes through OpenRouter.

  Remaining: Phase 4 (one-command Docker Compose for all services + k8s + hardening)
  and Phase 5 (docs/demo/submission).

