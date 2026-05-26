"""PDF export utility using Playwright to render presentation HTML."""

import re


async def html_to_pdf(html: str) -> bytes:
    """Convert presentation HTML to PDF using Playwright.

    Renders each slide individually in a headless Chromium browser
    and combines them into a multi-page PDF with 16:9 aspect ratio.
    """
    from playwright.async_api import async_playwright
    from pypdf import PdfWriter, PdfReader
    import io

    # Remove opacity:0 rule for non-active slides
    html = re.sub(r'\.slide-wrapper:not\(\.active\)\s*section\s*>\s*\*\s*\{[^}]*\}', '', html)
    html = html.replace('class="slide-wrapper"', 'class="slide-wrapper active"')

    # Extract individual slide <section> blocks (each slide is one <section>...</section>)
    sections = re.findall(r'<section[^>]*>.*?</section>', html, re.DOTALL)

    if not sections:
        # Fallback: render the whole page as single PDF
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await p.chromium.new_page(viewport={"width": 1920, "height": 1080})
            await page.set_content(html, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            pdf_bytes = await page.pdf(width="1920px", height="1080px", print_background=True)
            await browser.close()
            return pdf_bytes

    # Extract <head> content (styles, fonts) from the full HTML
    head_match = re.search(r'<head[^>]*>(.*?)</head>', html, re.DOTALL)
    head_content = head_match.group(1) if head_match else ""

    # Also extract any inline <style> blocks from outside <head>
    all_styles = re.findall(r'<style[^>]*>.*?</style>', html, re.DOTALL)
    extra_styles = "\n".join(all_styles)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        writer = PdfWriter()

        for section_html in sections:
            single_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">{head_content}{extra_styles}
<style>
html, body {{ margin: 0; padding: 0; width: 1920px; height: 1080px; overflow: hidden; }}
.slide-wrapper {{ width: 1920px; height: 1080px; overflow: hidden; }}
section {{ width: 1920px; height: 1080px; overflow: hidden; }}
section > * {{ opacity: 1 !important; animation: none !important; }}
</style>
</head><body>{section_html}</body></html>"""

            page = await browser.new_page(viewport={"width": 1920, "height": 1080})
            await page.set_content(single_html, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)

            page_pdf = await page.pdf(
                width="1920px",
                height="1080px",
                print_background=True,
            )
            await page.close()

            reader = PdfReader(io.BytesIO(page_pdf))
            for pdf_page in reader.pages:
                writer.add_page(pdf_page)

        await browser.close()

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()
