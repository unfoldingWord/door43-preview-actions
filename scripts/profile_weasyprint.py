#!/usr/bin/env python3
"""
Profile WeasyPrint PDF generation to identify bottlenecks.
Tests with different CSS configurations to see what slows down rendering.
"""

import sys
import time
import re
from pathlib import Path
from weasyprint import HTML, CSS
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def time_conversion(html_content: str, output_path: Path, description: str, base_url: str) -> float:
    """Time a PDF conversion and return elapsed seconds."""
    LOGGER.info(f"\n{'='*70}")
    LOGGER.info(f"Testing: {description}")
    LOGGER.info(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        html_doc = HTML(string=html_content, base_url=base_url)
        html_doc.write_pdf(str(output_path))
        elapsed = time.time() - start_time
        size_mb = output_path.stat().st_size / (1024 * 1024)
        
        LOGGER.info(f"✅ Time: {elapsed:.2f}s ({elapsed/60:.1f}m)")
        LOGGER.info(f"   Size: {size_mb:.2f} MB")
        return elapsed
        
    except Exception as e:
        LOGGER.error(f"❌ Failed: {e}")
        return -1


def remove_css_features(html_content: str, feature: str) -> str:
    """Remove specific CSS features from HTML."""
    if feature == "page-breaks":
        # Remove page break properties
        html_content = re.sub(r'page-break-[^:]+:[^;]+;', '', html_content)
        html_content = re.sub(r'break-[^:]+:[^;]+;', '', html_content)
        
    elif feature == "headers-footers":
        # Remove @page headers/footers
        html_content = re.sub(r'@(top|bottom)-(left|center|right)\s*{[^}]+}', '', html_content)
        
    elif feature == "toc-page-numbers":
        # Remove target-counter (TOC page numbers)
        html_content = re.sub(r'content:\s*target-counter[^;]+;', 'content: "";', html_content)
        
    elif feature == "left-right-pages":
        # Remove @page :left and @page :right rules
        html_content = re.sub(r'@page\s*:(left|right)\s*{[^}]+}', '', html_content)
        
    elif feature == "all-page-rules":
        # Remove all @page rules except basic size
        # Keep only the first @page with size
        pages = re.findall(r'(@page[^{]*{[^}]+})', html_content, re.DOTALL)
        if pages:
            # Keep just the basic page with size
            basic_page = '@page { size: 210mm 297mm; margin: 1cm; }'
            html_content = re.sub(r'@page[^{]*{[^}]+}', '', html_content, flags=re.DOTALL)
            # Insert basic page at the start of style
            html_content = html_content.replace('<style>', f'<style>\n{basic_page}\n', 1)
    
    elif feature == "minimal":
        # Absolute minimal - just page size
        html_content = re.sub(r'@page[^{]*{[^}]+}', '', html_content, flags=re.DOTALL)
        basic_page = '@page { size: 210mm 297mm; margin: 2cm; }'
        html_content = html_content.replace('<style>', f'<style>\n{basic_page}\n', 1)
        
    return html_content


def main():
    # Get HTML file
    if len(sys.argv) > 1:
        html_file = Path(sys.argv[1])
    else:
        repo_root = Path(__file__).parent.parent
        html_file = repo_root / "gen.html"
    
    if not html_file.exists():
        LOGGER.error(f"HTML file not found: {html_file}")
        return 1
    
    LOGGER.info("📄 Reading HTML file...")
    html_content = html_file.read_text(encoding='utf-8')
    file_size_mb = len(html_content) / (1024 * 1024)
    LOGGER.info(f"   Size: {file_size_mb:.2f} MB")
    
    base_url = html_file.resolve().parent.as_uri() + '/'
    output_dir = html_file.parent / "profile_test"
    output_dir.mkdir(exist_ok=True)
    
    results = {}
    
    # Test 1: Full features (baseline)
    results['baseline'] = time_conversion(
        html_content,
        output_dir / "1_baseline.pdf",
        "BASELINE - All features enabled",
        base_url
    )
    
    # Test 2: Remove TOC page numbers (target-counter)
    modified = remove_css_features(html_content, "toc-page-numbers")
    results['no_toc_numbers'] = time_conversion(
        modified,
        output_dir / "2_no_toc_page_numbers.pdf",
        "NO TOC PAGE NUMBERS - Remove target-counter()",
        base_url
    )
    
    # Test 3: Remove headers and footers
    modified = remove_css_features(html_content, "headers-footers")
    results['no_headers_footers'] = time_conversion(
        modified,
        output_dir / "3_no_headers_footers.pdf",
        "NO HEADERS/FOOTERS - Remove @top/@bottom rules",
        base_url
    )
    
    # Test 4: Remove left/right page distinction
    modified = remove_css_features(html_content, "left-right-pages")
    results['no_left_right'] = time_conversion(
        modified,
        output_dir / "4_no_left_right.pdf",
        "NO LEFT/RIGHT PAGES - Remove @page :left/:right",
        base_url
    )
    
    # Test 5: Remove all @page rules except basic size
    modified = remove_css_features(html_content, "all-page-rules")
    results['minimal_pages'] = time_conversion(
        modified,
        output_dir / "5_minimal_pages.pdf",
        "MINIMAL PAGES - Only size and margin",
        base_url
    )
    
    # Test 6: Absolute minimal
    modified = remove_css_features(html_content, "minimal")
    results['absolute_minimal'] = time_conversion(
        modified,
        output_dir / "6_absolute_minimal.pdf",
        "ABSOLUTE MINIMAL - Just page size",
        base_url
    )
    
    # Summary
    LOGGER.info(f"\n\n{'='*70}")
    LOGGER.info("PERFORMANCE SUMMARY")
    LOGGER.info(f"{'='*70}\n")
    
    baseline_time = results.get('baseline', 0)
    
    for name, elapsed in results.items():
        if elapsed < 0:
            continue
        if name == 'baseline':
            LOGGER.info(f"  {name:20s}: {elapsed:6.1f}s ({elapsed/60:4.1f}m) [BASELINE]")
        else:
            diff = elapsed - baseline_time
            pct = (diff / baseline_time * 100) if baseline_time > 0 else 0
            speedup = "FASTER" if diff < 0 else "SLOWER"
            LOGGER.info(f"  {name:20s}: {elapsed:6.1f}s ({elapsed/60:4.1f}m) [{diff:+6.1f}s, {pct:+5.1f}% {speedup}]")
    
    LOGGER.info(f"\n{'='*70}")
    LOGGER.info("\nKEY FINDINGS:")
    LOGGER.info("  • Check which feature removal saves the most time")
    LOGGER.info("  • target-counter() for TOC page numbers can be expensive")
    LOGGER.info("  • Headers/footers add processing overhead")
    LOGGER.info("  • Left/right page distinction requires more passes")
    LOGGER.info(f"\nTest PDFs saved to: {output_dir}/")
    LOGGER.info(f"{'='*70}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
