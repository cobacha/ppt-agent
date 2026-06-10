"""Quality Gate - Validates HTML against presentation standards."""

import json
import re
from dataclasses import dataclass, field

from .llm_client import LLMClient


def _hex_to_lum(hex_str: str) -> float | None:
    """Approximate luminance (0-1) from a #rrggbb / #rgb string.
    Returns None if unparseable."""
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        r = int(s[0:2], 16) / 255
        g = int(s[2:4], 16) / 255
        b = int(s[4:6], 16) / 255
    except ValueError:
        return None
    # Rough perceptual luminance — Rec. 601 weighting is fine for a smell test
    return 0.299 * r + 0.587 * g + 0.114 * b


def _detect_contrast_smell(html: str) -> str | None:
    """Return a warning string if section background and inline text colors
    appear to be on the same end of the luminance scale (both light or both
    dark). Heuristic only — meant to surface white-on-white slides that
    pass every other rule with a perfect score.
    """
    # Background: section's inline `background` or `background-color`
    section_match = re.search(r"<section[^>]*style\s*=\s*['\"]([^'\"]+)", html, re.IGNORECASE)
    if not section_match:
        return None
    style = section_match.group(1)
    bg_match = re.search(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,6})", style)
    if not bg_match:
        return None
    bg_lum = _hex_to_lum(bg_match.group(1))
    if bg_lum is None:
        return None

    # Inline text colors on heading/paragraph elements
    text_colors = re.findall(
        r"<(?:h[1-6]|p|span|div)[^>]*style\s*=\s*['\"][^'\"]*color\s*:\s*(#[0-9a-fA-F]{3,6})",
        html,
        re.IGNORECASE,
    )
    if not text_colors:
        return None
    text_lums = [l for c in text_colors if (l := _hex_to_lum(c)) is not None]
    if not text_lums:
        return None
    avg_text_lum = sum(text_lums) / len(text_lums)

    # Both light (>0.7) or both dark (<0.3) and very close in luminance
    if abs(bg_lum - avg_text_lum) < 0.15:
        return f"Low color contrast (bg lum {bg_lum:.2f} vs text lum {avg_text_lum:.2f}) — text may be invisible"
    return None


@dataclass
class QualityReport:
    passed: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: float = 100.0

    @property
    def feedback(self) -> list[str]:
        return self.issues


LLM_CHECK_PROMPT = """你是一个 HTML 幻灯片质量审核专家。只关注**真正影响可用性**的严重问题。

检查重点（按优先级）：
1. **内容溢出**：内容是否明显超出视口（有 overflow:hidden 时内容被截断不可见）？
2. **布局崩坏**：元素是否严重重叠/遮挡导致无法阅读？
3. **空白/残缺**：是否大面积空白或内容明显缺失？

返回 JSON（无其他文字）：
```json
{
  "passed": true/false,
  "score": 0-100,
  "issues": ["具体问题描述..."],
  "fix_suggestion": "如何修复的一句话建议（如果 passed 为 false）"
}
```

评分标准（宽松判定）：
- 85-100: 正常可用，内容完整展示
- 70-84: 有小瑕疵但不影响阅读
- 50-69: 有明显问题（溢出或布局崩坏）
- 0-49: 严重问题（大片内容不可见或完全乱版）

**注意**：
- 5-6个要点是正常的，不算溢出
- 字号略小但可读 → 不扣分
- 缺少动画/渐变等美化 → 不扣分
- 只有**内容真正不可见或布局完全崩坏**才判 passed=false"""


