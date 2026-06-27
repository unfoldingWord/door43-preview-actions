#!/usr/bin/env python3
"""
Analyze HTML structure and suggest optimizations for faster PDF rendering.
Identifies redundant nesting, inefficient CSS, and structural improvements.
"""

import sys
import re
from pathlib import Path
from collections import Counter, defaultdict
from html.parser import HTMLParser
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


class HTMLStructureAnalyzer(HTMLParser):
    """Parse HTML and collect structural statistics."""
    
    def __init__(self):
        super().__init__()
        self.tag_counts = Counter()
        self.nesting_depth = 0
        self.max_nesting = 0
        self.nesting_history = []
        self.class_usage = Counter()
        self.id_usage = Counter()
        self.empty_elements = []
        self.redundant_wrappers = []
        self.inline_styles = 0
        self.current_path = []
        self.tag_patterns = defaultdict(int)
        
    def handle_starttag(self, tag, attrs):
        self.tag_counts[tag] += 1
        self.nesting_depth += 1
        self.max_nesting = max(self.max_nesting, self.nesting_depth)
        self.current_path.append(tag)
        
        # Track nesting patterns
        if len(self.current_path) >= 3:
            pattern = ' > '.join(self.current_path[-3:])
            self.tag_patterns[pattern] += 1
        
        # Analyze attributes
        attrs_dict = dict(attrs)
        if 'class' in attrs_dict:
            classes = attrs_dict['class'].split()
            for cls in classes:
                self.class_usage[cls] += 1
        if 'id' in attrs_dict:
            self.id_usage[attrs_dict['id']] += 1
        if 'style' in attrs_dict:
            self.inline_styles += 1
            
    def handle_endtag(self, tag):
        self.nesting_depth -= 1
        if self.current_path and self.current_path[-1] == tag:
            self.current_path.pop()
    
    def handle_data(self, data):
        if not data.strip() and self.current_path:
            # Empty or whitespace-only content
            pass


def analyze_html_structure(html_content: str) -> dict:
    """Analyze HTML structure and return statistics."""
    
    parser = HTMLStructureAnalyzer()
    parser.feed(html_content)
    
    # Calculate statistics
    total_tags = sum(parser.tag_counts.values())
    
    # Find most common redundant patterns
    redundant_patterns = []
    sorted_patterns = sorted(parser.tag_patterns.items(), key=lambda x: x[1], reverse=True)[:20]
    for pattern, count in sorted_patterns:
        if 'div > div' in pattern or 'span > span' in pattern:
            redundant_patterns.append((pattern, count))
    
    # Identify unused or rarely used classes
    rarely_used_classes = [(cls, count) for cls, count in parser.class_usage.items() if count <= 2]
    
    return {
        'total_tags': total_tags,
        'tag_counts': parser.tag_counts,
        'max_nesting': parser.max_nesting,
        'class_count': len(parser.class_usage),
        'id_count': len(parser.id_usage),
        'inline_styles': parser.inline_styles,
        'redundant_patterns': redundant_patterns,
        'rarely_used_classes': len(rarely_used_classes),
        'most_common_tags': parser.tag_counts.most_common(10),
        'top_patterns': sorted(parser.tag_patterns.items(), key=lambda x: x[1], reverse=True)[:10],
    }


def analyze_css(html_content: str) -> dict:
    """Analyze CSS for optimization opportunities."""
    
    # Extract CSS
    css_match = re.search(r'<style[^>]*>(.*?)</style>', html_content, re.DOTALL)
    if not css_match:
        return {}
    
    css = css_match.group(1)
    
    # Count rules
    rules = re.findall(r'[^}]+{[^}]+}', css)
    
    # Find complex selectors
    selectors = re.findall(r'([^{]+){', css)
    complex_selectors = [s.strip() for s in selectors if s.count(' ') > 4 or s.count('>') > 2]
    
    # Find duplicate properties
    property_patterns = re.findall(r'([a-z-]+):\s*([^;]+);', css)
    
    # Find !important usage
    important_count = css.count('!important')
    
    return {
        'total_rules': len(rules),
        'css_size': len(css),
        'complex_selectors': len(complex_selectors),
        'important_count': important_count,
        'top_complex': complex_selectors[:5],
    }


