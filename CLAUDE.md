# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **GitHub/Gitea composite Action** (`action.yml`) that drives the [Door43 preview site](https://preview.door43.org)
to (a) warm its server-side cache and (b) export Bible-translation resources to PDF. It is *not* a Python
package — the two scripts under `scripts/` are the units of work, invoked by `action.yml`'s shell steps or
directly from the CLI. Output is unfoldingWord translation resources (en_ult, en_ust, en_tn, en_tq, en_ta, en_tw, …).

The action exposes one `action` input with two modes: `load-pages` and `create-pdfs`.

## Setup & common commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # local macOS/dev. On Linux/CI use: playwright install --with-deps chromium
```

Both modes need the Chromium browser; `create-pdfs` uses it to render the React app and download the print
HTML *even with the WeasyPrint backend* (WeasyPrint only does the later HTML→PDF step).

```bash
# List the 66 supported 3-letter book codes
python scripts/create_door43_preview_pdfs.py --list-books

# Warm the server cache for a resource (load-pages mode)
python scripts/load_preview_pages.py --owner unfoldingWord --repo en_tn --ref v89 --books rut

# Generate PDFs (create-pdfs mode). --books accepts codes, or all/ot/nt; omit for all catalog books
python scripts/create_door43_preview_pdfs.py --owner unfoldingWord --repo en_tn --ref v89 --books rut --backend weasyprint --verbose

# Download print HTML only (no PDFs) — useful to get everything local first on a flaky connection
python scripts/create_door43_preview_pdfs.py --owner unfoldingWord --repo en_tn --ref v89 --books all --html-only

# Debug a hang: run the browser visibly
python scripts/create_door43_preview_pdfs.py --owner unfoldingWord --repo en_tn --ref v89 --books rut --headed --verbose
```

There is **no local test suite** (there is no `tests/` dir). The real regression check is
`.github/workflows/test.yml`, which exercises both modes, both PDF backends, a bookless repo (`en_ta`), and
auto-detection against live `unfoldingWord` resources on the runner.

## Architecture

Both scripts share the same pipeline shape and a **duplicated `BIBLE_BOOK_DATA` table** (66 books with
`title`/`testament`/`verse_count`/`number`). If you change book metadata, change it in *both*
`load_preview_pages.py` and `create_door43_preview_pdfs.py`.

**1. Catalog discovery (both scripts).** `fetch_available_books()` hits the DCS catalog API
(`https://git.door43.org/api/v1/catalog/entry/{owner}/{repo}/{ref}`) and reads `ingredients[].identifier`
to learn which books a resource actually contains. A repo with no Bible-book ingredients (e.g. `en_ta`,
`en_tw`) is a **bookless repo**: the book list becomes `[None]`, meaning "render the whole repo as one page."
The `None` sentinel for bookless repos threads through every function — preserve it when editing.

**2. URL construction.** Pages live at
`{base_url}/u/{owner}/{repo}/{ref}/?rerender=1&book={book}` (book omitted for bookless repos).
`&rerender=1` forces a fresh render. `--base-url` defaults to `https://preview.door43.org`. The
`--server` flag (create-pdfs) appends `&server=<value>` — use `--base-url https://develop-preview.door43.org
--server prod` to render via the develop site against production DCS data.

**3a. `load-pages` mode** (`load_preview_pages.py`): navigates each page and waits for the Netlify
`cache-html` function POST (`/.netlify/functions/cache-html`) whose body path matches `/{book}.json.gz`
— that POST is the signal the server finished rendering and caching. `require_post=False`, so a page that's
already cached (no POST seen) is treated as success, not failure. **Note:** `load-pages` is *not* a
prerequisite for `create-pdfs` — the PDF script renders fresh via `?rerender=1` and downloads the HTML itself.

**3b. `create-pdfs` mode** (`create_door43_preview_pdfs.py`):
  - `ensure_print_view()` → toggles the page's Paged.js print view. Deliberately resilient: primary
    selector (`button[aria-label^="Print view"]`), then fallbacks (HTML-download button, print-options icon,
    finally just waiting for main content). Don't "simplify" the fallback chain — it exists because the
    preview UI varies and CI selectors are brittle.
  - `download_printable_html()` → clicks "Download the HTML for printing", or falls back to scraping
    `page.content()` from the DOM. Writes `<prefix>_A4.html`. **This HTML is cached** — re-runs skip the
    download (and skip existing PDFs) unless `--force` is passed. After the upstream preview app changes, you
    MUST re-run with `--force` (or a fresh `--output-dir`) or you silently reuse stale HTML.
  - PDF rendering goes through one of **two backends** (`render_html_to_pdf`):
    - `weasyprint` — synchronous, server-side HTML→PDF. Much faster, lower memory; the default in `action.yml`
      and the right choice for bulk/all-books runs (Playwright is slow and times out on large books).
    - `playwright` — loads the HTML in Chromium and waits for Paged.js to stop adding pages (page-count
      stable >1s) before `page.pdf()`.
    - **Gotcha:** the CLI's own default `--backend` is `playwright`; `action.yml` overrides it to `weasyprint`.

