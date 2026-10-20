# FullVision Demo CI/CD

本文说明 GitHub Actions 上的构建、测试和发布流程。各阶段都能用同名脚本在本地复现。

## 总览

| Workflow | 触发 | 内容 |
|----------|------|------|
| `.github/workflows/ci.yml` | push 到 `main` / `feature/**` / `ci/**`；对 `main` 的 PR；手动触发 | 单元测试 + 构建 + 集成测试 |
| `.github/workflows/release.yml` | push `v*` 标签；手动触发 | 构建 + 测试 + 打包；标签触发时额外发布 GitHub Release |

公共的工具链安装（Ubuntu 24.04 软件源中的 `yosys`、`yosys-dev`、`iverilog`、`cmake`）放在
`.github/actions/setup-eda`。

## CI 任务

### `unit-tests`（Python 3.10 / 3.12）

不需要 EDA 工具，运行很快：

```bash
cd fullvision_demo
python3 -m compileall -q compiler orchestrator scripts tests
python3 -m unittest discover -s tests -t . -v
shellcheck scripts/*.sh
```

覆盖范围：`orchestrator/verify.py` 的 VCD 解析和比较、`orchestrator/pipeline.py` 的信号列表生成、
步骤调度（`--stop-after`）以及严格验证（`--strict`）。

### `build-and-integration`

```bash
cd fullvision_demo
scripts/build_all.sh                       # Yosys 插件 + VPI 模块 (+ waveform_completion)
make -C compiler/yosys_plugin test         # 插件加载冒烟测试
scripts/ci_integration.sh ci_output        # 用 simple_alu 跑真实流水线
```

`ci_integration.sh` 用 `designs/simple_alu` 运行流水线，并检查 AIG、gtech 网表、映射 JSON、
信号列表、golden VCD 和 trace 是否都已生成且非空：

- `build/waveform_completion` **存在**时跑完整流水线，验证使用 `--strict`，出现任何 VCD 差异都判失败。
- **不存在**时运行到 `gtech_sim` 步骤为止，同时在 Actions 中给出 warning。

构建产物（`signal_mapper.so`、`trace_collector.vpi`、`waveform_completion`）和流水线输出会作为
artifact 上传，保留 14 天。

> 集成测试使用 simple_alu 而不是 mini_cpu，原因是 `dut/testbench.v` 中的 `$trace_init`
> 被注释掉了，mini_cpu 在 trace 采集这一步一定会失败。

## 发布流程

```bash
git tag -a v1.0.0 -m "FullVision demo v1.0.0"
git push origin v1.0.0
```

`release.yml` 会依次执行构建、单元测试、集成测试和 `scripts/package.sh`，然后用 `GITHUB_TOKEN`
创建 GitHub Release，release notes 自动生成。标签名中带 `-` 的（例如 `v1.1.0-rc1`）会标记为 pre-release。

发布包为 `fullvision_demo-<version>-linux-x86_64.tar.gz`，并附带 `.sha256` 校验文件，内容包括：

- 仓库中已跟踪的 `fullvision_demo` 源码（不含 `output/`）
- 预编译的二进制文件，放在与源码树相同的相对路径下，解压后可以直接运行 `scripts/run_demo.sh`
- `BUILD_INFO.txt`：版本、commit、yosys 和 iverilog 版本

注意：`signal_mapper.so` 是针对 Ubuntu 24.04 软件源中的 yosys 编译的，Yosys 插件要求与加载它的 yosys
版本一致，其他 yosys 版本需要在本地重新执行 `make -C compiler/yosys_plugin`。

手动触发（`workflow_dispatch`）只会打包并上传 artifact（版本号为 `dev-<sha>`），不会发布 Release。

## 已知缺口

1. **`waveform_completion` 的 C++ 源码不在仓库中。** `CMakeLists.txt` 引用了
   `waveform_completion/src/*.cpp`，但该目录从未提交过。原因是 `.gitignore` 中原有的
   `waveform_completion` 规则把同名的源码目录也一起忽略了，这条规则现已删除。提交源码后
   CI 会自动执行以下步骤，workflow 不需要改动：
   - clone mockturtle 到 `../mockturtle`
   - 编译 C++
   - 跑完整流水线，并启用 `--strict` 验证
2. mockturtle 目前取的是默认分支的最新提交。等 C++ 构建稳定后，建议在 workflow 中把它固定到某个
   tag 或 commit。
3. 如果确实存在可以接受的 VCD 差异（例如 x/z 的处理），需要从 `ci_integration.sh` 中去掉 `--strict`，
   或者改进比较逻辑。
