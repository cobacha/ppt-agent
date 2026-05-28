"""
PPT Agent - FastAPI Backend

Run: uvicorn main:app --reload --port 8001
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import html as html_mod
import json
import logging
import os
import queue
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from agent.loop import PPTAgent, SlideResult
from db import (
    init_db, save_generation, list_generations, get_generation, delete_generation,
    create_generation, update_generation_slides, complete_generation, get_active_generation,
    cleanup_stale_generations,
)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ppt-agent")

# --- Module-level shared resources ---
STYLES_DIR = Path(__file__).parent / "styles"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

executor = ThreadPoolExecutor(max_workers=12, thread_name_prefix="ppt-gen")

# Singleton PPTAgent instance (initialized at startup)
_agent: PPTAgent | None = None


def get_agent() -> PPTAgent:
    """Return the singleton PPTAgent (thread-safe: no mutable state modified)."""
    global _agent
    if _agent is None:
        _agent = PPTAgent()
    return _agent


# --- Rate Limiter ---
class RateLimiter:
    """Simple in-memory rate limiter: max N requests per minute per IP."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        # Clean old entries for this IP
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]
        if len(self._requests[ip]) >= self.max_requests:
            return False
        self._requests[ip].append(now)
        return True

    def cleanup(self):
        """Remove stale IPs entirely."""
        now = time.time()
        cutoff = now - self.window_seconds
        stale_keys = [k for k, v in self._requests.items() if all(t <= cutoff for t in v)]
        for k in stale_keys:
            del self._requests[k]


rate_limiter = RateLimiter(max_requests=5, window_seconds=60)

# Generation endpoints that should be rate-limited
RATE_LIMITED_PATHS = {"/api/generate", "/api/generate-slide", "/api/generate-slides-batch", "/api/generate-stream", "/api/outline", "/api/regen", "/api/import-url"}

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
LOCALHOST_IPS = {"127.0.0.1", "::1", "localhost"}


def _check_admin(request: Request):
    """Verify admin access. When ADMIN_TOKEN is set, always require it (proxy-safe).
    When no token configured, fall back to localhost IP check (dev mode)."""
    token = request.headers.get("X-Admin-Token", "")
    if ADMIN_TOKEN:
        if token == ADMIN_TOKEN:
            return
        raise HTTPException(403, "Admin access required")
    # No token configured — only allow from localhost (dev mode)
    client_ip = request.client.host if request.client else ""
    if client_ip in LOCALHOST_IPS:
        return
    raise HTTPException(403, "Admin access required")


# --- Lifespan ---
async def _periodic_rate_limiter_cleanup():
    """Purge stale IPs every 5 minutes to prevent unbounded memory growth."""
    import asyncio
    while True:
        await asyncio.sleep(300)
        rate_limiter.cleanup()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    init_db()
    cleanup_stale_generations()
    logger.info("Initializing PPTAgent singleton...")
    _agent = PPTAgent()
    logger.info("PPTAgent ready.")
    import asyncio
    cleanup_task = asyncio.create_task(_periodic_rate_limiter_cleanup())
    yield
    cleanup_task.cancel()
    executor.shutdown(wait=True, cancel_futures=True)
    logger.info("Shutdown complete.")


app = FastAPI(title="PPT Agent", version="0.2.0", lifespan=lifespan)

# --- CORS from environment ---
cors_origins_str = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:8877",
)
cors_origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request Logging Middleware ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)")
    return response


# --- Rate Limiting Middleware ---
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in RATE_LIMITED_PATHS:
        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.is_allowed(client_ip):
            from fastapi.responses import JSONResponse
            rate_limiter.cleanup()
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
            )
    response = await call_next(request)
    return response


# --- Request/Response Models ---

class GenerateRequest(BaseModel):
    content: str
    style: str = "corporate-navy"
    max_iterations: int = 3
    language: str = "zh"


class SlideDTO(BaseModel):
    index: int
    title: str
    html: str
    quality_score: float


class GenerateResponse(BaseModel):
    slides: list[SlideDTO]
    full_html: str
    iterations: int
    score: float
    issues: list[str]


class RegenRequest(BaseModel):
    slide_index: int
    content: str
    layout: str = "auto"
    style: str = "corporate-navy"
    context: str = ""
    context_slides: list[dict] = []


class RegenResponse(BaseModel):
    html: str
    quality_score: float


class OutlineRequest(BaseModel):
    content: str
    style: str = "corporate-navy"
    language: str = "zh"


class SlideSpecDTO(BaseModel):
    index: int
    title: str
    bullets: list[str]
    content_type: str
    suggested_layout: str


class OutlineResponse(BaseModel):
    title: str
    subtitle: str
    slides: list[SlideSpecDTO]


class GenerateSlideRequest(BaseModel):
    slide_spec: dict
    style: str = "corporate-navy"
    slide_index: int
    context_slides: list[dict] = []


class GenerateSlideResponse(BaseModel):
    html: str
    quality_score: float


class ExportRequest(BaseModel):
    slides: list[dict]
    style: str = "corporate-navy"
    title: str = ""


class ValidateRequest(BaseModel):
    html: str


class ValidateResponse(BaseModel):
    passed: bool
    score: float
    issues: list[str]
    warnings: list[str]


def validate_content(content: str) -> str | None:
    """Validate input content. Returns error message or None if valid."""
    stripped = content.strip()
    if not stripped:
        return "内容不能为空"
    if len(stripped) > 50000:
        return f"内容过长（{len(stripped)} 字符），请精简至 50,000 字符以内"
    non_printable_ratio = sum(1 for c in stripped[:500] if not c.isprintable() and c not in '\n\r\t') / min(len(stripped), 500)
    if non_printable_ratio > 0.3:
        return "输入内容包含大量非文本字符，请粘贴文本内容"
    return None


