"""PPTX export utility — creates editable PowerPoint slides from HTML content."""

import io
import re
from html import unescape
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR


ASPECT_RATIOS = {
    "16:9": (13.333, 7.5),
    "4:3": (10.0, 7.5),
    "16:10": (13.333, 8.333),
    "1:1": (7.5, 7.5),
}


def _strip_tags(html: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'<[^>]+>', '', text)
    return unescape(text).strip()


def _extract_color(style: str, prop: str = "color") -> str | None:
    """Extract a color value from inline style string."""
    match = re.search(rf'{prop}\s*:\s*(#[0-9a-fA-F]{{3,6}}|rgb[a]?\([^)]+\))', style)
    if match:
        color = match.group(1)
        if color.startswith('#'):
            c = color[1:]
            if len(c) == 3:
                c = c[0]*2 + c[1]*2 + c[2]*2
            return c
        # Parse rgb(r,g,b)
        nums = re.findall(r'\d+', color)
        if len(nums) >= 3:
            return f"{int(nums[0]):02x}{int(nums[1]):02x}{int(nums[2]):02x}"
    return None


def _extract_bg_color(section_html: str) -> str | None:
    """Extract background color from section's inline style."""
    style_match = re.search(r'<section[^>]*style="([^"]*)"', section_html)
    if style_match:
        style = style_match.group(1)
        # Check background or background-color
        bg = _extract_color(style, "background-color") or _extract_color(style, "background")
        return bg
    return None


def _parse_slide_content(html: str) -> dict:
    """Extract structured content from a single slide's HTML."""
    result = {
        "title": "",
        "subtitle": "",
        "bullets": [],
        "bg_color": _extract_bg_color(html),
        "text_color": None,
    }

    # Extract title (h1, h2, h3)
    title_match = re.search(r'<h[1-3][^>]*(?:style="([^"]*)")?[^>]*>(.*?)</h[1-3]>', html, re.DOTALL)
    if title_match:
        result["title"] = _strip_tags(title_match.group(2))
        if title_match.group(1):
            result["text_color"] = _extract_color(title_match.group(1))

    # Extract subtitle (h4, h5, h6 or first p after heading)
    sub_match = re.search(r'<h[4-6][^>]*>(.*?)</h[4-6]>', html, re.DOTALL)
    if sub_match:
        result["subtitle"] = _strip_tags(sub_match.group(1))
    elif not sub_match:
        # First <p> that's relatively short
        p_matches = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        for pm in p_matches[:1]:
            text = _strip_tags(pm)
            if len(text) < 100:
                result["subtitle"] = text
                break

    # Extract bullet points from <li> elements
    li_matches = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)
    for li in li_matches:
        text = _strip_tags(li)
        if text:
            result["bullets"].append(text)

    # If no bullets, extract <p> content as bullets
    if not result["bullets"]:
        p_matches = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        for pm in p_matches:
            text = _strip_tags(pm)
            if text and text != result["subtitle"] and len(text) > 5:
                result["bullets"].append(text)

    return result


async def html_to_pptx(full_html: str, aspect_ratio: str = "16:9") -> bytes:
    """Convert presentation HTML to an editable PPTX by extracting text content."""

    width_inches, height_inches = ASPECT_RATIOS.get(aspect_ratio, (13.333, 7.5))

    prs = Presentation()
    prs.slide_width = Inches(width_inches)
    prs.slide_height = Inches(height_inches)

    # Split HTML into individual slide sections
    sections = re.findall(r'<section[^>]*>.*?</section>', full_html, re.DOTALL)

    if not sections:
        # Fallback: try slide-wrapper divs
        sections = re.findall(r'<div[^>]*class="slide-wrapper[^"]*"[^>]*>(.*?)</div>\s*(?=<div|</div>)', full_html, re.DOTALL)

    for section_html in sections:
        content = _parse_slide_content(section_html)
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)

        # Set background color
        bg_color = content["bg_color"]
        if bg_color:
            background = slide.background
            fill = background.fill
            fill.solid()
            try:
                fill.fore_color.rgb = RGBColor.from_string(bg_color)
            except Exception:
                pass

        # Title text box
        if content["title"]:
            left = Inches(0.8)
            top = Inches(0.8)
            width = Inches(width_inches - 1.6)
            height = Inches(1.5)
            txBox = slide.shapes.add_textbox(left, top, width, height)
            tf = txBox.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = content["title"]
            p.font.size = Pt(36)
            p.font.bold = True
            if content["text_color"]:
                try:
                    p.font.color.rgb = RGBColor.from_string(content["text_color"])
                except Exception:
                    pass
            elif bg_color and _is_dark(bg_color):
                p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        # Subtitle
        if content["subtitle"]:
            left = Inches(0.8)
            top = Inches(2.2)
            width = Inches(width_inches - 1.6)
            height = Inches(0.8)
            txBox = slide.shapes.add_textbox(left, top, width, height)
            tf = txBox.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = content["subtitle"]
            p.font.size = Pt(18)
            p.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
            if bg_color and _is_dark(bg_color):
                p.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)

        # Bullet points
        if content["bullets"]:
            left = Inches(0.8)
            top = Inches(3.0) if content["subtitle"] else Inches(2.5)
            width = Inches(width_inches - 1.6)
            height = Inches(height_inches - top / 914400 * Inches(1) - Inches(0.5))
            txBox = slide.shapes.add_textbox(left, top, width, Inches(4.5))
            tf = txBox.text_frame
            tf.word_wrap = True

            for i, bullet in enumerate(content["bullets"][:8]):
                if i == 0:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                p.text = f"• {bullet}"
                p.font.size = Pt(16)
                p.space_after = Pt(8)
                if bg_color and _is_dark(bg_color):
                    p.font.color.rgb = RGBColor(0xEE, 0xEE, 0xEE)

    output = io.BytesIO()
    prs.save(output)
    return output.getvalue()


def _is_dark(hex_color: str) -> bool:
    """Check if a hex color is dark (for deciding text color)."""
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance < 0.5
    except Exception:
        return False
