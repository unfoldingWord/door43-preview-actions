"""Automate Door43 preview rendering and PDF export.

Usage example:

    python scripts/print_preview_pdf.py --repo en_ult --ref v86 --books gen exo --output-dir output

The script toggles the print preview, waits for Paged.js to finish rendering,
and then exports the page to an A4 PDF with zero margins.
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import logging
import re
import urllib.error
import urllib.request
from math import ceil
from pathlib import Path
from typing import Iterable, List, Tuple, Optional

from playwright.async_api import BrowserContext, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from weasyprint import HTML


LOGGER = logging.getLogger(__name__)


DEFAULT_BOOKS = ["gen", "exo", "lev", "num", "deu"]

BIBLE_BOOK_DATA = {
    "gen": {"title": "Genesis", "testament": "old", "verse_count": 1533, "number": 1},
    "exo": {"title": "Exodus", "testament": "old", "verse_count": 1213, "number": 2},
    "lev": {"title": "Leviticus", "testament": "old", "verse_count": 859, "number": 3},
    "num": {"title": "Numbers", "testament": "old", "verse_count": 1288, "number": 4},
    "deu": {"title": "Deuteronomy", "testament": "old", "verse_count": 959, "number": 5},
    "jos": {"title": "Joshua", "testament": "old", "verse_count": 658, "number": 6},
    "jdg": {"title": "Judges", "testament": "old", "verse_count": 618, "number": 7},
    "rut": {"title": "Ruth", "testament": "old", "verse_count": 85, "number": 8},
    "1sa": {"title": "1 Samuel", "testament": "old", "verse_count": 810, "number": 9},
    "2sa": {"title": "2 Samuel", "testament": "old", "verse_count": 695, "number": 10},
    "1ki": {"title": "1 Kings", "testament": "old", "verse_count": 816, "number": 11},
    "2ki": {"title": "2 Kings", "testament": "old", "verse_count": 719, "number": 12},
    "1ch": {"title": "1 Chronicles", "testament": "old", "verse_count": 942, "number": 13},
    "2ch": {"title": "2 Chronicles", "testament": "old", "verse_count": 822, "number": 14},
    "ezr": {"title": "Ezra", "testament": "old", "verse_count": 280, "number": 15},
    "neh": {"title": "Nehemiah", "testament": "old", "verse_count": 406, "number": 16},
    "est": {"title": "Esther", "testament": "old", "verse_count": 167, "number": 17},
    "job": {"title": "Job", "testament": "old", "verse_count": 1070, "number": 18},
    "psa": {"title": "Psalms", "testament": "old", "verse_count": 2461, "number": 19},
    "pro": {"title": "Proverbs", "testament": "old", "verse_count": 915, "number": 20},
    "ecc": {"title": "Ecclesiastes", "testament": "old", "verse_count": 222, "number": 21},
    "sng": {"title": "Song of Songs", "testament": "old", "verse_count": 117, "number": 22},
    "isa": {"title": "Isaiah", "testament": "old", "verse_count": 1292, "number": 23},
    "jer": {"title": "Jeremiah", "testament": "old", "verse_count": 1364, "number": 24},
    "lam": {"title": "Lamentations", "testament": "old", "verse_count": 154, "number": 25},
    "ezk": {"title": "Ezekiel", "testament": "old", "verse_count": 1273, "number": 26},
    "dan": {"title": "Daniel", "testament": "old", "verse_count": 357, "number": 27},
    "hos": {"title": "Hosea", "testament": "old", "verse_count": 197, "number": 28},
    "jol": {"title": "Joel", "testament": "old", "verse_count": 73, "number": 29},
    "amo": {"title": "Amos", "testament": "old", "verse_count": 146, "number": 30},
    "oba": {"title": "Obadiah", "testament": "old", "verse_count": 21, "number": 31},
    "jon": {"title": "Jonah", "testament": "old", "verse_count": 48, "number": 32},
    "mic": {"title": "Micah", "testament": "old", "verse_count": 105, "number": 33},
    "nam": {"title": "Nahum", "testament": "old", "verse_count": 47, "number": 34},
    "hab": {"title": "Habakkuk", "testament": "old", "verse_count": 56, "number": 35},
    "zep": {"title": "Zephaniah", "testament": "old", "verse_count": 53, "number": 36},
    "hag": {"title": "Haggai", "testament": "old", "verse_count": 38, "number": 37},
    "zec": {"title": "Zechariah", "testament": "old", "verse_count": 211, "number": 38},
    "mal": {"title": "Malachi", "testament": "old", "verse_count": 55, "number": 39},
    "mat": {"title": "Matthew", "testament": "new", "verse_count": 1071, "number": 41},
    "mrk": {"title": "Mark", "testament": "new", "verse_count": 678, "number": 42},
    "luk": {"title": "Luke", "testament": "new", "verse_count": 1151, "number": 43},
    "jhn": {"title": "John", "testament": "new", "verse_count": 879, "number": 44},
    "act": {"title": "Acts", "testament": "new", "verse_count": 1007, "number": 45},
    "rom": {"title": "Romans", "testament": "new", "verse_count": 433, "number": 46},
    "1co": {"title": "1 Corinthians", "testament": "new", "verse_count": 437, "number": 47},
    "2co": {"title": "2 Corinthians", "testament": "new", "verse_count": 257, "number": 48},
    "gal": {"title": "Galatians", "testament": "new", "verse_count": 149, "number": 49},
    "eph": {"title": "Ephesians", "testament": "new", "verse_count": 155, "number": 50},
    "php": {"title": "Philippians", "testament": "new", "verse_count": 104, "number": 51},
    "col": {"title": "Colossians", "testament": "new", "verse_count": 95, "number": 52},
    "1th": {"title": "1 Thessalonians", "testament": "new", "verse_count": 89, "number": 53},
    "2th": {"title": "2 Thessalonians", "testament": "new", "verse_count": 47, "number": 54},
    "1ti": {"title": "1 Timothy", "testament": "new", "verse_count": 113, "number": 55},
    "2ti": {"title": "2 Timothy", "testament": "new", "verse_count": 83, "number": 56},
    "tit": {"title": "Titus", "testament": "new", "verse_count": 46, "number": 57},
    "phm": {"title": "Philemon", "testament": "new", "verse_count": 25, "number": 58},
    "heb": {"title": "Hebrews", "testament": "new", "verse_count": 303, "number": 59},
    "jas": {"title": "James", "testament": "new", "verse_count": 108, "number": 60},
    "1pe": {"title": "1 Peter", "testament": "new", "verse_count": 105, "number": 61},
    "2pe": {"title": "2 Peter", "testament": "new", "verse_count": 61, "number": 62},
    "1jn": {"title": "1 John", "testament": "new", "verse_count": 105, "number": 63},
    "2jn": {"title": "2 John", "testament": "new", "verse_count": 13, "number": 64},
    "3jn": {"title": "3 John", "testament": "new", "verse_count": 15, "number": 65},
    "jud": {"title": "Jude", "testament": "new", "verse_count": 25, "number": 66},
    "rev": {"title": "Revelation", "testament": "new", "verse_count": 404, "number": 67},
}

OLD_TESTAMENT_CODES = tuple(code for code, meta in BIBLE_BOOK_DATA.items() if meta["testament"] == "old")
NEW_TESTAMENT_CODES = tuple(code for code, meta in BIBLE_BOOK_DATA.items() if meta["testament"] == "new")
ALL_BOOK_CODES = tuple(BIBLE_BOOK_DATA.keys())
PAGE_SIZE_CHOICES = ("A4", "LETTER")
PAGE_FORMAT_MAP = {"A4": "A4", "LETTER": "Letter"}
LETTER_SIZE_PATTERN = re.compile(r"(size:\s*)210mm\s+297mm;", re.IGNORECASE)
CATALOG_ENTRY_URL_TEMPLATE = "https://git.door43.org/api/v1/catalog/entry/{owner}/{repo}/{ref}"

PRINT_TOGGLE_SELECTOR = 'button[aria-label^="Print view"]'
PRINT_ICON_SELECTOR = 'button[aria-label^="Open print options"]'
DRAWER_PRINT_SELECTOR = 'button[aria-label="Print"]'
HTML_DOWNLOAD_BUTTON_SELECTOR = 'button[aria-label="Download the HTML for printing"]'


class RenderTimeoutError(RuntimeError):
    """Signal that the print preview never reached a ready state."""


class CatalogEntryNotFoundError(RuntimeError):
    """Signal that the owner/repo/ref combination has no catalog entry."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render Door43 preview pages in print mode and export them as PDFs "
            "using Playwright."
        )
    )
    parser.add_argument(
        "--books",
        nargs="+",
        default=DEFAULT_BOOKS,
        help="List of 3-letter book codes to export. Use 'all' for all available books, "
             "'ot' for Old Testament, 'nt' for New Testament. (default: %(default)s).",
    )
    parser.add_argument(
        "--base-url",
        default="https://preview.door43.org",
        help="Door43 preview base URL.",
    )
    parser.add_argument(
        "--owner",
        default="unfoldingWord",
        help="Owner/user segment in the preview URL (default: %(default)s).",
    )
    parser.add_argument(
        "--repo",
        help="Repository/resource slug in the preview URL (required unless --list-books).",
    )
    parser.add_argument(
        "--ref",
        default="master",
        help="Reference/branch identifier in the preview URL (default: %(default)s).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory where generated PDFs are written (default: %(default)s).",
    )
    parser.add_argument(
        "--render-timeout",
        type=int,
        default=600,
        help="Seconds to wait for print rendering before failing (default: %(default)s).",
    )
    parser.add_argument(
        "--render-timeout-per-verse",
        type=float,
        default=0.15,
        help="Additional seconds to add per verse when determining render timeout.",
    )
    parser.add_argument(
        "--navigation-timeout",
        type=int,
        default=90,
        help="Seconds to wait for initial navigation (default: %(default)s).",
    )
    parser.add_argument(
        "--navigation-timeout-per-verse",
        type=float,
        default=0.05,
        help="Additional seconds to add per verse when determining navigation timeout.",
    )
    parser.add_argument(
        "--sleep-after-ready",
        type=float,
        default=5.0,
        help="Extra seconds to wait after ready status for layout to stabilize.",
    )
    parser.add_argument(
        "--page",
        type=str,
        help="Page size to generate (A4 or Letter). Default: generate both sizes.",
    )
    parser.add_argument(
        "--headed",
        action="store_false",
        dest="headless",
        help="Run Chromium with a visible window for debugging.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging output.",
    )
    parser.add_argument(
        "--list-books",
        action="store_true",
        help="List available book codes grouped by testament and exit.",
    )
    parser.add_argument(
        "--backend",
        choices=["playwright", "weasyprint"],
        default="playwright",
        help="PDF rendering backend: 'playwright' uses Paged.js in browser (slower for large files), "
             "'weasyprint' renders server-side (much faster). (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download HTML and re-generate PDFs even if files already exist.",
    )

    parser.set_defaults(headless=True)
    args = parser.parse_args()

    if not args.list_books and not args.repo:
        parser.error("--repo is required unless --list-books is provided.")

    return args


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def resolve_page_sizes(selection: str | None) -> Tuple[str, ...]:
    if selection is None:
        return tuple(PAGE_SIZE_CHOICES)

    normalized = selection.strip().upper()
    if normalized not in PAGE_SIZE_CHOICES:
        raise ValueError(f"Unsupported page size '{selection}'. Choose from {', '.join(PAGE_SIZE_CHOICES)}.")
    return (normalized,)