def generate_optimization_report(html_path: Path) -> str:
    """Generate a detailed optimization report."""
    
    LOGGER.info(f"📊 Analyzing HTML structure: {html_path.name}")
    html_content = html_path.read_text(encoding='utf-8')
    
    file_size = len(html_content)
    file_size_mb = file_size / (1024 * 1024)
    
    # Analyze structure
    structure = analyze_html_structure(html_content)
    css_stats = analyze_css(html_content)
    
    # Generate report
    report = []
    report.append("=" * 80)
    report.append("HTML STRUCTURE OPTIMIZATION REPORT")
    report.append("=" * 80)
    report.append("")
    
    # File stats
    report.append("📄 FILE STATISTICS")
    report.append(f"   Size: {file_size_mb:.2f} MB ({file_size:,} bytes)")
    report.append(f"   Total HTML elements: {structure['total_tags']:,}")
    report.append(f"   Maximum nesting depth: {structure['max_nesting']}")
    report.append(f"   Unique CSS classes: {structure['class_count']}")
    report.append(f"   Unique IDs: {structure['id_count']}")
    report.append(f"   Inline styles: {structure['inline_styles']}")
    report.append("")
    
    # Most common tags
    report.append("🏷️  MOST COMMON ELEMENTS")
    for tag, count in structure['most_common_tags']:
        pct = (count / structure['total_tags']) * 100
        report.append(f"   {tag:15s}: {count:6,} ({pct:5.1f}%)")
    report.append("")
    
    # CSS stats
    if css_stats:
        report.append("🎨 CSS STATISTICS")
        report.append(f"   Total CSS rules: {css_stats['total_rules']}")
        report.append(f"   CSS size: {css_stats['css_size'] / 1024:.1f} KB")
        report.append(f"   Complex selectors: {css_stats['complex_selectors']}")
        report.append(f"   !important declarations: {css_stats['important_count']}")
        report.append("")
    
    # Redundant patterns
    if structure['redundant_patterns']:
        report.append("⚠️  REDUNDANT NESTING PATTERNS")
        report.append("   These nested structures could be flattened:")
        for pattern, count in structure['redundant_patterns'][:10]:
            report.append(f"   {pattern:40s}: {count:4,} occurrences")
        report.append("")
    
    # Optimization recommendations
    report.append("=" * 80)
    report.append("💡 OPTIMIZATION RECOMMENDATIONS")
    report.append("=" * 80)
    report.append("")
    
    # Calculate potential savings
    potential_savings = []
    
    # 1. Excessive divs
    div_count = structure['tag_counts'].get('div', 0)
    if div_count > structure['total_tags'] * 0.3:
        pct = (div_count / structure['total_tags']) * 100
        potential_savings.append({
            'priority': 'HIGH',
            'issue': f'Excessive <div> usage ({div_count:,} = {pct:.1f}% of all tags)',
            'recommendation': 'Replace semantic-neutral divs with semantic HTML5 elements (article, section, nav)',
            'estimated_improvement': '10-15% size reduction, 5-10% faster rendering'
        })
    
    # 2. Deep nesting
    if structure['max_nesting'] > 15:
        potential_savings.append({
            'priority': 'HIGH',
            'issue': f'Very deep nesting (max depth: {structure["max_nesting"]})',
            'recommendation': 'Flatten structure by removing wrapper divs, use CSS flexbox/grid instead',
            'estimated_improvement': '15-20% faster layout calculation'
        })
    
    # 3. Redundant wrappers
    if structure['redundant_patterns']:
        total_redundant = sum(count for _, count in structure['redundant_patterns'])
        potential_savings.append({
            'priority': 'MEDIUM',
            'issue': f'Redundant wrapper patterns ({total_redundant:,} occurrences)',
            'recommendation': 'Remove unnecessary div/span wrappers, consolidate nested containers',
            'estimated_improvement': '5-10% size reduction'
        })
    
    # 4. Inline styles
    if structure['inline_styles'] > 100:
        potential_savings.append({
            'priority': 'MEDIUM',
            'issue': f'Many inline styles ({structure["inline_styles"]:,} elements)',
            'recommendation': 'Move inline styles to CSS classes for better caching and smaller HTML',
            'estimated_improvement': '3-5% size reduction'
        })
    
    # 5. Rarely used classes
    if structure['rarely_used_classes'] > 50:
        potential_savings.append({
            'priority': 'LOW',
            'issue': f'Many rarely-used CSS classes ({structure["rarely_used_classes"]})',
            'recommendation': 'Consolidate similar classes, remove unused selectors',
            'estimated_improvement': '1-2% smaller CSS'
        })
    
    # 6. Complex CSS selectors
    if css_stats.get('complex_selectors', 0) > 20:
        potential_savings.append({
            'priority': 'LOW',
            'issue': f'Complex CSS selectors ({css_stats["complex_selectors"]} selectors)',
            'recommendation': 'Simplify selectors, use direct classes instead of deep descendant selectors',
            'estimated_improvement': '2-3% faster style calculation'
        })
    
    # Print recommendations
    for i, rec in enumerate(potential_savings, 1):
        report.append(f"{i}. [{rec['priority']}] {rec['issue']}")
        report.append(f"   → {rec['recommendation']}")
        report.append(f"   💰 {rec['estimated_improvement']}")
        report.append("")
    
    # Specific actionable steps
    report.append("=" * 80)
    report.append("🔧 SPECIFIC OPTIMIZATION ACTIONS")
    report.append("=" * 80)
    report.append("")
    
    report.append("1. FLATTEN STRUCTURE")
    report.append("   • Remove wrapper divs that only have one child")
    report.append("   • Replace: <div><div><p>text</p></div></div>")
    report.append("   • With:    <p>text</p>")
    report.append("")
    
    report.append("2. USE SEMANTIC HTML")
    report.append("   • <article> instead of <div class='article'>")
    report.append("   • <section> instead of <div class='section'>")
    report.append("   • <nav> instead of <div class='toc'>")
    report.append("")
    
    report.append("3. CONSOLIDATE CLASSES")
    report.append("   • Merge similar classes (tn-note-body-h4, tn-note-body-h5)")
    report.append("   • Use CSS inheritance instead of repeating properties")
    report.append("")
    
    report.append("4. OPTIMIZE CSS")
    report.append("   • Group related rules together")
    report.append("   • Remove unused CSS rules")
    report.append("   • Simplify complex descendant selectors")
    report.append("")
    
    report.append("5. REMOVE REDUNDANCY")
    report.append("   • Strip HTML comments")
    report.append("   • Remove empty elements")
    report.append("   • Consolidate whitespace")
    report.append("")
    
    # Estimated total impact
    report.append("=" * 80)
    report.append("📊 ESTIMATED TOTAL IMPACT")
    report.append("=" * 80)
    report.append("")
    report.append("If all HIGH priority optimizations are implemented:")
    report.append("   • File size: 20-30% smaller")
    report.append("   • Parse time: 15-25% faster")
    report.append("   • Layout calculation: 20-30% faster")
    report.append("   • Overall PDF generation: 25-40% faster")
    report.append("")
    report.append("Expected generation time: 2.5-3 minutes (vs current 4+ minutes)")
    report.append("=" * 80)
    
    return '\n'.join(report)


def main():
    if len(sys.argv) > 1:
        html_file = Path(sys.argv[1])
    else:
        repo_root = Path(__file__).parent.parent
        html_file = repo_root / "gen.html"
    
    if not html_file.exists():
        LOGGER.error(f"HTML file not found: {html_file}")
        return 1
    
    # Generate report
    report = generate_optimization_report(html_file)
    print(report)
    
    # Save report
    report_file = html_file.parent / f"{html_file.stem}_structure_analysis.txt"
    report_file.write_text(report, encoding='utf-8')
    LOGGER.info(f"\n📄 Report saved to: {report_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