import re as _re


def _safe_filename(title: str, ext: str) -> str:
    """Generate a safe filename from presentation title."""
    if not title.strip():
        return f"presentation.{ext}"
    safe = _re.sub(r'[^\w一-鿿\s-]', '', title.strip())
    safe = _re.sub(r'\s+', '_', safe)[:50]
    return f"{safe}.{ext}" if safe else f"presentation.{ext}"


# --- Endpoints ---

@app.get("/api/health")
async def health():
    """Health check for monitoring and Docker healthcheck."""
    db_ok = False
    try:
        db_ok = get_generation("__healthcheck__") is None or True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "model": os.environ.get("MODEL_ID", "claude-sonnet-4-6"),
        "version": "1.0.0",
        "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "db": "ok" if db_ok else "error",
    }


class ImportURLRequest(BaseModel):
    url: str


@app.post("/api/import-url")
async def import_url(req: ImportURLRequest):
    """Fetch a URL and extract text content for slide generation."""
    import ipaddress
    import socket
    import httpx
    from urllib.parse import urlparse
    from bs4 import BeautifulSoup

    url = req.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="仅支持 http/https 链接")

    # SSRF protection: resolve hostname, reject private IPs, pin resolved address
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=422, detail="无效的链接地址")
    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        safe_ip = None
        for family, _, _, _, sockaddr in resolved:
            ip = ipaddress.ip_address(sockaddr[0])
            if hasattr(ip, 'ipv4_mapped') and ip.ipv4_mapped:
                ip = ip.ipv4_mapped
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                raise HTTPException(status_code=422, detail="不允许访问内网地址")
            if safe_ip is None:
                safe_ip = str(ip)
        if not safe_ip:
            raise HTTPException(status_code=422, detail="无法解析该域名")
    except socket.gaierror:
        raise HTTPException(status_code=422, detail="无法解析该域名")

    # Pin the resolved IP to prevent DNS rebinding
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    pinned_url = f"{parsed.scheme}://{safe_ip}:{port}{parsed.path}"
    if parsed.query:
        pinned_url += f"?{parsed.query}"

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=15.0) as client:
            resp = await client.get(pinned_url, headers={"User-Agent": "Mozilla/5.0 PPTAgent/1.0", "Host": hostname})
            if resp.is_redirect:
                raise HTTPException(status_code=422, detail="链接发生了重定向，请使用最终地址")
            resp.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=422, detail="请求超时，请检查链接是否可访问")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=422, detail=f"无法访问该链接（HTTP {e.response.status_code}）")
    except httpx.RequestError:
        raise HTTPException(status_code=422, detail="网络请求失败，请检查链接")

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        raise HTTPException(status_code=422, detail="仅支持 HTML 页面，PDF 等格式请直接粘贴文本")

    if len(resp.content) > 50 * 1024:
        html_text = resp.content[:50 * 1024].decode("utf-8", errors="ignore")
    else:
        html_text = resp.text

    soup = BeautifulSoup(html_text, "html.parser")

    # Remove noise elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "aside", "header", "noscript"]):
        tag.decompose()

    # Extract title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Find main content
    main = soup.find("article") or soup.find("main") or soup.find("body")
    if not main:
        raise HTTPException(status_code=422, detail="无法从该页面提取有效内容")

    # Convert to markdown-like text
    lines = []
    for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        text = el.get_text(strip=True)
        if not text:
            continue
        if el.name in ("h1", "h2"):
            lines.append(f"# {text}")
        elif el.name in ("h3", "h4"):
            lines.append(f"## {text}")
        elif el.name == "li":
            lines.append(f"- {text}")
        elif el.name == "blockquote":
            lines.append(f"> {text}")
        else:
            lines.append(text)

    content = "\n\n".join(lines)

    # Truncate at ~5000 words
    words = content.split()
    truncated = False
    if len(words) > 5000:
        content = " ".join(words[:5000])
        truncated = True

    if len(content.strip()) < 100:
        raise HTTPException(status_code=422, detail="提取到的内容过少，该页面可能需要登录或为付费内容")

    result = {"content": content, "title": title, "word_count": len(content.split())}
    if truncated:
        result["warning"] = "内容已截断至约 5000 词"
    return result


@app.get("/api/styles")
async def list_styles():
    presets_path = STYLES_DIR / "presets.yaml"
    if not presets_path.exists():
        return {"presets": []}

    with open(presets_path) as f:
        data = yaml.safe_load(f)

    presets = []
    for key, val in data.items():
        presets.append({
            "id": key,
            "name": val.get("name", key),
            "vibe": val.get("vibe", ""),
            "colors": val.get("colors", {}),
            "fonts": val.get("fonts", {}),
        })

    return {"presets": presets}


@app.get("/api/layouts")
async def list_layouts():
    layouts_path = STYLES_DIR / "layouts.yaml"
    if not layouts_path.exists():
        return {"layouts": []}

    with open(layouts_path) as f:
        data = yaml.safe_load(f)

    return {"layouts": data.get("layouts", {})}


@app.post("/api/outline", response_model=OutlineResponse)
async def get_outline(req: OutlineRequest):
    """Stage 1: Generate slide outline (fast, no HTML)."""
    error = validate_content(req.content)
    if error:
        raise HTTPException(status_code=422, detail=error)
    agent = get_agent()
    outline = agent.generate_outline(req.content, language=req.language)

    slides = [
        SlideSpecDTO(
            index=i,
            title=s.title,
            bullets=s.bullets,
            content_type=s.content_type,
            suggested_layout=s.suggested_layout,
        )
        for i, s in enumerate(outline.slides)
    ]

    return OutlineResponse(title=outline.title, subtitle=outline.subtitle, slides=slides)


