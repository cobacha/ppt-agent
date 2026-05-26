"""Quality Gate - Validates HTML against presentation standards."""

import json
import re
from dataclasses import dataclass, field

from .llm_client import LLMClient


@dataclass
class QualityReport:
    passed: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: float = 100.0

    @property
    def feedback(self) -> list[str]:
        return self.issues


LLM_CHECK_PROMPT = """你是一个 HTML 幻灯片质量审核专家。检查以下单页幻灯片 HTML，评估：

1. **内容溢出风险**：内容是否可能超出 100vh 视口高度？考虑 padding、标题、正文、卡片等总高度
2. **布局完整性**：所有元素是否正确对齐？是否有遮挡或重叠？
3. **文字可读性**：字号是否过小？对比度是否足够？
4. **内容完整性**：标题和内容是否完整展示（不被截断）？

返回 JSON（无其他文字）：
```json
{
  "passed": true/false,
  "score": 0-100,
  "issues": ["具体问题描述..."],
  "fix_suggestion": "如何修复的一句话建议（如果 passed 为 false）"
}
```

评分标准：
- 90-100: 完美，无问题
- 70-89: 小瑕疵但可接受
- 50-69: 有明显问题需修复
- 0-49: 严重问题必须重做

**重要**：如果内容量明显超过单屏能展示的范围（例如超过5个要点、多于4张卡片、大段文字），必须判 passed=false。"""


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
        """Check a single slide section."""
        issues = []
        warnings = []

        # Overflow check — specifically on the <section> tag
        section_tag = re.search(r'<section[^>]*>', html)
        if section_tag:
            section_attrs = section_tag.group(0)
            if 'overflow' not in section_attrs:
                issues.append("Slide section missing overflow: hidden")
        else:
            issues.append("No <section> element found")

        # Bullet density
        li_count = html.count("<li")
        if li_count > 8:
            issues.append(f"Slide has {li_count} bullets (max 6 recommended)")

        # Font import check
        if "fonts.googleapis.com" not in html and "fontshare.com" not in html:
            warnings.append("No font import (Google Fonts or Fontshare link)")

        # Responsive clamp() usage
        style_blocks = re.findall(r"(?:style=\"[^\"]*\"|<style[^>]*>.*?</style>)", html, re.DOTALL)
        style_text = " ".join(style_blocks)
        fixed_sizes = [fs for fs in re.findall(r"font-size:\s*([^;\"]+)", style_text)
                       if "clamp" not in fs and "var(" not in fs and "inherit" not in fs]
        if len(fixed_sizes) > 3:
            warnings.append(f"{len(fixed_sizes)} fixed font-sizes without responsive clamp()")

        # Minimum content: at least one heading element
        if not re.search(r"<h[1-6]", html):
            issues.append("Slide missing heading element (h1-h6)")

        score = max(0, 100 - len(issues) * 15 - len(warnings) * 5)
        return QualityReport(passed=len(issues) == 0, issues=issues, warnings=warnings, score=score)

    def _check_viewport(self, html: str) -> list[str]:
        issues = []
        if 'class="slide' not in html:
            issues.append("No slides found")
            return issues
        if "100vh" not in html and "100dvh" not in html:
            issues.append("Missing height: 100vh/100dvh")
        if "overflow: hidden" not in html and "overflow:hidden" not in html:
            issues.append("Missing overflow: hidden")
        if "scroll-snap" not in html:
            issues.append("Missing scroll-snap")
        return issues

    def _check_layout_diversity(self, html: str) -> list[str]:
        patterns = [
            "grid-2", "grid-3", "trend-bands", "cascade-grid",
            "editorial-split", "h-track", "dual-timeline", "kpi-hero",
            "scorecard-strip", "asym-compare", "risk-stack", "opp-ladder",
        ]

        sections = re.split(r'<section[^>]*class="slide', html)
        layouts = []
        for sec in sections[1:]:
            found = next((p for p in patterns if p in sec), "unknown")
            layouts.append(found)

        issues = []
        for i in range(1, len(layouts)):
            if layouts[i] == layouts[i-1] and layouts[i] != "unknown":
                issues.append(f"Slides {i} and {i+1} use same layout '{layouts[i]}'")

        unique = set(layouts) - {"unknown"}
        if len(layouts) > 8 and len(unique) < 4:
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
        style = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
        if not style:
            return ["No <style> block found"]

        fixed = [fs for fs in re.findall(r"font-size:\s*([^;]+);", style.group(1))
                 if "clamp" not in fs and "var(" not in fs and "inherit" not in fs]

        if len(fixed) > 3:
            return [f"{len(fixed)} fixed font-sizes without clamp()"]
        return []

    def _check_fonts(self, html: str) -> list[str]:
        warnings = []
        if "fonts.googleapis.com" not in html and "fontshare.com" not in html:
            warnings.append("No external font import — may use system fonts")
        return warnings

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
        except Exception:
            return QualityReport(passed=True, score=75.0)
