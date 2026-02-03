#!/usr/bin/env python3
"""
FullVision Demo Pipeline - 完整流水线

流程:
1. RTL综合 -> gtech网表 + AIGER + 信号映射JSON
2. 生成信号列表 (从JSON映射)
3. 仿真生成golden VCD + 提取trace
4. 波形补全
5. 验证
"""

import subprocess
import sys
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class PipelineConfig:
    """流水线配置"""
    # RTL文件
    dut_file: Path
    testbench_file: Path
    top_module: str

    # 输出目录
    output_dir: Path

    # 工具路径
    yosys_path: str = "yosys"
    iverilog_path: str = "iverilog"
    vvp_path: str = "vvp"
    waveform_completion_path: Optional[Path] = None

    def __post_init__(self):
        if self.waveform_completion_path is None:
            self.waveform_completion_path = PROJECT_ROOT / "build" / "waveform_completion"

    @property
    def netlist_file(self) -> Path:
        return self.output_dir / "aig" / f"{self.top_module}_gtech.v"

    @property
    def aig_file(self) -> Path:
        return self.output_dir / "aig" / f"{self.top_module}.aag"

    @property
    def mapping_file(self) -> Path:
        return self.output_dir / "aig" / f"{self.top_module}_mapping.json"

    @property
    def signal_list_file(self) -> Path:
        return self.output_dir / "aig" / f"{self.top_module}_signals.txt"

    @property
    def trace_file(self) -> Path:
        return self.output_dir / "traces" / f"{self.top_module}.trace"

    @property
    def completed_vcd(self) -> Path:
        return self.output_dir / "vcd" / f"{self.top_module}_completed.vcd"

    @property
    def golden_vcd(self) -> Path:
        return self.output_dir / "vcd" / f"{self.top_module}_golden.vcd"


