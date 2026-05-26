"""Tests for ContentAnalyzer JSON parsing methods."""

import json
from unittest.mock import MagicMock

import pytest

from agent.analyzer import ContentAnalyzer, SlideOutline


@pytest.fixture
def analyzer():
    mock_client = MagicMock()
    return ContentAnalyzer(client=mock_client, model="test-model")


class TestFixJson:
    """Test _fix_json via _parse_outline (the actual usage path).

    Note: _fix_json is only called on text that already failed json.loads(),
    so we test it through _parse_outline which handles the full pipeline.
    """

    def test_valid_json_passes_through(self, analyzer):
        """Valid JSON is parsed directly without needing _fix_json."""
        data = '{"title": "Hello", "subtitle": "", "slides": []}'
        result = analyzer._parse_outline(data)
        assert result.title == "Hello"

    def test_trailing_commas_fixed(self, analyzer):
        bad = '{"title": "Fixed", "subtitle": "", "slides": [{"title": "S1", "content_type": "x",}],}'
        result = analyzer._parse_outline(bad)
        assert result.title == "Fixed"
        assert result.slides[0].title == "S1"

    def test_single_quoted_strings_fixed(self, analyzer):
        bad = "{'title': 'Hello', 'subtitle': '', 'slides': [{'title': 'S1', 'content_type': 'intro'}]}"
        result = analyzer._parse_outline(bad)
        assert result.title == "Hello"

    def test_unquoted_keys_fixed(self, analyzer):
        bad = '{title: "Hello", subtitle: "", slides: [{title: "S1", content_type: "x"}]}'
        result = analyzer._parse_outline(bad)
        assert result.title == "Hello"

    def test_truncated_json_auto_closed(self, analyzer):
        truncated = '{"title": "Hello", "subtitle": "sub", "slides": [{"title": "Slide 1", "content_type": "intro"'
        result = analyzer._parse_outline(truncated)
        assert result.title == "Hello"
        assert result.slides[0].title == "Slide 1"

    def test_multiple_unclosed_brackets(self, analyzer):
        truncated = '{"title": "Test", "subtitle": "", "slides": [{"title": "A", "content_type": "x", "bullets": ["one", "two"'
        result = analyzer._parse_outline(truncated)
        assert result.title == "Test"
        assert result.slides[0].bullets == ["one", "two"]


class TestParseOutline:
    def test_valid_json_parsed(self, analyzer):
        data = json.dumps({
            "title": "My Deck",
            "subtitle": "A subtitle",
            "theme_hint": "tech",
            "slides": [
                {"title": "Intro", "content_type": "title", "bullets": ["Point 1"], "suggested_layout": "hero"},
                {"title": "Content", "content_type": "content", "bullets": ["A", "B"], "suggested_layout": "grid-2"},
            ],
        })
        result = analyzer._parse_outline(data)
        assert isinstance(result, SlideOutline)
        assert result.title == "My Deck"
        assert result.subtitle == "A subtitle"
        assert result.slide_count == 2
        assert result.slides[0].title == "Intro"
        assert result.slides[0].suggested_layout == "hero"
        assert result.theme_hint == "tech"

    def test_json_in_code_block_extracted(self, analyzer):
        wrapped = '```json\n{"title": "Test", "subtitle": "", "slides": [{"title": "S1", "content_type": "content"}]}\n```'
        result = analyzer._parse_outline(wrapped)
        assert result.title == "Test"
        assert result.slides[0].title == "S1"

    def test_generic_code_block_extracted(self, analyzer):
        wrapped = '```\n{"title": "X", "subtitle": "", "slides": []}\n```'
        result = analyzer._parse_outline(wrapped)
        assert result.title == "X"

    def test_invalid_garbage_raises_valueerror(self, analyzer):
        with pytest.raises(ValueError, match="无法解析大纲"):
            analyzer._parse_outline("this is not json at all @@##$$")

    def test_truncated_json_recovered(self, analyzer):
        truncated = '{"title": "Recovered", "subtitle": "sub", "slides": [{"title": "S1", "content_type": "intro"'
        result = analyzer._parse_outline(truncated)
        assert result.title == "Recovered"
        assert result.slides[0].title == "S1"
