# Door43 Preview Actions

GitHub/Gitea Actions for loading Door43 preview pages and generating PDFs.

## Features

- 🔄 **Load Preview Pages**: Trigger server-side caching by loading preview pages
- 📄 **Generate PDFs**: Create PDF files from Door43 preview pages
- 🤖 **Auto-detection**: Automatically detects owner, repo, and ref from GitHub context
- ⚡ **Multiple backends**: Choose between Playwright (Paged.js) or WeasyPrint for PDF generation
- 📚 **Flexible book selection**: Load all books, specific books, or by testament (OT/NT)
- 🎯 **Bookless repos**: Supports repos without books (like en_ta, en_tw)

## Quick Start

### Load Preview Pages

```yaml
- name: Load preview pages
  uses: unfoldingWord/door43-preview-actions@v1
  with:
    action: load-pages
    books: all
```

### Generate PDFs

```yaml
- name: Generate PDFs
  uses: unfoldingWord/door43-preview-actions@v1
  with:
    action: create-pdfs
    books: all
    backend: weasyprint
    output-dir: pdfs
```

## Inputs

### Required Inputs

| Input | Description |
|-------|-------------|
| `action` | Action to run: `load-pages` or `create-pdfs` |

### Common Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `owner` | Repository owner | Auto-detected from `github.repository_owner` |
| `repo` | Repository name | Auto-detected from `github.repository` |
| `ref` | Git reference (branch/tag) | Auto-detected from `github.ref_name` |
| `books` | Book codes (`all`, `ot`, `nt`, or specific codes) | `all` |
| `base-url` | Door43 preview base URL | `https://preview.door43.org` |
| `verbose` | Enable verbose logging | `false` |

### Create PDFs Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `output-dir` | Output directory for PDFs | `output` |
| `page-size` | Page size: `A4`, `LETTER` | Both sizes |
| `backend` | PDF backend: `playwright` or `weasyprint` | `weasyprint` |
| `force` | Force regeneration of existing files | `false` |

### Load Pages Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `cache-timeout` | Cache timeout in seconds | 300 |

## Usage Examples

See [EXAMPLES.md](EXAMPLES.md) for complete workflow examples.

### Basic Usage

```yaml
name: Generate PDFs

on:
  push:
    tags: ['v*']

jobs:
  pdfs:
    runs-on: ubuntu-latest
    steps:
      - uses: unfoldingWord/door43-preview-actions@v1
        with:
          action: create-pdfs
          books: all
          backend: weasyprint
      
      - uses: actions/upload-artifact@v4
        with:
          name: pdfs
          path: output/*.pdf
```

### Specific Repository

```yaml
- uses: unfoldingWord/door43-preview-actions@v1
  with:
    action: create-pdfs
    owner: unfoldingWord
    repo: en_tn
    ref: v87
    books: mat mrk luk jhn
```

### Load Pages First

```yaml
- name: Load pages to cache
  uses: unfoldingWord/door43-preview-actions@v1
  with:
    action: load-pages
    books: all

- name: Generate PDFs
  uses: unfoldingWord/door43-preview-actions@v1
  with:
    action: create-pdfs
    books: all
```

## Backend Comparison

### WeasyPrint (Recommended)
- ✅ Much faster (10-100x)
- ✅ Lower memory usage
- ✅ Better for CI/CD
- ❌ Different rendering than browser

### Playwright (Paged.js)
- ✅ Browser-identical rendering
- ✅ Uses Paged.js pagination
- ❌ Much slower
- ❌ Higher memory usage
- ❌ Can timeout on large files

## Book Codes

### Shortcuts
- `all`: All available books in the catalog
- `ot`: All Old Testament books
- `nt`: All New Testament books

### Specific Books
Use 3-letter book codes: `gen exo lev mat mrk luk`

Old Testament: `gen exo lev num deu jos jdg rut 1sa 2sa 1ki 2ki 1ch 2ch ezr neh est job psa pro ecc sng isa jer lam ezk dan hos jol amo oba jon mic nam hab zep hag zec mal`

New Testament: `mat mrk luk jhn act rom 1co 2co gal eph php col 1th 2th 1ti 2ti tit phm heb jas 1pe 2pe 1jn 2jn 3jn jud rev`

## Outputs

| Output | Description |
|--------|-------------|
| `books-loaded` | Number of books successfully processed |
| `books-failed` | Number of books that failed |
| `output-directory` | Directory containing generated PDFs (create-pdfs only) |

## Requirements

- Python 3.10+
- Ubuntu or macOS runner
- For Playwright backend: Additional browser dependencies

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Repository Structure

```
.
├── action.yml                      # Action definition
├── scripts/
│   ├── load_preview_pages.py      # Load pages script
│   └── create_door43_preview_pdfs.py  # Generate PDFs script
├── requirements.txt                # Python dependencies
├── README.md                       # This file
└── EXAMPLES.md                     # Detailed examples
```