def build_url(base_url: str, owner: str, repo: str, ref: str, book: str | None) -> str:
    if book is None:
        return f"{base_url}/u/{owner}/{repo}/{ref}/"
    return f"{base_url}/u/{owner}/{repo}/{ref}/?book={book}"


def build_output_prefix(owner: str, repo: str, ref: str, book: str | None) -> str:
    """Build filename prefix in format: <repo>_<book#>-<BOOK>_<ref>
    
    Example: en_tn_01-GEN_v87
    For bookless repos: en_ta_v87
    """
    if book is None:
        return f"{repo}_{ref}"
    
    book_lower = book.lower()
    book_data = BIBLE_BOOK_DATA.get(book_lower, {})
    book_number = book_data.get("number", 0)
    book_upper = book_lower.upper()
    
    return f"{repo}_{book_number:02d}-{book_upper}_{ref}"


def print_available_books() -> None:
    sections = (
        ("Old Testament", OLD_TESTAMENT_CODES),
        ("New Testament", NEW_TESTAMENT_CODES),
    )
    for heading, codes in sections:
        print(f"{heading}:")
        for code in codes:
            title = BIBLE_BOOK_DATA[code]["title"]
            print(f"  {code.upper():<4} {title}")


def expand_book_arguments(values: Iterable[str]) -> Optional[List[str]]:
    """Expand book arguments, supporting 'all', 'ot', and 'nt' shortcuts.
    
    Returns a list of book codes, or None if 'all' is specified (indicating
    that all available books from the catalog should be used).
    """
    requested: List[str] = []
    for value in values:
        token = value.strip().lower()
        if not token:
            continue
        if token == "all":
            # Return None to signal that all catalog books should be used
            return None
        elif token == "ot":
            requested.extend(OLD_TESTAMENT_CODES)
        elif token == "nt":
            requested.extend(NEW_TESTAMENT_CODES)
        else:
            if token not in BIBLE_BOOK_DATA:
                raise ValueError(f"Unknown book code '{value}'.")
            requested.append(token)

    deduped: List[str] = []
    seen = set()
    for code in requested:
        if code not in seen:
            deduped.append(code)
            seen.add(code)

    if not deduped:
        raise ValueError("No valid books specified.")

    return deduped


