"""Tests for HTMLGenerator extraction logic."""
import pytest
from unittest.mock import MagicMock
from agent.generator import HTMLGenerator, _layout_class_for


class TestLayoutClassFor:
    """R11: layout-class picker must not mismatch `hero` inside `kpi-hero-row`."""

    @pytest.mark.parametrize("hint,ct,expected", [
        ("kpi-hero-row", "content", "kpi-hero-row"),
        ("hero", "content", "hero"),
        ("grid-2", "content", "grid-2"),
        ("grid-3", "content", "grid-3"),
        ("Equal-width horizontal panels with dividers", "content", "h-track"),
        ("3-4 large metric boxes in a prominent row", "content", "kpi-hero-row"),
        ("60/40 left-right split", "content", "editorial-split"),
        ("", "cover", "hero"),
        ("", "closing", "closing"),
        ("", "content", "grid-2"),
    ])
    def test_layout_class_pick(self, hint, ct, expected):
        assert _layout_class_for(hint, ct) == expected


class TestPostProcessLayoutClass:
    """R11: post_process must inject layout class when LLM only emits class='slide'."""

    def test_injects_missing_layout_class(self):
        gen = HTMLGenerator.__new__(HTMLGenerator)
        gen._presets_cache = {}
        gen._base_css = ""
        html = '<section class="slide" style="height:100vh;overflow:hidden;"><h1>x</h1></section>'
        out = gen._post_process_slide(html, "corporate-navy", layout_class="kpi-hero-row")
        assert 'class="slide kpi-hero-row"' in out

    def test_skips_when_layout_already_present(self):
        gen = HTMLGenerator.__new__(HTMLGenerator)
        gen._presets_cache = {}
        gen._base_css = ""
        html = '<section class="slide cascade-grid" style="height:100vh;overflow:hidden;"><h1>x</h1></section>'
        out = gen._post_process_slide(html, "corporate-navy", layout_class="kpi-hero-row")
        # Existing layout class should NOT be replaced
        assert 'cascade-grid' in out
        assert 'kpi-hero-row' not in out

    def test_inserts_class_when_section_has_none(self):
        """R33: section with no `class` attribute at all — must still get
        `class="slide {layout_class}"` injected."""
        gen = HTMLGenerator.__new__(HTMLGenerator)
        gen._presets_cache = {}
        gen._base_css = ""
        html = '<section style="height:100vh;overflow:hidden;"><h1>x</h1></section>'
        out = gen._post_process_slide(html, "corporate-navy", layout_class="risk-stack")
        assert 'class="slide risk-stack"' in out


@pytest.fixture
def generator():
    """Create generator with mocked LLM client."""
    mock_client = MagicMock()
    gen = HTMLGenerator.__new__(HTMLGenerator)
    gen.client = mock_client
    gen.model = "test"
    gen._generation_prompt = ""
    gen._regen_prompt = ""
    gen._base_css = ""
    gen._presets_cache = {}
    return gen


