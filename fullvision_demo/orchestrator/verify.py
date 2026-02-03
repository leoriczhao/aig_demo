#!/usr/bin/env python3
"""
VCD Verification - 对比两个VCD文件
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VCDParser:
    """简化的VCD解析器"""

    def __init__(self, filename: Path):
        self.filename = filename
        self.signals: Dict[str, int] = {}  # signal_id -> width
        self.signal_names: Dict[str, str] = {}  # signal_id -> full_name
        self.values: Dict[int, Dict[str, str]] = {}  # time -> {signal_id -> value}

    def parse(self) -> bool:
        """解析VCD文件"""
        try:
            with open(self.filename, 'r') as f:
                content = f.read()

            # 解析变量定义
            var_pattern = r'\$var\s+\w+\s+(\d+)\s+(\S+)\s+(\S+)\s+\$end'
            for match in re.finditer(var_pattern, content):
                width, signal_id, name = match.groups()
                self.signals[signal_id] = int(width)
                self.signal_names[signal_id] = name

            # 解析值变化
            lines = content.split('\n')
            current_time = 0
            in_values = False

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith('$enddefinitions'):
                    in_values = True
                    continue

                if not in_values:
                    continue

                if line.startswith('#'):
                    current_time = int(line[1:])
                    if current_time not in self.values:
                        self.values[current_time] = {}
                    continue

                # 值变化
                if line.startswith('b'):
                    # 多位值: b<value> <id>
                    match = re.match(r'b(\S+)\s+(\S+)', line)
                    if match:
                        value, sig_id = match.groups()
                        if current_time in self.values:
                            self.values[current_time][sig_id] = value
                elif line[0] in '01xXzZ':
                    # 单位值: <value><id>
                    value = line[0]
                    sig_id = line[1:]
                    if current_time in self.values:
                        self.values[current_time][sig_id] = value

            return True

        except Exception as e:
            logger.error(f"Failed to parse VCD: {e}")
            return False

    def get_signal_value(self, signal_name: str, time: int) -> Optional[str]:
        """获取指定信号在指定时间的值"""
        # 查找信号ID
        sig_id = None
        for id, name in self.signal_names.items():
            if name == signal_name:
                sig_id = id
                break

        if sig_id is None:
            return None

        # 查找最近的值（VCD只在值变化时记录）
        latest_value = None
        for t in sorted(self.values.keys()):
            if t > time:
                break
            if sig_id in self.values[t]:
                latest_value = self.values[t][sig_id]

        return latest_value


class VCDComparator:
    """VCD文件比较器"""

    def __init__(self):
        self.differences: List[Tuple[int, str, str, str]] = []  # (time, signal, golden, completed)

    def compare(self, golden_vcd: Path, completed_vcd: Path) -> int:
        """
        比较两个VCD文件
        返回差异数量
        """
        self.differences.clear()

        # 解析两个VCD
        golden = VCDParser(golden_vcd)
        completed = VCDParser(completed_vcd)

        if not golden.parse():
            logger.error("Failed to parse golden VCD")
            return -1

        if not completed.parse():
            logger.error("Failed to parse completed VCD")
            return -1

        logger.info(f"Golden VCD: {len(golden.signals)} signals, {len(golden.values)} time points")
        logger.info(f"Completed VCD: {len(completed.signals)} signals, {len(completed.values)} time points")

        # 获取所有时间点
        all_times = set(golden.values.keys()) | set(completed.values.keys())

        # 获取共同信号
        golden_names = set(golden.signal_names.values())
        completed_names = set(completed.signal_names.values())
        common_names = golden_names & completed_names

        logger.info(f"Common signals: {len(common_names)}")

        # 比较每个时间点的每个信号
        for time in sorted(all_times):
            for name in common_names:
                golden_value = golden.get_signal_value(name, time)
                completed_value = completed.get_signal_value(name, time)

                if golden_value != completed_value:
                    self.differences.append((time, name, golden_value, completed_value))

        # 输出部分差异
        if self.differences:
            logger.info(f"Found {len(self.differences)} differences:")
            for diff in self.differences[:10]:
                time, name, g_val, c_val = diff
                logger.info(f"  t={time}: {name} golden={g_val} completed={c_val}")
            if len(self.differences) > 10:
                logger.info(f"  ... and {len(self.differences) - 10} more")

        return len(self.differences)

    def get_differences(self) -> List[Tuple[int, str, str, str]]:
        """获取所有差异"""
        return self.differences


def compare_vcd(golden_vcd: Path, completed_vcd: Path) -> int:
    """便捷函数：比较两个VCD文件"""
    comparator = VCDComparator()
    return comparator.compare(golden_vcd, completed_vcd)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Compare two VCD files")
    parser.add_argument("golden", help="Golden VCD file")
    parser.add_argument("completed", help="Completed VCD file")

    args = parser.parse_args()

    diff_count = compare_vcd(Path(args.golden), Path(args.completed))

    if diff_count == 0:
        print("PASS: VCD files match")
        return 0
    elif diff_count > 0:
        print(f"FAIL: {diff_count} differences found")
        return 1
    else:
        print("ERROR: Comparison failed")
        return 2


if __name__ == "__main__":
    exit(main())
