"""Content Expander - Expands sparse outline bullets into detailed slide content."""

import json
from dataclasses import dataclass
from pathlib import Path

from .llm_client import LLMClient


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@dataclass
class ExpandedSlide:
    index: int
    title: str
    detailed_content: str
    key_visual: str = ""


class ContentExpander:
    def __init__(self, client: LLMClient, model: str):
        self.client = client
        self.model = model
        self._prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        path = PROMPTS_DIR / "content_expansion.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return "Expand slide bullets into detailed presentation content. Return JSON."

    def expand_single(
        self,
        index: int,
        title: str,
        bullets: list[str],
        content_type: str,
        language: str = "zh",
    ) -> ExpandedSlide:
        bullets_text = "\n".join(f"- {b}" for b in bullets)

        if language and language.lower().startswith("en"):
            user_msg = (
                f"Slide #{index + 1}\n"
                f"Title: {title}\n"
                f"Type: {content_type}\n"
                f"Bullets:\n{bullets_text}\n\n"
                f"Expand the bullets into detailed presentation content "
                f"in English. Return JSON."
            )
        else:
            user_msg = (
                f"幻灯片 #{index + 1}\n"
                f"标题: {title}\n"
                f"类型: {content_type}\n"
                f"要点:\n{bullets_text}\n\n"
                f"将以上要点扩展为详细的演示内容。返回 JSON。"
            )

        response = self.client.chat_completion(
            system=self._prompt + "\n\nReturn ONLY valid JSON, no other text.",
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=2048,
            temperature=0.3,
            timeout=30.0,
        )

        return self._parse_result(index, title, response.text)

    # Hard cap on what we feed downstream to the slide generator. Even if
    # the LLM ignores the prompt's "≤ 220 字" rule, this truncates so a
    # rambling expansion can't translate into an overflowing slide. 280 is
    # slightly above the prompt limit to leave a safety margin for short
    # CJK-plus-ASCII mixed content; tighten if overflow rate stays high.
    DETAILED_CONTENT_HARD_CAP = 280

    def _parse_result(self, index: int, title: str, text: str) -> ExpandedSlide:
        try:
            import re
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            text = text.strip()
            # If a code-fenced block had a language tag we didn't anticipate
            # (e.g. ```html), the first line is just the language identifier.
            # Strip it so we don't poison `detailed_content` with `html\n...`.
            text = re.sub(r"^[a-zA-Z]+\s*\n", "", text)
            # Fix trailing commas
            text = re.sub(r',\s*([}\]])', r'\1', text)
            data = json.loads(text)
            content = data.get("detailed_content", "")
            return ExpandedSlide(
                index=index,
                title=data.get("title", title),
                detailed_content=self._truncate(content),
                key_visual=data.get("key_visual", ""),
            )
        except (json.JSONDecodeError, IndexError):
            return ExpandedSlide(
                index=index,
                title=title,
                detailed_content=self._truncate(text.strip()),
            )

    @classmethod
    def _truncate(cls, text: str) -> str:
        """Hard-cap detailed_content length. Truncates at the nearest sentence
        boundary within range so we don't end mid-word; falls back to a hard
        char cut for inputs without punctuation. Adds an ellipsis when cut."""
        if not text or len(text) <= cls.DETAILED_CONTENT_HARD_CAP:
            return text
        cap = cls.DETAILED_CONTENT_HARD_CAP
        # Find last sentence terminator within [cap-40, cap]
        window_start = max(0, cap - 40)
        terminators = "。！？.!?"
        best = -1
        for i in range(cap, window_start, -1):
            if i < len(text) and text[i] in terminators:
                best = i + 1
                break
        if best > 0:
            return text[:best].rstrip()
        return text[:cap].rstrip() + "…"
