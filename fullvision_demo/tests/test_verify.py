"""orchestrator.verify 单元测试 (无需EDA工具)"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.verify import VCDComparator, VCDParser  # noqa: E402

VCD_TEMPLATE = """$timescale 1ns $end
$scope module testbench $end
$var wire 1 ! clk $end
$var wire 8 " result [7:0] $end
$upscope $end
$enddefinitions $end
#0
0!
b00000000 "
#5
1!
b{result} "
#10
0!
"""


class VCDTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_vcd(self, name, result):
        path = self.tmp / name
        path.write_text(VCD_TEMPLATE.format(result=result))
        return path


class TestVCDParser(VCDTestCase):
    def test_parses_vars_and_values(self):
        parser = VCDParser(self.write_vcd("a.vcd", "00101010"))
        self.assertTrue(parser.parse())
        self.assertEqual(parser.signals, {"!": 1, '"': 8})
        self.assertEqual(parser.signal_names["!"], "clk")
        self.assertEqual(parser.get_signal_value("result", 5), "00101010")
        # 值保持到下一次变化
        self.assertEqual(parser.get_signal_value("result", 10), "00101010")
        self.assertEqual(parser.get_signal_value("clk", 10), "0")

    def test_unknown_signal_returns_none(self):
        parser = VCDParser(self.write_vcd("a.vcd", "00000001"))
        parser.parse()
        self.assertIsNone(parser.get_signal_value("missing", 0))

    def test_missing_file_fails(self):
        self.assertFalse(VCDParser(self.tmp / "nope.vcd").parse())


class TestVCDComparator(VCDTestCase):
    def test_identical_files_have_no_differences(self):
        golden = self.write_vcd("golden.vcd", "11110000")
        completed = self.write_vcd("completed.vcd", "11110000")
        self.assertEqual(VCDComparator().compare(golden, completed), 0)

    def test_value_mismatch_is_reported(self):
        golden = self.write_vcd("golden.vcd", "11110000")
        completed = self.write_vcd("completed.vcd", "11110001")
        comparator = VCDComparator()
        # result 在 t=5 和 t=10 两个时间点都不同
        self.assertEqual(comparator.compare(golden, completed), 2)
        time, name, g_val, c_val = comparator.get_differences()[0]
        self.assertEqual((time, name, g_val, c_val), (5, "result", "11110000", "11110001"))

    def test_unparsable_input_returns_negative(self):
        golden = self.write_vcd("golden.vcd", "11110000")
        self.assertEqual(VCDComparator().compare(golden, self.tmp / "nope.vcd"), -1)


if __name__ == "__main__":
    unittest.main()
