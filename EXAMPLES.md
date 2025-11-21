# Example GitHub/Gitea Actions workflows for Door43 Preview Actions

## Load Preview Pages Example

This workflow loads preview pages to trigger server-side caching.

```yaml
name: Load Door43 Preview Pages

on:
  push:
    branches: [master, main]
  workflow_dispatch:

jobs:
  load-pages:
    runs-on: ubuntu-latest
    steps:
      - name: Load preview pages for current repo
        uses: unfoldingWord/door43-preview-actions@v1
        with:
          action: load-pages
          # owner, repo, and ref will be auto-detected from the current repository
          books: all
          verbose: true
      
      - name: Load pages for specific repo
        uses: unfoldingWord/door43-preview-actions@v1
        with:
          action: load-pages
          owner: unfoldingWord
          repo: en_tn
          ref: v87
          books: all
```

## Create PDFs Example

This workflow generates PDFs from Door43 preview pages.

```yaml
name: Generate Door43 Preview PDFs

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  create-pdfs:
    runs-on: ubuntu-latest
    steps:
      - name: Generate PDFs for current repo
        uses: unfoldingWord/door43-preview-actions@v1
        with:
          action: create-pdfs
          # owner, repo, and ref will be auto-detected from the current repository
          books: all
          backend: weasyprint
          output-dir: pdfs
          verbose: true
      
      - name: Upload PDFs as artifacts
        uses: actions/upload-artifact@v4
        with:
          name: door43-preview-pdfs
          path: pdfs/*.pdf
      
      - name: Generate PDFs for specific books
        uses: unfoldingWord/door43-preview-actions@v1
        with:
          action: create-pdfs
          owner: unfoldingWord
          repo: en_tn
          ref: v87
          books: mat mrk luk jhn
          backend: weasyprint
          page-size: A4
          output-dir: nt-pdfs
```

## Complete Example with Both Actions

```yaml
name: Load Pages and Generate PDFs

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  load-and-generate:
    runs-on: ubuntu-latest
    steps:
      - name: Load preview pages first
        uses: unfoldingWord/door43-preview-actions@v1
        with:
          action: load-pages
          owner: unfoldingWord
          repo: en_tn
          ref: v87
          books: all
          verbose: true
      
      - name: Wait for caching to complete
        run: sleep 30
      
      - name: Generate PDFs
        uses: unfoldingWord/door43-preview-actions@v1
        with:
          action: create-pdfs
          owner: unfoldingWord
          repo: en_tn
          ref: v87
          books: all
          backend: weasyprint
          output-dir: pdfs
          force: false
          verbose: true
      
      - name: Upload PDFs
        uses: actions/upload-artifact@v4
        with:
          name: en_tn-v87-pdfs
          path: pdfs/*.pdf
          retention-days: 90
```

## Action Inputs Reference

### Common Inputs (both actions)

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `action` | Which action to run: `load-pages` or `create-pdfs` | Yes | - |
| `owner` | Repository owner | No | Current repo owner |
| `repo` | Repository name | No | Current repo name |
| `ref` | Git reference (branch/tag) | No | Current ref |
| `books` | Space-separated book codes or `all`, `ot`, `nt` | No | `all` |
| `base-url` | Door43 preview base URL | No | `https://preview.door43.org` |
| `navigation-timeout` | Navigation timeout in seconds | No | Script defaults |
| `verbose` | Enable verbose logging | No | `false` |

### Create PDFs Specific Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `output-dir` | Output directory for PDFs | No | `output` |
| `page-size` | Page size: `A4`, `LETTER`, or both | No | Both |
| `backend` | PDF backend: `playwright` or `weasyprint` | No | `weasyprint` |
| `force` | Force regeneration even if files exist | No | `false` |
| `render-timeout` | Render timeout in seconds | No | Script defaults |

### Load Pages Specific Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `cache-timeout` | Cache timeout in seconds | No | Script defaults |

## Auto-Detection of Repository Info

If `owner`, `repo`, or `ref` are not provided, the action will automatically detect them from:

- `owner`: `${{ github.repository_owner }}`
- `repo`: Extracted from `${{ github.repository }}`
- `ref`: `${{ github.ref_name }}` (branch or tag name)

This makes it easy to use in the repository where the action is triggered:

```yaml
- name: Generate PDFs for this repo
  uses: unfoldingWord/door43-preview-actions@v1
  with:
    action: create-pdfs
    # owner, repo, ref automatically detected!
    books: all
```
