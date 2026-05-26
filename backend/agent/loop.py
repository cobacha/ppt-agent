"""
Agent Loop - Core orchestration for presentation generation.

Handles both bulk generation and single-slide regeneration.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

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
        self.client = create_llm_client()
        self.model = model or self.client.model
        self.max_iterations = max_iterations
        self.analyzer = ContentAnalyzer(self.client, self.model)
        self.expander = ContentExpander(self.client, self.model)
        self.generator = HTMLGenerator(self.client, self.model)
        self.quality_gate = QualityGate()

    def reload_prompts(self):
        """Re-initialize analyzer, expander, and generator to pick up fresh prompt content."""
        self.analyzer = ContentAnalyzer(self.client, self.model)
        self.expander = ContentExpander(self.client, self.model)
        self.generator = HTMLGenerator(self.client, self.model)

    def reload_client(self):
        """Re-create LLM client with current env vars (hot-reload after settings change)."""
        self.client = create_llm_client()
        self.model = self.client.model
        self.analyzer = ContentAnalyzer(self.client, self.model)
        self.expander = ContentExpander(self.client, self.model)
        self.generator = HTMLGenerator(self.client, self.model)

    def generate_bulk(self, content: str, style: str = "corporate-navy", max_iterations: int | None = None) -> GenerationResult:
        """Generate all slides from content."""
        iterations_limit = max_iterations if max_iterations is not None else self.max_iterations
        outline = self.analyzer.analyze(content)
        html = self.generator.generate_full(outline, style)

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

    def expand_slide(self, index: int, spec: SlideSpec) -> ExpandedSlide:
        """Stage 1.5: Expand a single slide's bullets into detailed content."""
        return self.expander.expand_single(
            index=index,
            title=spec.title,
            bullets=spec.bullets,
            content_type=spec.content_type,
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
        """Stage 2: Generate one slide from spec with context. Auto-retries on low quality."""
        MAX_RETRIES = 2
        QUALITY_THRESHOLD = 80
        best_html = ""
        best_score = 0.0
        retry_spec = dict(spec)

        for attempt in range(1 + MAX_RETRIES):
            html = self.generator.generate_from_spec(
                spec=retry_spec,
                style=style,
                slide_index=slide_index,
                context_slides=context_slides,
                language=language,
            )

            # Rule-based structural check
            report = self.quality_gate.check_single(html)

            if report.score >= QUALITY_THRESHOLD and report.passed:
                # LLM-based quality check
                llm_report = self.quality_gate.llm_check_single(html, self.client, self.model)
                combined_score = min(report.score, llm_report.score)

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

                if attempt < MAX_RETRIES:
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
                    retry_spec["quality_feedback"] = (
                        f"Attempt {attempt+1} scored {combined_score:.0f}/100. "
                        f"Issues: {'; '.join(all_feedback)}. "
                        f"Fix these structural problems in the new version."
                    )

        return SlideResult(
            index=slide_index,
            title=spec.get("title", ""),
            html=best_html,
            quality_score=best_score,
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
