"""HTML Generator - Produces presentation HTML via LLM."""

import logging
import re
from pathlib import Path

import yaml

from .llm_client import LLMClient
from .analyzer import SlideOutline
from utils.aspect_ratio import DEFAULT as _DEFAULT_AR, SUPPORTED as _SUPPORTED_AR


# Known layout classes (matches the prompt's allowed list). Used to coerce
# verbose layout hints from the analyzer back into a short kebab-case class
# the LLM will emit on the section.
_KNOWN_LAYOUT_CLASSES = {
    "trend-bands", "cascade-grid", "scorecard-strip", "asym-compare",
    "editorial-split", "h-track", "dual-timeline", "kpi-hero-row",
    "opp-ladder", "risk-stack", "data-table", "grid-3", "grid-2",
    "concentric-rings", "hero", "closing",
}


def _layout_class_for(layout_hint: str, content_type: str) -> str:
    """Pick a layout class. Prefer an exact known class in the hint, else
    a sensible default by content_type."""
    if layout_hint:
        # Match longest known class first — `hero` would otherwise match inside
        # `kpi-hero-row` (because `\b` treats `-` as a word boundary), causing
        # the wrong class to win. Sort descending by length to break ties.
        for known in sorted(_KNOWN_LAYOUT_CLASSES, key=len, reverse=True):
            # Use boundary that excludes `-` so e.g. `hero` doesn't match
            # inside `kpi-hero-row`. Lookbehind/lookahead reject hyphens.
            if re.search(rf"(?<![-\w]){re.escape(known)}(?![-\w])", layout_hint, re.IGNORECASE):
                return known
        # Otherwise pick by keyword heuristics on the description
        ht = layout_hint.lower()
        if "kpi" in ht or "metric" in ht and "row" in ht:
            return "kpi-hero-row"
        if "split" in ht or "60/40" in ht or "70/30" in ht:
            return "editorial-split"
        if "horizontal" in ht and ("panel" in ht or "track" in ht):
            return "h-track"
        if "stagger" in ht or "cascade" in ht:
            return "cascade-grid"
        if "timeline" in ht or "connector" in ht:
            return "dual-timeline"
        if "step" in ht or "ladder" in ht:
            return "opp-ladder"
        if "table" in ht:
            return "data-table"
        if "ring" in ht or "concentric" in ht:
            return "concentric-rings"
        if "compare" in ht or "asymmetric" in ht:
            return "asym-compare"
        if "stack" in ht or "severity" in ht or "gauge" in ht:
            return "risk-stack"
        if "score" in ht or "fill bar" in ht:
            return "scorecard-strip"
        if "strip" in ht or "band" in ht:
            return "trend-bands"
        if "3-column" in ht or "3 column" in ht:
            return "grid-3"
        if "2-column" in ht or "2 column" in ht:
            return "grid-2"
    # Fallback by role
    if content_type == "cover":
        return "hero"
    if content_type == "closing":
        return "closing"
    return "grid-2"

logger = logging.getLogger("ppt-agent")


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
STYLES_DIR = Path(__file__).parent.parent / "styles"


