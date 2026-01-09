#!/usr/bin/env python3
"""
从VCD文件提取trace（输入信号和寄存器值）
用于测试波形补全功能
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple
import json


def parse_vcd_for_trace(vcd_file: Path, signal_list_file: Path, output_trace: Path):
    """
    从VCD提取指定信号的值作为trace

    Args:
        vcd_file: Golden VCD文件
        signal_list_file: 需要采集的信号列表（来自mapping生成）
        output_trace: 输出的trace文件
    """
    # 读取需要采集的信号
    with open(signal_list_file, 'r') as f:
        target_signals = set()
        for line in f:
            parts = line.strip().split()
            if parts:
                target_signals.add(parts[0])

    print(f"Target signals to extract: {len(target_signals)}")

    # 解析VCD - 需要追踪scope层级
    with open(vcd_file, 'r') as f:
        vcd_lines = f.readlines()

    id_to_signal: Dict[str, Tuple[str, int]] = {}  # id -> (full_path, width)
    scope_stack: List[str] = []

    for line in vcd_lines:
        line = line.strip()

        if line.startswith('$scope'):
            # $scope module name $end
            parts = line.split()
            if len(parts) >= 3:
                scope_stack.append(parts[2])

        elif line.startswith('$upscope'):
            if scope_stack:
                scope_stack.pop()

        elif line.startswith('$var'):
            # $var wire 32 ! name [31:0] $end
            parts = line.split()
            if len(parts) >= 5:
                width = int(parts[2])
                var_id = parts[3]
                name = parts[4]
                # 构建完整路径
                full_path = '.'.join(scope_stack + [name])
                id_to_signal[var_id] = (full_path, width)

        elif line.startswith('$enddefinitions'):
            break

    print(f"Found {len(id_to_signal)} signals in VCD")

    # 找到需要提取的信号ID
    target_ids: Dict[str, str] = {}  # id -> signal_name
    for var_id, (name, width) in id_to_signal.items():
        if name in target_signals:
            target_ids[var_id] = name

    print(f"Matched {len(target_ids)} signals to extract")

    # 解析值变化 - 继续使用vcd_lines从$enddefinitions之后开始
    current_time = 0
    signal_values: Dict[int, Dict[str, str]] = {}  # time -> {signal: value}
    in_value_section = False

    for line in vcd_lines:
        line = line.strip()
        if not line:
            continue

        # 检测value section的开始
        if line.startswith('$enddefinitions') or line.startswith('$dumpvars'):
            in_value_section = True
            continue
        if line.startswith('$end'):
            continue

        if not in_value_section:
            continue

        if line.startswith('#'):
            # 时间戳
            try:
                current_time = int(line[1:])
                if current_time not in signal_values:
                    signal_values[current_time] = {}
            except ValueError:
                pass
        elif line.startswith('b'):
            # 多位值: bXXXX id
            parts = line.split()
            if len(parts) == 2:
                value = parts[0][1:]  # 去掉'b'
                var_id = parts[1]
                if var_id in target_ids:
                    signal_name = target_ids[var_id]
                    if current_time not in signal_values:
                        signal_values[current_time] = {}
                    signal_values[current_time][signal_name] = value
        elif line[0] in '01xXzZ':
            # 单位值: 0id 或 1id
            value = line[0]
            var_id = line[1:]
            if var_id in target_ids:
                signal_name = target_ids[var_id]
                if current_time not in signal_values:
                    signal_values[current_time] = {}
                signal_values[current_time][signal_name] = value

    print(f"Found {len(signal_values)} time points")

    # 输出trace文件
    with open(output_trace, 'w') as f:
        # Header
        f.write(f"$signals {len(target_ids)}\n")
        for signal_name in sorted(target_ids.values()):
            width = 1
            for var_id, (name, w) in id_to_signal.items():
                if name == signal_name:
                    width = w
                    break
            f.write(f"{signal_name} {width}\n")
        f.write("$end\n")

        # Values
        for time in sorted(signal_values.keys()):
            f.write(f"#{time}\n")
            for signal_name, value in signal_values[time].items():
                f.write(f"{signal_name} {value}\n")

    print(f"Wrote trace to {output_trace}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <golden.vcd> <signal_list.txt> <output.trace>")
        sys.exit(1)

    vcd_file = Path(sys.argv[1])
    signal_list = Path(sys.argv[2])
    output_trace = Path(sys.argv[3])

    success = parse_vcd_for_trace(vcd_file, signal_list, output_trace)
    sys.exit(0 if success else 1)
