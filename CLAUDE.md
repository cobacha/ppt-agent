# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PPT Agent is an AI-powered HTML presentation generator. Users input content (markdown/outline/text), and the system produces professional single-file HTML slide decks through a multi-stage pipeline: content analysis → outline → per-slide HTML generation → quality validation.

## Architecture

**Two-process system:**
- `backend/` — Python FastAPI server (port 8000/8001), handles LLM orchestration and slide generation
- `frontend/` — Next.js 16 + React 19 + Tailwind 4 app (port 8877), editor UI

**Backend Agent pipeline** (`backend/agent/`):
1. `analyzer.py` — Parses user content into a structured `SlideOutline` (title, bullets, content_type, suggested_layout per slide) via Claude API
2. `generator.py` — Produces HTML for each slide using LLM with style presets and layout constraints
3. `validator.py` — Quality gate: checks viewport overflow, layout diversity, bullet density, clamp() usage, font imports
4. `loop.py` — Orchestrates the pipeline; `PPTAgent` class is the singleton entry point

**Key data flow:** The primary generation path is SSE streaming (`POST /api/generate-stream`): outline first, then slides generated in batches of 5 concurrently via ThreadPoolExecutor.

**Frontend pages:**
- `/` — Home/content input
- `/editor` — Slide editor with preview, regen, export
- `/prompts` — Prompt management UI (edit system prompts live)

## Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Frontend
cd frontend
npm install
npm run dev          # starts on port 8877
npm run build
npm run lint

# Tests
cd backend
pytest tests/
```

## Environment Variables

Backend (`backend/.env`):
- `ANTHROPIC_API_KEY` — required
- `MODEL_ID` — Claude model (default: claude-sonnet-4-6-20250514)
- `CORS_ORIGINS` — comma-separated allowed origins

Frontend (`frontend/.env.local`):
- `NEXT_PUBLIC_API_URL` — backend URL (default: http://localhost:8001)
- `PORT` — frontend port (default: 8877)

## Design Constraints (Iron Rules)

These are enforced by the quality gate and must be maintained in all generated HTML:
1. Every slide: `height: 100vh` + `overflow: hidden` — content must never scroll
2. All font sizes use `clamp()` — responsive without breakpoints
3. Consecutive slides must use different layout modes (layout diversity)
4. Single-file output: all CSS/JS inline, zero external dependencies (except Google Fonts)
5. Max 6 bullets per slide; information density must stay low

## LLM Integration

- Uses `anthropic` Python SDK directly (not LangChain)
- System prompts live in `backend/prompts/*.md` — editable at runtime via `/api/prompts` API
- Style presets in `backend/styles/presets.yaml`, layouts in `backend/styles/layouts.yaml`
- Model is configured as singleton `PPTAgent` initialized at server startup

## Post-Change Verification (Mandatory)

After any backend or frontend code change, run:
```bash
./scripts/health-check.sh
```
This verifies both services are responsive and auto-restarts dead ones. If backend was modified, manually verify with:
```bash
curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:8001/api/styles
```
Do NOT report a change as complete until health check passes.

## Frontend Notes

- Next.js 16 with breaking changes from earlier versions — always check `node_modules/next/dist/docs/` before using Next.js APIs
- SSE consumption via custom `frontend/src/lib/sse.ts`
- API client in `frontend/src/lib/api.ts` — all backend calls go through here
