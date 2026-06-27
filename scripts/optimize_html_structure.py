#!/usr/bin/env python3
"""
Optimize HTML structure for faster PDF rendering.
Applies regex-based transformations while preserving visual appearance.
"""

import sys
import re
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def remove_html_comments(html: str) -> tuple[str, int]:
    """Remove HTML comments."""
    original_len = len(html)
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    removed = original_len - len(html)
    return html, removed


def compress_whitespace(html: str) -> tuple[str, int]:
    """Remove unnecessary whitespace while preserving structure."""
    original_len = len(html)
    
    # Consolidate multiple spaces into one
    html = re.sub(r' {2,}', ' ', html)
    
    # Remove spaces around tags (but preserve single space between text)
    html = re.sub(r'>\s+<', '><', html)
    
    # Remove leading/trailing whitespace on lines
    lines = []
    for line in html.split('\n'):
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    html = '\n'.join(lines)
    
    removed = original_len - len(html)
    return html, removed


def flatten_empty_divs(html: str) -> tuple[str, int]:
    """Remove divs that only wrap another single element."""
    count = 0
    
    # Pattern: <div><SINGLE_ELEMENT>...</SINGLE_ELEMENT></div>
    # But only if the div has no attributes or only style
    pattern = r'<div(?:\s+style="[^"]*")?\s*>(\s*<(?!div)[^>]+>.*?</[^>]+>\s*)</div>'
    
    def replace_func(match):
        nonlocal count
        count += 1
        return match.group(1)  # Return just the inner element
    
    html = re.sub(pattern, replace_func, html, flags=re.DOTALL)
    
    return html, count


def remove_redundant_nested_divs(html: str) -> tuple[str, int]:
    """Remove patterns like <div><div>...</div></div>."""
    count = 0
    
    # Pattern: <div><div class="something">...</div></div>
    # Remove outer div if it has no attributes
    pattern = r'<div>\s*(<div[^>]*>.*?</div>)\s*</div>'
    
    def replace_func(match):
        nonlocal count
        count += 1
        return match.group(1)  # Return just the inner div
    
    # May need multiple passes
    for _ in range(3):
        html, changes = re.subn(pattern, replace_func, html, flags=re.DOTALL)
        if changes == 0:
            break
        count += changes
    
    return html, count


def consolidate_classes(html: str) -> tuple[str, dict]:
    """Find patterns that could use shared classes."""
    # This is informational - shows what could be optimized
    class_patterns = {}
    
    # Find all class attributes
    for match in re.finditer(r'class="([^"]+)"', html):
        classes = match.group(1)
        class_patterns[classes] = class_patterns.get(classes, 0) + 1
    
    # Find duplicated class combinations (used more than 100 times)
    common_patterns = {k: v for k, v in class_patterns.items() if v > 100}
    
    return html, common_patterns


def optimize_html_regex(html_path: Path, output_path: Path) -> dict:
    """Apply regex-based optimizations to HTML file."""
    
    LOGGER.info(f"📖 Reading HTML from: {html_path}")
    html = html_path.read_text(encoding='utf-8')
    original_size = len(html)
    
    stats = {
        'original_size': original_size,
    }
    
    # Apply optimizations
    LOGGER.info("1️⃣  Removing HTML comments...")
    html, removed = remove_html_comments(html)
    stats['comments_removed'] = removed
    
    LOGGER.info("2️⃣  Compressing whitespace...")
    html, removed = compress_whitespace(html)
    stats['whitespace_removed'] = removed
    
    LOGGER.info("3️⃣  Flattening empty div wrappers...")
    html, count = flatten_empty_divs(html)
    stats['empty_divs_removed'] = count
    
    LOGGER.info("4️⃣  Removing redundant nested divs...")
    html, count = remove_redundant_nested_divs(html)
    stats['nested_divs_removed'] = count
    
    LOGGER.info("5️⃣  Analyzing class usage patterns...")
    html, common_classes = consolidate_classes(html)
    stats['common_class_patterns'] = len(common_classes)
    
    stats['optimized_size'] = len(html)
    stats['size_reduction'] = original_size - stats['optimized_size']
    stats['size_reduction_pct'] = (stats['size_reduction'] / original_size) * 100
    
    # Save optimized HTML
    LOGGER.info(f"💾 Writing optimized HTML to: {output_path}")
    output_path.write_text(html, encoding='utf-8')
    
    return stats, common_classes


def optimize_html(html_path: Path, output_path: Path) -> dict:
    """Optimize HTML structure."""
    return optimize_html_regex(html_path, output_path)


def main():
    if len(sys.argv) > 1:
        html_file = Path(sys.argv[1])
    else:
        repo_root = Path(__file__).parent.parent
        html_file = repo_root / "gen.html"
    
    if not html_file.exists():
        LOGGER.error(f"HTML file not found: {html_file}")
        return 1
    
    # Create output filename
    output_file = html_file.parent / f"{html_file.stem}_optimized.html"
    
    LOGGER.info("=" * 70)
    LOGGER.info("HTML STRUCTURE OPTIMIZER")
    LOGGER.info("=" * 70)
    LOGGER.info("")
    
    try:
        stats, common_classes = optimize_html(html_file, output_file)
        
        # Print summary
        LOGGER.info("")
        LOGGER.info("=" * 70)
        LOGGER.info("✨ OPTIMIZATION COMPLETE")
        LOGGER.info("=" * 70)
        LOGGER.info("")
        LOGGER.info(f"Original size:      {stats['original_size'] / (1024*1024):8.2f} MB")
        LOGGER.info(f"Optimized size:     {stats['optimized_size'] / (1024*1024):8.2f} MB")
        LOGGER.info(f"Size reduction:     {stats['size_reduction'] / (1024*1024):8.2f} MB ({stats['size_reduction_pct']:.1f}%)")
        LOGGER.info("")
        LOGGER.info(f"Comments removed:               {stats['comments_removed'] / 1024:6,.0f} KB")
        LOGGER.info(f"Whitespace removed:             {stats['whitespace_removed'] / 1024:6,.0f} KB")
        LOGGER.info(f"Empty div wrappers removed:     {stats['empty_divs_removed']:6,}")
        LOGGER.info(f"Nested divs flattened:          {stats['nested_divs_removed']:6,}")
        LOGGER.info(f"Common class patterns found:    {stats['common_class_patterns']:6,}")
        LOGGER.info("")
        if common_classes:
            LOGGER.info("Most common class patterns (used 100+ times):")
            for classes, count in sorted(common_classes.items(), key=lambda x: x[1], reverse=True)[:5]:
                LOGGER.info(f"  '{classes}': {count:,} times")
            LOGGER.info("")
        LOGGER.info(f"Output file: {output_file}")
        LOGGER.info("")
        LOGGER.info("Next steps:")
        LOGGER.info("  1. Test PDF generation: python scripts/convert_single_html.py gen_optimized.html")
        LOGGER.info("  2. Compare rendering time with original")
        LOGGER.info("  3. Verify visual output matches original PDF")
        LOGGER.info("=" * 70)
        
        return 0
        
    except Exception as e:
        LOGGER.error(f"❌ Optimization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