def compute_book_timeout(base_seconds: int, per_verse_seconds: float, verse_count: int) -> int:
    if verse_count <= 0 or per_verse_seconds <= 0:
        return base_seconds
    derived = base_seconds + verse_count * per_verse_seconds
    return max(base_seconds, int(ceil(derived)))


def fetch_available_books(owner: str, repo: str, ref: str) -> List[str]:
    """Return the ordered list of Bible books defined in the catalog entry."""
    url = CATALOG_ENTRY_URL_TEMPLATE.format(owner=owner, repo=repo, ref=ref)
    LOGGER.debug("Fetching catalog metadata from %s", url)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise CatalogEntryNotFoundError(
                f"Catalog entry not found for {owner}/{repo}@{ref}"
            ) from error
        raise RuntimeError(f"Failed to fetch catalog entry (HTTP {error.code})") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Failed to fetch catalog entry: {error}") from error

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError("Catalog entry response was not valid JSON") from error

    ingredients = data.get("ingredients", [])
    available: List[str] = []
    seen = set()
    for ingredient in ingredients:
        identifier = str(ingredient.get("identifier", "")).lower()
        if identifier in BIBLE_BOOK_DATA and identifier not in seen:
            available.append(identifier)
            seen.add(identifier)

    LOGGER.debug("Catalog provides %d Bible book(s)", len(available))
    return available


