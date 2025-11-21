#!/usr/bin/env python3
"""Rename existing PDF and HTML files to the new naming convention.

Old format: unfoldingWord--<repo>--<ref>--<BOOK>--<SIZE>.<ext>
New format: <repo>_<book#>-<BOOK>_<ref>_<SIZE>.<ext>

Example:
  unfoldingWord--en_tn--v87--ACT--LETTER.pdf -> en_tn_45-ACT_v87_LETTER.pdf
  unfoldingWord--en_tn--v87--MAT--A4.html -> en_tn_41-MAT_v87_A4.html
"""

import argparse
import re
import sys
from pathlib import Path

# Book number mapping (same as in print_preview_pdf.py)
BOOK_NUMBERS = {
    "GEN": 1, "EXO": 2, "LEV": 3, "NUM": 4, "DEU": 5, "JOS": 6, "JDG": 7, "RUT": 8,
    "1SA": 9, "2SA": 10, "1KI": 11, "2KI": 12, "1CH": 13, "2CH": 14, "EZR": 15,
    "NEH": 16, "EST": 17, "JOB": 18, "PSA": 19, "PRO": 20, "ECC": 21, "SNG": 22,
    "ISA": 23, "JER": 24, "LAM": 25, "EZK": 26, "DAN": 27, "HOS": 28, "JOL": 29,
    "AMO": 30, "OBA": 31, "JON": 32, "MIC": 33, "NAM": 34, "HAB": 35, "ZEP": 36,
    "HAG": 37, "ZEC": 38, "MAL": 39,
    # Book 40 is skipped (gap between testaments)
    "MAT": 41, "MRK": 42, "LUK": 43, "JHN": 44, "ACT": 45, "ROM": 46, "1CO": 47,
    "2CO": 48, "GAL": 49, "EPH": 50, "PHP": 51, "COL": 52, "1TH": 53, "2TH": 54,
    "1TI": 55, "2TI": 56, "TIT": 57, "PHM": 58, "HEB": 59, "JAS": 60, "1PE": 61,
    "2PE": 62, "1JN": 63, "2JN": 64, "3JN": 65, "JUD": 66, "REV": 67,
}

# Pattern: unfoldingWord--<repo>--<ref>--<BOOK>--<SIZE>.<ext>
OLD_PATTERN = re.compile(
    r"^unfoldingWord--(?P<repo>[^-]+)--(?P<ref>[^-]+)--(?P<book>[A-Z0-9]+)--(?P<size>A4|LETTER)\.(?P<ext>pdf|html)$"
)


def rename_file(file_path: Path, dry_run: bool = True) -> tuple[Path, Path] | None:
    """Rename a file from old to new format.
    
    Returns:
        Tuple of (old_path, new_path) if renamed, None if skipped
    """
    match = OLD_PATTERN.match(file_path.name)
    if not match:
        return None
    
    repo = match.group("repo")
    ref = match.group("ref")
    book = match.group("book")
    size = match.group("size")
    ext = match.group("ext")
    
    book_number = BOOK_NUMBERS.get(book)
    if book_number is None:
        print(f"WARNING: Unknown book code '{book}' in {file_path.name}", file=sys.stderr)
        return None
    
    # New format: <repo>_<book#>-<BOOK>_<ref>_<SIZE>.<ext>
    new_name = f"{repo}_{book_number:02d}-{book}_{ref}_{size}.{ext}"
    new_path = file_path.parent / new_name
    
    if new_path.exists() and new_path != file_path:
        print(f"WARNING: Target already exists: {new_name}", file=sys.stderr)
        return None
    
    if dry_run:
        print(f"Would rename: {file_path.name} -> {new_name}")
    else:
        file_path.rename(new_path)
        print(f"Renamed: {file_path.name} -> {new_name}")
    
    return (file_path, new_path)


def process_directory(directory: Path, dry_run: bool = True, recursive: bool = False):
    """Process all files in a directory."""
    pattern = "**/*" if recursive else "*"
    
    renamed_count = 0
    skipped_count = 0
    
    for file_path in directory.glob(pattern):
        if not file_path.is_file():
            continue
        
        if not (file_path.suffix in [".pdf", ".html"]):
            continue
        
        result = rename_file(file_path, dry_run=dry_run)
        if result:
            renamed_count += 1
        else:
            if OLD_PATTERN.match(file_path.name):
                skipped_count += 1
    
    return renamed_count, skipped_count


def main():
    parser = argparse.ArgumentParser(
        description="Rename PDF and HTML files to new naming convention",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview changes)
  python scripts/rename_files.py en_tn_v87

  # Actually rename files
  python scripts/rename_files.py en_tn_v87 --execute

  # Process multiple directories
  python scripts/rename_files.py en_tn_v87 en_ult_v87_titles --execute

  # Recursive (process subdirectories)
  python scripts/rename_files.py . --recursive --execute
        """,
    )
    parser.add_argument(
        "directories",
        nargs="+",
        type=Path,
        help="Directories containing files to rename",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually rename files (default is dry-run)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Process subdirectories recursively",
    )
    
    args = parser.parse_args()
    
    if not args.execute:
        print("DRY RUN MODE - no files will be renamed")
        print("Use --execute to actually rename files")
        print()
    
    total_renamed = 0
    total_skipped = 0
    
    for directory in args.directories:
        if not directory.exists():
            print(f"ERROR: Directory not found: {directory}", file=sys.stderr)
            continue
        
        if not directory.is_dir():
            print(f"ERROR: Not a directory: {directory}", file=sys.stderr)
            continue
        
        print(f"\nProcessing: {directory}")
        print("-" * 60)
        
        renamed, skipped = process_directory(
            directory,
            dry_run=not args.execute,
            recursive=args.recursive
        )
        
        total_renamed += renamed
        total_skipped += skipped
        
        print(f"\nSummary for {directory}:")
        print(f"  Renamed: {renamed}")
        print(f"  Skipped: {skipped}")
    
    print("\n" + "=" * 60)
    print(f"TOTAL: {total_renamed} renamed, {total_skipped} skipped")
    
    if not args.execute and total_renamed > 0:
        print("\nRe-run with --execute to perform the renames")


if __name__ == "__main__":
    main()
