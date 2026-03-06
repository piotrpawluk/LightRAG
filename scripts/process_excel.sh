#!/bin/bash
#
# Wrapper script for excel_lightrag_query.py
# Makes it easier to run with the correct Python interpreter
#
# Usage:
#   ./scripts/process_excel.sh data.xlsx
#   ./scripts/process_excel.sh data.xlsx --backup
#   ./scripts/process_excel.sh data.xlsx --dry-run
#

set -e  # Exit on error

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Find Python interpreter
if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
elif command -v python &> /dev/null; then
    PYTHON="python"
else
    echo "Error: Python not found"
    exit 1
fi

# Check if Excel file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <excel-file> [options]"
    echo ""
    echo "Examples:"
    echo "  $0 data.xlsx"
    echo "  $0 data.xlsx --backup"
    echo "  $0 data.xlsx --dry-run"
    echo "  $0 data.xlsx --api-url http://localhost:9621 --backup"
    echo ""
    echo "For full help:"
    echo "  $PYTHON $SCRIPT_DIR/excel_lightrag_query.py --help"
    exit 1
fi

# Check if first argument is a file
EXCEL_FILE="$1"
shift  # Remove first argument

if [ ! -f "$EXCEL_FILE" ]; then
    echo "Error: File not found: $EXCEL_FILE"
    exit 1
fi

# Run the Python script
echo "Using Python: $PYTHON"
echo "Processing: $EXCEL_FILE"
echo ""

exec "$PYTHON" "$SCRIPT_DIR/excel_lightrag_query.py" \
    --excel-file "$EXCEL_FILE" \
    "$@"