async def ensure_print_view(page: Page, timeout_ms: int) -> None:
    toggle = page.locator(PRINT_TOGGLE_SELECTOR)
    try:
        await toggle.wait_for(state="visible", timeout=timeout_ms)
        aria_pressed = await toggle.get_attribute("aria-pressed")
        if aria_pressed != "true":
            LOGGER.debug("Enabling print preview toggle")
            await toggle.click()
            await page.wait_for_function(
                "selector => document.querySelector(selector)?.getAttribute('aria-pressed') === 'true'",
                arg=PRINT_TOGGLE_SELECTOR,
                timeout=timeout_ms,
            )
        return
    except PlaywrightTimeoutError:
        LOGGER.debug("Print toggle not found via primary selector, trying fallbacks")

    # Fallbacks: the print UI can expose a direct download button or other
    # variations. Try to detect the download button or a drawer icon, or
    # finally wait for the main content to be present as a last resort.
    try:
        # If the download button is directly available, accept it
        await page.wait_for_selector(HTML_DOWNLOAD_BUTTON_SELECTOR, state="visible", timeout=timeout_ms / 3)
        LOGGER.debug("Found HTML download button without toggling print view")
        return
    except PlaywrightTimeoutError:
        LOGGER.debug("HTML download button not visible as fallback")

    try:
        # Try the print options icon (alternate UI path)
        await page.wait_for_selector(PRINT_ICON_SELECTOR, state="visible", timeout=timeout_ms / 3)
        LOGGER.debug("Found print options icon via fallback; clicking it")
        await page.locator(PRINT_ICON_SELECTOR).click()
        await page.wait_for_selector(HTML_DOWNLOAD_BUTTON_SELECTOR, state="visible", timeout=timeout_ms / 3)
        return
    except PlaywrightTimeoutError:
        LOGGER.debug("Print icon fallback also failed")

    # Last resort: wait for a main content indicator (pagedjs or book element)
    try:
        await page.wait_for_function(
            "() => document.querySelector('.pagedjs_pages') || document.querySelector('[data-book]') || document.querySelector('main')",
            timeout=timeout_ms / 3,
        )
        LOGGER.warning("Proceeding despite not seeing explicit print UI; main content detected")
        return
    except PlaywrightTimeoutError:
        LOGGER.error("Failed to find print UI or main content within timeout")
        raise


