"""
Agent Loop - Core orchestration for presentation generation.

Handles both bulk generation and single-slide regeneration.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("ppt-agent")

from .llm_client import create_llm_client, LLMClient

from .analyzer import ContentAnalyzer, SlideOutline, SlideSpec
from .expander import ContentExpander, ExpandedSlide
from .generator import HTMLGenerator
from .validator import QualityGate, QualityReport


@dataclass
class SlideResult:
    index: int
    title: str
    html: str
    quality_score: float = 100.0


@dataclass
class GenerationResult:
    slides: list[SlideResult]
    full_html: str
    iterations: int
    quality_report: QualityReport


class PPTAgent:
    def __init__(self, model: str | None = None, max_iterations: int = 3):
        import threading
        # Lock guards the bundle (client + analyzer + expander + generator)
        # against torn reads during settings hot-reload. Without this, an
        # in-flight generation can pick up the OLD expander but the NEW
        # generator (different provider mid-deck), silently producing
        # half-Claude-half-GPT output or all-fallback after auth failure.
        self._reload_lock = threading.Lock()
        self.client = create_llm_client()
        self.model = model or self.client.model
        self.max_iterations = max_iterations
        self.analyzer = ContentAnalyzer(self.client, self.model)
        self.expander = ContentExpander(self.client, self.model)
        self.generator = HTMLGenerator(self.client, self.model)
        self.quality_gate = QualityGate()

    def reload_prompts(self):
        """Re-initialize analyzer, expander, and generator to pick up fresh prompt content."""
        with self._reload_lock:
            self.analyzer = ContentAnalyzer(self.client, self.model)
            self.expander = ContentExpander(self.client, self.model)
            self.generator = HTMLGenerator(self.client, self.model)

    def reload_client(self):
        """Re-create LLM client with current env vars (hot-reload after settings change).

        Atomic with respect to itself and reload_prompts. Note: this does NOT
        cancel in-flight generations — they will continue with whichever
        components they captured by reference at call time. To make settings
        changes affect in-flight work, also cancel & restart the generation.
        """
        with self._reload_lock:
            self.client = create_llm_client()
            self.model = self.client.model
            self.analyzer = ContentAnalyzer(self.client, self.model)
            self.expander = ContentExpander(self.client, self.model)
            self.generator = HTMLGenerator(self.client, self.model)

    def generate_bulk(
        self,
        content: str,
        style: str = "corporate-navy",
        max_iterations: int | None = None,
        language: str = "zh",
    ) -> GenerationResult:
        """Generate all slides from content."""
        iterations_limit = max_iterations if max_iterations is not None else self.max_iterations
        outline = self.analyzer.analyze(content, language=language)
        html = self.generator.generate_full(outline, style, language=language)

        iteration = 0
        report = self.quality_gate.check(html)

        while not report.passed and iteration < iterations_limit:
            html = self.generator.revise(html, report.feedback)
            report = self.quality_gate.check(html)
            iteration += 1

        slides = self._split_slides(html, outline)

        return GenerationResult(
            slides=slides,
            full_html=html,
            iterations=iteration,
            quality_report=report,
        )

    def regenerate_slide(
        self, slide_index: int, content: str, layout: str, style: str,
        context: str = "", context_slides: list[dict] | None = None,
        language: str = "zh",
    ) -> SlideResult:
        """Regenerate a single slide using the same pipeline as initial generation."""
        title = content.split("\n")[0][:50]

        # Infer content_type from context (position info passed by frontend)
        content_type = "content"
        if "封面页" in context:
            content_type = "cover"
        elif "结尾页" in context:
            content_type = "closing"

        spec = {
            "title": title,
            "bullets": [line.strip("- ") for line in content.split("\n")[1:] if line.strip()],
            "content_type": content_type,
            "suggested_layout": layout if layout != "auto" else None,
            "detailed_content": content,
            "presentation_context": context,
        }

        return self.generate_single_from_spec(
            spec=spec,
            style=style,
            slide_index=slide_index,
            context_slides=context_slides or [],
            language=language,
        )

    def expand_slide(self, index: int, spec: SlideSpec, language: str = "zh") -> ExpandedSlide:
        """Stage 1.5: Expand a single slide's bullets into detailed content."""
        return self.expander.expand_single(
            index=index,
            title=spec.title,
            bullets=spec.bullets,
            content_type=spec.content_type,
            language=language,
        )

    def generate_outline(self, content: str, language: str = "zh") -> SlideOutline:
        """Stage 1: Generate outline only (fast)."""
        return self.analyzer.analyze(content, language=language)

    def generate_outline_streaming(self, content: str, language: str = "zh"):
        """Generator that yields text chunks during outline generation."""
        yield from self.analyzer.analyze_streaming(content, language=language)

    def get_last_outline(self) -> SlideOutline:
        """Get the parsed outline from the last streaming call."""
        return self.analyzer._last_streaming_result

    def generate_single_from_spec(
        self, spec: dict, style: str, slide_index: int, context_slides: list[dict], language: str = "zh"
    ) -> SlideResult:
        """Stage 2: Generate one slide from spec with context. Auto-retries on low quality.

        On total failure (all retries scored below QUALITY_THRESHOLD), we
        emit a deterministic fallback layout instead of shipping a broken
        slide — guarantees the deck is always visually intact even when
        the model misbehaves.
        """
        MAX_RETRIES = 2
        QUALITY_THRESHOLD = 70

        # Pre-LLM density gate: trim spec at the source so the model can't
        # "succeed at being asked too much". The prompt asks for max 4 bullets,
        # ≤ 20 chars each, but if the spec hands in 8 bullets of 50 chars,
        # the model will dutifully cram all 8 → guaranteed overflow no
        # matter how well it follows the per-item style rule. Catching here
        # is much cheaper than detecting overflow post-render and retrying.
        # We mutate a copy so we don't pollute the caller's spec object.
        spec = self._enforce_density_caps(spec)
        best_html = ""
        best_score = 0.0
        retry_spec = dict(spec)
        t0 = time.time()

        for attempt in range(1 + MAX_RETRIES):
            # First attempt at T=0 (deterministic, cache-friendly). Subsequent
            # attempts ramp up temperature so the model actually explores a
            # different sample — at T=0 retry feedback is theater because
            # same prompt + same temperature = same output.
            if attempt > 0:
                retry_spec["retry_temperature"] = 0.4 + 0.2 * attempt  # 0.6, 0.8

            html = self.generator.generate_from_spec(
                spec=retry_spec,
                style=style,
                slide_index=slide_index,
                context_slides=context_slides,
                language=language,
            )

            # Hard floor: an empty / structurally-invalid response must never
            # be treated as a candidate, regardless of how the rule-based
            # validator scores its absence (it currently scores empty HTML
            # at 82 because it counts only one missing-section issue). Without
            # this we silently emit blank slides with a green quality badge.
            html_stripped = html.strip() if html else ""
            if not html_stripped or "<section" not in html_stripped:
                logger.warning(f"Slide {slide_index} attempt {attempt+1}: missing <section>, skipping candidate")
                if attempt < MAX_RETRIES:
                    retry_spec = dict(spec)
                    retry_spec["quality_feedback"] = (
                        f"Attempt {attempt+1} returned no <section>. Output exactly one "
                        f"<section class='slide'>...</section> with the required structure."
                    )
                continue

            # Rule-based structural check
            report = self.quality_gate.check_single(html)

            # Pre-render fast check: did the model actually write CSS for
            # the classes it used, or did it emit class names with no
            # styles to back them? An unstyled slide renders as raw flowing
            # text (white bg, no layout) — looks "failed" to the user even
            # though all bullets are present. Catching this statically
            # avoids spinning up Playwright when the answer is obvious.
            if not self.quality_gate.has_styling(html):
                report.score = max(35.0, report.score - 35)
                report.passed = False
                msg = (
                    "本页缺少 CSS 样式定义——只用了类名（class=\"...\"）但没有"
                    "<style>规则或丰富的 inline style 来支撑。结果会退化为无样式纯文本。"
                    "必须包含一个完整的 <style> 块定义本页所有 layout/card/typography 的视觉规则。"
                )
                report.issues = list(report.issues) + [msg]
                logger.warning(
                    f"Slide {slide_index} attempt {attempt+1}: missing styling — "
                    f"class names without matching CSS rules"
                )

            # Real-render overflow check — the canonical viewport-fit gate.
            # Static rules can confirm CSS *intends* to clip (overflow:hidden,
            # 100vh, clamp()), but they can't confirm content actually fits.
            # We've shipped slides with section.scrollHeight = 10× viewport
            # because the LLM stuffed 30 grid cards into a layout sized for 6.
            # Run the real browser, measure, and if it exceeds tolerance:
            #   - degrade the rule score
            #   - prepare retry feedback that names the actual overflow
            # Soft-fail: if Playwright is missing or renders error, treat as
            # OK so generation never gets blocked by env issues.
            OVERFLOW_TOLERANCE_PX = 32  # sub-pixel rounding + minor decoration
            render_check = self.quality_gate.render_check_overflow_sync(html)
            overflow_y = render_check.get("overflow_y_px", 0) or 0
            overflow_x = render_check.get("overflow_x_px", 0) or 0
            leaked = render_check.get("leaked_text")
            # Density and empty-box metrics are exposed by the gate but
            # NOT used to fail the slide here — analysis on user-flagged
            # samples showed they correlate poorly with perceived failure
            # (good slides scored 0.07 density, bad slides scored 0.21).
            # We keep them in the metrics for diagnostic logging only;
            # the dominant signal remains overflow + leaked text.
            density = render_check.get("content_density", 1.0)
            empty_boxes = render_check.get("empty_content_boxes", 0)
            real_overflow = (
                overflow_y > OVERFLOW_TOLERANCE_PX
                or overflow_x > OVERFLOW_TOLERANCE_PX
                or bool(leaked)
            )
            if real_overflow:
                # Severity-weighted penalty: 1× viewport overflow → -25, 5×+ → floor at 30.
                penalty = min(50, 25 + (overflow_y // 540) * 5)
                report.score = max(30.0, report.score - penalty)
                report.passed = False
                msg_parts = []
                if overflow_y > OVERFLOW_TOLERANCE_PX:
                    msg_parts.append(f"内容超出视口 {overflow_y}px (约 {overflow_y//1080 + 1}屏)")
                if overflow_x > OVERFLOW_TOLERANCE_PX:
                    msg_parts.append(f"横向超出 {overflow_x}px")
                if leaked:
                    msg_parts.append(f"section 外泄漏文本: {leaked[:60]}")
                report.issues = list(report.issues) + msg_parts
                logger.warning(
                    f"Slide {slide_index} attempt {attempt+1}: real-render overflow "
                    f"y={overflow_y}px x={overflow_x}px density={density:.2f} empty={empty_boxes} leaked={'yes' if leaked else 'no'}"
                )

            if report.score >= QUALITY_THRESHOLD and report.passed:
                # Skip LLM check when rule-based score is high (fast path)
                if report.score >= 90:
                    return SlideResult(
                        index=slide_index,
                        title=spec.get("title", ""),
                        html=html,
                        quality_score=report.score,
                    )

                # LLM-based quality check (best-effort — timeout/error degrades gracefully)
                try:
                    llm_report = self.quality_gate.llm_check_single(html, self.client, self.model)
                    # Weighted average: rule-based (70%) + LLM (30%) — LLM is advisory, not authoritative
                    combined_score = report.score * 0.7 + llm_report.score * 0.3
                except Exception:
                    combined_score = report.score
                    llm_report = None

                if combined_score >= QUALITY_THRESHOLD:
                    return SlideResult(
                        index=slide_index,
                        title=spec.get("title", ""),
                        html=html,
                        quality_score=combined_score,
                    )

                # LLM check failed — prepare feedback for retry
                if combined_score > best_score:
                    best_html, best_score = html, combined_score

                if attempt < MAX_RETRIES and llm_report is not None:
                    feedback_parts = llm_report.issues + [w for w in llm_report.warnings if w]
                    retry_spec = dict(spec)
                    retry_spec["quality_feedback"] = (
                        f"Attempt {attempt+1} scored {combined_score:.0f}/100. "
                        f"Issues: {'; '.join(feedback_parts)}. "
                        f"Reduce content, ensure nothing overflows viewport. "
                        f"Max 4 bullet points, each under 20 characters."
                    )
            else:
                # Rule check failed or score too low
                combined_score = report.score
                if combined_score > best_score:
                    best_html, best_score = html, combined_score

                if attempt < MAX_RETRIES:
                    all_feedback = report.issues + report.warnings
                    retry_spec = dict(spec)
                    overflow_directive = ""
                    if real_overflow:
                        # Concrete, measurable feedback beats abstract pleas.
                        # Telling the model "你的页面超出了 9659 像素" makes it
                        # actually trim, where "fix overflow" usually doesn't.
                        overflow_directive = (
                            f" 上一版内容真实溢出视口 {overflow_y}px (1080p 视口)。"
                            f"必须大幅压缩内容：要点不超过 4 条，每条标题 ≤ 8 字，"
                            f"描述 ≤ 25 字；卡片/表格行数 ≤ 4；移除可有可无的装饰文本；"
                            f"font-size 用 clamp 但下限不超过 0.85rem。"
                        )
                    retry_spec["quality_feedback"] = (
                        f"Attempt {attempt+1} scored {combined_score:.0f}/100. "
                        f"Issues: {'; '.join(all_feedback)}. "
                        f"Fix these structural problems in the new version."
                        + overflow_directive
                    )

        elapsed = time.time() - t0
        # Last-resort fallback: if every attempt scored below the quality
        # threshold OR the loop never produced a parseable <section>, emit
        # a deterministic safe-layout slide instead of shipping the broken
        # candidate. The fallback is plain, dense-but-fitted, and uses the
        # style preset's palette so it doesn't visually clash with the
        # rest of the deck. This guarantees the deck is always intact —
        # the trade-off is a visual downgrade on a single slide vs. the
        # prior behavior of shipping overflow / leaked-CSS / blank pages.
        used_fallback = False
        if (
            not best_html.strip()
            or "<section" not in best_html
            or best_score < QUALITY_THRESHOLD
        ):
            logger.warning(
                f"Slide {slide_index} falling back to safe layout "
                f"(best_score={best_score:.0f} after {attempt+1} attempts, {elapsed:.1f}s)"
            )
            best_html = self._render_fallback_slide(spec, style)
            best_score = 60.0  # honest: passable but explicitly degraded
            used_fallback = True

        if used_fallback:
            pass  # already logged
        elif best_score < 70:
            logger.warning(f"Slide {slide_index} low quality ({best_score:.0f}/100) after {attempt+1} attempts in {elapsed:.1f}s")
        else:
            logger.info(f"Slide {slide_index} generated in {elapsed:.1f}s (score={best_score:.0f}, attempts={attempt+1})")
        return SlideResult(
            index=slide_index,
            title=spec.get("title", ""),
            html=best_html,
            quality_score=best_score,
        )

    # Pre-LLM density caps. Numbers chosen to match the prompt's
    # iron-rule density table (slide_generation.md:48-52). Cover/closing
    # types get tighter caps because they're traditionally minimal.
    _DENSITY_CAPS = {
        "cover":   {"max_bullets": 0, "max_bullet_chars": 0,  "max_title_chars": 30},
        "closing": {"max_bullets": 2, "max_bullet_chars": 30, "max_title_chars": 24},
        "content": {"max_bullets": 4, "max_bullet_chars": 28, "max_title_chars": 24},
    }

    def _enforce_density_caps(self, spec: dict) -> dict:
        """Trim oversized specs *before* prompting the model.

        Returns a shallow copy with bullets capped, oversize bullet text
        truncated at the nearest punctuation, and title clipped. This is
        deliberately mechanical — no LLM, no judgement — so it runs in
        microseconds and is fully deterministic. The original spec is not
        mutated; callers (regenerate_slide, generate_bulk) are unaffected.
        """
        out = dict(spec)
        ct = out.get("content_type", "content")
        caps = self._DENSITY_CAPS.get(ct, self._DENSITY_CAPS["content"])

        # Title
        title = (out.get("title") or "").strip()
        if len(title) > caps["max_title_chars"]:
            out["title"] = title[: caps["max_title_chars"]].rstrip("，,。.;； ")

        # Bullets
        bullets = list(out.get("bullets") or [])
        if caps["max_bullets"] == 0:
            out["bullets"] = []
        else:
            bullets = bullets[: caps["max_bullets"]]
            trimmed = []
            for b in bullets:
                b = str(b).strip()
                if len(b) > caps["max_bullet_chars"]:
                    cap = caps["max_bullet_chars"]
                    # Cut at last sentence terminator within window, else hard cut
                    win = max(0, cap - 8)
                    cut = -1
                    for i in range(cap, win, -1):
                        if i < len(b) and b[i] in "。.，,；;：:":
                            cut = i
                            break
                    b = b[: cut if cut > 0 else cap].rstrip("，,。.;；: ")
                trimmed.append(b)
            out["bullets"] = trimmed

        return out

    def _render_fallback_slide(self, spec: dict, style: str) -> str:
        """Deterministic safe-layout slide. Used when all LLM attempts fail
        the quality gate. Renders title + up to 6 bullets in a centered
        two-column flexbox that is guaranteed to fit a 1920×1080 viewport
        (clamp() font-sizes + max-content rows). Picks colors from the
        style preset so it doesn't visually clash with the rest of the deck.
        """
        from html import escape

        # Pull palette from the active preset; safe defaults if missing.
        preset = self.generator._presets_cache.get(style, {}) if hasattr(self, "generator") else {}
        colors = preset.get("colors", {}) if isinstance(preset, dict) else {}
        bg = colors.get("bg_primary", "#0a0a0a")
        fg = colors.get("text_primary", "#ffffff")
        accent = colors.get("accent", "#4361ee")
        fonts = preset.get("fonts", {}) if isinstance(preset, dict) else {}
        display_font = fonts.get("display") or "Manrope"
        body_font = fonts.get("body") or display_font

        title = (spec.get("title") or "Untitled").strip()[:80]
        bullets_raw = spec.get("bullets") or []
        # Defensive: spec may pass detailed_content as fallback
        if not bullets_raw and spec.get("detailed_content"):
            bullets_raw = [
                line.strip("-• ").strip()
                for line in str(spec["detailed_content"]).split("\n")[1:]
                if line.strip()
            ]
        # Cap to 6 bullets, 80 chars each — keeps content within the column.
        bullets = [str(b).strip()[:80] for b in bullets_raw[:6] if str(b).strip()]

        title_html = escape(title)
        bullets_html = "\n".join(
            f'      <li><span class="dot"></span><span>{escape(b)}</span></li>'
            for b in bullets
        ) or '      <li><span class="dot"></span><span>内容生成失败，请重新生成此页</span></li>'

        # Single source of truth for the safe layout. Inline everything to
        # mirror the deck-wide single-file constraint. The flex wrapper
        # forces vertical centering; clamp() keeps text readable across
        # any reasonable export resolution; overflow:hidden caps any
        # surprise content. families param is doubled (`+`) per Google Fonts API.
        font_param = display_font.replace(" ", "+")
        return (
            f'<link href="https://fonts.googleapis.com/css2?family={font_param}:wght@400;500;600;700&display=swap" rel="stylesheet">\n'
            f'<section class="slide fallback-safe" style="height:100vh;height:100dvh;overflow:hidden;'
            f'background:{bg};color:{fg};font-family:\'{body_font}\',system-ui,sans-serif;'
            f'display:flex;flex-direction:column;justify-content:center;'
            f'padding:clamp(2rem,5vw,4rem) clamp(3rem,8vw,6rem);box-sizing:border-box;">\n'
            '  <style data-id="__ppt_fallback__">\n'
            '    .fallback-safe .accent-bar{width:clamp(40px,5vw,72px);height:4px;border-radius:2px;'
            f'background:{accent};margin-bottom:clamp(1rem,2vh,1.5rem);}}\n'
            '    .fallback-safe h1{font-size:clamp(1.75rem,4.5vw,3.5rem);font-weight:700;'
            f'line-height:1.15;margin:0 0 clamp(1rem,3vh,2rem);font-family:\'{display_font}\',system-ui,sans-serif;}}\n'
            '    .fallback-safe ul{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;'
            'gap:clamp(0.6rem,1.2vh,1rem);max-width:1100px;}\n'
            '    .fallback-safe li{display:flex;align-items:flex-start;gap:clamp(0.5rem,1vw,0.85rem);'
            'font-size:clamp(0.95rem,1.6vw,1.4rem);line-height:1.45;color:rgba(255,255,255,0.88);}\n'
            f'    .fallback-safe .dot{{flex:0 0 auto;width:8px;height:8px;border-radius:50%;background:{accent};margin-top:0.6em;}}\n'
            '  </style>\n'
            '  <div class="accent-bar"></div>\n'
            f'  <h1>{title_html}</h1>\n'
            '  <ul>\n'
            f'{bullets_html}\n'
            '  </ul>\n'
            '</section>'
        )

    def _split_slides(self, full_html: str, outline: SlideOutline) -> list[SlideResult]:
        """Extract individual slide sections from full HTML."""
        import re

        sections = re.findall(
            r'(<section[^>]*class="slide[^"]*"[^>]*>.*?</section>)',
            full_html,
            re.DOTALL,
        )

        results = []
        for i, section_html in enumerate(sections):
            title = ""
            if i < len(outline.slides):
                title = outline.slides[i].title

            results.append(SlideResult(
                index=i,
                title=title,
                html=section_html,
                quality_score=100.0,
            ))

        return results
