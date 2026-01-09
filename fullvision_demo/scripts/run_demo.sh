#!/bin/bash
# FullVision Demo 运行脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "FullVision Demo"
echo "=========================================="
echo

# 检查工具
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo "ERROR: $1 not found. Please install it first."
        exit 1
    fi
}

echo "Checking tools..."
check_tool yosys
check_tool python3
echo "  yosys: OK"
echo "  python3: OK"

# 可选工具
if command -v iverilog &> /dev/null; then
    echo "  iverilog: OK"
else
    echo "  iverilog: NOT FOUND (simulation will be skipped)"
fi

echo

# 运行流水线
echo "Running pipeline..."
cd "$PROJECT_DIR"
python3 orchestrator/pipeline.py "$@"

echo
echo "Done!"