async def open_print_drawer(page: Page, timeout_ms: int) -> None:
    LOGGER.debug("Opening print options drawer")
    await page.wait_for_selector(PRINT_ICON_SELECTOR, state="visible", timeout=timeout_ms)
    await page.locator(PRINT_ICON_SELECTOR).click()
    await page.wait_for_selector(HTML_DOWNLOAD_BUTTON_SELECTOR, state="visible", timeout=timeout_ms)


async def download_printable_html(page: Page, timeout_ms: int, destination: Path) -> Path:
    LOGGER.info("Downloading printable HTML to %s", destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    await page.wait_for_selector(HTML_DOWNLOAD_BUTTON_SELECTOR, state="visible", timeout=timeout_ms)
    async with page.expect_download(timeout=timeout_ms) as download_info:
        await page.locator(HTML_DOWNLOAD_BUTTON_SELECTOR).click()
    download = await download_info.value
    await download.save_as(str(destination))
    return destination


def create_letter_variant(source_html: Path, destination_html: Path) -> Path:
    LOGGER.debug("Creating Letter-sized HTML %s", destination_html)
    destination_html.parent.mkdir(parents=True, exist_ok=True)
    content = source_html.read_text(encoding="utf-8")
    updated, replacements = LETTER_SIZE_PATTERN.subn(r"\1letter;", content, count=1)
    if replacements == 0:
        LOGGER.warning(
            "Could not find A4 size declaration in %s; writing unmodified content for Letter variant",
            source_html,
        )
        updated = content
    destination_html.write_text(updated, encoding="utf-8")
    return destination_html


async def export_pdf(page: Page, destination: Path, page_size: str) -> None:
    LOGGER.info("Writing %s PDF to %s", page_size, destination)
    await page.emulate_media(media="print")
    await page.pdf(
        path=str(destination),
        format=PAGE_FORMAT_MAP[page_size],
        print_background=True,
        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        prefer_css_page_size=True,
    )


def render_html_to_pdf_weasyprint(
    html_path: Path,
    destination: Path,
    page_size: str,
) -> None:
    """Render HTML to PDF using WeasyPrint (synchronous server-side rendering).
    
    This is significantly faster than waiting for Paged.js in the browser,
    especially for large documents (11MB+).
    
    Args:
        html_path: Path to the HTML file to render
        destination: Path where the PDF should be written
        page_size: Page size format ("A4" or "LETTER")
    """
    LOGGER.info("Writing %s PDF to %s using WeasyPrint", page_size, destination)
    
    # Map page size to WeasyPrint format
    page_format = PAGE_FORMAT_MAP[page_size]  # "A4" or "Letter"
    
    try:
        # Read HTML content as UTF-8
        html_content = html_path.read_text(encoding='utf-8')
        # Use base_url to resolve relative paths in the HTML (for images, CSS, etc.)
        # Must use resolve() to convert relative path to absolute path before as_uri()
        html_doc = HTML(string=html_content, base_url=html_path.resolve().parent.as_uri() + '/')
        html_doc.write_pdf(
            str(destination),
            page_size=page_format,
        )
        LOGGER.debug("Successfully rendered %s PDF", page_size)
        
        # Explicitly clean up to free memory
        del html_doc
        del html_content
        gc.collect()
        
    except Exception as e:
        LOGGER.error("Failed to render PDF with WeasyPrint: %s", e)
        raise


async def render_html_to_pdf(
    context: BrowserContext,
    html_path: Path,
    destination: Path,
    page_size: str,
    render_timeout_ms: int,
    sleep_after_ready: float,
    backend: str = "playwright",
) -> None:
    """Render HTML to PDF using the specified backend.
    
    Args:
        context: Playwright browser context
        html_path: Path to the HTML file to render
        destination: Path where the PDF should be written
        page_size: Page size format ("A4" or "LETTER")
        render_timeout_ms: Timeout in milliseconds for rendering
        sleep_after_ready: Extra seconds to wait after Paged.js is ready
        backend: Rendering backend ("playwright" for Paged.js or "weasyprint" for direct HTML->PDF)
    """
    if backend == "weasyprint":
        # Use WeasyPrint for fast server-side rendering
        render_html_to_pdf_weasyprint(html_path, destination, page_size)
    else:
        # Use Playwright with Paged.js for browser-based rendering
        render_page = await context.new_page()
        try:
            LOGGER.debug("Loading downloaded HTML %s", html_path)
            await render_page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=render_timeout_ms)
            LOGGER.debug("Waiting for Paged.js to finish layout")
            await render_page.wait_for_function(
                """
                () => {
                    const pages = document.querySelectorAll('.pagedjs_pages .pagedjs_page');
                    if (!pages.length) {
                        window.__PAGED_LAST_COUNT = 0;
                        window.__PAGED_LAST_CHANGE = Date.now();
                        return false;
                    }

                    if (window.__PAGED_LAST_COUNT !== pages.length) {
                        window.__PAGED_LAST_COUNT = pages.length;
                        window.__PAGED_LAST_CHANGE = Date.now();
                        return false;
                    }

                    return Date.now() - (window.__PAGED_LAST_CHANGE || 0) > 1000;
                }
                """,
                timeout=render_timeout_ms,
            )
            if sleep_after_ready:
                LOGGER.debug("Waiting %.1f seconds after Paged.js render", sleep_after_ready)
                await render_page.wait_for_timeout(int(sleep_after_ready * 1000))
            await export_pdf(render_page, destination, page_size)
        finally:
            await render_page.close()



