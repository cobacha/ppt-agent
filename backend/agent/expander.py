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

    def expand_single(self, index: int, title: str, bullets: list[str], content_type: str) -> ExpandedSlide:
        bullets_text = "\n".join(f"- {b}" for b in bullets)

        user_msg = f"""幻灯片 #{index + 1}
标题: {title}
类型: {content_type}
要点:
{bullets_text}

将以上要点扩展为详细的演示内容。返回 JSON。"""

        response = self.client.chat_completion(
            system=self._prompt + "\n\nReturn ONLY valid JSON, no other text.",
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=128000,
            temperature=0.3,
            timeout=60.0,
        )

        return self._parse_result(index, title, response.text)

    def _parse_result(self, index: int, title: str, text: str) -> ExpandedSlide:
        try:
            import re
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            text = text.strip()
            # Fix trailing commas
            text = re.sub(r',\s*([}\]])', r'\1', text)
            data = json.loads(text)
            return ExpandedSlide(
                index=index,
                title=data.get("title", title),
                detailed_content=data.get("detailed_content", ""),
                key_visual=data.get("key_visual", ""),
            )
        except (json.JSONDecodeError, IndexError):
            return ExpandedSlide(
                index=index,
                title=title,
                detailed_content=text.strip(),
            )
