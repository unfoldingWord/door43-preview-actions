#!/usr/bin/env python3
"""
Validate HTML structure: check for unclosed tags, malformed HTML, and structural issues.
Uses html.parser (stdlib) to detect problems without external dependencies.
"""

import sys
from pathlib import Path
from html.parser import HTMLParser
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


class HTMLValidator(HTMLParser):
    """Validate HTML structure and report issues."""
    
    # Self-closing tags that don't need closing tags
    VOID_ELEMENTS = {
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'link', 'meta', 'param', 'source', 'track', 'wbr'
    }
    
    def __init__(self):
        super().__init__()
        self.tag_stack = []
        self.errors = []
        self.warnings = []
        self.line_num = 1
        self.tag_positions = []
        self.unclosed_tags = []
        self.mismatched_tags = []
        self.duplicate_ids = defaultdict(list)
        self.all_ids = set()
        
    def handle_starttag(self, tag, attrs):
        # Track position
        position = self.getpos()
        
        # Check for duplicate IDs
        attrs_dict = dict(attrs)
        if 'id' in attrs_dict:
            id_value = attrs_dict['id']
            if id_value in self.all_ids:
                self.duplicate_ids[id_value].append(position)
                self.errors.append({
                    'type': 'duplicate_id',
                    'line': position[0],
                    'id': id_value,
                    'message': f"Duplicate ID '{id_value}' at line {position[0]}"
                })
            else:
                self.all_ids.add(id_value)
        
        # Only track non-void elements
        if tag not in self.VOID_ELEMENTS:
            self.tag_stack.append({
                'tag': tag,
                'line': position[0],
                'col': position[1],
                'attrs': attrs_dict
            })
    
    def handle_endtag(self, tag):
        position = self.getpos()
        
        # Void elements shouldn't have closing tags
        if tag in self.VOID_ELEMENTS:
            self.warnings.append({
                'type': 'void_closing_tag',
                'line': position[0],
                'tag': tag,
                'message': f"Unnecessary closing tag for void element <{tag}> at line {position[0]}"
            })
            return
        
        # Check if tag matches the most recent open tag
        if not self.tag_stack:
            self.errors.append({
                'type': 'unmatched_closing',
                'line': position[0],
                'tag': tag,
                'message': f"Closing tag </{tag}> at line {position[0]} has no matching opening tag"
            })
            return
        
        # Pop tags until we find a match
        found_match = False
        temp_stack = []
        
        while self.tag_stack:
            open_tag = self.tag_stack.pop()
            if open_tag['tag'] == tag:
                found_match = True
                break
            else:
                temp_stack.append(open_tag)
        
        if not found_match:
            # No match found - this is a mismatched closing tag
            self.errors.append({
                'type': 'mismatched_closing',
                'line': position[0],
                'tag': tag,
                'expected': temp_stack[-1]['tag'] if temp_stack else 'none',
                'message': f"Mismatched closing tag </{tag}> at line {position[0]}"
            })
            # Put tags back on stack
            self.tag_stack.extend(reversed(temp_stack))
        elif temp_stack:
            # We found a match but skipped other tags - they're unclosed
            for unclosed in temp_stack:
                self.warnings.append({
                    'type': 'implicitly_closed',
                    'line': unclosed['line'],
                    'tag': unclosed['tag'],
                    'message': f"Tag <{unclosed['tag']}> at line {unclosed['line']} was implicitly closed"
                })
    
    def close(self):
        """Called when parsing is complete."""
        super().close()
        
        # Any tags left on stack are unclosed
        for open_tag in self.tag_stack:
            self.errors.append({
                'type': 'unclosed_tag',
                'line': open_tag['line'],
                'tag': open_tag['tag'],
                'message': f"Unclosed tag <{open_tag['tag']}> opened at line {open_tag['line']}"
            })


def validate_html(html_path: Path) -> dict:
    """Validate HTML structure and return detailed report."""
    
    LOGGER.info(f"🔍 Validating HTML structure: {html_path.name}")
    
    try:
        html_content = html_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to read file: {e}",
            'errors': [],
            'warnings': []
        }
    
    validator = HTMLValidator()
    
    try:
        validator.feed(html_content)
        validator.close()
        
        return {
            'success': True,
            'errors': validator.errors,
            'warnings': validator.warnings,
            'duplicate_ids': dict(validator.duplicate_ids),
            'total_errors': len(validator.errors),
            'total_warnings': len(validator.warnings)
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f"Parse error: {e}",
            'errors': validator.errors,
            'warnings': validator.warnings
        }