async def generate_pdf_for_book(
    context: BrowserContext,
    owner: str,
    repo: str,
    ref: str,
    book: str | None,
    url: str,
    output_dir: Path,
    page_sizes: Tuple[str, ...],
    navigation_timeout_ms: int,
    render_timeout_ms: int,
    sleep_after_ready: float,
    backend: str = "playwright",
    force: bool = False,
) -> None:
    prefix = build_output_prefix(owner, repo, ref, book)
    html_a4_path = output_dir / f"{prefix}_A4.html"
    
    # Check if HTML already exists
    if html_a4_path.exists() and not force:
        LOGGER.info("HTML already exists: %s (skipping download)", html_a4_path.name)
    else:
        page = await context.new_page()
        
        # Add network logging for debugging
        async def log_request(request):
            LOGGER.debug("→ REQUEST: %s %s", request.method, request.url)
        
        async def log_response(response):
            LOGGER.debug("← RESPONSE: %s %s -> %d", response.request.method, response.url, response.status)
        
        page.on("request", log_request)
        page.on("response", log_response)
        
        try:
            page.set_default_timeout(render_timeout_ms)
            LOGGER.info("Navigating to %s", url)
            await page.goto(url, wait_until="networkidle", timeout=navigation_timeout_ms)

            await ensure_print_view(page, render_timeout_ms)
            await open_print_drawer(page, render_timeout_ms)
            await download_printable_html(page, render_timeout_ms, html_a4_path)
        finally:
            page.remove_listener("request", log_request)
            page.remove_listener("response", log_response)
            await page.close()

    html_variants = {"A4": html_a4_path}
    if "LETTER" in page_sizes:
        letter_html_path = output_dir / f"{prefix}_LETTER.html"
        if letter_html_path.exists() and not force:
            LOGGER.info("LETTER HTML already exists: %s (skipping creation)", letter_html_path.name)
            html_variants["LETTER"] = letter_html_path
        else:
            html_variants["LETTER"] = create_letter_variant(
                source_html=html_a4_path,
                destination_html=letter_html_path,
            )

    for page_size in page_sizes:
        html_path = html_variants.get(page_size)
        if html_path is None:
            continue
        
        pdf_destination = output_dir / f"{prefix}_{page_size}.pdf"
        
        # Check if PDF already exists
        if pdf_destination.exists() and not force:
            LOGGER.info("PDF already exists: %s (skipping generation)", pdf_destination.name)
            continue
        
        await render_html_to_pdf(
            context=context,
            html_path=html_path,
            destination=pdf_destination,
            page_size=page_size,
            render_timeout_ms=render_timeout_ms,
            sleep_after_ready=sleep_after_ready,
            backend=backend,
        )