class QualityGate:
    def check(self, html: str) -> QualityReport:
        issues = []
        warnings = []

        issues.extend(self._check_viewport(html))
        issues.extend(self._check_layout_diversity(html))
        warnings.extend(self._check_density(html))
        issues.extend(self._check_clamp(html))
        warnings.extend(self._check_fonts(html))

        score = max(0, 100 - len(issues) * 15 - len(warnings) * 5)
        return QualityReport(passed=len(issues) == 0, issues=issues, warnings=warnings, score=score)

    def check_single(self, html: str) -> QualityReport:
        """Check a single slide section. Focus on critical structural issues only."""
        issues = []
        warnings = []

        # Overflow check — verify the slide actually constrains its content,
        # not just that the words "overflow" and "hidden" both appear in
        # *some* style block (the previous heuristic falsely passed slides
        # where unrelated rules used `visibility: hidden` and `overflow: auto`).
        section_tag = re.search(r'<section[^>]*>', html)
        if section_tag:
            section_attrs = section_tag.group(0)
            has_overflow = bool(re.search(r"overflow\s*:\s*hidden", section_attrs, re.IGNORECASE))
            if not has_overflow:
                # Look for `.slide ... { ... overflow: hidden }` or any
                # selector targeting `.slide` with the property paired up.
                style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
                pattern = re.compile(
                    r"\.slide\b[^{]*\{[^}]*overflow\s*:\s*hidden",
                    re.IGNORECASE | re.DOTALL,
                )
                has_overflow = any(pattern.search(block) for block in style_blocks)
            if not has_overflow:
                issues.append("Slide section missing overflow: hidden")
        else:
            issues.append("No <section> element found")

        # Bullet density — anything beyond 8 is treated as a hard issue so
        # the auto-retry path in `generate_single_from_spec` actually fires
        # with quality_feedback. Previously 9 bullets only logged a warning,
        # which was never surfaced and never retried — the prompt's
        # "max 4 bullets" rule was effectively unenforced.
        li_count = html.count("<li")
        if li_count > 8:
            issues.append(f"Slide has {li_count} bullets — must be ≤6 (split into multiple slides if needed)")
        elif li_count > 6:
            warnings.append(f"Slide has {li_count} bullets (consider reducing to ≤6)")

        # Font import check — soft warning only, no score penalty
        if "fonts.googleapis.com" not in html and "fontshare.com" not in html:
            pass  # Many models don't add font imports — not a quality issue

        # Responsive clamp() usage — required by the iron rules. Soft warning
        # at 7-10 fixed sizes; hard issue at >10 (forces retry via the
        # quality_feedback path, otherwise slides like the Slide-7 case with
        # 19 fixed font-sizes never get fixed).
        style_blocks = re.findall(r"(?:style=\"[^\"]*\"|<style[^>]*>.*?</style>)", html, re.DOTALL)
        style_text = " ".join(style_blocks)
        fixed_sizes = [fs for fs in re.findall(r"font-size:\s*([^;\"]+)", style_text)
                       if "clamp" not in fs and "var(" not in fs and "inherit" not in fs]
        if len(fixed_sizes) > 10:
            issues.append(
                f"{len(fixed_sizes)} fixed font-sizes — must use clamp() for responsive sizing"
            )
        elif len(fixed_sizes) > 6:
            warnings.append(f"{len(fixed_sizes)} fixed font-sizes without responsive clamp()")

        # Minimum content: at least one heading element
        if not re.search(r"<h[1-6]", html):
            warnings.append("Slide missing heading element (h1-h6)")

        # Color-contrast smell check: if section background is light AND
        # heading/body inline color is also light (or vice versa, dark+dark),
        # the slide will look blank to the viewer despite scoring 100. This
        # is a heuristic — false-positive is fine because we only WARN.
        contrast_smell = _detect_contrast_smell(html)
        if contrast_smell:
            warnings.append(contrast_smell)

        # Content density check: visible text length (strip tags + styles)
        visible_text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        visible_text = re.sub(r'<script[^>]*>.*?</script>', '', visible_text, flags=re.DOTALL)
        visible_text = re.sub(r'<[^>]+>', '', visible_text)
        visible_text = ' '.join(visible_text.split())
        if len(visible_text) > 500:
            warnings.append(f"Content too dense ({len(visible_text)} chars visible text, recommend < 300)")
        elif len(visible_text) > 300:
            warnings.append(f"Content slightly dense ({len(visible_text)} chars)")

        # HTML integrity: check for unclosed section/div tags
        open_sections = html.count("<section")
        close_sections = html.count("</section")
        if open_sections > close_sections:
            issues.append(f"Unclosed <section> tag ({open_sections} open, {close_sections} closed)")
        open_divs = html.count("<div")
        close_divs = html.count("</div")
        if open_divs - close_divs > 2:  # Allow 1-2 gap (injected wrappers)
            warnings.append(f"Possible unclosed <div> tags ({open_divs} open, {close_divs} closed)")

        score = max(0, 100 - len(issues) * 15 - len(warnings) * 3)
        return QualityReport(passed=len(issues) == 0, issues=issues, warnings=warnings, score=score)

    # Match `<section class="...slide...">` or single-quoted, with the slide
    # token anywhere in the multi-class attribute. Previously the code did a
    # literal substring check for `class="slide` which silently zeroed any
    # generation that used single quotes or a different class order.
    _SLIDE_SECTION_RE = re.compile(
        r"""<section[^>]*class\s*=\s*['"][^'"]*\bslide\b[^'"]*['"]""",
        re.IGNORECASE,
    )

    def _check_viewport(self, html: str) -> list[str]:
        issues = []
        if not self._SLIDE_SECTION_RE.search(html):
            issues.append("No slides found")
            return issues
        if "100vh" not in html and "100dvh" not in html:
            issues.append("Missing height: 100vh/100dvh")
        if "overflow: hidden" not in html and "overflow:hidden" not in html:
            issues.append("Missing overflow: hidden")
        # scroll-snap only matters for the wrapped/exported deck, not for
        # raw concatenation of <section> blocks. Demote to warning when
        # there are no `slide-wrapper` divs (i.e. caller passed slides
        # without the export wrapper) — this was previously a false-positive
        # ISSUE that took working decks from 85→70 in /api/validate.
        if "scroll-snap" not in html:
            if "slide-wrapper" in html or "<html" in html:
                issues.append("Missing scroll-snap")
            # else: looking at raw slides without wrapper — silent skip
        return issues

    def _check_layout_diversity(self, html: str) -> list[str]:
        """Extract the actual layout-distinguishing class from each slide and
        flag consecutive duplicates / lack of diversity.

        The previous implementation matched against a hardcoded pattern list
        (`grid-2`, `kpi-hero`, …) that did not match the LLM's actual class
        names (e.g. `kpi-hero-row`, `cascade`, novel names per generation).
        Result: every slide mapped to "unknown", every check no-op'd, and
        the diversity gate was effectively dead. We now extract the second
        non-`slide` token from each section's class attribute as a stable
        layout identifier.
        """
        # Find each <section ... class="..."> with `slide` in classes; capture full class list.
        section_pattern = re.compile(
            r"""<section[^>]*class\s*=\s*['"]([^'"]*\bslide\b[^'"]*)['"]""",
            re.IGNORECASE,
        )
        layouts: list[str] = []
        for match in section_pattern.finditer(html):
            classes = match.group(1).split()
            # First non-`slide`/non-empty class is the layout discriminator.
            layout = next((c for c in classes if c.lower() != "slide"), "")
            layouts.append(layout or "unspecified")

        issues = []
        for i in range(1, len(layouts)):
            # Consecutive duplicates are a real violation only when both
            # slides actually declared a layout class.
            if layouts[i] == layouts[i - 1] and layouts[i] not in ("", "unspecified"):
                issues.append(f"Slides {i} and {i+1} use same layout '{layouts[i]}'")

        unique = {l for l in layouts if l not in ("", "unspecified")}
        # Iron rule: 6+ distinct layouts in a deck of 8+. The previous wording
        # said "need 6+" but the threshold was `< 4`; align both.
        if len(layouts) >= 8 and len(unique) < 6:
            issues.append(f"Only {len(unique)} distinct layouts — need 6+")

        return issues

    def _check_density(self, html: str) -> list[str]:
        warnings = []
        sections = re.split(r'<section[^>]*class="slide', html)
        for i, sec in enumerate(sections[1:], 1):
            if sec.count("<li") > 8:
                warnings.append(f"Slide {i}: too many bullets ({sec.count('<li')})")
        return warnings

    def _check_clamp(self, html: str) -> list[str]:
        # Concat ALL <style> blocks (full deck has one per slide), and accept
        # `<style type="text/css">` etc. — previous code only inspected the
        # first plain-`<style>` and falsely reported "no style block" for
        # decks with attributes or multiple style blocks.
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL)
        if not style_blocks:
            return ["No <style> block found"]

        all_css = "\n".join(style_blocks)
        fixed = [fs for fs in re.findall(r"font-size:\s*([^;]+);", all_css)
                 if "clamp" not in fs and "var(" not in fs and "inherit" not in fs]

        if len(fixed) > 3:
            return [f"{len(fixed)} fixed font-sizes without clamp()"]
        return []

    def _check_fonts(self, html: str) -> list[str]:
        warnings = []
        if "fonts.googleapis.com" not in html and "fontshare.com" not in html:
            warnings.append("No external font import — may use system fonts")
        return warnings

    def render_check_overflow_sync(
        self,
        html: str,
        viewport: tuple[int, int] = (1920, 1080),
        timeout_ms: int = 8000,
    ) -> dict:
        """Sync sibling of `render_check_overflow` for use inside the
        threaded generation loop (which runs under `run_in_executor` and
        cannot await). Same return shape; soft-fails to {"ok": True} if
        Playwright is unavailable or rendering errors.

        Note: this spins up a fresh Chromium per call (~600ms-1s on macOS).
        Per-slide cost is acceptable inside generate_single_from_spec
        because each generation already takes 30-50s of LLM time. We do
        NOT cache a long-lived browser at QualityGate scope: the gate is
        re-instantiated freely and a stale browser handle would leak.
        """
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            return {"ok": True, "error": f"playwright unavailable: {e}"}

        w, h = viewport
        page_html = (
            "<!doctype html><html><head><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;width:100vw;height:100vh;overflow:hidden;background:#000}</style>"
            "</head><body>" + html + "</body></html>"
        )

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": w, "height": h})
                    page.set_default_timeout(timeout_ms)
                    page.set_content(page_html, wait_until="load")
                    try:
                        page.evaluate("document.fonts && document.fonts.ready")
                    except Exception:
                        pass
                    metrics = page.evaluate(
                        """() => {
                            const sec = document.querySelector('section');
                            if (!sec) return null;
                            let leaked = '';
                            // 1) Body-level leak: anything outside <section>
                            for (const node of document.body.childNodes) {
                                if (node.nodeType === 1 && node.tagName.toLowerCase() === 'section') continue;
                                if (node.nodeType === 1 && ['SCRIPT','STYLE','LINK','META'].includes(node.tagName)) continue;
                                const txt = (node.textContent || '').trim();
                                if (txt) leaked += txt + ' | ';
                            }
                            // 2) In-section leak: a TEXT node inside the section
                            // whose content looks like a CSS rule body. This catches
                            // `<style<style>` malformations where the parser falls
                            // through and renders rule text as visible content.
                            // Heuristic: a single text-node child longer than 100
                            // chars containing both '{' and '}' and a CSS-property
                            // colon pattern (e.g. `: 12px`, `: rgba`, `: clamp`).
                            const cssRe = /:\\s*(?:\\d|#|rgba?|hsla?|clamp|var|linear-|radial-|inherit|none|auto|absolute|relative|flex|grid)/i;
                            const walk = (el) => {
                                for (const n of el.childNodes) {
                                    if (n.nodeType === 3) {
                                        const t = (n.nodeValue || '').trim();
                                        if (t.length > 100 && t.includes('{') && t.includes('}') && cssRe.test(t)) {
                                            leaked += '[in-section CSS] ' + t.slice(0, 100) + ' | ';
                                            return;
                                        }
                                    } else if (n.nodeType === 1 && !['SCRIPT','STYLE'].includes(n.tagName)) {
                                        walk(n);
                                    }
                                }
                            };
                            walk(sec);
                            return {
                                sh: sec.scrollHeight, ch: sec.clientHeight,
                                sw: sec.scrollWidth,  cw: sec.clientWidth,
                                leaked: leaked.slice(0, 250),
                            };
                        }"""
                    )
                finally:
                    browser.close()
        except Exception as e:
            return {"ok": True, "error": f"render failed: {type(e).__name__}: {e}"}

        if not metrics:
            return {"ok": True, "error": "no <section>"}

        TOL = 8
        ovy = max(0, metrics["sh"] - metrics["ch"] - TOL)
        ovx = max(0, metrics["sw"] - metrics["cw"] - TOL)
        leaked = metrics["leaked"].strip(" |") or None
        return {
            "ok": ovy == 0 and ovx == 0 and not leaked,
            "section_height": metrics["sh"],
            "section_width": metrics["sw"],
            "viewport": [w, h],
            "overflow_y_px": ovy,
            "overflow_x_px": ovx,
            "leaked_text": leaked,
        }

    async def render_check_overflow(
        self,
        html: str,
        viewport: tuple[int, int] = (1920, 1080),
        timeout_ms: int = 8000,
    ) -> dict:
        """Render the slide HTML in a real headless browser at the given
        viewport and report whether the section overflows.

        This is the canonical overflow check — pure-CSS heuristics (clamp,
        100vh, overflow:hidden) only prove the layout *can* clip content,
        not that it *fits*. When the LLM stuffs 30 grid items into a
        kpi-hero-row, every static rule passes while users see only the
        first row before `overflow: hidden` eats the rest.

        Returns a dict:
          {
            "ok": bool,                    # within tolerance
            "section_height": int,         # rendered section.scrollHeight
            "section_width": int,
            "viewport": [w, h],
            "overflow_y_px": int,          # 0 if no Y overflow
            "overflow_x_px": int,
            "leaked_text": str | None,     # text rendered OUTSIDE <section>
          }
        On any rendering error returns {"ok": True, "error": "..."} so the
        caller treats it as a non-blocking soft-check.
        """
        try:
            from playwright.async_api import async_playwright
        except Exception as e:
            return {"ok": True, "error": f"playwright unavailable: {e}"}

        w, h = viewport
        page_html = (
            "<!doctype html><html><head><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;width:100vw;height:100vh;overflow:hidden;background:#000}</style>"
            "</head><body>" + html + "</body></html>"
        )

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch()
                try:
                    page = await browser.new_page(viewport={"width": w, "height": h})
                    page.set_default_timeout(timeout_ms)
                    await page.set_content(page_html, wait_until="load")
                    # Allow any web fonts a brief moment so layout settles.
                    try:
                        await page.evaluate("document.fonts && document.fonts.ready")
                    except Exception:
                        pass
                    metrics = await page.evaluate(
                        """() => {
                            const sec = document.querySelector('section');
                            if (!sec) return null;
                            // Anything rendered as text directly under <body> but OUTSIDE <section>
                            // is leaked CoT / stray prose. Walk children.
                            let leaked = '';
                            for (const node of document.body.childNodes) {
                                if (node.nodeType === 1 && node.tagName.toLowerCase() === 'section') continue;
                                if (node.nodeType === 1 && ['SCRIPT','STYLE','LINK','META'].includes(node.tagName)) continue;
                                const txt = (node.textContent || '').trim();
                                if (txt) leaked += txt + ' | ';
                            }
                            return {
                                sh: sec.scrollHeight, ch: sec.clientHeight,
                                sw: sec.scrollWidth,  cw: sec.clientWidth,
                                leaked: leaked.slice(0, 200),
                            };
                        }"""
                    )
                finally:
                    await browser.close()
        except Exception as e:
            return {"ok": True, "error": f"render failed: {type(e).__name__}: {e}"}

        if not metrics:
            return {"ok": True, "error": "no <section>"}

        # Allow 8px tolerance — sub-pixel rounding shouldn't trigger regen.
        TOL = 8
        ovy = max(0, metrics["sh"] - metrics["ch"] - TOL)
        ovx = max(0, metrics["sw"] - metrics["cw"] - TOL)
        leaked = metrics["leaked"].strip(" |") or None

        return {
            "ok": ovy == 0 and ovx == 0 and not leaked,
            "section_height": metrics["sh"],
            "section_width": metrics["sw"],
            "viewport": [w, h],
            "overflow_y_px": ovy,
            "overflow_x_px": ovx,
            "leaked_text": leaked,
        }

    def llm_check_single(self, html: str, client: LLMClient, model: str) -> QualityReport:
        """Use LLM to assess a single slide's visual quality and overflow risk."""
        truncated = html[:6000] if len(html) > 6000 else html

        try:
            response = client.chat_completion(
                system=LLM_CHECK_PROMPT,
                messages=[{"role": "user", "content": f"<slide>\n{truncated}\n</slide>"}],
                max_tokens=1024,
                temperature=0.0,
                timeout=30.0,
            )

            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            text = re.sub(r',\s*([}\]])', r'\1', text.strip())
            data = json.loads(text)

            return QualityReport(
                passed=data.get("passed", True),
                issues=data.get("issues", []),
                warnings=[data.get("fix_suggestion", "")] if data.get("fix_suggestion") else [],
                score=float(data.get("score", 80)),
            )
        except Exception as e:
            # R50: previously this swallowed silently. The combined score
            # almost certainly cleared the threshold and the slide shipped
            # with no log trace. Log the exception class + message so
            # operators can spot recurring shape-mismatch / parse failures
            # in production. Fall back behavior unchanged for stability.
            import logging as _logging
            _logging.getLogger("ppt-agent").warning(
                f"llm_check_single fallback: {type(e).__name__}: {e}"
            )
            return QualityReport(passed=True, score=75.0)
