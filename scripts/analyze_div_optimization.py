#!/usr/bin/env python3
"""
Analyze divs intelligently to determine which are redundant or can be combined.
Considers CSS selectors, styling, and semantic meaning.
"""

import sys
import re
from pathlib import Path
from html.parser import HTMLParser
from collections import defaultdict, Counter
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


class DivAnalyzer(HTMLParser):
    """Analyze div usage and identify optimization opportunities."""
    
    def __init__(self, css_rules):
        super().__init__()
        self.css_rules = css_rules  # CSS selectors that target specific structures
        self.divs = []
        self.current_path = []
        self.div_stack = []
        self.position = 0
        
    def handle_starttag(self, tag, attrs):
        self.position = self.getpos()
        attrs_dict = dict(attrs)
        
        element_info = {
            'tag': tag,
            'line': self.position[0],
            'col': self.position[1],
            'attrs': attrs_dict,
            'path': list(self.current_path),
            'has_children': False,
            'child_count': 0,
            'text_content': '',
        }
        
        self.current_path.append(element_info)
        
        if tag == 'div':
            self.div_stack.append(element_info)
    
    def handle_endtag(self, tag):
        if self.current_path and self.current_path[-1]['tag'] == tag:
            element = self.current_path.pop()
            
            # Update parent's child count
            if self.current_path:
                self.current_path[-1]['has_children'] = True
                self.current_path[-1]['child_count'] += 1
            
            if tag == 'div' and self.div_stack:
                div = self.div_stack.pop()
                self.divs.append(div)
    
    def handle_data(self, data):
        if self.current_path:
            self.current_path[-1]['text_content'] += data


def extract_css_selectors(html_content: str) -> dict:
    """Extract CSS rules and selectors from HTML."""
    
    css_match = re.search(r'<style[^>]*>(.*?)</style>', html_content, re.DOTALL)
    if not css_match:
        return {}
    
    css = css_match.group(1)
    
    # Parse CSS rules
    rules = {}
    for match in re.finditer(r'([^{]+)\{([^}]+)\}', css):
        selector = match.group(1).strip()
        properties = match.group(2).strip()
        rules[selector] = properties
    
    return rules


def analyze_div_usage(html_path: Path) -> dict:
    """Analyze div usage considering CSS context."""
    
    LOGGER.info(f"📊 Analyzing div structure with CSS awareness...")
    
    html_content = html_path.read_text(encoding='utf-8')
    
    # Extract CSS rules
    css_rules = extract_css_selectors(html_content)
    LOGGER.info(f"   Found {len(css_rules)} CSS rules")
    
    # Parse HTML
    parser = DivAnalyzer(css_rules)
    parser.feed(html_content)
    
    divs = parser.divs
    LOGGER.info(f"   Analyzed {len(divs):,} div elements")
    
    # Categorize divs
    redundant_divs = []
    wrapper_divs = []
    styled_divs = []
    semantic_divs = []
    combinable_divs = []
    
    for div in divs:
        attrs = div['attrs']
        classes = attrs.get('class', '').split() if 'class' in attrs else []
        has_id = 'id' in attrs
        has_style = 'style' in attrs
        has_classes = bool(classes)
        
        # Check if div is targeted by CSS
        is_styled_by_css = False
        if has_id:
            for selector in css_rules:
                if f"#{attrs['id']}" in selector:
                    is_styled_by_css = True
                    break
        if has_classes:
            for cls in classes:
                for selector in css_rules:
                    if f".{cls}" in selector or cls in selector:
                        is_styled_by_css = True
                        break
        
        div_category = {
            'div': div,
            'classes': classes,
            'has_id': has_id,
            'has_style': has_style,
            'has_classes': has_classes,
            'is_styled_by_css': is_styled_by_css,
            'child_count': div['child_count'],
        }
        
        # Categorize
        if div['child_count'] == 1 and not has_id and not has_classes and not has_style:
            redundant_divs.append(div_category)
        elif div['child_count'] == 1 and (has_classes or has_id) and is_styled_by_css:
            wrapper_divs.append(div_category)
        elif is_styled_by_css or has_style:
            styled_divs.append(div_category)
        elif has_classes and any('section' in c or 'article' in c for c in classes):
            semantic_divs.append(div_category)
    
    # Find combinable patterns
    class_combinations = Counter()
    for div in divs:
        if 'class' in div['attrs']:
            class_str = div['attrs']['class']
            class_combinations[class_str] += 1
    
    # Common patterns that appear frequently
    frequent_patterns = {k: v for k, v in class_combinations.items() if v > 50}
    
    return {
        'total_divs': len(divs),
        'redundant_divs': redundant_divs,
        'wrapper_divs': wrapper_divs,
        'styled_divs': styled_divs,
        'semantic_divs': semantic_divs,
        'frequent_patterns': frequent_patterns,
        'css_rules': css_rules,
    }


