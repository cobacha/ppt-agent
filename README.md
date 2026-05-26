# PPT Agent

> Text in, slides out.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/cobacha/ppt-agent?style=social)](https://github.com/cobacha/ppt-agent)
[![Docker](https://img.shields.io/badge/Docker-ready-blue?logo=docker)](docker-compose.yml)

[English](README.md) | [中文](README.zh-CN.md)

**Turn any text or URL into animated, professional slides in 30 seconds.**

An open-source AI presentation generator — no signup, no watermarks, no vendor lock-in. Self-hostable with your own API key. Output is a single HTML file that works anywhere.

<p align="center">
  <img src="docs/screenshots/home.png" alt="PPT Agent — Home Page" width="720" />
</p>

<p align="center">
  <img src="docs/screenshots/editor.png" alt="PPT Agent — Editor" width="720" />
</p>

## Why PPT Agent?

| | PPT Agent | Gamma.app | Beautiful.ai | Google Slides + AI |
|---|---|---|---|---|
| Self-hostable | Yes | No | No | No |
| URL → Slides | Yes | No | No | No |
| No signup required | Yes | No | No | No |
| Single-file export | Yes | No | No | No |
| Theme remix (free) | Yes | Paid | Paid | Limited |
| Open source | MIT | Closed | Closed | Closed |

## Features

### Input — Zero Friction
- **Paste a URL** — blog post, docs page, article → slides automatically
- **Paste text** — markdown, bullet points, freeform paragraphs
- **3 example templates** — start generating in one click

### Generation — AI That Understands Design
- **18 curated themes** — hand-crafted style presets, not random AI aesthetics
- **Quality auto-retry** — slides that fail design checks get regenerated automatically
- **Smart layouts** — consecutive slides never repeat the same layout
- **Streaming generation** — watch your deck come to life in real-time

### Editor — Visual and Intuitive
- **Thumbnail sidebar** — see all slides at a glance with visual previews
- **Drag-to-reorder** — rearrange slides by dragging, not clicking arrows
- **Per-slide regeneration** — don't like one slide? Regenerate with a custom prompt
- **Quick Theme Remix** — switch all slides to a different theme instantly
- **Undo support** — every edit is reversible

### Presentation — Ready to Present
- **Presenter mode** — speaker notes, timer, current/next slide preview
- **Cinematic animations** — elements fade and slide in with staggered timing
- **Grid overview** — press `G` in exported HTML to see all slides at once
- **Keyboard navigation** — arrow keys, fullscreen, escape to exit

### Export — Your Slides, Your Way
- **Single HTML file** — all CSS/JS inline, zero dependencies, works offline
- **Smart filenames** — exports use your presentation title, not "download.html"
- **PDF export** — one-click PDF generation
- **No lock-in** — it's just HTML. Host it, email it, edit it, embed it

### Production-Ready
- **Rate limiting** — 10 requests/min per IP, ready for shared deployments
- **Health endpoint** — `/health` for monitoring and load balancers
- **History persistence** — SQLite-backed generation history
- **Live prompt editing** — modify AI behavior at runtime without restarting

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- [Anthropic API key](https://console.anthropic.com/)

### Option 1: Docker (recommended)

```bash
git clone https://github.com/cobacha/ppt-agent.git
cd ppt-agent
echo "ANTHROPIC_API_KEY=sk-ant-..." > backend/.env
docker compose up
```

Open http://localhost:8877 — paste a URL or text and generate.

### Option 2: Manual Setup

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8001

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:8877.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Your Anthropic API key |
| `MODEL_ID` | `claude-sonnet-4-6` | Claude model to use |
| `CORS_ORIGINS` | `http://localhost:8877` | Allowed CORS origins (comma-separated) |

## Supported Models

PPT Agent uses **Claude** (Anthropic) by default. You can also use any OpenAI-compatible API by setting:

```bash
ANTHROPIC_BASE_URL=https://your-openai-compatible-endpoint.com/v1
MODEL_ID=your-model-name
```

This works with providers like OpenRouter, Azure OpenAI, Together AI, or any local server that exposes an OpenAI-compatible chat completions endpoint.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 16 + React 19 + Tailwind 4)              │
│  Visual editor, thumbnails, drag-reorder, presenter mode    │
├─────────────────────────────────────────────────────────────┤
│            SSE Stream + REST API (port 8001)                 │
├─────────────────────────────────────────────────────────────┤
│  Backend (FastAPI + Anthropic SDK)                           │
│                                                             │
│  URL Import ─→ Analyzer ─→ Expander ─→ Generator ─→ QA Gate│
│  (extract)     (outline)   (details)    (HTML×5)    (retry) │
└─────────────────────────────────────────────────────────────┘
```

**Pipeline:** Content is analyzed into a structured outline, expanded with rich detail, then rendered as HTML slides in parallel batches of 5. A quality gate checks each slide for viewport overflow, layout diversity, bullet density, and responsive typography — failures are regenerated automatically.

## Design Principles

These rules are enforced by the quality gate on every generated slide:

1. **Viewport-locked** — `height: 100vh` + `overflow: hidden`. Slides never scroll.
2. **Responsive typography** — All font sizes use `clamp()`. No breakpoints needed.
3. **Layout diversity** — Consecutive slides automatically use different layouts.
4. **Self-contained** — All CSS/JS inline. One HTML file, zero external dependencies.
5. **Low density** — Max 6 bullets per slide. White space is a feature.

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/generate-stream` | Full SSE streaming generation |
| POST | `/api/import-url` | Extract content from a URL |
| POST | `/api/outline` | Generate outline only |
| POST | `/api/generate-slide` | Generate a single slide |
| POST | `/api/regen` | Regenerate slide with custom prompt |
| POST | `/api/export` | Assemble final HTML with animations |
| POST | `/api/export-pdf` | Export as PDF via Playwright |
| GET | `/api/styles` | List available style presets |
| GET/PUT | `/api/prompts/{file}` | Read/update system prompts at runtime |
| GET | `/api/history` | List generation history |
| GET | `/health` | Health check for monitoring |

## Project Structure

```
ppt-agent/
├── backend/
│   ├── agent/           # Pipeline: analyzer, expander, generator, validator, loop
│   ├── prompts/         # LLM system prompts (editable at runtime via API)
│   ├── styles/          # 18 style presets + layout definitions (YAML)
│   ├── templates/       # Base HTML/CSS template
│   ├── main.py          # FastAPI server + all endpoints
│   └── db.py            # SQLite history persistence
├── frontend/
│   └── src/
│       ├── app/         # Pages: home, editor, prompts manager
│       ├── components/  # SlidePreview, SlideList, Toolbar, PresenterMode...
│       ├── hooks/       # useGeneration (core state), useHistory
│       └── lib/         # API client, SSE handler
└── output/              # Generated presentations (gitignored)
```

## Themes

<p align="center">
  <img src="docs/screenshots/themes.png" alt="PPT Agent — 18 Themes" width="720" />
</p>

PPT Agent ships with 18 curated themes designed for different contexts:

| Business | Creative | Technical | Minimal |
|----------|----------|-----------|---------|
| Bold Signal | Electric Studio | Code Carbon | Clean Slate |
| Corporate Blue | Dark Botanical | Terminal Green | Paper White |
| Executive Gray | Sunset Warm | Blueprint | Swiss Grid |
| ... | ... | ... | ... |

Switch between themes instantly with the Remix button — no regeneration wait.

## Contributing

Contributions welcome! Areas where help is appreciated:

- **New themes** — Add style presets in `backend/styles/presets.yaml`
- **Layout patterns** — Expand `backend/styles/layouts.yaml` with new slide structures
- **Export formats** — PPTX, Keynote, or reveal.js output
- **Internationalization** — UI translations

```bash
# Run backend tests
cd backend && pytest tests/

# Run frontend linting
cd frontend && npm run lint
```

## License

MIT — use it however you want. Commercial use, modification, distribution, all permitted.

---

<p align="center">
  Built with <a href="https://www.anthropic.com">Claude</a> | 
  <a href="#quick-start">Get Started</a> | 
  <a href="https://github.com/cobacha/ppt-agent/issues">Report Issue</a>
</p>
