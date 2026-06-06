# Beacon Web: React (Vite) UI

The product surface: a streaming chat plus the observability dashboards and a
trace view, in one SPA. Three areas (Chat · Observability · Evaluation), a
persistent conversation sidebar with **list / resume / cancel / new**.

## Stack

React 19 + Vite + TypeScript + Tailwind v4 + Recharts. No backend code here: it
talks to the Beacon gateway over same-origin paths (Vite proxies them in dev).

## Run

```bash
npm install
cp .env.example .env        # VITE_GATEWAY_URL (defaults to http://localhost:8000)
npm run dev                 # http://localhost:5173
```

Needs the gateway running (`uvicorn beacon.gateway.main:app --port 8000`) for live
data; see `../beacon/README.md`.

```bash
npm run build               # typecheck (tsc) + production bundle to dist/
```

## What's where

- `components/ChatView.tsx` - SSE streaming chat, model selector, cancel, inline trace.
- `components/TracePanel.tsx` - per-conversation latency/TTFT waterfall + redaction receipts.
- `components/Dashboard.tsx` - latency percentiles, throughput, errors, cost (Recharts).
- `components/Sidebar.tsx` - conversation list / resume / new.
- `components/EvaluationView.tsx` - Underwriter scorecard shell (filled in Phase 3).
- `lib/sse.ts` - SSE-over-POST reader; `api/client.ts` - typed gateway client.
