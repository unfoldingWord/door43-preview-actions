# Repository Guidelines

## Project Structure & Module Organization
- Keep executable automation code under `scripts/`. The primary entry point is `scripts/print_preview_pdf.py`, which orchestrates browser automation for generating resource PDFs.
- Store supporting configuration (book lists, environment overrides) alongside the script in clearly named Python modules. Use `data/` or `config/` folders only when shared across multiple scripts.
- Output artifacts such as generated PDFs should live outside the repo by default. When samples are required, place them in a `.gitignored` `output/` directory and document their purpose.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` — create and activate a local virtual environment for development.
- `pip install -r requirements.txt` — install runtime dependencies, including Playwright.
- `playwright install --with-deps chromium` — download the Chromium browser used for headless print jobs. Re-run after Playwright upgrades.
- `python scripts/print_preview_pdf.py --help` — view CLI usage, supported flags, and defaults.

## Coding Style & Naming Conventions
- Target Python 3.10+ features (type hints, `pathlib`, `dataclasses`). Maintain PEP 8 compliance with 4-space indentation.
- Prefer descriptive module and function names (`generate_print_preview`, `wait_for_render_ready`) over abbreviations. Keep module-level constants uppercase.
- When adding linting or formatting, use `ruff` or `black` consistently across the repo and document the command in this file.

## Testing Guidelines
- Add automated tests under `tests/` using `pytest`. Mirror the scripts' package structure to keep fixtures discoverable.
- For browser-driven flows, create integration tests guarded by a `--runslow` marker to avoid accidental execution in CI without the necessary dependencies.
- Aim for coverage on critical control flow: successful PDF generation, timeouts, and error reporting. Update test data to reflect new book codes or URL patterns.

## Commit & Pull Request Guidelines
- Write conventional-style commit messages (e.g., `feat: add CLI flags for book range`) to make change intent clear in the history.
- Keep pull requests focused: describe the scenario, list reproducible steps, and attach logs or sample PDFs when relevant.
- Ensure CI (once configured) runs clean before requesting review. Highlight any follow-up tasks or known gaps directly in the PR description.
