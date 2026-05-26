"""Tests for QualityGate validator."""

import pytest

from agent.validator import QualityGate


@pytest.fixture
def gate():
    return QualityGate()


# --- QualityGate.check() tests ---

class TestCheck:
    def test_valid_full_html(self, gate):
        html = """
        <style>
        .slide { height: 100vh; overflow: hidden; scroll-snap-align: start; }
        body { scroll-snap-type: y mandatory; }
        h1 { font-size: clamp(1.5rem, 3vw, 2.5rem); }
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">
        <section class="slide grid-2">
            <h1>Title</h1>
            <p>Content</p>
        </section>
        <section class="slide editorial-split">
            <h2>Second</h2>
            <p>More content</p>
        </section>
        """
        report = gate.check(html)
        assert report.score > 0
        assert isinstance(report.issues, list)
        assert isinstance(report.warnings, list)

    def test_missing_slides(self, gate):
        html = "<div>No slides here</div>"
        report = gate.check(html)
        assert not report.passed
        assert any("No slides found" in i for i in report.issues)

    def test_missing_viewport_height(self, gate):
        html = """
        <style>.slide { overflow: hidden; scroll-snap-align: start; }</style>
        <section class="slide grid-2"><h1>Hi</h1></section>
        """
        report = gate.check(html)
        assert any("100vh" in i or "100dvh" in i for i in report.issues)

    def test_missing_scroll_snap(self, gate):
        html = """
        <style>.slide { height: 100vh; overflow: hidden; }</style>
        <section class="slide grid-2"><h1>Hi</h1></section>
        """
        report = gate.check(html)
        assert any("scroll-snap" in i for i in report.issues)

    def test_no_font_import_warning(self, gate):
        html = """
        <style>
        .slide { height: 100vh; overflow: hidden; scroll-snap-type: y mandatory; }
        h1 { font-size: clamp(1rem, 2vw, 2rem); }
        </style>
        <section class="slide grid-2"><h1>Hi</h1></section>
        """
        report = gate.check(html)
        assert any("font" in w.lower() for w in report.warnings)

    def test_score_deduction(self, gate):
        html = "<div>No slides</div>"
        report = gate.check(html)
        # "No slides found" is an issue => -15
        assert report.score <= 85


# --- QualityGate.check_single() tests ---

class TestCheckSingle:
    def test_valid_single_slide(self, gate):
        html = """
        <link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">
        <section class="slide" style="overflow: hidden; height: 100vh;">
            <h1 style="font-size: clamp(1.5rem, 3vw, 2.5rem);">Title</h1>
            <p>Some content</p>
        </section>
        """
        report = gate.check_single(html)
        assert report.passed
        assert report.score == 100

    def test_missing_overflow(self, gate):
        html = """
        <link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">
        <section class="slide" style="height: 100vh;">
            <h1>Title</h1>
        </section>
        """
        report = gate.check_single(html)
        assert not report.passed
        assert any("overflow" in i for i in report.issues)

    def test_too_many_bullets(self, gate):
        bullets = "\n".join(f"<li>Item {i}</li>" for i in range(10))
        html = f"""
        <link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">
        <section class="slide" style="overflow: hidden;">
            <h2>Title</h2>
            <ul>{bullets}</ul>
        </section>
        """
        report = gate.check_single(html)
        assert any("bullets" in i for i in report.issues)

    def test_missing_heading(self, gate):
        html = """
        <link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">
        <section class="slide" style="overflow: hidden;">
            <p>No heading here</p>
        </section>
        """
        report = gate.check_single(html)
        assert not report.passed
        assert any("heading" in i for i in report.issues)

    def test_no_font_import_warning(self, gate):
        html = """
        <section class="slide" style="overflow: hidden;">
            <h1>Title</h1>
        </section>
        """
        report = gate.check_single(html)
        assert any("font" in w.lower() for w in report.warnings)

    def test_fixed_font_sizes_warning(self, gate):
        html = """
        <link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">
        <section class="slide" style="overflow: hidden;">
            <h1 style="font-size: 32px;">Title</h1>
            <h2 style="font-size: 24px;">Sub</h2>
            <p style="font-size: 16px;">Text</p>
            <span style="font-size: 14px;">Small</span>
            <small style="font-size: 12px;">Tiny</small>
        </section>
        """
        report = gate.check_single(html)
        assert any("clamp" in w for w in report.warnings)

    def test_score_calculation(self, gate):
        # Missing overflow (issue: -15) + missing heading (issue: -15) + no font (warning: -5) + fixed sizes (warning: -5)
        html = """
        <section class="slide" style="height: 100vh;">
            <p style="font-size: 16px;">A</p>
            <p style="font-size: 14px;">B</p>
            <p style="font-size: 12px;">C</p>
            <p style="font-size: 10px;">D</p>
        </section>
        """
        report = gate.check_single(html)
        assert not report.passed
        # At least two issues: overflow + heading
        assert len(report.issues) >= 2
        assert report.score < 100