@app.post("/api/generate-slide", response_model=GenerateSlideResponse)
async def generate_single_slide(req: GenerateSlideRequest):
    """Stage 2: Generate a single slide with context."""
    agent = get_agent()
    result = agent.generate_single_from_spec(
        spec=req.slide_spec,
        style=req.style,
        slide_index=req.slide_index,
        context_slides=req.context_slides,
    )

    return GenerateSlideResponse(html=result.html, quality_score=result.quality_score)


class DuplicateSlideRequest(BaseModel):
    source_html: str
    new_content: str | None = None
    style: str = "corporate-navy"
    slide_index: int = 0


class DuplicateSlideResponse(BaseModel):
    html: str
    quality_score: float


@app.post("/api/duplicate-slide", response_model=DuplicateSlideResponse)
async def duplicate_slide(req: DuplicateSlideRequest):
    """Duplicate a slide, optionally regenerating with new content in the same layout style."""
    if not req.new_content:
        return DuplicateSlideResponse(html=req.source_html, quality_score=100.0)

    agent = get_agent()
    result = agent.regenerate_slide(
        slide_index=req.slide_index,
        content=req.new_content,
        layout="auto",
        style=req.style,
        context=f"Match the visual layout and style of this reference slide:\n{req.source_html[:2000]}",
    )
    return DuplicateSlideResponse(html=result.html, quality_score=result.quality_score)


class BatchSlideRequest(BaseModel):
    slide_specs: list[dict]
    style: str = "corporate-navy"
    start_index: int = 0
    context_slides: list[dict] = []


class BatchSlideResponse(BaseModel):
    results: list[GenerateSlideResponse]


@app.post("/api/generate-slides-batch", response_model=BatchSlideResponse)
async def generate_slides_batch(req: BatchSlideRequest):
    """Generate multiple slides concurrently."""
    agent = get_agent()

    def gen_one(spec: dict, idx: int, ctx: list[dict]) -> GenerateSlideResponse:
        result = agent.generate_single_from_spec(
            spec=spec, style=req.style, slide_index=idx, context_slides=ctx,
        )
        return GenerateSlideResponse(html=result.html, quality_score=result.quality_score)

    loop = asyncio.get_event_loop()

    futures = []
    for i, spec in enumerate(req.slide_specs):
        idx = req.start_index + i
        futures.append(loop.run_in_executor(executor, gen_one, spec, idx, req.context_slides))

    results = await asyncio.gather(*futures)
    return BatchSlideResponse(results=list(results))


class StreamRequest(BaseModel):
    content: str
    style: str = "corporate-navy"
    language: str = "zh"
    aspect_ratio: str = "16:9"
    request_id: str | None = None


# Track recent request_ids to prevent duplicate generation on SSE retry (TTL 10 min, max 200)
_recent_request_ids: dict[str, tuple[str, float]] = {}  # request_id -> (gen_id, timestamp)

# Concurrency gate: limit simultaneous SSE generations
_generation_semaphore = asyncio.Semaphore(3)