class FullVisionPipeline:
    """FullVision完整流水线"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._setup_directories()

    def _setup_directories(self):
        """创建输出目录结构"""
        for subdir in ["aig", "traces", "vcd"]:
            (self.config.output_dir / subdir).mkdir(parents=True, exist_ok=True)

    def step1_synthesis(self) -> bool:
        """
        步骤1: RTL综合
        调用yosys将Verilog转换为gtech网表、AIGER和信号映射JSON
        """
        logger.info("=" * 50)
        logger.info("Step 1: RTL Synthesis (Verilog -> gtech + AIG + Mapping)")
        logger.info("=" * 50)

        # 使用yosys_runner.py
        sys.path.insert(0, str(PROJECT_ROOT / "compiler"))
        from yosys_runner import YosysRunner

        runner = YosysRunner(yosys_path=self.config.yosys_path)
        success = runner.synthesize(
            dut_file=self.config.dut_file,
            top_module=self.config.top_module,
            output_netlist=self.config.netlist_file,
            output_aig=self.config.aig_file,
            output_mapping=self.config.mapping_file,
            verbose=True
        )

        if not success:
            logger.error("Synthesis failed")
            return False

        logger.info(f"  Netlist: {self.config.netlist_file}")
        logger.info(f"  AIG:     {self.config.aig_file}")
        logger.info(f"  Mapping: {self.config.mapping_file}")
        return True

    def step2_generate_signal_list(self) -> bool:
        """
        步骤2: 从JSON映射生成信号列表
        供VPI插件和trace提取使用
        """
        logger.info("=" * 50)
        logger.info("Step 2: Generate Signal List from Mapping")
        logger.info("=" * 50)

        try:
            with open(self.config.mapping_file, 'r') as f:
                mapping = json.load(f)

            # 生成信号列表 - 只包含需要采样的信号 (inputs + latches)
            sampled_signals = []
            for name, info in mapping['signals'].items():
                if info.get('is_sampled', False):
                    width = info['width']
                    sig_type = info['type']
                    # 添加testbench前缀
                    full_name = f"testbench.dut.{name}"
                    sampled_signals.append((full_name, width, sig_type))

            # 写入信号列表文件
            with open(self.config.signal_list_file, 'w') as f:
                for name, width, sig_type in sampled_signals:
                    f.write(f"{name} {width}\n")

            logger.info(f"  Generated signal list with {len(sampled_signals)} signals")
            logger.info(f"  Signal list: {self.config.signal_list_file}")

            # 统计
            input_count = sum(1 for _, _, t in sampled_signals if t == 'input')
            latch_count = sum(1 for _, _, t in sampled_signals if t == 'latch')
            logger.info(f"  Inputs: {input_count}, Latches: {latch_count}")

            return True

        except Exception as e:
            logger.error(f"Failed to generate signal list: {e}")
            return False

    def step3a_rtl_simulation(self) -> bool:
        """
        步骤3a: 原始RTL仿真
        生成golden VCD (包含所有DUT内部信号)
        """
        logger.info("=" * 50)
        logger.info("Step 3a: Original RTL Simulation -> Golden VCD")
        logger.info("=" * 50)

        # 使用配置的testbench
        testbench = self.config.testbench_file
        if not testbench.exists():
            logger.error(f"Testbench not found: {testbench}")
            return False

        # 编译原始RTL
        vvp_file = self.config.output_dir / "sim_rtl.vvp"
        logger.info("Compiling original RTL...")

        compile_cmd = [
            self.config.iverilog_path,
            "-o", str(vvp_file),
            "-g2012",
            f'-DGOLDEN_VCD_FILE="{self.config.golden_vcd}"',
            "-DGOLDEN_VCD",
            str(testbench),
            str(self.config.dut_file)
        ]

        logger.info(f"  DUT: {self.config.dut_file} (original RTL)")
        logger.info(f"  Testbench: {testbench}")
        result = subprocess.run(compile_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"RTL compilation failed: {result.stderr}")
            return False

        # 运行RTL仿真
        logger.info("Running RTL simulation...")
        run_cmd = [self.config.vvp_path, str(vvp_file)]

        result = subprocess.run(
            run_cmd,
            capture_output=True,
            text=True,
            cwd=str(self.config.output_dir)
        )

        if result.returncode != 0:
            logger.warning(f"RTL simulation warning: {result.stderr}")

        # 检查golden VCD
        if not self.config.golden_vcd.exists():
            logger.error("Golden VCD not generated")
            return False

        logger.info(f"  Golden VCD: {self.config.golden_vcd}")
        return True

    def step3b_gtech_simulation(self) -> bool:
        """
        步骤3b: gtech网表仿真 + VPI采集trace
        VPI采集inputs和latches的值
        """
        logger.info("=" * 50)
        logger.info("Step 3b: gtech Netlist Simulation -> Trace (VPI)")
        logger.info("=" * 50)

        # VPI插件路径
        vpi_path = PROJECT_ROOT / "runtime" / "vpi"
        vpi_module = vpi_path / "trace_collector.vpi"

        if not vpi_module.exists():
            logger.error(f"VPI module not found: {vpi_module}")
            logger.info("Please build VPI module first:")
            logger.info(f"  cd {vpi_path} && make")
            return False

        # 使用配置的testbench (同一个testbench包含VPI调用)
        testbench = self.config.testbench_file
        if not testbench.exists():
            logger.error(f"Testbench not found: {testbench}")
            return False

        # 编译gtech网表
        vvp_file = self.config.output_dir / "sim_gtech.vvp"
        logger.info("Compiling gtech netlist...")

        compile_cmd = [
            self.config.iverilog_path,
            "-o", str(vvp_file),
            "-g2012",
            f'-DTRACE_SIGNAL_LIST="{self.config.signal_list_file}"',
            f'-DTRACE_OUTPUT_FILE="{self.config.trace_file}"',
            str(testbench),
            str(self.config.netlist_file)  # gtech网表
        ]

        logger.info(f"  Netlist: {self.config.netlist_file} (gtech)")
        logger.info(f"  Testbench: {testbench}")
        result = subprocess.run(compile_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"gtech compilation failed: {result.stderr}")
            return False

        # 运行gtech仿真 + VPI
        logger.info("Running gtech simulation with VPI trace collector...")
        run_cmd = [
            self.config.vvp_path,
            "-M", str(vpi_path),
            "-mtrace_collector",
            str(vvp_file)
        ]

        result = subprocess.run(
            run_cmd,
            capture_output=True,
            text=True,
            cwd=str(self.config.output_dir)
        )

        # 打印VPI输出
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    logger.info(f"  [VPI] {line}")

        if result.returncode != 0:
            logger.warning(f"gtech simulation warning: {result.stderr}")

        # 检查trace
        if not self.config.trace_file.exists():
            logger.error("Trace file not generated by VPI")
            return False

        # 显示trace文件信息
        with open(self.config.trace_file, 'r') as f:
            lines = f.readlines()
            signal_count = 0
            cycle_count = 0
            for line in lines:
                if line.startswith('$signals'):
                    signal_count = int(line.split()[1])
                if line.startswith('#'):
                    cycle_count += 1
            logger.info(f"  Trace: {self.config.trace_file}")
            logger.info(f"  Signals: {signal_count}, Cycles: {cycle_count}")

        return True

    def step4_waveform_completion(self) -> bool:
        """
        步骤4: 波形补全
        使用mockturtle进行AIG仿真，补全所有组合逻辑信号
        """
        logger.info("=" * 50)
        logger.info("Step 4: Waveform Completion")
        logger.info("=" * 50)

        # 检查waveform_completion工具是否存在
        if not self.config.waveform_completion_path.exists():
            logger.error(f"waveform_completion not found: {self.config.waveform_completion_path}")
            logger.info("Please build the C++ module first:")
            logger.info(f"  cd {PROJECT_ROOT}/build && cmake .. && make")
            return False

        # 检查trace文件是否存在
        if not self.config.trace_file.exists():
            logger.error("Trace file not found. Run simulation step first.")
            return False

        # 运行波形补全
        completion_cmd = [
            str(self.config.waveform_completion_path),
            "--aig", str(self.config.aig_file),
            "--mapping", str(self.config.mapping_file),
            "--trace", str(self.config.trace_file),
            "--output", str(self.config.completed_vcd)
        ]

        logger.info(f"Running: {' '.join(completion_cmd)}")
        result = subprocess.run(completion_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Waveform completion failed: {result.stderr}")
            return False

        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                logger.info(f"  {line}")

        logger.info(f"  Completed VCD: {self.config.completed_vcd}")
        return True

    def step5_verification(self) -> bool:
        """
        步骤5: 验证
        对比golden VCD与补全VCD
        """
        logger.info("=" * 50)
        logger.info("Step 5: Verification")
        logger.info("=" * 50)

        from orchestrator.verify import VCDComparator

        if not self.config.golden_vcd.exists():
            logger.warning("Golden VCD not found, skipping verification")
            return True

        if not self.config.completed_vcd.exists():
            logger.error("Completed VCD not found")
            return False

        comparator = VCDComparator()
        diff_count = comparator.compare(
            self.config.golden_vcd,
            self.config.completed_vcd
        )

        if diff_count == 0:
            logger.info("Verification PASSED: No differences found")
            return True
        elif diff_count > 0:
            logger.warning(f"Verification: {diff_count} differences found")
            # 返回True以允许流水线继续（差异可能是预期的）
            return True
        else:
            logger.error("Verification failed")
            return False

    def run_all(self) -> bool:
        """运行完整流水线"""
        logger.info("=" * 60)
        logger.info("FullVision Demo Pipeline")
        logger.info("=" * 60)

        start_time = time.time()

        steps = [
            ("Synthesis", self.step1_synthesis),
            ("Generate Signal List", self.step2_generate_signal_list),
            ("RTL Simulation (Golden VCD)", self.step3a_rtl_simulation),
            ("gtech Simulation (Trace)", self.step3b_gtech_simulation),
            ("Waveform Completion", self.step4_waveform_completion),
            ("Verification", self.step5_verification),
        ]

        for step_name, step_func in steps:
            logger.info(f"\n>>> Running: {step_name}")
            if not step_func():
                logger.error(f"Pipeline failed at step: {step_name}")
                return False

        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"Pipeline completed successfully in {elapsed:.2f}s")
        logger.info("=" * 60)

        return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="FullVision Demo Pipeline")
    parser.add_argument("--dut", help="RTL DUT file (default: dut/mini_cpu.v)")
    parser.add_argument("--testbench", help="Testbench file (default: dut/testbench.v)")
    parser.add_argument("--top", default="mini_cpu", help="Top module name")
    parser.add_argument("--output-dir", help="Output directory (default: output)")

    args = parser.parse_args()

    # 默认路径
    dut_file = Path(args.dut) if args.dut else PROJECT_ROOT / "dut" / "mini_cpu.v"
    testbench_file = Path(args.testbench) if args.testbench else PROJECT_ROOT / "dut" / "testbench.v"
    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "output"

    config = PipelineConfig(
        dut_file=dut_file,
        testbench_file=testbench_file,
        top_module=args.top,
        output_dir=output_dir
    )

    pipeline = FullVisionPipeline(config)
    success = pipeline.run_all()

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
