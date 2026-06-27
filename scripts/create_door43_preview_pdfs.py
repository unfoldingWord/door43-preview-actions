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
import os
import re
import urllib.error
import urllib.request
from math import ceil
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Optional

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
PAGEDJS_CONTAINER_PATTERN = re.compile(r'<div[^>]*id=["\']pagedjs-print["\'][^>]*>', re.IGNORECASE)


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
        default=None,
        help="List of 3-letter book codes to export. Use 'all' for all available books, "
             "'ot' for Old Testament, 'nt' for New Testament. "
             "If not specified, all books from the catalog will be processed.",
    )
    parser.add_argument(
        "--base-url",
        default="https://preview.door43.org",
        help="Door43 preview base URL.",
    )
    parser.add_argument(
        "--server",
        default=None,
        help="Value for the preview app's '?server=' query param (e.g. 'prod'). "
             "Use when rendering via develop-preview.door43.org against production DCS data.",
    )
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="Bypass any HTTP(S) proxy for this process only (clears *_PROXY env for the "
             "Python+Chromium subprocess and forces Chromium '--no-proxy-server'). Use when "
             "door43 is reachable directly but a system/VPN proxy is slow or flaky; your other "
             "processes (and their VPN) are unaffected.",
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
    parser.add_argument(
        "--html-only",
        action="store_true",
        help="Download HTML files only without generating PDFs. Useful for offline PDF generation later.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate one combined PDF for all selected books. In this mode, book HTML files are downloaded first, "
             "then merged into a single all-books HTML/PDF.",
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


def build_url(base_url: str, owner: str, repo: str, ref: str, book: str | None, server: str | None = None) -> str:
    suffix = f"&server={server}" if server else ""
    if book is None:
        return f"{base_url}/u/{owner}/{repo}/{ref}/?rerender=1{suffix}"
    return f"{base_url}/u/{owner}/{repo}/{ref}/?rerender=1&book={book}{suffix}"


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


def sort_books_canonical(books: Iterable[str]) -> List[str]:
    deduped: List[str] = []
    seen = set()
    for raw_code in books:
        code = raw_code.lower()
        if code in seen:
            continue
        deduped.append(code)
        seen.add(code)

    return sorted(
        deduped,
        key=lambda code: (
            BIBLE_BOOK_DATA.get(code, {}).get("number", 999),
            code,
        ),
    )


def find_matching_tag_end(document: str, tag_start: int, tag_name: str) -> int:
    lower_document = document.lower()
    lower_tag_name = tag_name.lower()
    open_tag_end = lower_document.find(">", tag_start)
    if open_tag_end == -1:
        raise ValueError(f"Malformed <{tag_name}> tag starting at index {tag_start}")

    open_pattern = f"<{lower_tag_name}"
    close_pattern = f"</{lower_tag_name}>"

    cursor = open_tag_end + 1
    depth = 1
    while depth > 0:
        next_open = lower_document.find(open_pattern, cursor)
        next_close = lower_document.find(close_pattern, cursor)

        if next_close == -1:
            raise ValueError(f"Missing closing tag </{tag_name}>")

        if next_open != -1 and next_open < next_close:
            depth += 1
            cursor = next_open + len(open_pattern)
            continue

        depth -= 1
        cursor = next_close + len(close_pattern)

    return cursor


def split_top_level_divs(container_content: str) -> List[str]:
    blocks: List[str] = []
    lower_content = container_content.lower()
    cursor = 0

    while True:
        next_open = lower_content.find("<div", cursor)
        if next_open == -1:
            break

        block_end = find_matching_tag_end(container_content, next_open, "div")
        blocks.append(container_content[next_open:block_end])
        cursor = block_end

    return blocks


def extract_pagedjs_sections(html_content: str) -> Tuple[str, str, List[str], str]:
    container_match = PAGEDJS_CONTAINER_PATTERN.search(html_content)
    if container_match is None:
        raise ValueError("Could not locate pagedjs-print container in HTML")

    container_start = container_match.start()
    container_open_tag = container_match.group(0)
    container_end = find_matching_tag_end(html_content, container_start, "div")
    container_inner = html_content[container_match.end():container_end - len("</div>")]
    sections = split_top_level_divs(container_inner)

    return (
        html_content[:container_start],
        container_open_tag,
        sections,
        html_content[container_end:],
    )


def find_cover_section(sections: Iterable[str]) -> Optional[str]:
    for section in sections:
        if "cover-page" in section:
            return section
    return None


def find_copyright_section(sections: Iterable[str]) -> Optional[str]:
    for section in sections:
        if 'id="copyright-page"' in section or "id='copyright-page'" in section:
            return section
    return None


def find_book_section(sections: Iterable[str], book_code: str) -> Optional[str]:
    pattern = re.compile(rf'id=["\']nav-{re.escape(book_code.lower())}["\']', re.IGNORECASE)
    for section in sections:
        if pattern.search(section):
            return section
    return None


def remove_book_name_from_cover(cover_section: str, book_title: str) -> str:
    if not book_title:
        return cover_section

    updated = re.sub(
        rf"\s*<h[1-6](?![^>]*cover-version)[^>]*>\s*{re.escape(book_title)}\s*</h[1-6]>\s*",
        "\n",
        cover_section,
        count=1,
        flags=re.IGNORECASE,
    )
    updated = re.sub(
        rf"(<h[1-6][^>]*>[^<]*?)\s*-\s*{re.escape(book_title)}(\s*</h[1-6]>)",
        r"\1\2",
        updated,
        count=1,
        flags=re.IGNORECASE,
    )
    return updated


def build_all_books_toc_section(book_codes: Iterable[str]) -> str:
    entries: List[str] = []
    for code in book_codes:
        title = BIBLE_BOOK_DATA.get(code, {}).get("title", code.upper())
        entries.append(
            "\n".join(
                [
                    '<li class="toc-entry">',
                    f'  <a class="toc-element" href="#nav-{code}"><span class="toc-element-title">{title}</span></a>',
                    "</li>",
                ]
            )
        )

    toc_items = "\n".join(entries)
    return (
        '<div class="section toc-page">\n'
        '  <h1 class="header toc-header">Table of Contents</h1>\n'
        '  <div id="toc-contents">\n'
        '    <ul class="toc-section top-toc-section">\n'
        f"{toc_items}\n"
        "    </ul>\n"
        "  </div>\n"
        "</div>"
    )


def build_all_books_output_prefix(repo: str, ref: str) -> str:
    return f"{repo}_ALL_{ref}"


def build_all_books_html(
    repo: str,
    ref: str,
    ordered_books: Iterable[str],
    book_html_paths: Dict[str, Path],
) -> str:
    ordered = [book.lower() for book in ordered_books]
    if not ordered:
        raise ValueError("No books were provided for all-books HTML generation")

    missing = [book for book in ordered if book not in book_html_paths]
    if missing:
        raise ValueError(
            f"Missing HTML files for {len(missing)} book(s): {', '.join(book.upper() for book in missing)}"
        )

    first_book = ordered[0]
    first_html = book_html_paths[first_book].read_text(encoding="utf-8")
    prefix, container_open_tag, first_sections, suffix = extract_pagedjs_sections(first_html)

    cover_section = find_cover_section(first_sections)
    if cover_section is None:
        raise ValueError(f"Could not locate cover page in {book_html_paths[first_book]}")

    cover_section = remove_book_name_from_cover(
        cover_section,
        BIBLE_BOOK_DATA.get(first_book, {}).get("title", ""),
    )

    copyright_section = find_copyright_section(first_sections)
    if copyright_section is None:
        raise ValueError(f"Could not locate copyright page in {book_html_paths[first_book]}")

    merged_sections: List[str] = [
        cover_section,
        copyright_section,
        build_all_books_toc_section(ordered),
    ]

    for book in ordered:
        html_content = book_html_paths[book].read_text(encoding="utf-8")
        _, _, sections, _ = extract_pagedjs_sections(html_content)
        book_section = find_book_section(sections, book)
        if book_section is None:
            raise ValueError(f"Could not locate nav-{book} section in {book_html_paths[book]}")
        merged_sections.append(book_section)

    merged_content = "\n".join(merged_sections)
    merged_html = f"{prefix}{container_open_tag}\n{merged_content}\n</div>{suffix}"
    merged_title = f"{repo} {ref} - All Books"

    return re.sub(
        r"<title>.*?</title>",
        f"<title>{merged_title}</title>",
        merged_html,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )


async def ensure_print_view(page: Page, timeout_ms: int) -> None:
    LOGGER.debug("Looking for print toggle button...")
    toggle = page.locator(PRINT_TOGGLE_SELECTOR)
    try:
        await toggle.wait_for(state="visible", timeout=timeout_ms)
        aria_pressed = await toggle.get_attribute("aria-pressed")
        LOGGER.debug(f"Print toggle found, aria-pressed={aria_pressed}")
        if aria_pressed != "true":
            LOGGER.debug("Enabling print preview toggle")
            await toggle.click()
            await page.wait_for_function(
                "selector => document.querySelector(selector)?.getAttribute('aria-pressed') === 'true'",
                arg=PRINT_TOGGLE_SELECTOR,
                timeout=timeout_ms,
            )
        LOGGER.debug("Print view enabled successfully")
        return
    except PlaywrightTimeoutError:
        LOGGER.debug("Print toggle not found via primary selector, trying fallbacks")

    # Fallbacks: the print UI can expose a direct download button or other
    # variations. Try to detect the download button or a drawer icon, or
    # finally wait for the main content to be present as a last resort.
    try:
        # If the download button is directly available, accept it
        LOGGER.debug(f"Looking for HTML download button: {HTML_DOWNLOAD_BUTTON_SELECTOR}")
        await page.wait_for_selector(HTML_DOWNLOAD_BUTTON_SELECTOR, state="visible", timeout=timeout_ms / 3)
        LOGGER.debug("Found HTML download button without toggling print view")
        return
    except PlaywrightTimeoutError:
        LOGGER.debug("HTML download button not visible as fallback")

    try:
        # Try the print options icon (alternate UI path)
        LOGGER.debug(f"Looking for print options icon: {PRINT_ICON_SELECTOR}")
        await page.wait_for_selector(PRINT_ICON_SELECTOR, state="visible", timeout=timeout_ms / 3)
        LOGGER.debug("Found print options icon via fallback; clicking it")
        await page.locator(PRINT_ICON_SELECTOR).click()
        await page.wait_for_selector(HTML_DOWNLOAD_BUTTON_SELECTOR, state="visible", timeout=timeout_ms / 3)
        LOGGER.debug("Print drawer opened successfully")
        return
    except PlaywrightTimeoutError:
        LOGGER.debug("Print icon fallback also failed")

    # Last resort: wait for a main content indicator (pagedjs or book element)
    try:
        LOGGER.debug("Trying last resort: looking for main content...")
        await page.wait_for_function(
            "() => document.querySelector('.pagedjs_pages') || document.querySelector('[data-book]') || document.querySelector('main')",
            timeout=timeout_ms / 3,
        )
        LOGGER.info("Main content detected - proceeding without print UI")
        
        # List what we can see on the page for debugging
        if LOGGER.level == logging.DEBUG:
            buttons = await page.query_selector_all('button')
            LOGGER.debug(f"Found {len(buttons)} button elements on page")
            for i, button in enumerate(buttons[:5]):
                aria_label = await button.get_attribute('aria-label')
                text = await button.inner_text()
                LOGGER.debug(f"  Button {i+1}: aria-label='{aria_label}', text='{text[:50]}'")
        
        return
    except PlaywrightTimeoutError:
        LOGGER.warning("Could not find print UI or main content")
        LOGGER.warning("Will attempt to extract HTML directly from current page state")
        # Don't raise - let download_printable_html try to extract from DOM
        return


async def open_print_drawer(page: Page, timeout_ms: int) -> None:
    """Try to open print drawer, but don't fail if not available."""
    LOGGER.debug("Attempting to open print options drawer")
    try:
        await page.wait_for_selector(PRINT_ICON_SELECTOR, state="visible", timeout=min(timeout_ms, 5000))
        LOGGER.debug(f"Found print icon: {PRINT_ICON_SELECTOR}")
        await page.locator(PRINT_ICON_SELECTOR).click()
        await page.wait_for_selector(HTML_DOWNLOAD_BUTTON_SELECTOR, state="visible", timeout=min(timeout_ms, 5000))
        LOGGER.debug("Print drawer opened and download button visible")
    except PlaywrightTimeoutError:
        LOGGER.warning(f"Could not open print drawer - this is OK, will extract HTML directly from DOM")
    except Exception as e:
        LOGGER.warning(f"Error opening print drawer: {e} - will extract HTML directly from DOM")


async def download_printable_html(page: Page, timeout_ms: int, destination: Path) -> Path:
    LOGGER.info("Downloading printable HTML to %s", destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    # Try the normal download button flow first
    try:
        await page.wait_for_selector(HTML_DOWNLOAD_BUTTON_SELECTOR, state="visible", timeout=timeout_ms)
        async with page.expect_download(timeout=timeout_ms) as download_info:
            await page.locator(HTML_DOWNLOAD_BUTTON_SELECTOR).click()
        download = await download_info.value
        await download.save_as(str(destination))
        LOGGER.info("HTML downloaded successfully via download button")
        return destination
    except PlaywrightTimeoutError:
        LOGGER.warning("Download button method failed, trying direct HTML extraction...")
    except Exception as e:
        LOGGER.warning(f"Download button method failed ({e}), trying direct HTML extraction...")
    
    # Fallback: Extract HTML directly from the page DOM
    # This works even if the server-side caching POST fails
    try:
        LOGGER.info("Extracting rendered HTML directly from page DOM...")
        
        # Wait for content to be rendered (wait for main content or pagedjs)
        await page.wait_for_function(
            "() => document.querySelector('.pagedjs_pages') || document.querySelector('[data-book]') || document.querySelector('main')",
            timeout=timeout_ms,
        )
        
        # Get the full HTML content
        html_content = await page.content()
        
        # Save it
        destination.write_text(html_content, encoding='utf-8')
        LOGGER.info(f"HTML extracted successfully ({len(html_content) / (1024*1024):.2f} MB)")
        return destination
        
    except Exception as e:
        LOGGER.error(f"Failed to extract HTML from page: {e}")
        raise


def create_letter_variant(source_html: Path, destination_html: Path) -> Path:
    LOGGER.debug("Creating Letter-sized HTML %s", destination_html)
    destination_html.parent.mkdir(parents=True, exist_ok=True)
    content = source_html.read_text(encoding="utf-8")
    updated, replacements = LETTER_SIZE_PATTERN.subn(r"\1letter;", content, count=1)
    if replacements == 0:
        raise RuntimeError(
            f"Could not find the A4 '@page {{ size: 210mm 297mm; }}' declaration in "
            f"{source_html.name}; the Letter variant would be a byte-identical A4 copy. "
            "Aborting this book rather than emitting a mislabeled PDF. The source print "
            "HTML's @page size rule likely changed upstream -- update LETTER_SIZE_PATTERN "
            "to match the new declaration."
        )
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

    try:
        # Read HTML content as UTF-8
        html_content = html_path.read_text(encoding='utf-8')
        # Use base_url to resolve relative paths in the HTML (for images, CSS, etc.)
        # Must use resolve() to convert relative path to absolute path before as_uri()
        html_doc = HTML(string=html_content, base_url=html_path.resolve().parent.as_uri() + '/')
        # The page size comes from the HTML's own `@page { size: ... }` rule. WeasyPrint
        # has no page-size argument -- passing page_size= just logged "Unknown rendering
        # option" and did nothing -- so the A4/LETTER distinction is baked into the HTML
        # by create_letter_variant() before we get here.
        html_doc.write_pdf(str(destination))
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
    html_only: bool = False,
) -> Path:
    prefix = build_output_prefix(owner, repo, ref, book)
    html_a4_path = output_dir / f"{prefix}_A4.html"
    
    # Check if HTML already exists
    if html_a4_path.exists() and not force:
        LOGGER.info("HTML already exists: %s (skipping download)", html_a4_path.name)
    else:
        page = await context.new_page()
        
        # Hide automation indicators that might prevent React from loading content
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)
        
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
            
            # For localhost/dev servers (Vite), use 'domcontentloaded' instead of 'networkidle'
            # because Vite keeps making requests and never reaches networkidle
            is_localhost = url.startswith("http://localhost") or url.startswith("http://127.0.0.1")
            wait_until = "domcontentloaded" if is_localhost else "networkidle"
            
            LOGGER.debug("Using wait strategy: %s (localhost=%s)", wait_until, is_localhost)
            await page.goto(url, wait_until=wait_until, timeout=navigation_timeout_ms)
            
            LOGGER.debug("Page loaded, waiting for content to render...")
            
            # Give React/Vue time to render the content
            # Increase wait time for localhost since we're not waiting for networkidle
            wait_time = 5000 if is_localhost else 2000
            await page.wait_for_timeout(wait_time)
            
            # Take a screenshot for debugging if verbose
            if LOGGER.level == logging.DEBUG:
                screenshot_path = output_dir / f"{prefix}_debug_screenshot.png"
                await page.screenshot(path=str(screenshot_path))
                LOGGER.debug(f"Screenshot saved to {screenshot_path}")

            await ensure_print_view(page, render_timeout_ms)
            await open_print_drawer(page, render_timeout_ms)
            await download_printable_html(page, render_timeout_ms, html_a4_path)
        except PlaywrightTimeoutError as e:
            LOGGER.error(f"Timeout while processing {url}")
            LOGGER.error(f"Error: {e}")
            
            # Save page content for debugging
            debug_html = output_dir / f"{prefix}_debug_page.html"
            content = await page.content()
            debug_html.write_text(content, encoding='utf-8')
            LOGGER.error(f"Page HTML saved to {debug_html} for debugging")
            
            # Save screenshot
            debug_screenshot = output_dir / f"{prefix}_debug_error.png"
            await page.screenshot(path=str(debug_screenshot), full_page=True)
            LOGGER.error(f"Screenshot saved to {debug_screenshot}")
            
            raise
        except Exception as e:
            LOGGER.error(f"Unexpected error while processing {url}: {e}")
            raise
        finally:
            page.remove_listener("request", log_request)
            page.remove_listener("response", log_response)
            await page.close()

    # If html_only mode, skip PDF generation
    if html_only:
        LOGGER.info("HTML-only mode: skipping PDF generation for %s", prefix)
        # Still create LETTER variant HTML if needed
        if "LETTER" in page_sizes:
            letter_html_path = output_dir / f"{prefix}_LETTER.html"
            if letter_html_path.exists() and not force:
                LOGGER.info("LETTER HTML already exists: %s (skipping creation)", letter_html_path.name)
            else:
                create_letter_variant(
                    source_html=html_a4_path,
                    destination_html=letter_html_path,
                )
        return html_a4_path

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

    return html_a4_path


