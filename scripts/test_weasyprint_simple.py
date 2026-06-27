#!/usr/bin/env python3
"""
Simple test script to convert HTML to PDF using WeasyPrint.
Demonstrates that WeasyPrint handles CSS Paged Media without needing Paged.js.
"""

import sys
from pathlib import Path
from weasyprint import HTML, CSS
import time


def convert_html_to_pdf(html_path: Path, output_path: Path, remove_pagedjs: bool = False):
    """
    Convert HTML file to PDF using WeasyPrint.
    
    Args:
        html_path: Path to input HTML file
        output_path: Path to output PDF file
        remove_pagedjs: If True, removes the Paged.js script tag before processing
    """
    print(f"📄 Reading HTML from: {html_path}")
    
    # Read the HTML content
    html_content = html_path.read_text(encoding='utf-8')
    
    # Optionally remove the Paged.js script tag
    if remove_pagedjs:
        print("🔧 Removing Paged.js script tag...")
        original_length = len(html_content)
        html_content = html_content.replace(
            '<script src="https://unpkg.com/pagedjs/dist/paged.polyfill.js"></script>',
            '<!-- Paged.js script removed for WeasyPrint -->'
        )
        if len(html_content) != original_length:
            print("   ✓ Paged.js script tag removed")
        else:
            print("   ℹ No Paged.js script tag found")
    
    # Convert to PDF
    print("🔨 Generating PDF with WeasyPrint...")
    start_time = time.time()
    
    # Create HTML object from string
    html_doc = HTML(string=html_content, base_url=str(html_path.parent))
    
    # Write PDF
    html_doc.write_pdf(output_path)
    
    elapsed = time.time() - start_time
    
    # Get file size
    size_mb = output_path.stat().st_size / (1024 * 1024)
    
    print(f"✅ PDF generated successfully!")
    print(f"   Output: {output_path}")
    print(f"   Size: {size_mb:.2f} MB")
    print(f"   Time: {elapsed:.2f} seconds")
    
    return output_path


def main():
    # Setup paths
    repo_root = Path(__file__).parent.parent
    html_file = repo_root / "rut.html"
    output_dir = repo_root / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Check if input file exists
    if not html_file.exists():
        print(f"❌ Error: HTML file not found: {html_file}")
        sys.exit(1)
    
    print("=" * 70)
    print("WeasyPrint Simple Test")
    print("=" * 70)
    print()
    
    # Test 1: With Paged.js script tag (WeasyPrint will ignore it)
    print("Test 1: Converting HTML with Paged.js script tag")
    print("-" * 70)
    pdf_with_script = output_dir / "test_with_pagedjs_script.pdf"
    convert_html_to_pdf(html_file, pdf_with_script, remove_pagedjs=False)
    print()
    
    # Test 2: Without Paged.js script tag
    print("Test 2: Converting HTML with Paged.js script tag removed")
    print("-" * 70)
    pdf_without_script = output_dir / "test_without_pagedjs_script.pdf"
    convert_html_to_pdf(html_file, pdf_without_script, remove_pagedjs=True)
    print()
    
    print("=" * 70)
    print("✨ Both PDFs generated successfully!")
    print()
    print("Compare the two PDFs - they should be identical because:")
    print("  • WeasyPrint ignores JavaScript (including Paged.js)")
    print("  • WeasyPrint natively supports CSS Paged Media properties")
    print("  • target-counter(), @page rules, headers/footers work directly")
    print()
    print(f"Output directory: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