@app.post("/api/generate-stream")
async def generate_stream(req: StreamRequest, request: Request):
    """SSE endpoint that streams slide generation progress."""
    error = validate_content(req.content)
    if error:
        raise HTTPException(status_code=422, detail=error)

    # Dedup: if client retries with same request_id, redirect to existing generation
    if req.request_id and req.request_id in _recent_request_ids:
        existing_gen_id, _ts = _recent_request_ids[req.request_id]
        existing = get_generation(existing_gen_id)
        if existing and existing.get("status") in ("generating", "completed"):
            async def resume_generator():
                yield f"event: resume\ndata: {json.dumps({'gen_id': existing_gen_id, 'status': existing.get('status')})}\n\n"
                yield f"event: done\ndata: {json.dumps({'gen_id': existing_gen_id})}\n\n"
            return StreamingResponse(resume_generator(), media_type="text/event-stream")

    async def event_generator():
        try:
            await asyncio.wait_for(_generation_semaphore.acquire(), timeout=2.0)
        except asyncio.TimeoutError:
            yield f"event: error\ndata: {json.dumps({'message': '服务繁忙，请稍后重试'})}\n\n"
            yield f"event: done\ndata: {json.dumps({})}\n\n"
            return
        gen_id = None
        generation_completed = False
        try:
            agent = get_agent()

            # Stage 1: Generate outline with streaming thinking
            loop = asyncio.get_event_loop()
            outline = None
            try:
                # We need to yield thinking events as they come, so use a queue
                think_queue: queue.Queue[str | None] = queue.Queue()

                streaming_outline_result: list = []  # mutable container for thread result

                def run_streaming_with_queue():
                    try:
                        buffer = ""
                        gen = agent.analyzer.analyze_streaming(req.content, language=req.language)
                        try:
                            while True:
                                chunk = next(gen)
                                buffer += chunk
                                if len(buffer) >= 20:
                                    think_queue.put(buffer)
                                    buffer = ""
                        except StopIteration as stop:
                            streaming_outline_result.append(stop.value)
                        if buffer:
                            think_queue.put(buffer)
                    except Exception as e:
                        think_queue.put(None)
                        raise
                    finally:
                        think_queue.put(None)  # sentinel

                future = loop.run_in_executor(executor, run_streaming_with_queue)

                # Consume thinking chunks — poll without blocking the event loop or exhausting threads
                while True:
                    try:
                        chunk = think_queue.get_nowait()
                    except queue.Empty:
                        if future.done():
                            # Drain any remaining items
                            while not think_queue.empty():
                                c = think_queue.get_nowait()
                                if c is not None:
                                    yield f"event: thinking\ndata: {json.dumps({'text': c}, ensure_ascii=False)}\n\n"
                            break
                        await asyncio.sleep(0.15)
                        continue

                    if chunk is None:
                        break
                    yield f"event: thinking\ndata: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

                # Wait for the future to complete (handles exceptions)
                await future
                outline = streaming_outline_result[0] if streaming_outline_result else agent.get_last_outline()
            except Exception as e:
                # Fallback to non-streaming outline (retry up to 2 times)
                logger.warning(f"Streaming outline failed, falling back: {e}")
                for attempt in range(2):
                    try:
                        outline = agent.generate_outline(req.content, language=req.language)
                        break
                    except Exception as retry_err:
                        if attempt == 1:
                            raise retry_err
                        logger.warning(f"Outline retry {attempt+1} failed: {retry_err}")

            outline_data = {
                "title": outline.title,
                "subtitle": outline.subtitle,
                "slides": [
                    {
                        "index": i,
                        "title": s.title,
                        "bullets": s.bullets,
                        "content_type": s.content_type,
                        "suggested_layout": s.suggested_layout,
                    }
                    for i, s in enumerate(outline.slides)
                ],
            }

            # Persist to DB: create generation record with placeholder slides (include bullets for resume)
            gen_title = outline.title or (outline.slides[0].title if outline.slides else "")
            initial_slides = [
                {"index": i, "title": s.title, "html": "", "quality_score": 0, "bullets": s.bullets}
                for i, s in enumerate(outline.slides)
            ]
            gen_id = create_generation(
                content=req.content, style=req.style,
                title=gen_title, slides=initial_slides, status="generating",
            )
            if req.request_id:
                now = time.time()
                _recent_request_ids[req.request_id] = (gen_id, now)
                # Evict expired entries (>10 min) and cap at 200
                if len(_recent_request_ids) > 200:
                    cutoff = now - 600
                    expired = [k for k, (_, ts) in _recent_request_ids.items() if ts <= cutoff]
                    for k in expired:
                        _recent_request_ids.pop(k, None)
                    if len(_recent_request_ids) > 200:
                        oldest = sorted(_recent_request_ids.items(), key=lambda x: x[1][1])[:100]
                        for k, _ in oldest:
                            _recent_request_ids.pop(k, None)
            # Track slides for DB updates
            db_slides = list(initial_slides)

            outline_data["gen_id"] = gen_id
            yield f"event: outline\ndata: {json.dumps(outline_data, ensure_ascii=False)}\n\n"

            # Stage 2: Generate slides in batches (expand + render per slide)
            BATCH_SIZE = 3
            context_slides: list[dict] = []
            slide_events: queue.Queue[dict | None] = queue.Queue()

            def gen_one_with_expand(spec, idx: int, ctx: list[dict]) -> dict:
                """Per-slide: expand content → render HTML → quality check (three-step)."""
                # Step 1: Expand content
                slide_events.put({"type": "slide_step", "index": idx, "step": "expanding", "title": spec.title})
                expanded = agent.expand_slide(idx, spec)
                spec_dict = {
                    "title": spec.title,
                    "bullets": spec.bullets,
                    "content_type": spec.content_type,
                    "suggested_layout": spec.suggested_layout,
                    "detailed_content": expanded.detailed_content,
                    "aspect_ratio": req.aspect_ratio,
                }
                # Step 2: Generate HTML (includes LLM quality check + auto-retry)
                slide_events.put({"type": "slide_step", "index": idx, "step": "rendering", "title": spec.title})
                result = agent.generate_single_from_spec(
                    spec=spec_dict,
                    style=req.style,
                    slide_index=idx,
                    context_slides=ctx,
                    language=req.language,
                )
                return {
                    "index": idx,
                    "html": result.html,
                    "quality_score": result.quality_score,
                    "title": spec.title,
                }

            for batch_start in range(0, len(outline.slides), BATCH_SIZE):
                if await request.is_disconnected():
                    return

                batch_end = min(batch_start + BATCH_SIZE, len(outline.slides))
                batch_specs = outline.slides[batch_start:batch_end]

                # Notify frontend which slides are being generated concurrently
                yield f"event: batch_start\ndata: {json.dumps({'start': batch_start, 'end': batch_end})}\n\n"

                ctx_snapshot = context_slides[-3:]
                futures = []
                for i, spec in enumerate(batch_specs):
                    idx = batch_start + i
                    futures.append(
                        loop.run_in_executor(executor, gen_one_with_expand, spec, idx, ctx_snapshot)
                    )

                # Drain slide_step events while waiting for batch to complete
                gather_task = asyncio.ensure_future(asyncio.gather(*futures, return_exceptions=True))
                while not gather_task.done():
                    try:
                        evt = slide_events.get_nowait()
                        if evt:
                            yield f"event: {evt['type']}\ndata: {json.dumps(evt, ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        pass
                    await asyncio.sleep(0.1)

                # Drain remaining events
                while not slide_events.empty():
                    evt = slide_events.get_nowait()
                    if evt:
                        yield f"event: {evt['type']}\ndata: {json.dumps(evt, ensure_ascii=False)}\n\n"

                results = gather_task.result()

                failed_slides = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        failed_idx = batch_start + i
                        failed_slides.append((failed_idx, batch_specs[i]))
                        logger.error(f"Slide {failed_idx+1} generation failed: {result}")
                        yield f"event: error\ndata: {json.dumps({'message': f'第 {failed_idx+1} 页生成失败，将自动重试'}, ensure_ascii=False)}\n\n"
                    else:
                        yield f"event: slide\ndata: {json.dumps(result, ensure_ascii=False)}\n\n"
                        context_slides.append({
                            "index": result["index"],
                            "title": result["title"],
                            "layout_used": outline.slides[result["index"]].suggested_layout,
                            "html": result["html"],
                        })
                        # Persist slide to DB
                        idx = result["index"]
                        if idx < len(db_slides):
                            db_slides[idx] = {
                                "index": idx, "title": result["title"],
                                "html": result["html"], "quality_score": result.get("quality_score", 0),
                            }
                            update_generation_slides(gen_id, db_slides, gen_title)

                # Retry failed slides once, then emit fallback
                for failed_idx, failed_spec in failed_slides:
                    slide_title = failed_spec.title
                    try:
                        spec_dict = {
                            "title": failed_spec.title,
                            "bullets": failed_spec.bullets,
                            "content_type": failed_spec.content_type,
                            "suggested_layout": failed_spec.suggested_layout,
                        }
                        retry_result = agent.generate_single_from_spec(
                            spec=spec_dict,
                            style=req.style,
                            slide_index=failed_idx,
                            context_slides=context_slides[-3:],
                            language=req.language,
                        )
                        result_data = {
                            "index": failed_idx,
                            "html": retry_result.html,
                            "quality_score": retry_result.quality_score,
                            "title": slide_title,
                        }
                        yield f"event: slide\ndata: {json.dumps(result_data, ensure_ascii=False)}\n\n"
                        context_slides.append({
                            "index": failed_idx,
                            "title": slide_title,
                            "layout_used": failed_spec.suggested_layout,
                            "html": retry_result.html,
                        })
                        if failed_idx < len(db_slides):
                            db_slides[failed_idx] = {
                                "index": failed_idx, "title": slide_title,
                                "html": retry_result.html, "quality_score": retry_result.quality_score,
                            }
                            update_generation_slides(gen_id, db_slides, gen_title)
                    except Exception as retry_err:
                        logger.warning(f"Retry also failed for slide {failed_idx}: {retry_err}")
                        safe_title = html_mod.escape(slide_title)
                        fallback_html = f'''<section class="slide" style="height:100vh;height:100dvh;overflow:hidden;display:flex;align-items:center;justify-content:center;background:#f8f9fa;">
  <div style="text-align:center;padding:2rem;">
    <h2 style="font-size:clamp(1.2rem,2.5vw,2rem);color:#6b7280;">⚠️ 生成失败</h2>
    <p style="font-size:clamp(0.9rem,1.5vw,1.1rem);color:#9ca3af;margin-top:1rem;">{safe_title}</p>
    <p style="font-size:clamp(0.8rem,1.2vw,0.9rem);color:#d1d5db;margin-top:0.5rem;">请点击重新生成此页</p>
  </div>
</section>'''
                        fallback_data = {"index": failed_idx, "html": fallback_html, "quality_score": 0, "title": slide_title}
                        yield f"event: slide\ndata: {json.dumps(fallback_data, ensure_ascii=False)}\n\n"
                        if failed_idx < len(db_slides):
                            db_slides[failed_idx] = {
                                "index": failed_idx, "title": slide_title,
                                "html": fallback_html, "quality_score": 0,
                            }
                            update_generation_slides(gen_id, db_slides, gen_title)

            complete_generation(gen_id, "completed")
            generation_completed = True
            yield f"event: done\ndata: {json.dumps({'gen_id': gen_id})}\n\n"

        except Exception as e:
            logger.exception("SSE generation error")
            if gen_id:
                complete_generation(gen_id, "failed")
                generation_completed = True
            yield f"event: error\ndata: {json.dumps({'message': '生成过程出错，请重试'}, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps({'gen_id': gen_id} if gen_id else {})}\n\n"
        finally:
            _generation_semaphore.release()
            if gen_id and not generation_completed:
                logger.warning(f"SSE stream ended without completion (client disconnect?), marking {gen_id} as failed")
                complete_generation(gen_id, "failed")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    error = validate_content(req.content)
    if error:
        raise HTTPException(status_code=422, detail=error)
    agent = get_agent()
    result = agent.generate_bulk(req.content, req.style, max_iterations=req.max_iterations)

    return GenerateResponse(
        slides=[
            SlideDTO(index=s.index, title=s.title, html=s.html, quality_score=s.quality_score)
            for s in result.slides
        ],
        full_html=result.full_html,
        iterations=result.iterations,
        score=result.quality_report.score,
        issues=result.quality_report.issues,
    )