class TestExtractHtml:
    def test_extracts_from_html_fenced_block(self, generator):
        text = 'Here is the slide:\n```html\n<section class="slide">Hello</section>\n```\nDone!'
        result = generator._extract_html(text)
        assert result == '<section class="slide">Hello</section>'

    def test_extracts_longest_html_block(self, generator):
        text = '```html\n<section>short</section>\n```\n```html\n<section class="slide" style="height:100vh">longer content here</section>\n```'
        result = generator._extract_html(text)
        assert "longer content here" in result

    def test_passes_through_raw_html(self, generator):
        text = '<!DOCTYPE html><html><body><section>test</section></body></html>'
        result = generator._extract_html(text)
        assert result == text

    def test_wraps_plain_text_in_section(self, generator):
        text = "This is just a plain text response with no HTML at all."
        result = generator._extract_html(text)
        assert "<section" in result
        assert "overflow:hidden" in result
        assert "This is just a plain text response" in result

    def test_plain_text_escapes_html_entities(self, generator):
        text = "Revenue < Cost & Loss > Profit"
        result = generator._extract_html(text)
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result
        # Original text should not appear unescaped
        assert "< Cost" not in result

    def test_section_tag_passes_through(self, generator):
        text = '<section style="height:100vh"><h1>Title</h1></section>'
        result = generator._extract_html(text)
        assert result == text

    def test_strips_think_block(self, generator):
        """<think>...</think> reasoning blocks (Qwen/R1/GLM-style) must
        not leak into the final HTML body."""
        text = (
            "<think>\nThe user wants me to generate slide #7 with:\n"
            "- Title: 设计规范与平台一致性\n- Layout: grid-3\n"
            "Let me create three cards...\n</think>\n"
            '<section class="slide grid-3"><h2>设计规范</h2></section>'
        )
        result = generator._extract_html(text)
        assert "<think>" not in result
        assert "wants me to generate" not in result
        assert result.startswith("<section")

    def test_strips_unclosed_think_block(self, generator):
        """If a <think> block is truncated mid-stream, drop everything up
        to the first real HTML tag we recognize."""
        text = (
            "<think>\nReasoning that never closes...\n"
            '<section class="slide hero"><h1>Title</h1></section>'
        )
        result = generator._extract_html(text)
        assert "<think>" not in result
        assert "Reasoning that never closes" not in result
        assert result.startswith("<section")

    def test_collapses_malformed_double_style_open(self, generator):
        """Models occasionally emit <style<style> (a double-open of <style>)
        when they meant </style><style>. Browsers parse it as a malformed
        single open with bogus attribute "<style", and rule content renders
        as visible body text. Repair by collapsing to a single legal open."""
        text = (
            '<section class="slide hero">'
            '<style data-id="prior">a{color:red}</style>'
            '<style<style>\n.hero { background: #000; padding: clamp(1rem, 2vw, 2rem); }\n</style>'
            '<h1>Title</h1></section>'
        )
        result = generator._post_process_slide(text, "electric-studio", layout_class="hero")
        assert "<style<style>" not in result
        # And critically: the surviving <style> wrapping the rule must NOT be
        # double-wrapped by _wrap_leaked_css (the historical regression).
        import re as _re
        double_open = _re.search(r"<style\b[^>]*>\s*<style\b", result)
        assert double_open is None, f"double-wrap regression: {result[double_open.start():double_open.start()+80]!r}"
        # The CSS rule body must remain inside a style block, not as text.
        assert ".hero { background:" in result  # content preserved
        assert ">.hero { background:" not in result  # not as text after `>`

    def test_wrap_leaked_css_skips_inside_style(self, generator):
        """The _wrap_leaked_css helper must not wrap content that's already
        inside a <style>...</style> block — wrapping it again produces the
        same double-<style> malformation we're trying to fix."""
        text = (
            '<section class="slide hero">'
            '<style>.foo { color: red; padding: 12px; margin: 8px 16px; '
            'background: linear-gradient(90deg, #000, #111); border-radius: 4px; }</style>'
            '<h1>Title</h1></section>'
        )
        result = generator._post_process_slide(text, "electric-studio", layout_class="hero")
        import re as _re
        # No `<style><style>` adjacent opens
        assert _re.search(r"<style\b[^>]*>\s*<style\b", result) is None

    def test_strips_orphan_style_after_section(self, generator):
        """Models sometimes emit a malformed <style<style>...</style> block
        AFTER </section> with CSS that should have been inside the section.
        Browser parses this as text and the rules appear as visible body
        content. Anything after </section> must be stripped."""
        text = (
            '<section class="slide hero"><h1>Title</h1></section>\n\n'
            '<style<style>\n.hero { background: #0a0a0a; }\n'
            '.hero-bg { position: absolute; }\n</style>'
        )
        result = generator._extract_html(text)
        # _extract_html doesn't strip tail (that's _post_process_slide's job),
        # but make sure end-to-end the orphan is gone.
        result = generator._post_process_slide(result, "electric-studio")
        assert "</section>" in result
        # Nothing meaningful after the last </section>
        assert result.rstrip().endswith("</section>")
        assert ".hero { background:" not in result.split("</section>")[-1]

    def test_strips_prose_preamble_before_section(self, generator):
        """Models sometimes narrate `Here is the slide:` before HTML."""
        text = (
            'Here is the slide:\n\n<section class="slide">content</section>'
        )
        result = generator._extract_html(text)
        assert result.startswith("<section")
        assert "Here is the slide" not in result
