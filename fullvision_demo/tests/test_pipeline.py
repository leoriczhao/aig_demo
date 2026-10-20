"""orchestrator.pipeline 单元测试 (无需EDA工具)"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.pipeline import FullVisionPipeline, PipelineConfig  # noqa: E402


class PipelineTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.config = PipelineConfig(
            dut_file=self.tmp / "dut.v",
            testbench_file=self.tmp / "tb.v",
            top_module="simple_alu",
            output_dir=self.tmp / "out",
        )
        self.pipeline = FullVisionPipeline(self.config)

    def tearDown(self):
        self._tmp.cleanup()


class TestSetup(PipelineTestCase):
    def test_creates_output_layout(self):
        for subdir in ["aig", "traces", "vcd"]:
            self.assertTrue((self.config.output_dir / subdir).is_dir())

    def test_derived_paths(self):
        self.assertEqual(self.config.aig_file.name, "simple_alu.aag")
        self.assertEqual(self.config.golden_vcd.name, "simple_alu_golden.vcd")


class TestSignalList(PipelineTestCase):
    def test_only_sampled_signals_are_listed(self):
        mapping = {
            "signals": {
                "a": {"width": 8, "type": "input", "is_sampled": True},
                "acc": {"width": 8, "type": "latch", "is_sampled": True},
                "sum": {"width": 8, "type": "and", "is_sampled": False},
            }
        }
        self.config.mapping_file.write_text(json.dumps(mapping))

        self.assertTrue(self.pipeline.step2_generate_signal_list())
        lines = self.config.signal_list_file.read_text().splitlines()
        self.assertEqual(lines, ["testbench.dut.a 8", "testbench.dut.acc 8"])

    def test_missing_mapping_fails(self):
        self.assertFalse(self.pipeline.step2_generate_signal_list())


class TestRunAll(PipelineTestCase):
    def stub_steps(self, failing=None):
        calls = []

        def make(key):
            def step():
                calls.append(key)
                return key != failing
            return step

        steps = [(key, name, make(key)) for key, name, _ in self.pipeline.steps()]
        return calls, mock.patch.object(self.pipeline, "steps", return_value=steps)

    def test_stop_after(self):
        calls, patch = self.stub_steps()
        with patch:
            self.assertTrue(self.pipeline.run_all(stop_after="gtech_sim"))
        self.assertEqual(calls, ["synthesis", "signals", "rtl_sim", "gtech_sim"])

    def test_failure_stops_pipeline(self):
        calls, patch = self.stub_steps(failing="rtl_sim")
        with patch:
            self.assertFalse(self.pipeline.run_all())
        self.assertEqual(calls, ["synthesis", "signals", "rtl_sim"])


class TestVerification(PipelineTestCase):
    def setUp(self):
        super().setUp()
        self.config.golden_vcd.write_text("")
        self.config.completed_vcd.write_text("")

    def run_verify(self, diff_count):
        with mock.patch("orchestrator.verify.VCDComparator.compare", return_value=diff_count):
            return self.pipeline.step5_verification()

    def test_differences_tolerated_by_default(self):
        self.assertTrue(self.run_verify(3))

    def test_differences_fail_in_strict_mode(self):
        self.config.strict_verify = True
        self.assertFalse(self.run_verify(3))

    def test_comparison_error_fails(self):
        self.assertFalse(self.run_verify(-1))


if __name__ == "__main__":
    unittest.main()