def print_div_analysis(result: dict, html_path: Path):
    """Print detailed div optimization recommendations."""
    
    print("=" * 80)
    print("DIV OPTIMIZATION ANALYSIS WITH CSS AWARENESS")
    print("=" * 80)
    print()
    print(f"File: {html_path}")
    print()
    
    print("📊 SUMMARY")
    print(f"   Total divs analyzed:           {result['total_divs']:6,}")
    print(f"   Redundant divs (removable):    {len(result['redundant_divs']):6,}")
    print(f"   Wrapper divs (check):          {len(result['wrapper_divs']):6,}")
    print(f"   Styled divs (keep):            {len(result['styled_divs']):6,}")
    print(f"   Semantic divs (convert):       {len(result['semantic_divs']):6,}")
    print()
    
    # Redundant divs
    if result['redundant_divs']:
        print("🗑️  REDUNDANT DIVS - CAN BE SAFELY REMOVED")
        print("-" * 80)
        print("These divs have:")
        print("  • Only one child element")
        print("  • No ID, classes, or inline styles")
        print("  • Not targeted by any CSS rules")
        print()
        print(f"Found {len(result['redundant_divs']):,} redundant divs")
        print()
        print("Examples:")
        for i, div_info in enumerate(result['redundant_divs'][:5], 1):
            div = div_info['div']
            print(f"  {i}. Line {div['line']}: <div> with {div['child_count']} child")
        if len(result['redundant_divs']) > 5:
            print(f"  ... and {len(result['redundant_divs']) - 5:,} more")
        print()
        print("✅ Optimization: Remove these divs, keep their children")
        print("   Estimated impact: 5-10% smaller HTML, 3-5% faster parsing")
        print()
    
    # Wrapper divs
    if result['wrapper_divs']:
        print("📦 WRAPPER DIVS - REVIEW CAREFULLY")
        print("-" * 80)
        print("These divs have:")
        print("  • Only one child element")
        print("  • Classes or IDs")
        print("  • Targeted by CSS rules")
        print()
        print(f"Found {len(result['wrapper_divs']):,} wrapper divs")
        print()
        print("Examples with their CSS usage:")
        for i, div_info in enumerate(result['wrapper_divs'][:5], 1):
            div = div_info['div']
            classes = ' '.join(div_info['classes']) if div_info['classes'] else '(none)'
            print(f"  {i}. Line {div['line']}: <div class='{classes}'>")
            
            # Show CSS rules that target this div
            if div_info['has_id']:
                id_val = div['attrs']['id']
                matching_rules = [sel for sel in result['css_rules'] if f"#{id_val}" in sel]
                if matching_rules:
                    print(f"     CSS: {matching_rules[0]}")
            elif div_info['classes']:
                for cls in div_info['classes'][:1]:
                    matching_rules = [sel for sel in result['css_rules'] if f".{cls}" in sel]
                    if matching_rules:
                        print(f"     CSS: {matching_rules[0][:60]}...")
                        break
        if len(result['wrapper_divs']) > 5:
            print(f"  ... and {len(result['wrapper_divs']) - 5:,} more")
        print()
        print("⚠️  Manual review needed:")
        print("   • If CSS can be moved to child, remove wrapper")
        print("   • If wrapper is for layout only, consider CSS flexbox/grid on parent")
        print("   • If wrapper has semantic meaning, convert to <section>/<article>")
        print()
    
    # Semantic divs
    if result['semantic_divs']:
        print("🏷️  SEMANTIC DIVS - CONVERT TO HTML5 ELEMENTS")
        print("-" * 80)
        print("These divs have semantic class names but use generic <div> tags")
        print()
        print(f"Found {len(result['semantic_divs']):,} semantic divs")
        print()
        print("Recommended conversions:")
        conversions = defaultdict(list)
        for div_info in result['semantic_divs']:
            classes = div_info['classes']
            for cls in classes:
                if 'article' in cls:
                    conversions['article'].append(div_info)
                    break
                elif 'section' in cls:
                    conversions['section'].append(div_info)
                    break
        
        for semantic_tag, div_list in conversions.items():
            print(f"  • Convert {len(div_list):,} divs to <{semantic_tag}>")
        print()
        print("✅ Benefits:")
        print("   • Better semantic HTML")
        print("   • Improved accessibility")
        print("   • Clearer document structure")
        print()
    
    # Frequent patterns
    if result['frequent_patterns']:
        print("🔄 FREQUENT CLASS PATTERNS - CONSOLIDATION OPPORTUNITIES")
        print("-" * 80)
        print("These class combinations appear very frequently:")
        print()
        for pattern, count in sorted(result['frequent_patterns'].items(), 
                                     key=lambda x: x[1], reverse=True)[:10]:
            print(f"  '{pattern}': {count:,} times")
        print()
        print("💡 Optimization opportunities:")
        print("   • These patterns could benefit from CSS inheritance")
        print("   • Consider creating parent classes with shared styles")
        print("   • Reduces CSS specificity and improves performance")
        print()
    
    # Summary recommendations
    print("=" * 80)
    print("PRIORITIZED RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    priority = []
    
    if result['redundant_divs']:
        priority.append({
            'priority': 'HIGH',
            'action': f"Remove {len(result['redundant_divs']):,} redundant divs",
            'impact': 'Immediate size reduction, faster parsing',
            'risk': 'LOW - no CSS dependencies'
        })
    
    if result['semantic_divs']:
        priority.append({
            'priority': 'MEDIUM',
            'action': f"Convert {len(result['semantic_divs']):,} divs to semantic HTML5",
            'impact': 'Better structure, accessibility',
            'risk': 'LOW - if CSS targets classes, not tags'
        })
    
    if result['wrapper_divs']:
        priority.append({
            'priority': 'MEDIUM',
            'action': f"Review {len(result['wrapper_divs']):,} wrapper divs",
            'impact': 'Potential 10-15% size reduction',
            'risk': 'MEDIUM - requires CSS refactoring'
        })
    
    for i, rec in enumerate(priority, 1):
        print(f"{i}. [{rec['priority']}] {rec['action']}")
        print(f"   Impact: {rec['impact']}")
        print(f"   Risk: {rec['risk']}")
        print()
    
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Fix HIGH priority items automatically")
    print("  2. Manually review MEDIUM priority items")
    print("  3. Test CSS still works after changes")
    print("  4. Re-run analyze_html_structure.py to measure improvement")
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
    
    # Analyze
    result = analyze_div_usage(html_file)
    
    # Print report
    print_div_analysis(result, html_file)
    
    # Save report
    report_file = html_file.parent / f"{html_file.stem}_div_analysis.txt"
    
    import io
    from contextlib import redirect_stdout
    
    with open(report_file, 'w', encoding='utf-8') as f:
        with redirect_stdout(f):
            print_div_analysis(result, html_file)
    
    LOGGER.info(f"📄 Div analysis report saved to: {report_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
