"""HTML Generator - Produces presentation HTML via LLM."""

from pathlib import Path

import yaml

from .llm_client import LLMClient
from .analyzer import SlideOutline


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
        # Cache presets.yaml at init time
        self._presets_cache = self._load_presets()

    def _load_file(self, path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _load_presets(self) -> dict:
        style_path = STYLES_DIR / "presets.yaml"
        if style_path.exists():
            with open(style_path) as f:
                return yaml.safe_load(f) or {}
        return {}

    def generate_full(self, outline: SlideOutline, style: str) -> str:
        system = self._build_system_prompt(style)
        user_msg = self._format_outline(outline)

        response = self.client.chat_completion(
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=128000,
            timeout=60.0,
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
        aspect_ratio = spec.get("aspect_ratio", "16:9")

        # Map aspect ratio to CSS dimensions
        ar_map = {
            "16:9": ("100vw", "100vh"),
            "4:3": ("min(100vw, 133.33vh)", "min(100vh, 75vw)"),
            "16:10": ("min(100vw, 160vh)", "min(100vh, 62.5vw)"),
            "1:1": ("min(100vw, 100vh)", "min(100vh, 100vw)"),
        }
        ar_width, ar_height = ar_map.get(aspect_ratio, ("100vw", "100vh"))
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

        user_msg = f"""Generate slide #{slide_index + 1}.

Title: {spec.get('title', '')}
Content type: {content_type}{role_hint}
Bullets:
{bullets_text}
{detail_section}Layout: {layout}

{f"Context (previous slides):{chr(10)}{context_text}" if context_text else "This is the first slide."}{pres_section}

Generate ONLY the <section class="slide">...</section> HTML for this single slide.
Include inline styles consistent with the style preset. Make it visually polished."""

        quality_feedback = spec.get("quality_feedback", "")
        if quality_feedback:
            user_msg += f"\n\nIMPORTANT quality requirements:\n{quality_feedback}"

        # Use structured system with cache_control so the system prompt (which is
        # identical across all slides in a generation) is cached by the Anthropic API.
        # For non-Anthropic providers, the client extracts text and ignores cache_control.
        response = self.client.chat_completion(
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=8192,
            timeout=60.0,
        )

        return self._post_process_slide(self._extract_html(response.text), style)

    def generate_single(
        self, content: str, layout: str, style: str, context: str, slide_index: int
    ) -> str:
        system = self._regen_prompt or self._generation_prompt
        system += f"\n\nStyle: {style}\nLayout pattern to use: {layout}"

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
            max_tokens=64000,
            timeout=60.0,
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
        if "```html" in text:
            blocks = text.split("```html")[1:]
            candidates = []
            for block in blocks:
                html_part = block.split("```")[0] if "```" in block else block
                candidates.append(html_part.strip())
            # Take the longest block
            text = max(candidates, key=len) if candidates else text
        elif text.strip().startswith("<!DOCTYPE") or text.strip().startswith("<"):
            pass
        return text.strip()

    def _post_process_slide(self, html: str, style: str) -> str:
        """Inject consistent base styles that the LLM sometimes forgets."""
        import re

        if '<section' not in html:
            return html

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

        # Ensure height: 100vh on section's inline style
        section_match = re.search(r'<section[^>]*style="([^"]*)"', html)
        if section_match:
            existing_style = section_match.group(1)
            if '100vh' not in existing_style and '100dvh' not in existing_style:
                new_style = existing_style + '; height: 100vh; height: 100dvh;'
                html = html[:section_match.start(1)] + new_style + html[section_match.end(1):]
        elif '100vh' not in html:
            html = html.replace('<section', '<section style="height:100vh;height:100dvh;overflow:hidden;"', 1)

        # Inject anti-overflow CSS: flex column layout + auto-scaling fallback
        if '__ppt_antioverflow__' not in html:
            antioverflow_css = (
                '<style data-id="__ppt_antioverflow__">'
                'section{display:flex!important;flex-direction:column!important;'
                'justify-content:flex-start!important;max-height:100vh!important;'
                'max-height:100dvh!important;box-sizing:border-box!important}'
                'section>*{flex-shrink:1!important;min-height:0!important}'
                'section>h1,section>h2,section>h3{flex-shrink:0!important}'
                '</style>'
            )
            html = antioverflow_css + '\n' + html

        # Inject entrance animation CSS if not already present
        if '@keyframes fadeInUp' not in html:
            anim_css = (
                '<style>'
                '@keyframes fadeInUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}'
                '@keyframes fadeIn{from{opacity:0}to{opacity:1}}'
                'section>h1,section>h2,section>h3,section>p,section>li,section>ul,section>ol'
                '{animation:fadeInUp .6s ease-out both}'
                'section>img,section>svg{animation:fadeIn .8s ease-out both}'
                'section>*:nth-child(1){animation-delay:.1s}'
                'section>*:nth-child(2){animation-delay:.2s}'
                'section>*:nth-child(3){animation-delay:.35s}'
                'section>*:nth-child(4){animation-delay:.5s}'
                'section>*:nth-child(5){animation-delay:.65s}'
                'section>*:nth-child(6){animation-delay:.8s}'
                '@media(prefers-reduced-motion:reduce){section>*{animation:none!important}}'
                '</style>'
            )
            html = anim_css + '\n' + html

        return html
