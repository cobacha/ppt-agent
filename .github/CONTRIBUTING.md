# Contributing to PPT Agent

Thanks for your interest in contributing! This guide covers setup, workflow, and guidelines.

## Local Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/ppt-agent.git
cd ppt-agent

# 2. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8001

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Verify both are running: http://localhost:8877 (frontend) and http://localhost:8001/health (backend).

## Pull Request Guidelines

### Branch naming

Use descriptive names: `feat/new-theme-dark-ocean`, `fix/export-pdf-timeout`, `docs/api-examples`.

### PR title format

```
feat: add dark ocean theme
fix: PDF export timeout on large decks
docs: add API usage examples
```

Prefixes: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

### PR description

- Explain **what** changed and **why**
- Include screenshots/GIFs for any UI changes
- Note any breaking changes or new environment variables

### Before submitting

1. Backend: `cd backend && pytest tests/`
2. Frontend: `cd frontend && npm run lint`
3. Verify the app works end-to-end (generate slides, export HTML)

## Code Style

### Python (backend)

- Formatter/linter: [ruff](https://docs.astral.sh/ruff/)
- Run: `ruff check . && ruff format --check .`
- Type hints encouraged for function signatures

### TypeScript (frontend)

- ESLint + Prettier (configured in `frontend/.eslintrc*` and `.prettierrc`)
- Run: `npm run lint`

### General

- No commented-out code in PRs
- Keep functions focused — one responsibility per function
- Write descriptive variable names over comments

## Areas Where Contributions Are Welcome

| Area | What to do | Where |
|------|-----------|-------|
| **Themes** | Add new style presets | `backend/styles/presets.yaml` |
| **Layouts** | New slide layout patterns | `backend/styles/layouts.yaml` |
| **Export formats** | PPTX, Keynote, reveal.js | `backend/agent/` |
| **i18n** | UI translations | `frontend/src/` |
| **Documentation** | Usage examples, tutorials | `docs/` |
| **Tests** | Expand test coverage | `backend/tests/`, `frontend/` |

## Questions?

Open a [Discussion](../../discussions) or file an issue. We're happy to help you find a good first contribution.
