"""Load Door43 preview pages to trigger server-side caching.

Usage example:

    python scripts/load_preview_pages.py --repo en_ult --ref v86 --books gen exo

The script navigates to each book's preview page and waits for the cache-html
POST request to complete, which indicates the page has been fully rendered
and cached on the server.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import urllib.error
import urllib.request
from math import ceil
from typing import Iterable, List, Optional

from playwright.async_api import BrowserContext, Page, Response
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


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
CATALOG_ENTRY_URL_TEMPLATE = "https://git.door43.org/api/v1/catalog/entry/{owner}/{repo}/{ref}"
CACHE_HTML_URL = "https://preview.door43.org/.netlify/functions/cache-html"
PRINT_TOGGLE_SELECTOR = 'button[aria-label^="Print view"]'


class CatalogEntryNotFoundError(RuntimeError):
    """Signal that the owner/repo/ref combination has no catalog entry."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load Door43 preview pages to trigger server-side caching."
    )
    parser.add_argument(
        "--books",
        nargs="+",
        default=DEFAULT_BOOKS,
        help="List of 3-letter book codes to load. Use 'all' for all available books, "
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
        "--cache-timeout",
        type=int,
        default=300,
        help="Seconds to wait for cache-html POST request (default: %(default)s).",
    )
    parser.add_argument(
        "--cache-timeout-per-verse",
        type=float,
        default=0.1,
        help="Additional seconds to add per verse when determining cache timeout.",
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

    parser.set_defaults(headless=True)
    args = parser.parse_args()

    if not args.list_books and not args.repo:
        parser.error("--repo is required unless --list-books is provided.")

    return args


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def build_url(base_url: str, owner: str, repo: str, ref: str, book: str | None) -> str:
    if book is None:
        return f"{base_url}/u/{owner}/{repo}/{ref}/?rerender=1"
    return f"{base_url}/u/{owner}/{repo}/{ref}/?book={book}&rerender=1"


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


async def wait_for_cache_html_post(page: Page, book: str | None, repo: str, timeout_ms: int) -> None:
    """Wait for the main book cache-html POST request to complete."""
    LOGGER.debug("Waiting for main book cache-html POST request")
    
    cache_html_completed = asyncio.Event()
    all_requests = []
    all_responses = []
    cache_posts_seen = []
    
    # Determine what URL pattern to look for
    if book is None:
        # For bookless repos, look for repo name in the path
        expected_pattern = f"/{repo}.json.gz"
    else:
        # For book-based repos, look for book name in the path (lowercase)
        expected_pattern = f"/{book.lower()}.json.gz"
    
    LOGGER.debug("Looking for cache-html POST with pattern: %s", expected_pattern)
    
    async def handle_request(request):
        method = request.method
        url = request.url
        LOGGER.debug("REQUEST: %s %s", method, url)
        all_requests.append((method, url))
    
    async def handle_response(response: Response):
        method = response.request.method
        url = response.url
        status = response.status
        LOGGER.debug("RESPONSE: %s %s -> %d", method, url, status)
        all_responses.append((method, url, status))
        
        if CACHE_HTML_URL in response.url and response.request.method == "POST":
            cache_posts_seen.append(url)
            LOGGER.info("✓ Cache-html POST seen: %s (status %d)", url, status)
            
            # Check if this is the main book cache POST
            if expected_pattern in url:
                LOGGER.info("✓ Main book cache-html POST completed!")
                cache_html_completed.set()
    
    page.on("request", handle_request)
    page.on("response", handle_response)
    
    try:
        # Wait for the main cache-html POST
        await asyncio.wait_for(cache_html_completed.wait(), timeout=timeout_ms / 1000.0)
        LOGGER.info("Page successfully loaded and cached")
        
    except asyncio.TimeoutError:
        LOGGER.error("Timeout waiting for main book cache-html POST after %dms", timeout_ms)
        LOGGER.error("Total requests made: %d", len(all_requests))
        LOGGER.error("Total responses received: %d", len(all_responses))
        LOGGER.error("Expected pattern: %s", expected_pattern)
        
        if cache_posts_seen:
            LOGGER.error("Cache-html POSTs seen (%d):", len(cache_posts_seen))
            for url in cache_posts_seen:
                LOGGER.error("  - %s", url)
        else:
            LOGGER.error("No cache-html POST requests were seen!")
        
        # Log any POST requests that were made
        post_requests = [url for method, url in all_requests if method == "POST" and "google-analytics" not in url]
        if post_requests:
            LOGGER.error("Other POST requests seen:")
            for url in post_requests[:10]:  # Limit to first 10
                LOGGER.error("  - %s", url)
        
        raise PlaywrightTimeoutError(f"Timeout waiting for main book cache-html POST after {timeout_ms}ms")
    finally:
        page.remove_listener("request", handle_request)
        page.remove_listener("response", handle_response)


async def load_preview_page(
    context: BrowserContext,
    owner: str,
    repo: str,
    ref: str,
    book: str | None,
    url: str,
    navigation_timeout_ms: int,
    cache_timeout_ms: int,
) -> None:
    """Load a preview page and wait for cache-html POST."""
    page = await context.new_page()
    try:
        page.set_default_timeout(cache_timeout_ms)
        LOGGER.info("Navigating to %s", url)
        
        # Start waiting for cache-html POST before navigation
        cache_task = asyncio.create_task(wait_for_cache_html_post(page, book, repo, cache_timeout_ms))
        
        await page.goto(url, wait_until="networkidle", timeout=navigation_timeout_ms)
        
        # Wait for cache-html POST to complete
        await cache_task
        
    finally:
        await page.close()


async def run_load(
    books: Iterable[str | None],
    base_url: str,
    owner: str,
    repo: str,
    ref: str,
    headless: bool,
    navigation_timeout: int,
    navigation_timeout_per_verse: float,
    cache_timeout: int,
    cache_timeout_per_verse: float,
) -> None:
    failed_books = []
    successful_books = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context()

        try:
            for raw_book in books:
                # Handle None for bookless repos
                book = raw_book.lower() if raw_book is not None else None
                url = build_url(base_url, owner, repo, ref, book)
                
                if book is None:
                    # For bookless repos, use default timeouts
                    verse_count = 0
                    book_navigation_timeout = navigation_timeout
                    book_cache_timeout = cache_timeout
                    display_name = repo.upper()
                else:
                    verse_count = BIBLE_BOOK_DATA.get(book, {}).get("verse_count", 0)
                    book_navigation_timeout = compute_book_timeout(
                        navigation_timeout, navigation_timeout_per_verse, verse_count
                    )
                    book_cache_timeout = compute_book_timeout(
                        cache_timeout, cache_timeout_per_verse, verse_count
                    )
                    display_name = book.upper()
                
                LOGGER.debug(
                    "Timeouts for %s: navigation=%ss cache=%ss",
                    display_name,
                    book_navigation_timeout,
                    book_cache_timeout,
                )

                try:
                    await load_preview_page(
                        context=context,
                        owner=owner,
                        repo=repo,
                        ref=ref,
                        book=book,
                        url=url,
                        navigation_timeout_ms=book_navigation_timeout * 1000,
                        cache_timeout_ms=book_cache_timeout * 1000,
                    )
                    LOGGER.info("Successfully loaded and cached %s", display_name)
                    successful_books.append(display_name)
                    
                except PlaywrightTimeoutError as exc:
                    LOGGER.error(
                        "Timed out while loading preview for %s: %s",
                        display_name,
                        exc,
                    )
                    LOGGER.warning("Skipping %s and continuing with next book", display_name)
                    failed_books.append((display_name, "Timeout"))
                except Exception as exc:
                    LOGGER.error(
                        "Failed to load preview for %s: %s",
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
    LOGGER.info("LOAD SUMMARY")
    LOGGER.info("=" * 60)
    LOGGER.info("Successfully loaded: %d book(s)", len(successful_books))
    if successful_books:
        LOGGER.info("  %s", ", ".join(successful_books))
    
    if failed_books:
        LOGGER.warning("Failed to load: %d book(s)", len(failed_books))
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
        "Starting load for %d book(s)",
        len(selected_books),
    )

    try:
        asyncio.run(
            run_load(
                books=selected_books,
                base_url=args.base_url,
                owner=args.owner,
                repo=args.repo,
                ref=args.ref,
                headless=args.headless,
                navigation_timeout=args.navigation_timeout,
                navigation_timeout_per_verse=args.navigation_timeout_per_verse,
                cache_timeout=args.cache_timeout,
                cache_timeout_per_verse=args.cache_timeout_per_verse,
            )
        )
    except Exception as error:
        LOGGER.error("Unexpected error: %s", error)
        return 1

    LOGGER.info("Load completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
