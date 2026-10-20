#!/bin/bash
# FullVision Demo 构建脚本 (本地与CI共用)
#
# 构建:
#   1. Yosys signal_mapper 插件   (需要 yosys-config)
#   2. VPI trace_collector 模块   (需要 iverilog-vpi)
#   3. waveform_completion (C++) (需要源码与 ../mockturtle, 缺失时跳过)
#
# 环境变量:
#   REQUIRE_COMPLETION=1  缺少 waveform_completion 源码时报错而不是跳过

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MOCKTURTLE_DIR="$(dirname "$PROJECT_DIR")/mockturtle"
JOBS="$(nproc 2>/dev/null || echo 2)"

echo "== [1/3] Yosys plugin: signal_mapper.so"
make -C "$PROJECT_DIR/compiler/yosys_plugin"

echo "== [2/3] VPI module: trace_collector.vpi"
make -C "$PROJECT_DIR/runtime/vpi"

echo "== [3/3] waveform_completion"
if [ ! -f "$PROJECT_DIR/waveform_completion/src/main.cpp" ]; then
    echo "WARNING: waveform_completion/src not found, skipping C++ build"
    if [ "${REQUIRE_COMPLETION:-0}" = "1" ]; then
        exit 1
    fi
    exit 0
fi
if [ ! -d "$MOCKTURTLE_DIR/include" ]; then
    echo "ERROR: mockturtle not found at $MOCKTURTLE_DIR"
    echo "  git clone --depth 1 https://github.com/lsils/mockturtle.git $MOCKTURTLE_DIR"
    exit 1
fi
cmake -S "$PROJECT_DIR" -B "$PROJECT_DIR/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$PROJECT_DIR/build" -j "$JOBS"
