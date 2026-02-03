# FullVision Demo 架构设计

## 核心流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         编译阶段 (Compile Time)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  RTL (.v)  ──► Yosys + 自定义插件 ──┬──► gtech网表 (.v)                 │
│                                     ├──► AIG文件 (.aig)                 │
│                                     └──► 信号映射 (.json)               │
│                                           ↑                             │
│                              RTL信号bit → AIG节点ID                     │
│                              (在综合过程中跟踪生成)                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         仿真阶段 (Simulation)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  gtech网表 + testbench ──► iverilog ──► VPI采集 ──► trace文件           │
│                                         (只采集PI+寄存器)               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       波形补全阶段 (Waveform Completion)                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  AIG + 信号映射 + trace ──► mockturtle仿真 ──► 完整VCD                  │
│                              (补全所有组合逻辑信号)                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 信号映射生成 (关键改进)

### 之前的错误方法
```
yosys综合 → 输出AIGER → 从AIGER解析符号表 → 映射
                              ↑
                      问题：async2sync后信号名丢失
```

### 正确方法：yosys插件
```
yosys综合过程中：
  1. techmap后：记录 RTL wire name → SigBit
  2. async2sync：跟踪 旧SigBit → 新SigBit
  3. aigmap后：查询 SigBit → AIG节点ID
  4. 输出：RTL信号bit → AIG节点ID 映射
```

## 信号映射JSON格式

```json
{
  "aig_info": {
    "num_inputs": 66,
    "num_latches": 632,
    "num_outputs": 66,
    "num_ands": 8003
  },
  "inputs": {
    "clk": {"width": 1, "bits": [{"bit": 0, "aig_lit": 2}]},
    "rst_n": {"width": 1, "bits": [{"bit": 0, "aig_lit": 4}]},
    "instr_in": {"width": 32, "bits": [
      {"bit": 0, "aig_lit": 6},
      {"bit": 1, "aig_lit": 8},
      ...
    ]}
  },
  "registers": {
    "pc": {"width": 32, "bits": [
      {"bit": 0, "latch_id": 0, "aig_lit": 134},
      {"bit": 1, "latch_id": 1, "aig_lit": 136},
      ...
    ]},
    "regfile[0]": {"width": 32, "bits": [...]}
  },
  "outputs": {
    "pc_out": {"width": 32, "bits": [
      {"bit": 0, "aig_lit": 17404},
      ...
    ]}
  },
  "internals": {
    "alu_result": {"width": 32, "bits": [
      {"bit": 0, "aig_node": 1234, "inverted": false},
      ...
    ]}
  }
}
```

## 模块职责

### 1. compiler/yosys_plugin/ - Yosys插件
- `signal_tracker.cc`: 跟踪RTL信号到AIG节点的映射
- 编译为 `signal_tracker.so`
- 提供 `write_signal_map` 命令

### 2. compiler/ - Python编译器
- `yosys_runner.py`: 调用yosys，加载插件
- `synthesis.ys`: 综合脚本，调用插件命令

### 3. runtime/vpi/ - VPI采集
- `trace_collector.c`: 采集PI和寄存器信号

### 4. waveform_completion/ - C++波形补全
- 使用mockturtle进行AIG仿真
- 根据映射生成完整VCD

### 5. orchestrator/ - 流水线编排
- `pipeline.py`: 协调各模块执行
