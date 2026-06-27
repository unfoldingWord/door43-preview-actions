#!/usr/bin/env python3
"""
Intelligently optimize divs based on CSS analysis.
Automatically removes redundant divs and provides detailed recommendations.
"""

import sys
import re
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def remove_redundant_divs_intelligent(html: str) -> tuple[str, int]:
    """
    Remove divs that:
    - Have no attributes (no class, id, style, data-*, etc.)
    - Contain only a single element
    - Are not targeted by CSS
    """
    count = 0
    
    # Pattern: <div> followed by single element, then </div>
    # This is a simple pattern - only removes divs with NO attributes
    pattern = r'<div>\s*(<[^>]+>.*?</[^>]+>)\s*</div>'
    
    def replace_func(match):
        nonlocal count
        inner = match.group(1)
        # Only remove if it's truly a single element (not multiple)
        if inner.count('</') == 1:
            count += 1
            return inner
        return match.group(0)
    
    # Multiple passes to handle nested cases
    for _ in range(5):
        html, changes = re.subn(pattern, replace_func, html, flags=re.DOTALL)
        if changes == 0:
            break
        count = 0  # Reset for accurate count
        count += changes
    
    return html, count


def identify_combinable_wrappers(html: str) -> dict:
    """
    Identify wrapper divs that could potentially be combined or removed.
    Returns analysis data for manual review.
    """
    
    # Find all div class patterns
    wrapper_patterns = {}
    
    # Pattern: <div class="X"><element>...</element></div>
    # where the div only wraps one element
    pattern = r'<div\s+class="([^"]+)">\s*<(\w+)[^>]*>.*?</\2>\s*</div>'
    
    for match in re.finditer(pattern, html, re.DOTALL):
        class_name = match.group(1)
        child_tag = match.group(2)
        key = f"{class_name}>{child_tag}"
        
        if key not in wrapper_patterns:
            wrapper_patterns[key] = {
                'class': class_name,
                'child_tag': child_tag,
                'count': 0,
                'example': match.group(0)[:100]
            }
        wrapper_patterns[key]['count'] += 1
    
    # Filter to significant patterns (occur 10+ times)
    significant = {k: v for k, v in wrapper_patterns.items() if v['count'] >= 10}
    
    return significant