class HTMLGenerator:
    def __init__(self, client: LLMClient, model: str):
        self.client = client
        self.model = model
        self._generation_prompt = self._load_file(PROMPTS_DIR / "slide_generation.md")
        self._regen_prompt = self._load_file(PROMPTS_DIR / "single_slide_regen.md")
        self._base_css = self._load_file(TEMPLATES_DIR / "base_css.css")
        # Cache presets.yaml + layouts.yaml at init time
        self._presets_cache = self._load_presets()
        self._layouts_cache = self._load_layouts()

    def _load_file(self, path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _load_presets(self) -> dict:
        style_path = STYLES_DIR / "presets.yaml"
        if style_path.exists():
            with open(style_path) as f:
                return yaml.safe_load(f) or {}
        return {}

    def _load_layouts(self) -> dict:
        """Load layouts.yaml — used to inject execution rules for the
        chosen layout into the per-slide prompt. Layouts that aren't well
        executed (dual-timeline missing its center line, asym-compare with
        equal columns) read as 'failed' even when content is complete."""
        layouts_path = STYLES_DIR / "layouts.yaml"
        if layouts_path.exists():
            try:
                with open(layouts_path) as f:
                    data = yaml.safe_load(f) or {}
                return data.get("layouts", {})
            except Exception:
                pass
        return {}

    def generate_full(self, outline: SlideOutline, style: str, language: str = "zh") -> str:
        system = self._build_system_prompt(style)
        # Without this, /api/generate (non-streaming) silently produced
        # Chinese decks regardless of the requested language because the
        # base template is in Chinese.
        lang_rule = (
            "All visible text content on the slides MUST be in Chinese (中文)."
            if language == "zh"
            else "All visible text content on the slides MUST be in English."
        )
        system += f"\n\n{lang_rule}"
        user_msg = self._format_outline(outline)

        response = self.client.chat_completion(
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=32000,
            timeout=120.0,
        )

        return self._extract_html(response.text)

    def generate_from_spec(
        self, spec: dict, style: str, slide_index: int, context_slides: list[dict], language: str = "zh"
    ) -> str:
        """Generate a single slide from spec with context from previous slides."""
        system = self._generation_prompt or "Generate a presentation slide as HTML."
        lang_rule = "All visible text content on the slide MUST be in Chinese (中文)." if language == "zh" else "All visible text content on the slide MUST be in English."
        system += f"\n\n{lang_rule}\n\nStyle: {style}"

        if self._base_css:
            system += f"\n\nBase CSS (include relevant parts):\n```css\n{self._base_css}\n```"

        if style in self._presets_cache:
            system += f"\n\nStyle preset:\n```yaml\n{yaml.dump(self._presets_cache[style])}\n```"

        context_text = ""
        if context_slides:
            context_parts = []
            for cs in context_slides[:-1]:
                context_parts.append(f"Slide {cs['index']+1}: {cs['title']} (layout: {cs.get('layout_used', 'auto')})")
            if context_slides:
                last = context_slides[-1]
                if last.get("html"):
                    last_html = last["html"]
                    if len(last_html) > 3000:
                        last_html = last_html[:3000] + "..."
                    context_parts.append(f"Previous slide (full HTML for visual continuity):\n{last_html}")
            context_text = "\n".join(context_parts)

        layout = spec.get("suggested_layout", "auto")
        bullets_text = "\n".join(f"  - {b}" for b in spec.get("bullets", []))
        detailed_content = spec.get("detailed_content", "")
        aspect_ratio = spec.get("aspect_ratio", _DEFAULT_AR)
        # Coerce unknown values to default so we never emit broken CSS.
        if aspect_ratio not in _SUPPORTED_AR:
            aspect_ratio = _DEFAULT_AR

        # Map aspect ratio to CSS viewport-relative dimensions for the
        # generated section. The CSS expressions can't live in
        # utils.aspect_ratio (that module is platform-neutral); but the keys
        # MUST be a subset of SUPPORTED — guarded by the assert below so
        # adding a ratio to SUPPORTED without updating this map is loud.
        ar_map = {
            "16:9":  ("100vw", "100vh"),
            "4:3":   ("min(100vw, 133.33vh)", "min(100vh, 75vw)"),
            "16:10": ("min(100vw, 160vh)", "min(100vh, 62.5vw)"),
            "1:1":   ("min(100vw, 100vh)", "min(100vh, 100vw)"),
        }
        assert _SUPPORTED_AR.issubset(ar_map.keys()), (
            f"generator.ar_map missing entries for: {_SUPPORTED_AR - ar_map.keys()}"
        )
        ar_width, ar_height = ar_map[aspect_ratio]
        system += f"\n\nSlide aspect ratio: {aspect_ratio}. Use width: {ar_width}; height: {ar_height}; on the section."

        detail_section = ""
        if detailed_content:
            detail_section = f"\nDetailed content (use this for richer slide text):\n{detailed_content}\n"

        # Presentation-level context (title, outline, position) for regeneration
        pres_context = spec.get("presentation_context", "")
        pres_section = f"\n\nPresentation context:\n{pres_context}" if pres_context else ""

        content_type = spec.get('content_type', 'content')
        role_hint = ""
        if content_type == "cover":
            role_hint = "\nThis is the COVER slide — use a hero/title layout with the presentation title prominently displayed. Keep it visually impactful with minimal text."
        elif content_type == "closing":
            role_hint = "\nThis is the CLOSING slide — use a centered, minimal layout (thank-you, Q&A, or call-to-action). Keep it clean and conclusive."

        # Map verbose layout descriptions in suggested_layout back to short
        # class names the validator can recognise. The LLM ignores hints
        # like "Equal-width horizontal panels with dividers" and emits
        # `class="slide"` literally — so we extract a kebab-case token from
        # the hint, default to a sensible class for content_type if absent.
        layout_class = _layout_class_for(layout, content_type)

        # Inject layout-specific execution rules. Without this, layouts
        # like dual-timeline degrade into "two random lists" because the
        # model doesn't know its signature element (center vertical line
        # connecting all entries). User-flagged "failed" slides clustered
        # on layouts that have a distinguishing visual element the model
        # didn't draw: dual-timeline (missing connector), asym-compare
        # (equal columns instead of 3:2), opp-ladder (missing left border),
        # grid-3 (used for 4+ items).
        layout_rules_section = ""
        layout_def = self._layouts_cache.get(layout_class)
        if layout_def and isinstance(layout_def, dict):
            must_rules = layout_def.get("execution_must") or []
            fail_modes = layout_def.get("fails_when") or []
            if must_rules:
                rules_md = "\n".join(f"- {r}" for r in must_rules)
                layout_rules_section = (
                    f"\n\nLayout `{layout_class}` execution rules — these are the visible "
                    f"signature of the layout. Without them the slide degenerates into a "
                    f"generic card grid:\n{rules_md}"
                )
                if fail_modes:
                    failures = ", ".join(fail_modes)
                    layout_rules_section += f"\n\nThis layout is considered FAILED if any of: {failures}"

        user_msg = f"""Generate slide #{slide_index + 1}.

Title: {spec.get('title', '')}
Content type: {content_type}{role_hint}
Bullets:
{bullets_text}
{detail_section}Layout: {layout}{layout_rules_section}

{f"Context (previous slides):{chr(10)}{context_text}" if context_text else "This is the first slide."}{pres_section}

CRITICAL — output structure:
- The root MUST be exactly: <section class="slide {layout_class}"> ... </section>
- The second class "{layout_class}" identifies the layout pattern; do NOT omit it.
- This is required for layout-diversity validation across the deck.

CRITICAL — content completeness:
- 每个 bullet 必须完整呈现：标题 + 至少 1 句描述。绝不允许只放标题或空壳卡片。
- 内容是主角，装饰是配角。主内容区必须占据 section 中央 ≥ 40% 面积。
- 装饰元素 ≤ 2 个（gradient-orb / accent-bar / grid-overlay 任选 2）；signature recipe 用 1 条即可。

Generate ONLY the <section class="slide {layout_class}">...</section> HTML for this single slide.
Include inline styles consistent with the style preset. Make it visually polished."""

        quality_feedback = spec.get("quality_feedback", "")
        if quality_feedback:
            user_msg += f"\n\nIMPORTANT quality requirements:\n{quality_feedback}"

        # Use structured system with cache_control so the system prompt (which is
        # identical across all slides in a generation) is cached by the Anthropic API.
        # For non-Anthropic providers, the client extracts text and ignores cache_control.
        # Retry temperature: T=0 produces deterministic output, so a retry with the
        # same prompt yields ≈ the same broken slide. The loop bumps temperature on
        # retries to force the model into a different sample of the distribution —
        # the only way feedback like "上一版溢出 9659px" can actually steer output.
        retry_temp = float(spec.get("retry_temperature") or 0.0)
        response = self.client.chat_completion(
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=8192,
            temperature=retry_temp,
            timeout=60.0,
        )

        return self._post_process_slide(self._extract_html(response.text), style, layout_class=layout_class)

    def generate_single(
        self, content: str, layout: str, style: str, context: str, slide_index: int
    ) -> str:
        system = self._regen_prompt or self._generation_prompt
        system += f"\n\nStyle: {style}\nLayout pattern to use: {layout}"

        if style in self._presets_cache:
            system += f"\n\nStyle preset:\n```yaml\n{yaml.dump(self._presets_cache[style])}\n```"

        if self._base_css:
            system += f"\n\nBase CSS (include relevant parts):\n```css\n{self._base_css}\n```"

        user_msg = f"""Regenerate slide #{slide_index + 1} with this content:

{content}

Context (surrounding slides for consistency):
{context}

Generate ONLY the <section class="slide">...</section> HTML for this single slide.
Use the '{layout}' layout pattern. Include relevant inline styles."""

        response = self.client.chat_completion(
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=8192,
            timeout=60.0,
        )

        return self._post_process_slide(self._extract_html(response.text), style)

    def revise(self, html: str, feedback: list[str]) -> str:
        feedback_text = "\n".join(f"- {f}" for f in feedback)

        response = self.client.chat_completion(
            system="Fix quality issues in this HTML presentation. Return the complete corrected HTML only.",
            messages=[{"role": "user", "content": f"Issues:\n{feedback_text}\n\nHTML:\n{html}"}],
            max_tokens=16000,
            timeout=90.0,
        )

        return self._extract_html(response.text)

    def _build_system_prompt(self, style: str) -> str:
        parts = [self._generation_prompt]
        if self._base_css:
            parts.append(f"\n## Base CSS\n```css\n{self._base_css}\n```")

        if style in self._presets_cache:
            parts.append(f"\n## Active Style Preset\n```yaml\n{yaml.dump(self._presets_cache[style])}\n```")

        return "\n".join(parts)

    def _format_outline(self, outline: SlideOutline) -> str:
        lines = [f"Title: {outline.title}", f"Subtitle: {outline.subtitle}",
                 f"Theme: {outline.theme_hint}", f"Slides: {outline.slide_count}", ""]

        for i, s in enumerate(outline.slides, 1):
            lines.append(f"Slide {i} [{s.content_type}]: {s.title}")
            if s.bullets:
                for b in s.bullets[:5]:
                    lines.append(f"  - {b}")
            if s.suggested_layout:
                lines.append(f"  Layout: {s.suggested_layout}")
            lines.append("")

        lines.append("Generate the COMPLETE single-file HTML with all CSS/JS inline.")
        return "\n".join(lines)

    def _extract_html(self, text: str) -> str:
        """Extract HTML from LLM response. If multiple ```html blocks, take the longest."""
        # 1) Strip <think>...</think> reasoning blocks emitted by some models
        #    (Qwen/R1/GLM/Sonnet-thinking variants on custom gateways). These
        #    leak into the final HTML body because <think> starts with `<`,
        #    which previously slipped past the `startswith("<")` passthrough.
        text = re.sub(r"<think\b[^>]*>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Also handle a stray opening <think> with no closer (truncated CoT).
        if re.search(r"<think\b", text, re.IGNORECASE) and not re.search(r"</think>", text, re.IGNORECASE):
            # Drop everything up to and including the orphan opener's first
            # `<section`/`<!DOCTYPE`/`<link` boundary if any; otherwise nuke it.
            m = re.search(r"<(?:section|!DOCTYPE|link|style|html)\b", text, re.IGNORECASE)
            text = text[m.start():] if m else re.sub(r"<think\b[^>]*>", "", text, flags=re.IGNORECASE)

        if "```html" in text:
            blocks = text.split("```html")[1:]
            candidates = []
            for block in blocks:
                html_part = block.split("```")[0] if "```" in block else block
                candidates.append(html_part.strip())
            # Take the longest block
            text = max(candidates, key=len) if candidates else text
        else:
            # 2) Strip any prose/preamble before the first real HTML tag we
            #    care about. Some models emit "Here is the slide:\n<section>"
            #    or similar narration even after we've removed <think>.
            #    We do this regardless of leading char — narration may start
            #    with prose, not with `<`.
            m = re.search(
                r"<(?:!DOCTYPE|html|section|link|style)\b", text, re.IGNORECASE
            )
            if m:
                if m.start() > 0:
                    text = text[m.start():]
                # else: text already starts with HTML — pass through
            else:
                # LLM returned plain text without HTML — wrap in a minimal slide structure
                logger.warning("LLM returned non-HTML response, wrapping in fallback slide")
                escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                text = (
                    '<section style="height:100vh;overflow:hidden;display:flex;align-items:center;'
                    'justify-content:center;padding:clamp(2rem,5vw,4rem)">'
                    f'<p style="font-size:clamp(1rem,2vw,1.5rem);white-space:pre-wrap">{escaped}</p>'
                    '</section>'
                )
        return text.strip()

    def _post_process_slide(self, html: str, style: str, layout_class: str = "") -> str:
        """Inject consistent base styles that the LLM sometimes forgets."""
        import re

        if '<section' not in html:
            return html

        # Defense in depth: strip everything after the LAST </section>.
        # Generator emits ONE slide section per call — nothing legitimate
        # follows it. Models occasionally emit:
        #   - "The slide is complete.\n```" prose / markdown closers
        #   - Stray <style<style>...</style> blocks with the orphan CSS that
        #     should have been inside the section's existing <style> tag
        #     (browser parses `<style<style>` as malformed and renders the
        #     rules as visible body text — see slide 0 / WWDC2026 hero)
        #   - Duplicate trailing <script> blocks
        # An earlier policy preserved <style|script|link> in the tail under
        # the assumption they might be legitimate footers; in practice every
        # observed case was junk. Strip unconditionally.
        last_close = html.lower().rfind('</section>')
        if last_close != -1:
            tail = html[last_close + len('</section>'):]
            if tail.strip():
                html = html[:last_close + len('</section>')]

        # CRITICAL: collapse malformed `<style<style>` (and similar double-open
        # patterns) into a single legal `<style>`. Some models emit this when
        # they meant `</style><style>` — they accidentally use `<` instead of
        # `</`. Browsers interpret `<style<style>` as a `<style>` tag with a
        # bogus attribute named "<style", which then opens a real style
        # block; but in practice the contents render inconsistently and
        # observed pages show the rule body leaking as visible text inside
        # the slide. Treat any `<style...<style>` (with no `>` between) as
        # a single open. Same defense for `<script<script>` though we have
        # not yet seen this in the wild.
        html = re.sub(
            r"<style\b[^>]*<style\b([^>]*)>",
            r"<style\1>",
            html,
            flags=re.IGNORECASE,
        )
        html = re.sub(
            r"<script\b[^>]*<script\b([^>]*)>",
            r"<script\1>",
            html,
            flags=re.IGNORECASE,
        )

        # Strip orphan close-tag fragments that some models emit ("</style></style>"
        # collapses to "</style>/style>" after a sibling deduplicator, or the
        # model literally writes "/style>" without a leading "<"). Without
        # this, browsers render the literal text "/style>" inside the slide.
        # Only target /style>, /script>, /link>, /head> — the real tags that
        # are usually duplicated. We do NOT touch /section>, /div>, /h*> etc
        # because those are common content endings where a typo shouldn't
        # silently reshape the document.
        html = re.sub(
            r"(?<!<)/(?:style|script|link|head)>", "", html, flags=re.IGNORECASE
        )

        # Safety net: if the LLM emitted only `class="slide"` without the
        # layout discriminator class we requested, splice it in. Without
        # this, the deck-level layout-diversity validator reports zero
        # distinct layouts even on a perfectly varied deck.
        if layout_class and layout_class != "slide":
            class_match = re.search(
                r"<section\b[^>]*?\bclass\s*=\s*[\"']([^\"']*)[\"']",
                html,
                re.IGNORECASE,
            )
            if class_match:
                classes = class_match.group(1).split()
                has_layout = any(c in _KNOWN_LAYOUT_CLASSES for c in classes if c.lower() != "slide")
                if not has_layout and layout_class not in classes:
                    new_classes = " ".join(classes + [layout_class])
                    html = (
                        html[: class_match.start(1)]
                        + new_classes
                        + html[class_match.end(1):]
                    )
            else:
                # No `class` attribute at all on the section — insert one.
                # This happens when the LLM forgets the class entirely or
                # the fallback _extract_html wrapping path produced bare
                # `<section style="...">`.
                html = re.sub(
                    r"<section\b",
                    f'<section class="slide {layout_class}"',
                    html,
                    count=1,
                )

        # Fix CSS leakage: bare CSS rules outside <style> tags get wrapped.
        # Detect patterns like ".classname {" or "[data-x] {" or "section {" appearing in body text.
        # IMPORTANT: skip content already inside <style>...</style> blocks. We
        # used to wrap blindly, which double-wrapped legitimate style content
        # any time a malformed `<style<style>` was repaired upstream — yielding
        # `<style><style>...</style></style>` which browsers render as text.
        def _wrap_leaked_css(match_html: str) -> str:
            # Mask out everything inside <style>...</style> with a sentinel so
            # the wrap regex can't match across it. Keep mapping to restore.
            sentinels: list[str] = []
            def _mask(m):
                sentinels.append(m.group(0))
                return f"\x00STYLE{len(sentinels)-1}\x00"
            masked = re.sub(
                r"<style\b[^>]*>.*?</style>",
                _mask,
                match_html,
                flags=re.IGNORECASE | re.DOTALL,
            )

            def fix_leaked(m):
                content = m.group(1)
                # Check if this looks like CSS (has { } with properties)
                if re.search(r'[{]\s*[\w-]+\s*:', content) and content.count('{') > 0:
                    return f'<style>{content}</style>'
                return m.group(0)
            wrapped = re.sub(
                r'>(\s*(?:\.[a-zA-Z][\w-]*|\[[\w-]+[^\]]*\]|[a-z]+)\s*\{[^<]{20,}?}(?:\s*})*\s*)<',
                fix_leaked,
                masked,
            )
            # Restore masked style blocks
            def _unmask(m):
                return sentinels[int(m.group(1))]
            return re.sub(r"\x00STYLE(\d+)\x00", _unmask, wrapped)
        html = _wrap_leaked_css(html)

        # Ensure overflow: hidden on the section element specifically
        section_tag_match = re.search(r'<section([^>]*)>', html)
        if section_tag_match:
            section_attrs = section_tag_match.group(1)
            style_in_section = re.search(r'style="([^"]*)"', section_attrs)
            if style_in_section:
                existing = style_in_section.group(1)
                if 'overflow:' not in existing and 'overflow :' not in existing:
                    new_style = existing.rstrip(';') + '; overflow: hidden;'
                    new_attrs = section_attrs.replace(style_in_section.group(0), f'style="{new_style}"')
                    html = html[:section_tag_match.start(1)] + new_attrs + html[section_tag_match.end(1):]
            else:
                html = html.replace(section_tag_match.group(0), f'<section{section_attrs} style="overflow:hidden;">', 1)

        # Ensure font import exists (from style preset)
        if style in self._presets_cache:
            preset = self._presets_cache[style]
            fonts = preset.get("fonts", {})
            display_font = fonts.get("display", "")
            body_font = fonts.get("body", "")
            font_families = set(filter(None, [display_font, body_font]))

            if font_families and "fonts.googleapis.com" not in html:
                families_param = "|".join(f.replace(" ", "+") for f in font_families)
                font_link = f'<link href="https://fonts.googleapis.com/css2?family={families_param}:wght@300;400;500;600;700&display=swap" rel="stylesheet">'
                html = html.replace('<section', f'{font_link}\n<section', 1)

            # Ensure section uses the preset font-family so single-slide iframe
            # preview doesn't fall back to the browser default (Times). Without
            # this, individual slides look unstyled in the editor preview even
            # though they render fine inside the full deck wrapper.
            if body_font and 'font-family' not in html[:html.find('</style>') if '</style>' in html else min(2000, len(html))]:
                ff_value = f"'{body_font}', system-ui, -apple-system, sans-serif"
                # Inject into section's inline style
                section_match = re.search(r"<section([^>]*)style\s*=\s*\"([^\"]*)\"", html)
                if section_match:
                    if 'font-family' not in section_match.group(2):
                        new_style = section_match.group(2).rstrip("; ") + f"; font-family: {ff_value};"
                        html = html[:section_match.start(2)] + new_style + html[section_match.end(2):]
                else:
                    # No inline style — add one
                    html = re.sub(
                        r"<section\b",
                        f"<section style=\"font-family: {ff_value};\"",
                        html,
                        count=1,
                    )

        # Ensure height: 100vh on section's inline style
        section_match = re.search(r'<section[^>]*style="([^"]*)"', html)
        if section_match:
            existing_style = section_match.group(1)
            if '100vh' not in existing_style and '100dvh' not in existing_style:
                new_style = existing_style + '; height: 100vh; height: 100dvh;'
                html = html[:section_match.start(1)] + new_style + html[section_match.end(1):]
        elif '100vh' not in html:
            html = html.replace('<section', '<section style="height:100vh;height:100dvh;overflow:hidden;"', 1)

        # Ensure section has a background. Models occasionally style decoration
        # (orbs, grid overlays) but forget to set the section's own background
        # — leaves a transparent section showing through whatever container
        # color the embed environment uses (white in default iframe srcdoc),
        # making the slide look "broken" next to its dark neighbors.
        # Strategy: if neither section's inline `style` nor any user CSS rule
        # targets the section/layout class with a `background`, splice a
        # default from the preset's bg_primary into the inline style.
        if style in self._presets_cache:
            preset_colors = self._presets_cache[style].get("colors", {}) if isinstance(self._presets_cache[style], dict) else {}
            preset_bg = preset_colors.get("bg_primary") or preset_colors.get("bg_gradient") or "#0a0a0a"
            section_match = re.search(r'<section([^>]*)>', html)
            if section_match:
                attrs = section_match.group(1)
                inline_style_match = re.search(r'style\s*=\s*"([^"]*)"', attrs)
                inline_has_bg = inline_style_match and re.search(r"\bbackground\b", inline_style_match.group(1))
                # Look in any user <style> block for a rule targeting `section`,
                # `.slide`, or the layout class that sets background.
                section_class_match = re.search(r"<section[^>]*class\s*=\s*['\"][^'\"]*\bslide\s+([\w-]+)", html)
                layout_cls = section_class_match.group(1) if section_class_match else ""
                user_css_blocks = re.findall(
                    r"<style\b(?![^>]*data-id=\"__ppt_)[^>]*>(.*?)</style>",
                    html,
                    re.DOTALL | re.IGNORECASE,
                )
                user_css = "\n".join(user_css_blocks)
                # Selectors that would set the slide background (must NOT be
                # a deeper-nested rule like `.layout .child`). We require the
                # selector to end at the layout class — i.e. no `.something`
                # or whitespace+more selectors before the `{`.
                bg_in_user_css = False
                if user_css:
                    selectors = [r"\.slide\s*\{", r"section\s*\{"]
                    if layout_cls:
                        selectors.append(rf"\.{re.escape(layout_cls)}\s*\{{")
                    for sel in selectors:
                        for m in re.finditer(sel, user_css):
                            # peek into the rule body for `background`
                            tail = user_css[m.end(): m.end() + 400]
                            brace_close = tail.find("}")
                            body_block = tail[:brace_close] if brace_close >= 0 else tail
                            if re.search(r"\bbackground\b", body_block):
                                bg_in_user_css = True
                                break
                        if bg_in_user_css:
                            break

                if not inline_has_bg and not bg_in_user_css:
                    # Splice background into the inline style (or create one).
                    bg_decl = f"background: {preset_bg};"
                    if inline_style_match:
                        new_style = inline_style_match.group(1).rstrip("; ") + f"; {bg_decl}"
                        html = (
                            html[:section_match.start(1) + inline_style_match.start(1)]
                            + new_style
                            + html[section_match.start(1) + inline_style_match.end(1):]
                        )
                    else:
                        html = re.sub(
                            r"<section\b",
                            f'<section style="{bg_decl}"',
                            html,
                            count=1,
                        )

        # Inject anti-overflow CSS and fragment system INSIDE the <section> tag
        # to avoid rendering as visible text nodes outside the element.
        inject_css = ""
        inject_js = ""

        if '__ppt_antioverflow__' not in html:
            # Safety net only: clip overflow and constrain box, do NOT override layout.
            # The LLM picks display:grid/flex/block based on the layout — never force flex-column here.
            inject_css += (
                '<style data-id="__ppt_antioverflow__">'
                'section{max-height:100vh;max-height:100dvh;box-sizing:border-box;overflow:hidden}'
                '</style>'
            )

        # Decouple CSS and JS injection. The model occasionally COPIES the
        # injected fragment <style> block from a context slide but DROPS the
        # <script>. The previous coupled check (`if '__ppt_fragments__' not
        # in html`) saw the leaked CSS and skipped both injections — leaving
        # fragments stuck at opacity:0 forever (JS that toggles `.visible`
        # never runs). Result: entire timeline / step content invisible
        # despite being in the DOM. Fix: check CSS and JS independently.
        # Additional defense: the CSS now defaults `.fragment` to opacity:1
        # so a missing JS doesn't blank the slide. The hide-by-default
        # behavior only kicks in when explicitly opted into via the
        # `[data-frag-hidden]` attribute that the JS sets at startup —
        # if the JS never runs, content stays visible.
        # Inject default values for common CSS custom properties. The model
        # sometimes references `var(--page-padding)`, `var(--accent)` etc.
        # without defining them anywhere on the page — when the fallback
        # is empty, properties resolve to "" which can collapse padding
        # to 0 (content vs section edge crops, looks "broken"). Defining
        # safe defaults at section level lets the model's `var()` calls
        # always resolve to something sensible. Model-defined vars in the
        # same scope override these (cascade specificity).
        if '<style data-id="__ppt_var_defaults__"' not in html:
            preset_colors = {}
            preset_fonts = {}
            if style in self._presets_cache and isinstance(self._presets_cache[style], dict):
                preset_colors = self._presets_cache[style].get("colors", {}) or {}
                preset_fonts = self._presets_cache[style].get("fonts", {}) or {}
            accent = preset_colors.get("accent") or preset_colors.get("accent_blue") or "#4361ee"
            bg_primary = preset_colors.get("bg_primary") or "#0a0a0a"
            text_primary = preset_colors.get("text_primary") or "#ffffff"
            display_font = preset_fonts.get("display") or "Manrope"
            body_font = preset_fonts.get("body") or display_font

            # Auto-emit a CSS var for every preset.colors key, in both
            # underscore (`--bg_primary`) and kebab (`--bg-primary`) form.
            # The model copies YAML keys verbatim into CSS without
            # case-normalising — so `colors.bg_primary` becomes
            # `var(--bg_primary)` in their output. We supply both forms so
            # whichever the model picks resolves correctly.
            preset_var_defs = []
            for k, v in preset_colors.items():
                if not isinstance(v, str):
                    continue
                preset_var_defs.append(f"--{k}:{v};")
                kebab = k.replace("_", "-")
                if kebab != k:
                    preset_var_defs.append(f"--{kebab}:{v};")

            inject_css += (
                '<style data-id="__ppt_var_defaults__">'
                f"section{{"
                # Spacing tokens
                "--page-padding:clamp(2.5rem,6vw,4.5rem);"
                "--section-padding:clamp(2.5rem,6vw,4.5rem);"
                "--block-gap:clamp(1.5rem,3vh,2.5rem);"
                "--inline-gap:clamp(0.8rem,1.5vw,1.2rem);"
                "--gap:clamp(1rem,2vw,1.5rem);"
                # Generic color aliases
                f"--accent:{accent};"
                f"--accent-color:{accent};"
                f"--primary:{accent};"
                f"--bg:{bg_primary};"
                f"--text:{text_primary};"
                "--text-dim:rgba(255,255,255,0.62);"
                "--text_dim:rgba(255,255,255,0.62);"
                "--border-subtle:rgba(255,255,255,0.08);"
                "--border_subtle:rgba(255,255,255,0.08);"
                # Per-preset color tokens (both _ and - forms)
                + "".join(preset_var_defs) +
                # Typography tokens
                "--h1-size:clamp(2.4rem,5.5vw,4.5rem);"
                "--h2-size:clamp(1.6rem,3.4vw,2.6rem);"
                "--h3-size:clamp(1.1rem,1.9vw,1.5rem);"
                "--body-size:clamp(0.9rem,1.35vw,1.15rem);"
                "--caption-size:clamp(0.7rem,1.05vw,0.85rem);"
                f"--display-font:'{display_font}',system-ui,sans-serif;"
                f"--body-font:'{body_font}',system-ui,sans-serif;"
                # Shadow / radius
                "--shadow-card:0 1px 2px rgba(0,0,0,0.4),0 12px 32px rgba(0,0,0,0.28);"
                "--radius:12px;"
                "}"
                "</style>"
            )

        if '<style data-id="__ppt_fragments__"' not in html:
            inject_css += (
                '<style data-id="__ppt_fragments__">'
                '@keyframes fadeInUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}'
                '@keyframes fadeIn{from{opacity:0}to{opacity:1}}'
                # Default-visible: if the JS never runs (stripped by injection
                # bug, blocked by CSP, removed by streaming truncation), all
                # fragments still render. Hidden state is opt-in via the
                # body[data-frag-active] attribute set by the JS at startup.
                'body[data-frag-active] .fragment{opacity:0;transform:translateY(18px);transition:opacity .5s ease,transform .5s ease;pointer-events:none}'
                'body[data-frag-active] .fragment.visible{opacity:1;transform:none;pointer-events:auto}'
                'body[data-frag-active] .fragment.fade-in{transform:none}'
                'body[data-frag-active] .fragment.fade-up{transform:translateY(18px)}'
                'body[data-frag-active] .fragment.fade-left{transform:translateX(30px)}'
                'body[data-frag-active] .fragment.fade-right{transform:translateX(-30px)}'
                'body[data-frag-active] .fragment.zoom-in{transform:scale(.85)}'
                'body[data-frag-active] .fragment.visible.fade-in,'
                'body[data-frag-active] .fragment.visible.fade-up,'
                'body[data-frag-active] .fragment.visible.fade-left,'
                'body[data-frag-active] .fragment.visible.fade-right,'
                'body[data-frag-active] .fragment.visible.zoom-in{opacity:1;transform:none}'
                'body[data-frag-active] .fragment.highlight-current{opacity:.4;transition:opacity .4s}'
                'body[data-frag-active] .fragment.highlight-current.current-fragment{opacity:1}'
                'section>h1,section>h2,section>h3{animation:fadeInUp .5s ease-out both}'
                '@media(prefers-reduced-motion:reduce){.fragment{opacity:1!important;transform:none!important;transition:none!important}}'
                '</style>'
            )
        if '<script data-id="__ppt_fragments__"' not in html:
            inject_js += (
                '<script data-id="__ppt_fragments__">'
                '(function(){'
                # Mark body so the hide-by-default CSS rule kicks in. If this
                # script never runs, body lacks the marker and all .fragment
                # elements stay visible (graceful degradation).
                'document.body.setAttribute("data-frag-active","");'
                'var frags=document.querySelectorAll(".fragment");'
                'var idx=-1;'
                'function reveal(n){'
                '  if(n<-1||n>=frags.length)return;'
                '  idx=n;'
                '  frags.forEach(function(f,i){f.classList.toggle("visible",i<=idx);f.classList.toggle("current-fragment",i===idx)});'
                '  window.parent&&window.parent.postMessage({type:"fragment-state",current:idx,total:frags.length},"*");'
                '}'
                'function next(){reveal(Math.min(idx+1,frags.length-1))}'
                'function prev(){reveal(idx-1)}'
                'document.addEventListener("click",function(e){if(e.button===0)next()});'
                'document.addEventListener("keydown",function(e){'
                '  if(e.key==="ArrowRight"||e.key===" ")next();'
                '  else if(e.key==="ArrowLeft")prev();'
                '});'
                'window.addEventListener("message",function(e){'
                '  if(e.data&&e.data.type==="fragment-cmd"){'
                '    if(e.data.cmd==="next")next();'
                '    else if(e.data.cmd==="prev")prev();'
                '    else if(e.data.cmd==="show-all")reveal(frags.length-1);'
                '    else if(e.data.cmd==="reset")reveal(-1);'
                '  }'
                '});'
                'reveal(frags.length-1);'
                '})();'
                '</script>'
            )

        # Place CSS right after <section...> opening tag, JS before </section>
        if inject_css or inject_js:
            section_open = re.search(r'<section[^>]*>', html)
            if section_open:
                insert_pos = section_open.end()
                html = html[:insert_pos] + inject_css + html[insert_pos:]
                if inject_js:
                    close_pos = html.rfind('</section>')
                    if close_pos != -1:
                        html = html[:close_pos] + inject_js + html[close_pos:]
                    else:
                        html = html + inject_js

        return html
