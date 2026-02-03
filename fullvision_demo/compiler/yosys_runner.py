#!/usr/bin/env python3
"""
Yosys Runner - 调用yosys进行RTL综合
使用自定义signal_mapper插件生成RTL信号到AIG节点的映射（包含内部信号）和AIGER文件
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 插件路径
PLUGIN_DIR = Path(__file__).parent / "yosys_plugin"
PLUGIN_SO = PLUGIN_DIR / "signal_mapper.so"


class YosysRunner:
    """Yosys综合器封装"""

    def __init__(self, yosys_path: str = "yosys"):
        self.yosys_path = yosys_path
        self.script_template = Path(__file__).parent / "synthesis.ys"
        self.plugin_path = PLUGIN_SO

    def synthesize(
        self,
        dut_file: Path,
        top_module: str,
        output_netlist: Path,
        output_aig: Path,
        output_mapping: Optional[Path] = None,
        verbose: bool = False
    ) -> bool:
        """
        运行综合流程

        Args:
            dut_file: RTL源文件路径
            top_module: 顶层模块名
            output_netlist: gtech网表输出路径
            output_aig: AIGER文件输出路径
            output_mapping: 信号映射JSON输出路径
            verbose: 是否输出详细信息

        Returns:
            成功返回True，失败返回False
        """
        # 检查插件
        if not self.plugin_path.exists():
            logger.error(f"Plugin not found: {self.plugin_path}")
            logger.info("Please build the plugin first: cd compiler/yosys_plugin && make")
            return False

        # 读取脚本模板
        if not self.script_template.exists():
            logger.error(f"Script template not found: {self.script_template}")
            return False

        template = self.script_template.read_text()

        # 默认映射输出路径
        if output_mapping is None:
            output_mapping = output_aig.parent / f"{output_aig.stem}_mapping.json"

        # 替换变量
        script = template.replace("${DUT_FILE}", str(dut_file.absolute()))
        script = script.replace("${TOP_MODULE}", top_module)
        script = script.replace("${OUTPUT_NETLIST}", str(output_netlist.absolute()))
        script = script.replace("${OUTPUT_AIG}", str(output_aig.absolute()))
        script = script.replace("${OUTPUT_MAPPING}", str(output_mapping.absolute()))

        # 确保输出目录存在
        output_netlist.parent.mkdir(parents=True, exist_ok=True)
        output_aig.parent.mkdir(parents=True, exist_ok=True)
        output_mapping.parent.mkdir(parents=True, exist_ok=True)

        # 写入临时脚本文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ys', delete=False) as f:
            f.write(script)
            temp_script = Path(f.name)

        try:
            logger.info(f"Running yosys synthesis with signal mapper plugin...")
            logger.info(f"  DUT:      {dut_file}")
            logger.info(f"  Top:      {top_module}")
            logger.info(f"  Netlist:  {output_netlist}")
            logger.info(f"  AIG:      {output_aig}")
            logger.info(f"  Mapping:  {output_mapping}")

            # 运行yosys（加载插件）
            result = subprocess.run(
                [self.yosys_path, "-m", str(self.plugin_path), "-s", str(temp_script)],
                capture_output=True,
                text=True
            )

            if verbose or result.returncode != 0:
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)

            if result.returncode != 0:
                logger.error("Yosys synthesis failed")
                return False

            # 验证输出文件
            if not output_netlist.exists():
                logger.error(f"Netlist not generated: {output_netlist}")
                return False

            if not output_aig.exists():
                logger.error(f"AIG not generated: {output_aig}")
                return False

            if not output_mapping.exists():
                logger.warning(f"Mapping not generated: {output_mapping}")

            logger.info("Synthesis completed successfully")
            logger.info(f"  Generated: {output_netlist}")
            logger.info(f"  Generated: {output_aig}")
            if output_mapping.exists():
                logger.info(f"  Generated: {output_mapping}")
            return True

        finally:
            # 清理临时文件
            temp_script.unlink(missing_ok=True)


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Yosys RTL synthesis with signal mapping")
    parser.add_argument("--dut", required=True, help="RTL source file")
    parser.add_argument("--top", required=True, help="Top module name")
    parser.add_argument("--netlist", required=True, help="Output netlist file")
    parser.add_argument("--aig", required=True, help="Output AIG file")
    parser.add_argument("--mapping", help="Output signal mapping JSON file")
    parser.add_argument("--yosys", default="yosys", help="Yosys executable path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    runner = YosysRunner(yosys_path=args.yosys)
    success = runner.synthesize(
        dut_file=Path(args.dut),
        top_module=args.top,
        output_netlist=Path(args.netlist),
        output_aig=Path(args.aig),
        output_mapping=Path(args.mapping) if args.mapping else None,
        verbose=args.verbose
    )

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
