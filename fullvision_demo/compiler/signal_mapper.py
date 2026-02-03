#!/usr/bin/env python3
"""
Signal Mapper - 解析AIGER文件并生成信号映射JSON
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class BitMapping:
    """单个bit的映射信息"""
    bit: int              # 位索引
    aig_node: int         # AIG节点ID (literal / 2)
    inverted: bool        # 是否取反 (literal % 2)


@dataclass
class SignalInfo:
    """信号信息"""
    width: int
    type: str             # 'input', 'latch', 'output'
    is_sampled: bool      # 是否需要采集
    bits: List[BitMapping] = field(default_factory=list)


@dataclass
class AIGInfo:
    """AIG统计信息"""
    num_inputs: int
    num_latches: int
    num_outputs: int
    num_ands: int
    max_var: int


class AIGERParser:
    """AIGER ASCII格式解析器"""

    def __init__(self, aig_file: Path):
        self.aig_file = aig_file
        self.aig_info: Optional[AIGInfo] = None
        self.inputs: List[int] = []          # 输入literals
        self.latches: List[Tuple[int, int]] = []  # (current, next) literals
        self.outputs: List[int] = []          # 输出literals
        self.ands: List[Tuple[int, int, int]] = []  # (lhs, rhs0, rhs1) literals
        self.input_names: Dict[int, str] = {}  # 索引 -> 名称
        self.latch_names: Dict[int, str] = {}
        self.output_names: Dict[int, str] = {}

    def parse(self) -> bool:
        """解析AIGER文件"""
        try:
            with open(self.aig_file, 'r') as f:
                lines = f.readlines()

            if not lines:
                logger.error("Empty AIGER file")
                return False

            # 解析header
            header = lines[0].strip().split()
            if header[0] != 'aag':
                logger.error(f"Invalid AIGER header: expected 'aag', got '{header[0]}'")
                return False

            m = int(header[1])  # max variable index
            i = int(header[2])  # inputs
            l = int(header[3])  # latches
            o = int(header[4])  # outputs
            a = int(header[5])  # ands

            self.aig_info = AIGInfo(
                num_inputs=i,
                num_latches=l,
                num_outputs=o,
                num_ands=a,
                max_var=m
            )

            line_idx = 1

            # 解析inputs
            for _ in range(i):
                lit = int(lines[line_idx].strip())
                self.inputs.append(lit)
                line_idx += 1

            # 解析latches
            for _ in range(l):
                parts = lines[line_idx].strip().split()
                current_lit = int(parts[0])
                next_lit = int(parts[1])
                self.latches.append((current_lit, next_lit))
                line_idx += 1

            # 解析outputs
            for _ in range(o):
                lit = int(lines[line_idx].strip())
                self.outputs.append(lit)
                line_idx += 1

            # 解析and gates
            for _ in range(a):
                parts = lines[line_idx].strip().split()
                lhs = int(parts[0])
                rhs0 = int(parts[1])
                rhs1 = int(parts[2])
                self.ands.append((lhs, rhs0, rhs1))
                line_idx += 1

            # 解析symbol table
            while line_idx < len(lines):
                line = lines[line_idx].strip()
                if not line or line.startswith('c'):
                    break

                if line.startswith('i'):
                    # 输入符号: i<index> <name>
                    match = re.match(r'i(\d+)\s+(.+)', line)
                    if match:
                        idx, name = int(match.group(1)), match.group(2)
                        self.input_names[idx] = name

                elif line.startswith('l'):
                    # Latch符号: l<index> <name>
                    match = re.match(r'l(\d+)\s+(.+)', line)
                    if match:
                        idx, name = int(match.group(1)), match.group(2)
                        self.latch_names[idx] = name

                elif line.startswith('o'):
                    # 输出符号: o<index> <name>
                    match = re.match(r'o(\d+)\s+(.+)', line)
                    if match:
                        idx, name = int(match.group(1)), match.group(2)
                        self.output_names[idx] = name

                line_idx += 1

            logger.info(f"Parsed AIGER: {i} inputs, {l} latches, {o} outputs, {a} ANDs")
            logger.info(f"  Input symbols: {len(self.input_names)}")
            logger.info(f"  Latch symbols: {len(self.latch_names)}")
            logger.info(f"  Output symbols: {len(self.output_names)}")

            return True

        except Exception as e:
            logger.error(f"Failed to parse AIGER file: {e}")
            return False


class SignalMapper:
    """信号映射生成器"""

    def __init__(self, aiger_parser: AIGERParser):
        self.parser = aiger_parser
        self.signals: Dict[str, SignalInfo] = {}

    def _parse_signal_name(self, name: str) -> Tuple[str, int]:
        """
        解析信号名，提取基础名和位索引

        例如:
            "data[3]" -> ("data", 3)
            "clk" -> ("clk", 0)
            "\\regfile[2][15]" -> ("regfile[2]", 15)
        """
        # 处理转义信号名
        name = name.lstrip('\\').rstrip()

        # 匹配最后一个 [n]
        match = re.match(r'(.+)\[(\d+)\]$', name)
        if match:
            return match.group(1), int(match.group(2))

        return name, 0

    def build_mapping(self) -> Dict[str, SignalInfo]:
        """构建信号映射"""

        # 处理输入信号
        for idx, lit in enumerate(self.parser.inputs):
            name = self.parser.input_names.get(idx, f"i{idx}")
            base_name, bit_idx = self._parse_signal_name(name)
            node_id = lit // 2
            inverted = (lit % 2) == 1

            if base_name not in self.signals:
                self.signals[base_name] = SignalInfo(
                    width=0,
                    type='input',
                    is_sampled=True,  # 输入需要采集
                    bits=[]
                )

            sig = self.signals[base_name]
            sig.bits.append(BitMapping(bit=bit_idx, aig_node=node_id, inverted=inverted))
            sig.width = max(sig.width, bit_idx + 1)

        # 处理latch信号 (寄存器)
        for idx, (current_lit, next_lit) in enumerate(self.parser.latches):
            name = self.parser.latch_names.get(idx, f"l{idx}")
            base_name, bit_idx = self._parse_signal_name(name)
            node_id = current_lit // 2
            inverted = (current_lit % 2) == 1

            if base_name not in self.signals:
                self.signals[base_name] = SignalInfo(
                    width=0,
                    type='latch',
                    is_sampled=True,  # 寄存器需要采集
                    bits=[]
                )

            sig = self.signals[base_name]
            sig.bits.append(BitMapping(bit=bit_idx, aig_node=node_id, inverted=inverted))
            sig.width = max(sig.width, bit_idx + 1)

        # 处理输出信号
        for idx, lit in enumerate(self.parser.outputs):
            name = self.parser.output_names.get(idx, f"o{idx}")
            base_name, bit_idx = self._parse_signal_name(name)
            node_id = lit // 2
            inverted = (lit % 2) == 1

            if base_name not in self.signals:
                self.signals[base_name] = SignalInfo(
                    width=0,
                    type='output',
                    is_sampled=False,  # 输出不需要采集，通过补全计算
                    bits=[]
                )

            sig = self.signals[base_name]
            sig.bits.append(BitMapping(bit=bit_idx, aig_node=node_id, inverted=inverted))
            sig.width = max(sig.width, bit_idx + 1)

        # 按bit索引排序
        for sig in self.signals.values():
            sig.bits.sort(key=lambda b: b.bit)

        return self.signals

    def get_sampled_signals(self) -> List[str]:
        """获取需要采集的信号列表"""
        return [name for name, sig in self.signals.items() if sig.is_sampled]

    def export_json(self, output_file: Path):
        """导出映射为JSON格式"""

        def signal_to_dict(sig: SignalInfo) -> dict:
            return {
                'width': sig.width,
                'type': sig.type,
                'is_sampled': sig.is_sampled,
                'bits': [asdict(b) for b in sig.bits]
            }

        data = {
            'aig_info': asdict(self.parser.aig_info),
            'signals': {name: signal_to_dict(sig) for name, sig in self.signals.items()}
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Mapping exported to: {output_file}")

    def export_signal_list(self, output_file: Path, prefix: str = ""):
        """导出需要采集的信号列表（供VPI使用）"""
        sampled = self.get_sampled_signals()

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            for name in sorted(sampled):
                sig = self.signals[name]
                # 写入完整信号名和位宽
                full_name = f"{prefix}{name}" if prefix else name
                f.write(f"{full_name} {sig.width}\n")

        logger.info(f"Signal list exported to: {output_file} ({len(sampled)} signals)")


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Parse AIGER and generate signal mapping")
    parser.add_argument("--aig", required=True, help="Input AIGER file")
    parser.add_argument("--output", required=True, help="Output mapping JSON file")
    parser.add_argument("--signal-list", help="Output signal list file (for VPI)")
    parser.add_argument("--prefix", default="", help="Signal name prefix for VPI list")

    args = parser.parse_args()

    # 解析AIGER
    aig_parser = AIGERParser(Path(args.aig))
    if not aig_parser.parse():
        return 1

    # 构建映射
    mapper = SignalMapper(aig_parser)
    mapper.build_mapping()

    # 导出JSON
    mapper.export_json(Path(args.output))

    # 可选: 导出信号列表
    if args.signal_list:
        mapper.export_signal_list(Path(args.signal_list), args.prefix)

    return 0


if __name__ == "__main__":
    exit(main())
