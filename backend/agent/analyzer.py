"""Content Analyzer - Structures raw input into slide outline."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

from .llm_client import LLMClient

logger = logging.getLogger("ppt-agent")


@dataclass
class SlideSpec:
    title: str
    content_type: str
    bullets: list[str] = field(default_factory=list)
    data_points: dict = field(default_factory=dict)
    suggested_layout: str = ""


@dataclass
class SlideOutline:
    title: str
    subtitle: str
    slide_count: int
    slides: list[SlideSpec] = field(default_factory=list)
    theme_hint: str = ""


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class ContentAnalyzer:
    def __init__(self, client: LLMClient, model: str):
        self.client = client
        self.model = model
        self._system_prompt = self._load_prompt()
        self._last_streaming_result: SlideOutline | None = None

    def _load_prompt(self) -> str:
        path = PROMPTS_DIR / "content_analysis.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return "Analyze content and produce a JSON slide outline."

    def _fix_json(self, text: str) -> str:
        """Fix common JSON issues from LLM output."""
        import re
        # Remove trailing commas before } or ]
        text = re.sub(r',\s*([}\]])', r'\1', text)
        # Remove comments
        text = re.sub(r'//[^\n]*', '', text)
        # Fix single-quoted strings → double-quoted
        text = re.sub(r"(?<=[{,\[])\s*'([^']+)'\s*:", r' "\1":', text)
        text = re.sub(r":\s*'([^']*)'", r': "\1"', text)
        # Fix unquoted keys
        text = re.sub(r'(?<=[{,])\s*([a-zA-Z_]\w*)\s*:', r' "\1":', text)
        # Fix truncated JSON: close unclosed brackets
        text = self._close_json(text)
        return text

    def _close_json(self, text: str) -> str:
        """Attempt to close truncated JSON by balancing brackets."""
        import re
        text = text.rstrip()
        # Strip trailing comma
        if text.endswith(','):
            text = text[:-1]
        # Check if there's an unterminated string (odd number of unescaped quotes)
        # by scanning for string state at end of text
        in_string = False
        escape = False
        for ch in text:
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
        # Only strip trailing incomplete string if we're actually inside an unterminated string
        if in_string:
            text = re.sub(r',?\s*"[^"]*$', '', text)
        # Count open/close brackets
        opens = []
        in_string = False
        escape = False
        for ch in text:
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in ('{', '['):
                opens.append(ch)
            elif ch == '}' and opens and opens[-1] == '{':
                opens.pop()
            elif ch == ']' and opens and opens[-1] == '[':
                opens.pop()
        # Close remaining open brackets in reverse order
        for bracket in reversed(opens):
            text += ']' if bracket == '[' else '}'
        return text

    def _parse_outline(self, text: str) -> SlideOutline:
        """Parse raw LLM text output into a SlideOutline."""
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            fixed = self._fix_json(text)
            try:
                data = json.loads(fixed)
            except json.JSONDecodeError:
                try:
                    import ast
                    data = ast.literal_eval(fixed)
                except (ValueError, SyntaxError):
                    raise ValueError(f"无法解析大纲 JSON，请重试")

        slides = [
            SlideSpec(
                title=s.get("title", ""),
                content_type=s.get("content_type", "content"),
                bullets=s.get("bullets", []),
                data_points=s.get("data_points", {}),
                suggested_layout=s.get("suggested_layout", ""),
            )
            for s in data.get("slides", [])
        ]

        raw_title = data.get("title", "")
        if not raw_title or raw_title in ("Untitled", "untitled", "未命名"):
            raw_title = slides[0].title if slides else "演示文稿"

        outline = SlideOutline(
            title=raw_title,
            subtitle=data.get("subtitle", ""),
            slide_count=len(slides),
            slides=slides,
            theme_hint=data.get("theme_hint", "corporate"),
        )

        if len(slides) < 7:
            logger.warning(f"Outline has only {len(slides)} slides (minimum 7 expected: 5 content + cover + closing)")

        return outline

    def _build_user_content(self, content: str, language: str) -> str:
        lang_instruction = "Generate all slide titles, bullets, and text content in Chinese (中文)." if language == "zh" else "Generate all slide titles, bullets, and text content in English."
        return f"[Language: {lang_instruction}]\n\n{content}"

    def analyze(self, content: str, language: str = "zh") -> SlideOutline:
        response = self.client.chat_completion(
            system=self._system_prompt + "\n\nCRITICAL: Return ONLY valid JSON. No trailing commas. All keys and string values MUST use double quotes. No comments. No explanation.",
            messages=[{"role": "user", "content": self._build_user_content(content, language)}],
            max_tokens=128000,
            temperature=0,
            timeout=60.0,
        )

        return self._parse_outline(response.text)

    def analyze_streaming(self, content: str, language: str = "zh") -> Generator[str, None, None]:
        """Generate outline with streaming, yielding text chunks as they arrive."""
        full_text = ""
        for chunk in self.client.stream_completion(
            system=self._system_prompt + "\n\nCRITICAL: Return ONLY valid JSON. No trailing commas. All keys and string values MUST use double quotes. No comments. No explanation.",
            messages=[{"role": "user", "content": self._build_user_content(content, language)}],
            max_tokens=128000,
            temperature=0,
        ):
            full_text += chunk
            yield chunk

        # After streaming completes, parse the full result
        self._last_streaming_result = self._parse_outline(full_text)