async def run_export(
    books: Iterable[str | None],
    base_url: str,
    server: str | None,
    no_proxy: bool,
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
    html_only: bool = False,
    combine_all: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    failed_books = []
    successful_books = []
    combined_outputs: List[str] = []
    downloaded_book_html: Dict[str, Path] = {}
    book_sequence = list(books)
    per_book_html_only = html_only or combine_all
    download_page_sizes = ("A4",) if combine_all else page_sizes

    launch_args = [
        '--disable-blink-features=AutomationControlled',  # Hide automation
        '--disable-dev-shm-usage',  # Prevent crashes in Docker
        '--no-sandbox',  # Required for Docker/CI environments
    ]
    if no_proxy:
        launch_args.append('--no-proxy-server')  # Force a direct connection (bypass system/VPN proxy)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless,
            args=launch_args,
        )
        context = await browser.new_context(
            accept_downloads=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',  # Real browser UA
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            ignore_https_errors=False,
            java_script_enabled=True,
        )

        try:
            for raw_book in book_sequence:
                # Handle None for bookless repos
                book = raw_book.lower() if raw_book is not None else None
                url = build_url(base_url, owner, repo, ref, book, server=server)
                
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
                    downloaded_html_path = await generate_pdf_for_book(
                        context=context,
                        owner=owner,
                        repo=repo,
                        ref=ref,
                        book=book,
                        url=url,
                        output_dir=output_dir,
                        page_sizes=download_page_sizes,
                        navigation_timeout_ms=book_navigation_timeout * 1000,
                        render_timeout_ms=book_render_timeout * 1000,
                        sleep_after_ready=sleep_after_ready,
                        backend=backend,
                        force=force,
                        html_only=per_book_html_only,
                    )
                    LOGGER.info("Successfully completed %s", display_name)
                    successful_books.append(display_name)
                    if book is not None:
                        downloaded_book_html[book] = downloaded_html_path
                    
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

            if combine_all:
                ordered_downloaded_books = sort_books_canonical(
                    [
                        raw_book
                        for raw_book in book_sequence
                        if raw_book is not None and raw_book.lower() in downloaded_book_html
                    ]
                )
                if not ordered_downloaded_books:
                    raise RuntimeError(
                        "Could not generate combined all-books output because no book HTML files were downloaded."
                    )
                if failed_books:
                    LOGGER.warning(
                        "Building combined output with %d successful book(s); %d book(s) failed earlier.",
                        len(ordered_downloaded_books),
                        len(failed_books),
                    )

                combined_prefix = build_all_books_output_prefix(repo, ref)
                combined_a4_html_path = output_dir / f"{combined_prefix}_A4.html"

                if combined_a4_html_path.exists() and not force:
                    LOGGER.info(
                        "Combined HTML already exists: %s (skipping creation)",
                        combined_a4_html_path.name,
                    )
                else:
                    merged_html = build_all_books_html(
                        repo=repo,
                        ref=ref,
                        ordered_books=ordered_downloaded_books,
                        book_html_paths=downloaded_book_html,
                    )
                    combined_a4_html_path.write_text(merged_html, encoding="utf-8")
                    LOGGER.info("Created combined all-books HTML: %s", combined_a4_html_path.name)

                if html_only:
                    combined_outputs.append(combined_a4_html_path.name)
                else:
                    combined_html_variants = {"A4": combined_a4_html_path}
                    if "LETTER" in page_sizes:
                        combined_letter_html_path = output_dir / f"{combined_prefix}_LETTER.html"
                        if combined_letter_html_path.exists() and not force:
                            LOGGER.info(
                                "Combined LETTER HTML already exists: %s (skipping creation)",
                                combined_letter_html_path.name,
                            )
                        else:
                            create_letter_variant(
                                source_html=combined_a4_html_path,
                                destination_html=combined_letter_html_path,
                            )
                        combined_html_variants["LETTER"] = combined_letter_html_path

                    for page_size in page_sizes:
                        combined_html_path = combined_html_variants.get(page_size)
                        if combined_html_path is None:
                            continue

                        pdf_destination = output_dir / f"{combined_prefix}_{page_size}.pdf"
                        if pdf_destination.exists() and not force:
                            LOGGER.info(
                                "Combined PDF already exists: %s (skipping generation)",
                                pdf_destination.name,
                            )
                            combined_outputs.append(pdf_destination.name)
                            continue

                        await render_html_to_pdf(
                            context=context,
                            html_path=combined_html_path,
                            destination=pdf_destination,
                            page_size=page_size,
                            render_timeout_ms=render_timeout * 1000,
                            sleep_after_ready=sleep_after_ready,
                            backend=backend,
                        )
                        combined_outputs.append(pdf_destination.name)

        finally:
            await context.close()
            await browser.close()
    
    # Print summary
    LOGGER.info("=" * 60)
    LOGGER.info("EXPORT SUMMARY")
    LOGGER.info("=" * 60)
    if html_only:
        LOGGER.info("Successfully downloaded HTML: %d book(s)", len(successful_books))
    elif combine_all:
        LOGGER.info("Successfully processed HTML for %d book(s)", len(successful_books))
    else:
        LOGGER.info("Successfully generated: %d book(s)", len(successful_books))
    if successful_books:
        LOGGER.info("  %s", ", ".join(successful_books))

    if combined_outputs:
        LOGGER.info("Combined output(s): %s", ", ".join(combined_outputs))
    
    if failed_books:
        LOGGER.warning("Failed to generate: %d book(s)", len(failed_books))
        for book_code, reason in failed_books:
            LOGGER.warning("  %s: %s", book_code, reason[:80])
    LOGGER.info("=" * 60)


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    if args.no_proxy:
        # Bypass any proxy for THIS process only (urllib catalog fetch + the Chromium child,
        # which inherits this env). The parent shell / other apps keep their proxy + VPN.
        for _var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
            os.environ.pop(_var, None)
        os.environ["no_proxy"] = "*"
        urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
        LOGGER.info("Proxy bypass enabled: direct connection for this process (urllib + Chromium --no-proxy-server)")

    if args.list_books:
        print_available_books()
        return 0

    try:
        page_sizes = resolve_page_sizes(args.page)
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

    # If --books not specified or 'all' specified, use all catalog books
    if args.books is None:
        book_list = None
    else:
        try:
            book_list = expand_book_arguments(args.books)
        except ValueError as error:
            LOGGER.error("%s", error)
            return 1

    # Handle bookless repos (e.g., en_ta, en_tw)
    if not available_books:
        if args.all:
            LOGGER.error("--all requires a book-based repo with catalog book identifiers.")
            return 1
        LOGGER.info("Repo has no books - treating as single-page resource")
        selected_books = [None]  # Use None to represent the entire repo
        missing_books = []
    # If book_list is None, it means --books was not specified or 'all' was used
    elif book_list is None:
        selected_books = available_books
        missing_books = []
        LOGGER.info("Processing all %d books from catalog", len(selected_books))
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

    if args.all:
        selected_books = sort_books_canonical(book for book in selected_books if book is not None)
        if not selected_books:
            LOGGER.error("--all requires at least one valid book to merge.")
            return 1

    LOGGER.info(
        "Starting export for %d book(s) with page size(s): %s",
        len(selected_books),
        ", ".join(page_sizes),
    )
    
    if args.html_only:
        LOGGER.info("HTML-only mode: PDFs will NOT be generated")
    if args.all:
        LOGGER.info(
            "All-books mode enabled: per-book PDFs will be skipped and a combined all-books output will be created."
        )

    try:
        asyncio.run(
            run_export(
                books=selected_books,
                base_url=args.base_url,
                server=args.server,
                no_proxy=args.no_proxy,
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
                html_only=args.html_only,
                combine_all=args.all,
            )
        )
    except RenderTimeoutError as error:
        LOGGER.error("%s", error)
        return 1

    LOGGER.info("Export completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