@app.post("/api/regen", response_model=RegenResponse)
async def regenerate_slide(req: RegenRequest):
    agent = get_agent()
    result = agent.regenerate_slide(
        slide_index=req.slide_index,
        content=req.content,
        layout=req.layout,
        style=req.style,
        context=req.context,
        context_slides=req.context_slides,
    )

    return RegenResponse(html=result.html, quality_score=result.quality_score)


@app.post("/api/validate", response_model=ValidateResponse)
async def validate(req: ValidateRequest):
    from agent.validator import QualityGate

    gate = QualityGate()
    report = gate.check(req.html)

    return ValidateResponse(
        passed=report.passed,
        score=report.score,
        issues=report.issues,
        warnings=report.warnings,
    )


@app.post("/api/export")
async def export_html(req: ExportRequest):
    """Combine individual slide HTMLs into a single presentation file with navigation."""
    slides_html_parts = []
    for i, s in enumerate(req.slides):
        html = s.get("html", "")
        slides_html_parts.append(f'<div class="slide-wrapper" data-slide="{i}">{html}</div>')

    slides_html = "\n".join(slides_html_parts)
    total_slides = len(req.slides)

    # Load font imports from style preset
    font_import = ""
    presets_path = STYLES_DIR / "presets.yaml"
    if presets_path.exists():
        with open(presets_path) as f:
            presets = yaml.safe_load(f)
        if req.style in presets:
            preset = presets[req.style]
            fonts = preset.get("fonts", {})
            display_font = fonts.get("display", "")
            body_font = fonts.get("body", "")
            font_families = set(filter(None, [display_font, body_font]))
            if font_families:
                families_param = "|".join(f.replace(" ", "+") for f in font_families)
                font_import = f'<link href="https://fonts.googleapis.com/css2?family={families_param}:wght@300;400;500;600;700&display=swap" rel="stylesheet">'

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_mod.escape(req.title) if req.title else 'Generated Presentation'}</title>
{font_import}
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{
    height: 100%;
    overflow: hidden;
    font-family: system-ui, sans-serif;
}}
.presentation-container {{
    height: 100vh;
    overflow-y: scroll;
    scroll-snap-type: y mandatory;
    scroll-behavior: smooth;
}}
.slide-wrapper {{
    height: 100vh;
    scroll-snap-align: start;
    overflow: hidden;
    position: relative;
}}
.slide-counter {{
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: rgba(0,0,0,0.6);
    color: #fff;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 14px;
    z-index: 9999;
    pointer-events: none;
    font-family: monospace;
}}
@keyframes fadeInUp {{
    from {{ opacity: 0; transform: translateY(20px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes fadeIn {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
}}
.slide-wrapper.active section > * {{
    animation: fadeInUp 0.6s ease-out both;
}}
.slide-wrapper.active section img,
.slide-wrapper.active section svg {{
    animation: fadeIn 0.8s ease-out both;
}}
.slide-wrapper.active section > *:nth-child(1) {{ animation-delay: 0.1s; }}
.slide-wrapper.active section > *:nth-child(2) {{ animation-delay: 0.2s; }}
.slide-wrapper.active section > *:nth-child(3) {{ animation-delay: 0.35s; }}
.slide-wrapper.active section > *:nth-child(4) {{ animation-delay: 0.5s; }}
.slide-wrapper.active section > *:nth-child(5) {{ animation-delay: 0.65s; }}
.slide-wrapper.active section > *:nth-child(6) {{ animation-delay: 0.8s; }}
.slide-wrapper:not(.active) section > * {{
    opacity: 0;
}}
@media (prefers-reduced-motion: reduce) {{
    .slide-wrapper.active section > * {{ animation: none; opacity: 1; }}
    .slide-wrapper:not(.active) section > * {{ opacity: 1; }}
}}
</style>
</head>
<body>
<div class="presentation-container" id="pres">
{slides_html}
</div>
<div class="slide-counter" id="counter">1 / {total_slides}</div>
<script>
(function() {{
    const container = document.getElementById('pres');
    const counter = document.getElementById('counter');
    const total = {total_slides};
    let current = 0;

    function goTo(idx) {{
        idx = Math.max(0, Math.min(total - 1, idx));
        current = idx;
        container.children[idx].scrollIntoView({{ behavior: 'smooth' }});
        counter.textContent = (idx + 1) + ' / ' + total;
        // Trigger entrance animations
        Array.from(container.children).forEach(function(el, i) {{
            el.classList.toggle('active', i === idx);
        }});
    }}
    // Activate first slide on load
    if (container.children.length > 0) container.children[0].classList.add('active');

    let gridMode = false;

    function exitGrid() {{
        gridMode = false;
        container.style.cssText = 'height:100vh;overflow-y:scroll;scroll-snap-type:y mandatory;scroll-behavior:smooth;';
        Array.from(container.children).forEach(function(el) {{
            el.style.cssText = 'height:100vh;scroll-snap-align:start;overflow:hidden;position:relative;';
        }});
        goTo(current);
    }}

    function enterGrid() {{
        gridMode = true;
        container.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;padding:20px;height:auto;overflow-y:auto;scroll-snap-type:none;';
        Array.from(container.children).forEach(function(el) {{
            el.style.cssText = 'height:200px;scroll-snap-align:none;border:2px solid #e5e7eb;border-radius:8px;cursor:pointer;overflow:hidden;';
        }});
        counter.textContent = 'Grid View — press G to exit, click slide to jump';
    }}

    document.addEventListener('keydown', function(e) {{
        if (e.key === 'g' || e.key === 'G') {{
            if (gridMode) {{ exitGrid(); }} else {{ enterGrid(); }}
            return;
        }}
        if (gridMode) return;
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight' || e.key === ' ') {{
            e.preventDefault();
            goTo(current + 1);
        }} else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {{
            e.preventDefault();
            goTo(current - 1);
        }}
    }});

    container.addEventListener('click', function(e) {{
        if (gridMode) {{
            const wrapper = e.target.closest('.slide-wrapper');
            if (wrapper) {{
                current = parseInt(wrapper.dataset.slide) || 0;
                exitGrid();
            }}
            return;
        }}
        const rect = container.getBoundingClientRect();
        if (e.clientX > rect.width / 2) {{
            goTo(current + 1);
        }} else {{
            goTo(current - 1);
        }}
    }});

    // Update counter + animations on scroll
    container.addEventListener('scroll', function() {{
        if (gridMode) return;
        const idx = Math.round(container.scrollTop / window.innerHeight);
        if (idx !== current) {{
            current = idx;
            counter.textContent = (idx + 1) + ' / ' + total;
            Array.from(container.children).forEach(function(el, i) {{
                el.classList.toggle('active', i === idx);
            }});
        }}
    }});
}})();
</script>
</body>
</html>"""

    return {"html": full_html, "filename": _safe_filename(req.title, "html")}


# --- Prompt Management ---

PROMPTS_DIR = Path(__file__).parent / "prompts"

PROMPT_DESCRIPTIONS: dict[str, str] = {
    "content_analysis": "内容分析提示词",
    "slide_generation": "幻灯片生成提示词",
    "single_slide_regen": "单页重新生成提示词",
    "quality_review": "质量审核提示词",
}


class PromptUpdateRequest(BaseModel):
    content: str


@app.get("/api/prompts")
async def list_prompts():
    """List all prompt files."""
    prompts = []
    for path in sorted(PROMPTS_DIR.glob("*.md")):
        stem = path.stem
        prompts.append({
            "name": stem,
            "filename": path.name,
            "content": path.read_text(encoding="utf-8"),
            "description": PROMPT_DESCRIPTIONS.get(stem, stem),
        })
    return {"prompts": prompts}


@app.get("/api/prompts/{filename}")
async def get_prompt(filename: str):
    """Get a single prompt file content."""
    if not filename.endswith(".md"):
        raise HTTPException(400, "Filename must end with .md")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    path = (PROMPTS_DIR / filename).resolve()
    if not path.is_relative_to(PROMPTS_DIR.resolve()):
        raise HTTPException(400, "Invalid filename")
    if not path.exists():
        raise HTTPException(404, f"Prompt file not found: {filename}")
    stem = path.stem
    return {
        "name": stem,
        "filename": filename,
        "content": path.read_text(encoding="utf-8"),
        "description": PROMPT_DESCRIPTIONS.get(stem, stem),
    }


@app.put("/api/prompts/{filename}")
async def update_prompt(filename: str, req: PromptUpdateRequest, request: Request):
    """Update an existing prompt file (admin-only)."""
    _check_admin(request)
    if not filename.endswith(".md"):
        raise HTTPException(400, "Filename must end with .md")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    path = (PROMPTS_DIR / filename).resolve()
    if not path.is_relative_to(PROMPTS_DIR.resolve()):
        raise HTTPException(400, "Invalid filename")
    if not path.exists():
        raise HTTPException(404, f"Prompt file not found: {filename}")
    if not req.content.strip():
        raise HTTPException(400, "Content must not be empty")
    path.write_text(req.content, encoding="utf-8")
    # Reload prompts in the singleton agent
    agent = get_agent()
    agent.reload_prompts()
    return {"success": True}


# --- Settings API ---

class SettingsUpdateRequest(BaseModel):
    provider: str | None = None
    anthropic_key: str | None = None
    anthropic_base_url: str | None = None
    anthropic_model: str | None = None
    openai_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None


def _mask_key(key: str) -> str:
    """Mask an API key: show first 7 + last 4 chars."""
    if not key or len(key) < 12:
        return ""
    return key[:7] + "..." + key[-4:]


def _read_env_file() -> dict[str, str]:
    """Read backend/.env into a dict."""
    env_path = Path(__file__).parent / ".env"
    data: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    return data


def _write_env_file(data: dict[str, str]):
    """Update backend/.env preserving comments, order, and unrecognized keys."""
    env_path = Path(__file__).parent / ".env"
    updated_keys: set[str] = set()
    output_lines: list[str] = []

    if env_path.exists():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                output_lines.append(line)
                continue
            if "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in data:
                    output_lines.append(f"{k}={data[k]}")
                    updated_keys.add(k)
                else:
                    output_lines.append(line)
            else:
                output_lines.append(line)

    # Append any new keys not already in the file
    for k, v in data.items():
        if k not in updated_keys:
            output_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(output_lines) + "\n")


@app.get("/api/settings")
async def get_settings():
    """Return current LLM configuration for both providers."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
    anthropic_model = os.environ.get("MODEL_ID", "claude-sonnet-4-6")

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    return {
        "provider": provider,
        "anthropic": {
            "has_key": bool(anthropic_key),
            "key_preview": _mask_key(anthropic_key),
            "base_url": anthropic_base_url,
            "model": anthropic_model,
        },
        "openai": {
            "has_key": bool(openai_key),
            "key_preview": _mask_key(openai_key),
            "base_url": openai_base_url,
            "model": openai_model,
        },
    }


@app.put("/api/settings")
async def update_settings(req: SettingsUpdateRequest, request: Request):
    """Update LLM settings (admin-only): write .env, update os.environ, reload agent client."""
    _check_admin(request)
    env_data = _read_env_file()

    if req.provider is not None:
        env_data["LLM_PROVIDER"] = req.provider

    if req.anthropic_key is not None:
        env_data["ANTHROPIC_API_KEY"] = req.anthropic_key
    if req.anthropic_base_url is not None:
        env_data["ANTHROPIC_BASE_URL"] = req.anthropic_base_url
    if req.anthropic_model is not None:
        env_data["MODEL_ID"] = req.anthropic_model

    if req.openai_key is not None:
        env_data["OPENAI_API_KEY"] = req.openai_key
    if req.openai_base_url is not None:
        env_data["OPENAI_BASE_URL"] = req.openai_base_url
    if req.openai_model is not None:
        env_data["OPENAI_MODEL"] = req.openai_model

    # Write to .env file
    _write_env_file(env_data)

    # Update os.environ
    for k, v in env_data.items():
        os.environ[k] = v

    # Reload the LLM client in the singleton agent
    agent = get_agent()
    agent.reload_client()

    current_provider = env_data.get("LLM_PROVIDER", "anthropic").lower()
    return {"success": True, "provider": current_provider, "model": env_data.get("MODEL_ID") or env_data.get("OPENAI_MODEL", "")}


@app.post("/api/settings/test")
async def test_settings(req: SettingsUpdateRequest):
    """Test LLM connection with provided (or current) settings without persisting."""
    provider = req.provider or os.environ.get("LLM_PROVIDER", "anthropic")
    provider = provider.lower()

    try:
        if provider == "openai":
            try:
                import openai
            except ImportError:
                return {"success": False, "error": "未安装 openai 包，请执行: pip install openai"}

            api_key = req.openai_key or os.environ.get("OPENAI_API_KEY", "")
            base_url = req.openai_base_url or os.environ.get("OPENAI_BASE_URL")
            model = req.openai_model or os.environ.get("OPENAI_MODEL", "gpt-4o")

            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url

            client = openai.OpenAI(**kwargs)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=5,
                timeout=15.0,
            )
            reply = response.choices[0].message.content or ""
            return {"success": True, "message": f"连接成功。模型: {model}，响应: {reply[:50]}"}

        else:
            from anthropic import Anthropic

            api_key = req.anthropic_key or os.environ.get("ANTHROPIC_API_KEY", "")
            base_url = req.anthropic_base_url or os.environ.get("ANTHROPIC_BASE_URL")
            model = req.anthropic_model or os.environ.get("MODEL_ID", "claude-sonnet-4-6")

            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url

            client = Anthropic(**kwargs)
            response = client.messages.create(
                model=model,
                max_tokens=5,
                messages=[{"role": "user", "content": "Say OK"}],
                timeout=15.0,
            )
            reply = ""
            for block in response.content:
                if hasattr(block, "text"):
                    reply = block.text
                    break
            return {"success": True, "message": f"连接成功。模型: {model}，响应: {reply[:50]}"}

    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
            return {"success": False, "error": "认证失败，请检查 API Key 是否正确"}
        if "timeout" in error_msg.lower():
            return {"success": False, "error": "连接超时，请检查 Base URL 是否可达"}
        if "connection" in error_msg.lower():
            return {"success": False, "error": f"连接失败: {error_msg}"}
        return {"success": False, "error": f"测试失败: {error_msg}"}


@app.post("/api/export-pdf")
async def export_pdf(req: ExportRequest):
    """Export presentation as PDF using Playwright to render HTML."""
    try:
        from utils.pdf_export import html_to_pdf
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="PDF export requires playwright. Run: pip install playwright && playwright install chromium",
        )

    # Reuse the same HTML assembly logic as /api/export
    export_result = await export_html(req)
    full_html = export_result["html"]

    try:
        pdf_bytes = await html_to_pdf(full_html)
    except Exception as e:
        error_msg = str(e)
        if "Executable doesn't exist" in error_msg or "browserType.launch" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="PDF export requires playwright. Run: pip install playwright && playwright install chromium",
            )
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {error_msg}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(req.title, "pdf")}"'},
    )