async def run_export(
    books: Iterable[str],
    base_url: str,
    owner: str,
    repo: str,
    ref: str,
    output_dir: Path,
    headless: bool,
    navigation_timeout: int,
    render_timeout: int,
    navigation_timeout_per_verse: float,
    render_timeout_per_verse: float,
    sleep_after_ready: float,
    page_sizes: Tuple[str, ...],
    backend: str = "playwright",
    force: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    failed_books = []
    successful_books = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context(accept_downloads=True)

        try:
            for raw_book in books:
                # Handle None for bookless repos
                book = raw_book.lower() if raw_book is not None else None
                url = build_url(base_url, owner, repo, ref, book)
                
                if book is None:
                    # For bookless repos, use default timeouts
                    verse_count = 0
                    book_navigation_timeout = navigation_timeout
                    book_render_timeout = render_timeout
                    display_name = repo.upper()
                else:
                    verse_count = BIBLE_BOOK_DATA.get(book, {}).get("verse_count", 0)
                    book_navigation_timeout = compute_book_timeout(
                        navigation_timeout, navigation_timeout_per_verse, verse_count
                    )
                    book_render_timeout = compute_book_timeout(
                        render_timeout, render_timeout_per_verse, verse_count
                    )
                    display_name = book.upper()
                
                LOGGER.debug(
                    "Timeouts for %s: navigation=%ss render=%ss",
                    display_name,
                    book_navigation_timeout,
                    book_render_timeout,
                )

                try:
                    await generate_pdf_for_book(
                        context=context,
                        owner=owner,
                        repo=repo,
                        ref=ref,
                        book=book,
                        url=url,
                        output_dir=output_dir,
                        page_sizes=page_sizes,
                        navigation_timeout_ms=book_navigation_timeout * 1000,
                        render_timeout_ms=book_render_timeout * 1000,
                        sleep_after_ready=sleep_after_ready,
                        backend=backend,
                        force=force,
                    )
                    LOGGER.info("Successfully completed %s", display_name)
                    successful_books.append(display_name)
                    
                    # Force garbage collection after each book to free memory
                    gc.collect()
                    
                except PlaywrightTimeoutError as exc:
                    display_name = repo.upper() if book is None else book.upper()
                    LOGGER.error(
                        "Timed out while preparing print preview for %s: %s",
                        display_name,
                        exc,
                    )
                    LOGGER.warning("Skipping %s and continuing with next book", display_name)
                    failed_books.append((display_name, "Timeout"))
                except Exception as exc:
                    display_name = repo.upper() if book is None else book.upper()
                    LOGGER.error(
                        "Failed to generate PDF for %s: %s",
                        display_name,
                        exc,
                    )
                    LOGGER.warning("Skipping %s and continuing with next book", display_name)
                    failed_books.append((display_name, str(exc)))

        finally:
            await context.close()
            await browser.close()
    
    # Print summary
    LOGGER.info("=" * 60)
    LOGGER.info("EXPORT SUMMARY")
    LOGGER.info("=" * 60)
    LOGGER.info("Successfully generated: %d book(s)", len(successful_books))
    if successful_books:
        LOGGER.info("  %s", ", ".join(successful_books))
    
    if failed_books:
        LOGGER.warning("Failed to generate: %d book(s)", len(failed_books))
        for book_code, reason in failed_books:
            LOGGER.warning("  %s: %s", book_code, reason[:80])
    LOGGER.info("=" * 60)


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    if args.list_books:
        print_available_books()
        return 0

    try:
        page_sizes = resolve_page_sizes(args.page)
    except ValueError as error:
        LOGGER.error("%s", error)
        return 1

    try:
        book_list = expand_book_arguments(args.books)
    except ValueError as error:
        LOGGER.error("%s", error)
        return 1

    try:
        available_books = fetch_available_books(args.owner, args.repo, args.ref)
    except CatalogEntryNotFoundError as error:
        LOGGER.error("%s", error)
        return 1
    except RuntimeError as error:
        LOGGER.error("%s", error)
        return 1

    # Handle bookless repos (e.g., en_ta, en_tw)
    if not available_books:
        LOGGER.info("Repo has no books - treating as single-page resource")
        selected_books = [None]  # Use None to represent the entire repo
        missing_books = []
    # If book_list is None, it means 'all' was specified - use all available books
    elif book_list is None:
        selected_books = available_books
        missing_books = []
    else:
        available_set = set(available_books)
        selected_books = [book for book in book_list if book in available_set]
        missing_books = [book for book in book_list if book not in available_set]

    if missing_books:
        LOGGER.warning(
            "Skipping %d unavailable book(s): %s",
            len(missing_books),
            ", ".join(code.upper() for code in missing_books),
        )

    if not selected_books:
        LOGGER.error(
            "None of the requested books are available in catalog entry %s/%s@%s",
            args.owner,
            args.repo,
            args.ref,
        )
        return 1

    LOGGER.info(
        "Starting export for %d book(s) with page size(s): %s",
        len(selected_books),
        ", ".join(page_sizes),
    )

    try:
        asyncio.run(
            run_export(
                books=selected_books,
                base_url=args.base_url,
                owner=args.owner,
                repo=args.repo,
                ref=args.ref,
                output_dir=args.output_dir,
                headless=args.headless,
                navigation_timeout=args.navigation_timeout,
                render_timeout=args.render_timeout,
                navigation_timeout_per_verse=args.navigation_timeout_per_verse,
                render_timeout_per_verse=args.render_timeout_per_verse,
                sleep_after_ready=args.sleep_after_ready,
                page_sizes=page_sizes,
                backend=args.backend,
                force=args.force,
            )
        )
    except RenderTimeoutError as error:
        LOGGER.error("%s", error)
        return 1

    LOGGER.info("Export completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
