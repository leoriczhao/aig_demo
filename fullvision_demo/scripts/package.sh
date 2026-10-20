#!/bin/bash
# FullVision Demo 打包脚本
#
# 将仓库中已跟踪的 fullvision_demo 源码 + 已构建的二进制打成 tar.gz,
# 二进制放在与源码树相同的相对路径下, 解压后可直接运行 scripts/run_demo.sh
#
# 用法: scripts/package.sh <version> [dist_dir]   (需先运行 scripts/build_all.sh)

set -euo pipefail

VERSION="${1:?usage: package.sh <version> [dist_dir]}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$(realpath -m "${2:-$PROJECT_DIR/dist}")"
PKG="fullvision_demo-${VERSION}-linux-$(uname -m)"
STAGE="$DIST_DIR/$PKG"

binaries=(
    compiler/yosys_plugin/signal_mapper.so
    runtime/vpi/trace_collector.vpi
)
if [ -x "$PROJECT_DIR/build/waveform_completion" ]; then
    binaries+=(build/waveform_completion)
fi

rm -rf "$STAGE"
mkdir -p "$STAGE"

# 源码: 仅 git 跟踪的文件 (排除已提交的 output/ 等生成物)
git -C "$PROJECT_DIR" archive --format=tar HEAD -- . ':(exclude)output' \
    | tar -x -C "$STAGE"

for bin in "${binaries[@]}"; do
    if [ ! -f "$PROJECT_DIR/$bin" ]; then
        echo "ERROR: $bin not built; run scripts/build_all.sh first"
        exit 1
    fi
    mkdir -p "$STAGE/$(dirname "$bin")"
    cp "$PROJECT_DIR/$bin" "$STAGE/$bin"
done

{
    echo "version: $VERSION"
    echo "commit:  $(git -C "$PROJECT_DIR" rev-parse HEAD)"
    echo "built:   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "yosys:   $(yosys -V 2>/dev/null || echo unknown)"
    echo "iverilog: $(iverilog -V 2>&1 | head -1 || echo unknown)"
    echo "binaries:"
    printf '  %s\n' "${binaries[@]}"
} > "$STAGE/BUILD_INFO.txt"

tar -czf "$DIST_DIR/$PKG.tar.gz" -C "$DIST_DIR" "$PKG"
(cd "$DIST_DIR" && sha256sum "$PKG.tar.gz" > "$PKG.tar.gz.sha256")
rm -rf "$STAGE"

echo "Package: $DIST_DIR/$PKG.tar.gz"
