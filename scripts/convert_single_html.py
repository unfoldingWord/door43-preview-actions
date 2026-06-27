#!/usr/bin/env python3
"""
Quick test script to convert a single HTML file to PDF using WeasyPrint.
Tests that CSS Paged Media features work without Paged.js.
"""

import sys
import time
from pathlib import Path
from weasyprint import HTML, CSS
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def convert_html_to_pdf(html_path: Path, output_path: Path):
    """
    Convert HTML file to PDF using WeasyPrint.
    
    Args:
        html_path: Path to input HTML file
        output_path: Path to output PDF file
    """
    if not html_path.exists():
        LOGGER.error(f"HTML file not found: {html_path}")
        return False
    
    LOGGER.info(f"📄 Reading HTML from: {html_path}")
    LOGGER.info(f"📄 File size: {html_path.stat().st_size / (1024*1024):.2f} MB")
    
    # Read the HTML content
    html_content = html_path.read_text(encoding='utf-8')
    
    # Check for Paged.js script
    if 'pagedjs' in html_content.lower():
        LOGGER.warning("⚠️  Paged.js reference found in HTML (will be ignored by WeasyPrint)")
    
    # Convert to PDF
    LOGGER.info("🔨 Generating PDF with WeasyPrint...")
    LOGGER.info("   This may take a few minutes for large documents...")
    start_time = time.time()
    
    try:
        # Create HTML object from string with base URL for resolving relative paths
        html_doc = HTML(
            string=html_content,
            base_url=html_path.resolve().parent.as_uri() + '/'
        )
        
        # Write PDF with A4 page size
        html_doc.write_pdf(
            str(output_path),
            # Note: WeasyPrint respects @page rules in CSS, so A4 size should come from there
            # But we can also specify it here as a fallback
        )
        
        elapsed = time.time() - start_time
        
        # Get file size
        size_mb = output_path.stat().st_size / (1024 * 1024)
        
        LOGGER.info(f"✅ PDF generated successfully!")
        LOGGER.info(f"   Output: {output_path}")
        LOGGER.info(f"   Size: {size_mb:.2f} MB")
        LOGGER.info(f"   Time: {elapsed:.2f} seconds ({elapsed/60:.1f} minutes)")
        
        return True
        
    except Exception as e:
        LOGGER.error(f"❌ Failed to render PDF: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    if len(sys.argv) > 1:
        html_file = Path(sys.argv[1])
    else:
        # Default to gen.html in repo root
        repo_root = Path(__file__).parent.parent
        html_file = repo_root / "gen.html"
    
    if not html_file.exists():
        LOGGER.error(f"HTML file not found: {html_file}")
        LOGGER.info("Usage: python convert_single_html.py [path/to/file.html]")
        return 1
    
    # Create output filename
    output_file = html_file.parent / f"{html_file.stem}_converted.pdf"
    
    LOGGER.info("=" * 70)
    LOGGER.info("WeasyPrint HTML to PDF Converter")
    LOGGER.info("=" * 70)
    LOGGER.info("")
    
    success = convert_html_to_pdf(html_file, output_file)
    
    if success:
        LOGGER.info("")
        LOGGER.info("=" * 70)
        LOGGER.info("✨ Conversion complete!")
        LOGGER.info("")
        LOGGER.info("The PDF should include:")
        LOGGER.info("  ✓ A4-sized pages (210mm x 297mm)")
        LOGGER.info("  ✓ Table of Contents with page numbers")
        LOGGER.info("  ✓ Headers on left/right pages")
        LOGGER.info("  ✓ Footer page numbers")
        LOGGER.info("")
        LOGGER.info(f"Open the PDF to verify: {output_file}")
        LOGGER.info("=" * 70)
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