@app.post("/api/export-pptx")
async def export_pptx(req: ExportRequest):
    """Export presentation as PowerPoint (.pptx) with slides rendered as images."""
    try:
        from utils.pptx_export import html_to_pptx
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="PPTX export requires python-pptx and playwright. Run: pip install python-pptx playwright && playwright install chromium",
        )

    export_result = await export_html(req)
    full_html = export_result["html"]
    aspect_ratio = getattr(req, "aspect_ratio", "16:9") if hasattr(req, "aspect_ratio") else "16:9"

    try:
        pptx_bytes = await html_to_pptx(full_html, aspect_ratio)
    except Exception as e:
        logger.error(f"PPTX generation failed: {e}")
        raise HTTPException(status_code=500, detail="PPTX 导出失败，请稍后重试")

    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(req.title, "pptx")}"'},
    )


@app.get("/preview/{filename}", response_class=HTMLResponse)
async def preview_file(filename: str):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    path = (OUTPUT_DIR / filename).resolve()
    if not path.is_relative_to(OUTPUT_DIR.resolve()):
        raise HTTPException(400, "Invalid filename")
    if not path.exists():
        raise HTTPException(404)
    return path.read_text(encoding="utf-8")


# --- History API ---


@app.get("/api/active-generation")
async def api_active_generation():
    """Return the most recent in-progress generation (if any)."""
    result = get_active_generation()
    if not result:
        return {"active": None}
    return {"active": result}


@app.get("/api/history")
async def api_list_history(limit: int = 20):
    items = list_generations(limit)
    return {"items": items}


@app.get("/api/history/{gen_id}")
async def api_get_history(gen_id: str):
    result = get_generation(gen_id)
    if not result:
        raise HTTPException(404, "记录不存在")
    return result


class HistorySaveRequest(BaseModel):
    content: str
    style: str
    slides: list[dict]
    gen_id: str | None = None
    title: str | None = None


@app.post("/api/history")
async def api_save_history(req: HistorySaveRequest):
    if req.gen_id:
        # Update existing generation (already created during SSE stream)
        existing = get_generation(req.gen_id)
        if existing:
            update_generation_slides(req.gen_id, req.slides, req.title or "")
            complete_generation(req.gen_id, "completed")
            return {"id": req.gen_id}
    gen_id = save_generation(req.content, req.style, req.slides)
    return {"id": gen_id}


@app.delete("/api/history/{gen_id}")
async def api_delete_history(gen_id: str):
    deleted = delete_generation(gen_id)
    if not deleted:
        raise HTTPException(404, "记录不存在")
    return Response(status_code=204)