def print_validation_report(result: dict, html_path: Path):
    """Print a formatted validation report."""
    
    print("=" * 80)
    print("HTML STRUCTURE VALIDATION REPORT")
    print("=" * 80)
    print()
    print(f"File: {html_path}")
    print(f"Size: {html_path.stat().st_size / (1024*1024):.2f} MB")
    print()
    
    if not result['success']:
        print("❌ VALIDATION FAILED")
        print(f"   Error: {result.get('error', 'Unknown error')}")
        print()
        return
    
    # Summary
    total_errors = result['total_errors']
    total_warnings = result['total_warnings']
    
    if total_errors == 0 and total_warnings == 0:
        print("✅ HTML IS WELL-FORMED")
        print("   No structural issues detected!")
        print()
    else:
        print(f"⚠️  ISSUES FOUND")
        print(f"   Errors:   {total_errors:5,}")
        print(f"   Warnings: {total_warnings:5,}")
        print()
    
    # Errors
    if result['errors']:
        print("❌ ERRORS (must be fixed)")
        print("-" * 80)
        
        # Group errors by type
        errors_by_type = defaultdict(list)
        for error in result['errors']:
            errors_by_type[error['type']].append(error)
        
        for error_type, errors in sorted(errors_by_type.items()):
            print(f"\n{error_type.upper().replace('_', ' ')} ({len(errors)} occurrences):")
            # Show first 10 of each type
            for error in errors[:10]:
                print(f"  Line {error['line']:5d}: {error['message']}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")
        print()
    
    # Warnings
    if result['warnings']:
        print("⚠️  WARNINGS (should be reviewed)")
        print("-" * 80)
        
        # Group warnings by type
        warnings_by_type = defaultdict(list)
        for warning in result['warnings']:
            warnings_by_type[warning['type']].append(warning)
        
        for warning_type, warnings in sorted(warnings_by_type.items()):
            print(f"\n{warning_type.upper().replace('_', ' ')} ({len(warnings)} occurrences):")
            # Show first 5 of each type
            for warning in warnings[:5]:
                print(f"  Line {warning['line']:5d}: {warning['message']}")
            if len(warnings) > 5:
                print(f"  ... and {len(warnings) - 5} more")
        print()
    
    # Duplicate IDs
    if result['duplicate_ids']:
        print("🔴 DUPLICATE IDs")
        print("-" * 80)
        for id_value, positions in sorted(result['duplicate_ids'].items())[:10]:
            print(f"  ID '{id_value}' appears at lines: {', '.join(str(p[0]) for p in positions)}")
        if len(result['duplicate_ids']) > 10:
            print(f"  ... and {len(result['duplicate_ids']) - 10} more duplicate IDs")
        print()
    
    # Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    if total_errors > 0:
        print("1. FIX CRITICAL ERRORS")
        print("   • Unclosed tags will cause rendering issues")
        print("   • Mismatched closing tags break document structure")
        print("   • Duplicate IDs violate HTML spec and break CSS/JS")
        print()
    
    if total_warnings > 0:
        print("2. REVIEW WARNINGS")
        print("   • Implicitly closed tags may indicate structural issues")
        print("   • Void element closing tags are redundant")
        print()
    
    if total_errors == 0 and total_warnings == 0:
        print("Your HTML structure is valid! ✨")
        print()
        print("Next steps:")
        print("  • Run optimize_html_structure.py to improve performance")
        print("  • Run analyze_div_optimization.py to find redundant divs")
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
    
    # Validate
    result = validate_html(html_file)
    
    # Print report
    print_validation_report(result, html_file)
    
    # Save report
    report_file = html_file.parent / f"{html_file.stem}_validation.txt"
    
    # Redirect print to file
    import io
    from contextlib import redirect_stdout
    
    with open(report_file, 'w', encoding='utf-8') as f:
        with redirect_stdout(f):
            print_validation_report(result, html_file)
    
    LOGGER.info(f"📄 Validation report saved to: {report_file}")
    
    # Return exit code
    return 1 if result['total_errors'] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
