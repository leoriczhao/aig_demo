#!/bin/bash
# FullVision Demo 集成测试 (本地与CI共用)
#
# 以 simple_alu 跑一遍真实流水线 (yosys + iverilog + VPI):
#   - 若 build/waveform_completion 存在: 跑完整流水线, 验证使用 --strict
#   - 否则: 运行到 gtech 仿真 (trace 采集) 为止
#
# 用法: scripts/ci_integration.sh [output_dir]   (默认: ci_output)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUT_DIR="${1:-ci_output}"
TOP=simple_alu

cd "$PROJECT_DIR"
rm -rf "$OUT_DIR"

if [ -x build/waveform_completion ]; then
    MODE_ARGS=(--strict)
else
    echo "::warning::waveform_completion not built; integration test stops after gtech simulation"
    MODE_ARGS=(--stop-after gtech_sim)
fi

python3 orchestrator/pipeline.py \
    --dut "designs/$TOP/$TOP.v" \
    --testbench "designs/$TOP/testbench.v" \
    --top "$TOP" \
    --output-dir "$OUT_DIR" \
    "${MODE_ARGS[@]}"

# 产物检查: 存在且非空
expected=(
    "$OUT_DIR/aig/${TOP}.aag"
    "$OUT_DIR/aig/${TOP}_gtech.v"
    "$OUT_DIR/aig/${TOP}_mapping.json"
    "$OUT_DIR/aig/${TOP}_signals.txt"
    "$OUT_DIR/vcd/${TOP}_golden.vcd"
    "$OUT_DIR/traces/${TOP}.trace"
)
if [ -x build/waveform_completion ]; then
    expected+=("$OUT_DIR/vcd/${TOP}_completed.vcd")
fi

status=0
for f in "${expected[@]}"; do
    if [ -s "$f" ]; then
        echo "OK      $f"
    else
        echo "MISSING $f"
        status=1
    fi
done

# 映射JSON须可解析且包含被采样信号
python3 - "$OUT_DIR/aig/${TOP}_mapping.json" <<'EOF' || status=1
import json, sys
mapping = json.load(open(sys.argv[1]))
sampled = [n for n, info in mapping["signals"].items() if info.get("is_sampled")]
print(f"mapping: {len(mapping['signals'])} signals, {len(sampled)} sampled")
sys.exit(0 if sampled else 1)
EOF

exit $status