**Page size comes from CSS, not arguments.** The downloaded print HTML's own `@page { size: ... }` rule
determines the page size for *both* backends — WeasyPrint has no page-size argument (it's controlled purely by
`@page`), and the Playwright path uses `prefer_css_page_size=True` so CSS wins over its `format` arg. The
A4→Letter variant is produced by `create_letter_variant()` regex-swapping `size: 210mm 297mm;` → `size: letter;`
in the A4 HTML (`LETTER_SIZE_PATTERN`); if that declaration isn't present it **raises** (fails loudly) rather
than emitting a mislabeled A4-sized "LETTER" file. This whole mechanism depends on the preview app emitting
`@page { size: 210mm 297mm; }` (fixed upstream in preview.door43.org v1.4.6); if upstream switches to the `A4`
keyword form, update `LETTER_SIZE_PATTERN`.

**Backend fidelity differs.** WeasyPrint is a *different* paged-media engine than the app's Paged.js, so it
silently drops CSS features it doesn't fully support. Verified on en_tn: page counts match within ~1 page and
body/boxes/links/page-numbers/cover all render correctly, but WeasyPrint **omits the running header**
(`unfoldingWord® Translation Notes :: Ruth X:Y`) because it uses the CSS `running()`/`element()` feature.
WeasyPrint also drops `@footnote`/`position: note(footnotes)` (footnote layout) and the `@page :cover-page`
named-page rule (look for these in the run's `WARNING Ignored …` / `Unsupported @page selector` lines). Use
Playwright when the output must match the on-screen print preview exactly; use WeasyPrint for speed when those
features don't matter for the resource.

**4. Output naming** (`build_output_prefix`): `<repo>_<NN>-<BOOK>_<ref>_<SIZE>.{html,pdf}`
(e.g. `en_tn_08-RUT_v89_A4.pdf`); bookless repos drop the book segment (`en_ta_v89_A4.pdf`). The CI assertions
depend on this exact format.

**5. `--all` mode** (`build_all_books_html`): downloads each book's HTML, then string-surgery-merges them into
one document — takes cover + copyright from the first book, generates a fresh TOC, and concatenates each book's
`#nav-<book>` section. Output prefix is `<repo>_ALL_<ref>`. The HTML parsing here
(`extract_pagedjs_sections`, `find_matching_tag_end`) is hand-rolled depth-tracking over the `#pagedjs-print`
container — not a real HTML parser, so it assumes the preview site's specific markup.

**Timeouts scale per book.** `compute_book_timeout()` adds `verse_count * per-verse-seconds` to the base
navigation/render/cache timeouts, so Psalms gets far longer than Obadiah. The `--*-per-verse` flags tune this.

**Anti-bot measures.** Both scripts launch Chromium with automation flags hidden
(`--disable-blink-features=AutomationControlled`), a real Chrome user agent, and an init script that overrides
`navigator.webdriver`/`plugins`/`languages`. Without these the preview site's React app may refuse to load
content. Keep them when touching browser-launch code.

## Helper scripts (one-off tooling, not part of the action)

`scripts/{analyze_html_structure,analyze_div_optimization,intelligent_div_optimizer,optimize_html_structure,validate_html_structure}.py`
and `scripts/{profile_weasyprint,convert_single_html,test_weasyprint_simple}.py` are standalone tools used to
diagnose and speed up WeasyPrint rendering of downloaded HTML. They are not wired into `action.yml`.

## Gotchas

- **Stale entry-point name `scripts/print_preview_pdf.py`** appears in the docstring at the top of
  `create_door43_preview_pdfs.py` and in `scripts/batch_process_books.sh`. That file does not exist — the real
  script is `scripts/create_door43_preview_pdfs.py`. `batch_process_books.sh` is therefore broken as written.
- Repo-root artifacts (`gen*.html`, `*.pdf`, `rut.html`, `ult_all/`, `ust_all/`, `tw/`, `test/`,
  `completed_urls`, `errors_urls`, `hit_preview_pages*.py`, `output/`) are scratch/working files, not tracked
  source. `output/` is gitignored. Don't treat them as part of the action.

## Conventions

- Python 3.10+ (`from __future__ import annotations`, `pathlib`, type hints). PEP 8, 4-space indent.
- Conventional-commit messages (`feat:`, `fix:`, `debug:`) — match the existing git history.
- Module-level constants are UPPERCASE; selectors and URL templates live as constants near the top of each script.
- Keep generated PDFs/HTML out of the repo — write them to the gitignored `output/` directory.
