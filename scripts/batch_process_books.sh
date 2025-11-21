#!/bin/bash
# Batch process all books one at a time to avoid memory issues
# Usage: ./scripts/batch_process_books.sh --repo en_ult --ref v87 [additional args]

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
ARGS=("$@")
REPO=""
REF=""

# Extract repo and ref from arguments
for i in "${!ARGS[@]}"; do
    if [[ "${ARGS[$i]}" == "--repo" ]]; then
        REPO="${ARGS[$((i+1))]}"
    fi
    if [[ "${ARGS[$i]}" == "--ref" ]]; then
        REF="${ARGS[$((i+1))]}"
    fi
done

if [ -z "$REPO" ] || [ -z "$REF" ]; then
    echo "Usage: $0 --repo <repo> --ref <ref> [additional args]"
    echo "Example: $0 --repo en_ult --ref v87 --backend weasyprint --verbose"
    exit 1
fi

# Get list of all books
ALL_BOOKS=(gen exo lev num deu jos jdg rut 1sa 2sa 1ki 2ki 1ch 2ch ezr neh est job psa pro ecc sng isa jer lam ezk dan hos jol amo oba jon mic nam hab zep hag zec mal mat mrk luk jhn act rom 1co 2co gal eph php col 1th 2th 1ti 2ti tit phm heb jas 1pe 2pe 1jn 2jn 3jn jud rev)

SUCCESSFUL=0
FAILED=0
FAILED_BOOKS=()

echo -e "${GREEN}Starting batch processing of ${#ALL_BOOKS[@]} books${NC}"
echo "Repo: $REPO, Ref: $REF"
echo "Additional args: ${ARGS[*]}"
echo ""

for BOOK in "${ALL_BOOKS[@]}"; do
    echo -e "${YELLOW}Processing $BOOK...${NC}"
    
    if python scripts/print_preview_pdf.py "${ARGS[@]}" --books "$BOOK"; then
        echo -e "${GREEN}✓ Successfully processed $BOOK${NC}"
        ((SUCCESSFUL++))
    else
        EXIT_CODE=$?
        echo -e "${RED}✗ Failed to process $BOOK (exit code: $EXIT_CODE)${NC}"
        ((FAILED++))
        FAILED_BOOKS+=("$BOOK")
    fi
    
    echo ""
done

# Print summary
echo "=========================================="
echo "BATCH PROCESSING SUMMARY"
echo "=========================================="
echo -e "${GREEN}Successful: $SUCCESSFUL${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED${NC}"
    echo "Failed books: ${FAILED_BOOKS[*]}"
else
    echo "Failed: 0"
fi
echo "=========================================="

exit 0