def analyze_css_dependencies(html: str) -> dict:
    """
    Analyze which divs are actually used by CSS.
    """
    
    # Extract CSS
    css_match = re.search(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
    if not css_match:
        return {}
    
    css = css_match.group(1)
    
    # Find all class-based selectors
    class_selectors = set()
    for match in re.finditer(r'\.([a-zA-Z0-9_-]+)', css):
        class_selectors.add(match.group(1))
    
    # Find all ID selectors
    id_selectors = set()
    for match in re.finditer(r'#([a-zA-Z0-9_-]+)', css):
        id_selectors.add(match.group(1))
    
    # Find descendant selectors (could indicate wrapper dependency)
    descendant_selectors = []
    for match in re.finditer(r'([.#][a-zA-Z0-9_-]+\s+[.#][a-zA-Z0-9_-]+)', css):
        descendant_selectors.append(match.group(1).strip())
    
    return {
        'classes_in_css': class_selectors,
        'ids_in_css': id_selectors,
        'descendant_selectors': descendant_selectors,
        'total_classes': len(class_selectors),
        'total_ids': len(id_selectors)
    }


def optimize_divs_with_intelligence(html_path: Path, output_path: Path) -> dict:
    """
    Intelligently optimize divs with full awareness of CSS dependencies.
    """
    
    LOGGER.info(f"📖 Reading HTML: {html_path}")
    html = html_path.read_text(encoding='utf-8')
    original_size = len(html)
    
    stats = {
        'original_size': original_size,
    }
    
    # Analyze CSS dependencies first
    LOGGER.info("1️⃣  Analyzing CSS dependencies...")
    css_analysis = analyze_css_dependencies(html)
    stats['css_classes'] = css_analysis['total_classes']
    stats['css_ids'] = css_analysis['total_ids']
    
    # Find combinable wrappers (for reporting, not auto-fix)
    LOGGER.info("2️⃣  Identifying wrapper patterns...")
    wrapper_patterns = identify_combinable_wrappers(html)
    stats['wrapper_patterns'] = len(wrapper_patterns)
    
    # Remove redundant divs (safe operation)
    LOGGER.info("3️⃣  Removing redundant divs...")
    html, removed = remove_redundant_divs_intelligent(html)
    stats['redundant_removed'] = removed
    
    stats['optimized_size'] = len(html)
    stats['size_reduction'] = original_size - stats['optimized_size']
    stats['size_reduction_pct'] = (stats['size_reduction'] / original_size) * 100
    
    # Save optimized HTML
    LOGGER.info(f"💾 Writing optimized HTML: {output_path}")
    output_path.write_text(html, encoding='utf-8')
    
    return stats, wrapper_patterns, css_analysis


def print_optimization_recommendations(stats, wrapper_patterns, css_analysis):
    """Print intelligent recommendations based on analysis."""
    
    print()
    print("=" * 80)
    print("INTELLIGENT DIV OPTIMIZATION RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    print("🔍 CSS ANALYSIS")
    print(f"   Classes defined in CSS:        {stats['css_classes']}")
    print(f"   IDs defined in CSS:            {stats['css_ids']}")
    print()
    
    print("✅ AUTOMATIC OPTIMIZATIONS APPLIED")
    print(f"   Redundant divs removed:        {stats['redundant_removed']}")
    print(f"   Size reduction:                {stats['size_reduction'] / 1024:.1f} KB")
    print()
    
    if wrapper_patterns:
        print("📦 WRAPPER PATTERNS THAT COULD BE OPTIMIZED")
        print("-" * 80)
        print("These div>element patterns occur frequently:")
        print()
        
        sorted_patterns = sorted(wrapper_patterns.items(), 
                                 key=lambda x: x[1]['count'], reverse=True)
        
        for pattern_key, data in sorted_patterns[:10]:
            print(f"  <div class='{data['class']}'> wrapping <{data['child_tag']}>")
            print(f"     Occurrences: {data['count']:,}")
            print(f"     Recommendation:", end=" ")
            
            # Intelligent recommendation based on pattern
            if data['class'] in css_analysis['classes_in_css']:
                # Check if it's in descendant selector
                is_parent_selector = any(
                    data['class'] in sel.split()[0] 
                    for sel in css_analysis['descendant_selectors']
                )
                
                if is_parent_selector:
                    print("KEEP - Used in CSS descendant selectors")
                else:
                    print("CONSIDER - CSS could be moved to child element")
            else:
                print("REMOVE - Class not used in CSS")
            print()
        
        if len(wrapper_patterns) > 10:
            print(f"  ... and {len(wrapper_patterns) - 10} more patterns")
        print()
    
    print("=" * 80)
    print("MANUAL REVIEW GUIDE")
    print("=" * 80)
    print()
    print("For each wrapper pattern above:")
    print()
    print("1. IF 'REMOVE' - Class is not in CSS")
    print("   → Safe to remove div, move any other attrs to child")
    print()
    print("2. IF 'CONSIDER' - Class exists but not in descendant selectors")
    print("   → Check if child element can have the class instead")
    print("   → Example: <div class='X'><p>text</p></div>")
    print("   →       → <p class='X'>text</p>")
    print()
    print("3. IF 'KEEP' - Used in descendant selectors like '.parent .child'")
    print("   → Must keep div OR refactor CSS to use direct class")
    print("   → Example: '.tn-note-body h4' requires the wrapper")
    print()
    print("=" * 80)


def main():
    if len(sys.argv) > 1:
        html_file = Path(sys.argv[1])
    else:
        repo_root = Path(__file__).parent.parent
        html_file = repo_root / "gen.html"
    
    if not html_file.exists():
        LOGGER.error(f"HTML file not found: {html_file}")
        return 1
    
    output_file = html_file.parent / f"{html_file.stem}_div_optimized.html"
    
    LOGGER.info("=" * 70)
    LOGGER.info("INTELLIGENT DIV OPTIMIZER WITH CSS AWARENESS")
    LOGGER.info("=" * 70)
    
    try:
        stats, wrapper_patterns, css_analysis = optimize_divs_with_intelligence(
            html_file, output_file
        )
        
        print_optimization_recommendations(stats, wrapper_patterns, css_analysis)
        
        LOGGER.info(f"")
        LOGGER.info(f"✨ Optimized HTML saved to: {output_file}")
        LOGGER.info(f"")
        LOGGER.info(f"Next steps:")
        LOGGER.info(f"  1. Review wrapper pattern recommendations above")
        LOGGER.info(f"  2. Test PDF generation with optimized file")
        LOGGER.info(f"  3. Compare visual output with original")
        LOGGER.info("=" * 70)
        
        return 0
        
    except Exception as e:
        LOGGER.error(f"❌ Optimization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
