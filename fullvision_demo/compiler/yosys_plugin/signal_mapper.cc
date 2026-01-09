/*
 * FullVision Signal Mapper - Yosys Plugin
 *
 * 功能：在yosys综合过程中生成RTL信号到AIG节点的映射，并输出AIGER文件
 *
 * 使用方法：
 *   yosys -m signal_mapper.so -p "read_verilog design.v; synth; record_rtl_signals; write_signal_map mapping.json design.aag"
 */

#include "kernel/yosys.h"
#include "kernel/sigtools.h"
#include <fstream>
#include <vector>
#include <set>

USING_YOSYS_NAMESPACE
PRIVATE_NAMESPACE_BEGIN

// 全局变量：存储RTL信号名（在综合变换前记录）
namespace RecordRtlSignals {
    dict<SigBit, std::string> saved_names;
}

// 信号映射器
class SignalMapper {
public:
    Module *module;
    SigMap sigmap;

    // AIG构建
    dict<SigBit, int> aig_map;      // SigBit -> AIG literal
    std::vector<std::pair<int, int>> aig_ands;  // AND gates: (rhs0, rhs1)
    int next_aig_id;

    // 输入、latch和输出
    std::vector<SigBit> inputs;
    std::vector<SigBit> latches;    // latch当前状态 (Q)
    std::vector<SigBit> latch_next; // latch下一状态 (D)
    std::vector<SigBit> outputs;

    // RTL信号名
    dict<SigBit, std::string> rtl_names;
    dict<SigBit, std::string> latch_rtl_names;

    SignalMapper(Module *mod) : module(mod), sigmap(mod), next_aig_id(1) {
        aig_map[State::S0] = 0;
        aig_map[State::S1] = 1;
    }

    // 查找SigBit的RTL名称
    std::string find_rtl_name_for_bit(SigBit bit) {
        bit = sigmap(bit);

        // 1. 检查rtl_names
        if (rtl_names.count(bit))
            return rtl_names.at(bit);

        // 2. 检查saved_names
        if (RecordRtlSignals::saved_names.count(bit))
            return RecordRtlSignals::saved_names.at(bit);

        // 3. 检查公共wire
        for (auto wire : module->wires()) {
            if (wire->name[0] != '\\')
                continue;

            for (int i = 0; i < wire->width; i++) {
                SigBit wire_bit = sigmap(SigBit(wire, i));
                if (wire_bit == bit) {
                    std::string base_name = wire->name.str().substr(1);
                    if (wire->width == 1) {
                        return base_name;
                    } else {
                        return base_name + "[" + std::to_string(wire->start_offset + i) + "]";
                    }
                }
            }
        }

        // 4. 检查module连接
        for (auto &conn : module->connections()) {
            SigSpec lhs = conn.first;
            SigSpec rhs = conn.second;

            for (int i = 0; i < rhs.size() && i < lhs.size(); i++) {
                if (sigmap(rhs[i]) == bit) {
                    SigBit lhs_bit = lhs[i];
                    if (lhs_bit.wire && lhs_bit.wire->name[0] == '\\') {
                        std::string base_name = lhs_bit.wire->name.str().substr(1);
                        if (lhs_bit.wire->width == 1) {
                            return base_name;
                        } else {
                            return base_name + "[" + std::to_string(lhs_bit.wire->start_offset + lhs_bit.offset) + "]";
                        }
                    }
                }
            }
        }

        return "";
    }

    // 记录RTL信号名
    void record_rtl_names() {
        for (auto wire : module->wires()) {
            if (wire->name[0] == '\\') {
                std::string base_name = wire->name.str().substr(1);
                for (int i = 0; i < wire->width; i++) {
                    SigBit bit = sigmap(SigBit(wire, i));
                    if (wire->width == 1) {
                        rtl_names[bit] = base_name;
                    } else {
                        rtl_names[bit] = base_name + "[" + std::to_string(i) + "]";
                    }
                }
            }
        }
    }

    // 构建AIG
    void build_aig() {
        // 1. 收集输入
        for (auto wire : module->wires()) {
            if (wire->port_input) {
                for (int i = 0; i < wire->width; i++) {
                    SigBit bit = sigmap(SigBit(wire, i));
                    if (!aig_map.count(bit)) {
                        int lit = next_aig_id++ * 2;
                        aig_map[bit] = lit;
                        inputs.push_back(bit);
                    }
                }
            }
        }

        // 2. 收集DFF（支持各种类型）
        for (auto cell : module->cells()) {
            bool is_dff = (cell->type == ID($_DFF_P_) || cell->type == ID($_DFF_N_) ||
                cell->type == ID($_DFF_PP0_) || cell->type == ID($_DFF_PP1_) ||
                cell->type == ID($_DFF_PN0_) || cell->type == ID($_DFF_PN1_) ||
                cell->type == ID($_DFF_NP0_) || cell->type == ID($_DFF_NP1_) ||
                cell->type == ID($_DFF_NN0_) || cell->type == ID($_DFF_NN1_) ||
                cell->type == ID($_DFFE_PP_) || cell->type == ID($_DFFE_PN_) ||
                cell->type == ID($_DFFE_NP_) || cell->type == ID($_DFFE_NN_) ||
                cell->type == ID($_DFFE_PP0P_) || cell->type == ID($_DFFE_PP0N_) ||
                cell->type == ID($_DFFE_PP1P_) || cell->type == ID($_DFFE_PP1N_) ||
                cell->type == ID($_DFFE_PN0P_) || cell->type == ID($_DFFE_PN0N_) ||
                cell->type == ID($_DFFE_PN1P_) || cell->type == ID($_DFFE_PN1N_) ||
                cell->type == ID($_DFFE_NP0P_) || cell->type == ID($_DFFE_NP0N_) ||
                cell->type == ID($_DFFE_NP1P_) || cell->type == ID($_DFFE_NP1N_) ||
                cell->type == ID($_DFFE_NN0P_) || cell->type == ID($_DFFE_NN0N_) ||
                cell->type == ID($_DFFE_NN1P_) || cell->type == ID($_DFFE_NN1N_));

            if (is_dff) {
                SigBit q_bit = sigmap(cell->getPort(ID::Q)[0]);
                SigBit d_bit = sigmap(cell->getPort(ID::D)[0]);

                if (!aig_map.count(q_bit)) {
                    int lit = next_aig_id++ * 2;
                    aig_map[q_bit] = lit;
                    latches.push_back(q_bit);
                    latch_next.push_back(d_bit);

                    std::string rtl_name = find_rtl_name_for_bit(q_bit);
                    if (!rtl_name.empty()) {
                        latch_rtl_names[q_bit] = rtl_name;
                    }
                }
            }
        }

        // 3. 拓扑排序处理AND/NOT门
        std::set<Cell*> processed;
        bool changed = true;
        while (changed) {
            changed = false;
            for (auto cell : module->cells()) {
                if (processed.count(cell))
                    continue;

                if (cell->type == ID($_NOT_)) {
                    SigBit a = sigmap(cell->getPort(ID::A)[0]);
                    SigBit y = sigmap(cell->getPort(ID::Y)[0]);

                    if (aig_map.count(a) && !aig_map.count(y)) {
                        aig_map[y] = aig_map[a] ^ 1;
                        processed.insert(cell);
                        changed = true;
                    }
                }
                else if (cell->type == ID($_AND_)) {
                    SigBit a = sigmap(cell->getPort(ID::A)[0]);
                    SigBit b = sigmap(cell->getPort(ID::B)[0]);
                    SigBit y = sigmap(cell->getPort(ID::Y)[0]);

                    if (aig_map.count(a) && aig_map.count(b) && !aig_map.count(y)) {
                        int lit = next_aig_id++ * 2;
                        aig_map[y] = lit;
                        aig_ands.push_back({aig_map[a], aig_map[b]});
                        processed.insert(cell);
                        changed = true;
                    }
                }
            }
        }

        // 4. 收集输出
        for (auto wire : module->wires()) {
            if (wire->port_output) {
                for (int i = 0; i < wire->width; i++) {
                    SigBit bit = sigmap(SigBit(wire, i));
                    outputs.push_back(bit);
                }
            }
        }
    }

    // 确定AIG节点类型
    std::string get_aig_node_type(int aig_lit) {
        int aig_node = aig_lit / 2;
        if (aig_node == 0) return "constant";

        int num_inputs = inputs.size();
        int num_latches = latches.size();

        // 节点1到num_inputs是PI
        if (aig_node >= 1 && aig_node <= num_inputs) {
            return "input";
        }
        // 节点num_inputs+1到num_inputs+num_latches是latch
        if (aig_node >= num_inputs + 1 && aig_node <= num_inputs + num_latches) {
            return "latch";
        }
        // 其他是AND门
        return "and";
    }

    // 导出JSON映射 - 从RTL信号角度出发
    void export_json(const std::string &filename) {
        std::ofstream f(filename);

        int max_var = next_aig_id - 1;

        f << "{\n";
        f << "  \"aig_info\": {\n";
        f << "    \"num_inputs\": " << inputs.size() << ",\n";
        f << "    \"num_latches\": " << latches.size() << ",\n";
        f << "    \"num_outputs\": " << outputs.size() << ",\n";
        f << "    \"num_ands\": " << aig_ands.size() << ",\n";
        f << "    \"max_var\": " << max_var << "\n";
        f << "  },\n";

        // 收集所有RTL信号（从saved_names和当前公共wire）
        dict<std::string, std::vector<std::tuple<int, int, bool, std::string>>> all_signals;
        // tuple: (bit_idx, aig_node, inverted, node_type)

        // 1. 遍历所有当前公共wire
        for (auto wire : module->wires()) {
            if (wire->name[0] != '\\')
                continue;

            std::string base_name = wire->name.str().substr(1);

            for (int i = 0; i < wire->width; i++) {
                SigBit bit = sigmap(SigBit(wire, i));
                int bit_idx = wire->start_offset + i;

                // 查找这个bit的AIG映射
                if (aig_map.count(bit)) {
                    int aig_lit = aig_map[bit];
                    int aig_node = aig_lit / 2;
                    bool inverted = (aig_lit % 2) == 1;
                    std::string node_type = get_aig_node_type(aig_lit);

                    all_signals[base_name].push_back(
                        std::make_tuple(bit_idx, aig_node, inverted, node_type));
                } else {
                    // 信号被优化为常量或不存在于AIG
                    all_signals[base_name].push_back(
                        std::make_tuple(bit_idx, -1, false, "optimized"));
                }
            }
        }

        // 2. 检查saved_names中的信号（综合前记录的）
        for (auto &it : RecordRtlSignals::saved_names) {
            SigBit saved_bit = it.first;
            std::string full_name = it.second;

            // 解析信号名和bit索引
            std::string base_name = full_name;
            int bit_idx = 0;
            size_t bracket = full_name.find('[');
            if (bracket != std::string::npos) {
                base_name = full_name.substr(0, bracket);
                bit_idx = std::stoi(full_name.substr(bracket + 1));
            }

            // 如果这个信号还没有被记录，添加它
            bool already_recorded = false;
            if (all_signals.count(base_name)) {
                for (auto &entry : all_signals[base_name]) {
                    if (std::get<0>(entry) == bit_idx) {
                        already_recorded = true;
                        break;
                    }
                }
            }

            if (!already_recorded) {
                // 尝试在当前设计中找到这个信号
                SigBit current_bit = sigmap(saved_bit);
                if (aig_map.count(current_bit)) {
                    int aig_lit = aig_map[current_bit];
                    int aig_node = aig_lit / 2;
                    bool inverted = (aig_lit % 2) == 1;
                    std::string node_type = get_aig_node_type(aig_lit);

                    all_signals[base_name].push_back(
                        std::make_tuple(bit_idx, aig_node, inverted, node_type));
                } else {
                    // 信号被优化掉了
                    all_signals[base_name].push_back(
                        std::make_tuple(bit_idx, -1, false, "optimized"));
                }
            }
        }

        // 输出信号映射
        f << "  \"signals\": {\n";

        bool first_signal = true;
        for (auto &it : all_signals) {
            if (!first_signal) f << ",\n";
            first_signal = false;

            const std::string &name = it.first;
            auto &bits = it.second;

            // 排序
            std::sort(bits.begin(), bits.end());

            // 计算width
            int width = 0;
            for (auto &b : bits) {
                width = std::max(width, std::get<0>(b) + 1);
            }

            // 确定主类型（大多数bit的类型）
            std::string main_type = "optimized";
            for (auto &b : bits) {
                std::string t = std::get<3>(b);
                if (t == "input" || t == "latch") {
                    main_type = t;
                    break;
                } else if (t == "and" && main_type == "optimized") {
                    main_type = t;
                }
            }

            // is_sampled: input和latch需要从trace采样
            bool is_sampled = (main_type == "input" || main_type == "latch");

            f << "    \"" << escape_json(name) << "\": {\n";
            f << "      \"width\": " << width << ",\n";
            f << "      \"type\": \"" << main_type << "\",\n";
            f << "      \"is_sampled\": " << (is_sampled ? "true" : "false") << ",\n";
            f << "      \"bits\": [";

            bool first_bit = true;
            for (auto &bit_info : bits) {
                if (!first_bit) f << ", ";
                first_bit = false;
                int bit_idx = std::get<0>(bit_info);
                int aig_node = std::get<1>(bit_info);
                bool inverted = std::get<2>(bit_info);
                std::string node_type = std::get<3>(bit_info);

                f << "{\"bit\": " << bit_idx
                  << ", \"aig_node\": " << aig_node
                  << ", \"inverted\": " << (inverted ? "true" : "false")
                  << ", \"node_type\": \"" << node_type << "\"}";
            }
            f << "]\n    }";
        }
        f << "\n  }\n";
        f << "}\n";
        f.close();

        log("Exported signal mapping to %s\n", filename.c_str());
        log("  Total RTL signals: %zu\n", all_signals.size());
        log("  Inputs: %zu, Latches: %zu, Outputs: %zu, ANDs: %zu\n",
            inputs.size(), latches.size(), outputs.size(), aig_ands.size());
    }

    // 收集信号用于导出
    void collect_signals_for_export(
        const std::vector<SigBit> &bits,
        const std::string &type,
        bool is_sampled,
        dict<std::string, std::tuple<std::string, bool, std::vector<std::tuple<int, int, bool>>>> &all_signals
    ) {
        for (size_t i = 0; i < bits.size(); i++) {
            SigBit bit = bits[i];
            std::string name = "unknown";
            int bit_idx = 0;
            std::string full_name;

            if (type == "latch" && latch_rtl_names.count(bit)) {
                full_name = latch_rtl_names[bit];
            } else if (rtl_names.count(bit)) {
                full_name = rtl_names[bit];
            }

            if (!full_name.empty()) {
                size_t bracket = full_name.find('[');
                if (bracket != std::string::npos) {
                    name = full_name.substr(0, bracket);
                    bit_idx = std::stoi(full_name.substr(bracket + 1));
                } else {
                    name = full_name;
                    bit_idx = 0;
                }
            } else {
                for (auto wire : module->wires()) {
                    for (int j = 0; j < wire->width; j++) {
                        if (sigmap(SigBit(wire, j)) == bit) {
                            name = wire->name.str();
                            if (name[0] == '\\') name = name.substr(1);
                            bit_idx = j;
                            goto found;
                        }
                    }
                }
                found:;
            }

            int aig_lit = aig_map.count(bit) ? aig_map[bit] : -1;
            int aig_node = aig_lit / 2;
            bool inverted = (aig_lit % 2) == 1;

            if (!all_signals.count(name)) {
                all_signals[name] = std::make_tuple(type, is_sampled, std::vector<std::tuple<int, int, bool>>());
            }
            std::get<2>(all_signals[name]).push_back(std::make_tuple(bit_idx, aig_node, inverted));
        }
    }

    // 导出AIGER格式（ASCII），包含symbol信息
    void export_aiger(const std::string &filename) {
        std::ofstream f(filename);

        int M = next_aig_id - 1;
        int I = inputs.size();
        int L = latches.size();
        int O = outputs.size();
        int A = aig_ands.size();

        f << "aag " << M << " " << I << " " << L << " " << O << " " << A << "\n";

        for (auto &bit : inputs) {
            f << aig_map[bit] << "\n";
        }

        for (size_t i = 0; i < latches.size(); i++) {
            int current_lit = aig_map[latches[i]];
            int next_lit = aig_map.count(latch_next[i]) ? aig_map[latch_next[i]] : 0;
            f << current_lit << " " << next_lit << "\n";
        }

        for (auto &bit : outputs) {
            int lit = aig_map.count(bit) ? aig_map[bit] : 0;
            f << lit << "\n";
        }

        int and_lit = (1 + I + L) * 2;
        for (auto &and_gate : aig_ands) {
            f << and_lit << " " << and_gate.first << " " << and_gate.second << "\n";
            and_lit += 2;
        }

        // 写入symbol section（AIGER格式规范）
        // 输入符号: i<idx> <name>
        for (size_t i = 0; i < inputs.size(); i++) {
            std::string name = get_signal_name(inputs[i]);
            if (!name.empty()) {
                f << "i" << i << " " << name << "\n";
            }
        }

        // Latch符号: l<idx> <name>
        for (size_t i = 0; i < latches.size(); i++) {
            std::string name;
            if (latch_rtl_names.count(latches[i])) {
                name = latch_rtl_names[latches[i]];
            } else {
                name = get_signal_name(latches[i]);
            }
            if (!name.empty()) {
                f << "l" << i << " " << name << "\n";
            }
        }

        // 输出符号: o<idx> <name>
        for (size_t i = 0; i < outputs.size(); i++) {
            std::string name = get_signal_name(outputs[i]);
            if (!name.empty()) {
                f << "o" << i << " " << name << "\n";
            }
        }

        f.close();

        log("Exported AIGER to %s\n", filename.c_str());
        log("  aag %d %d %d %d %d\n", M, I, L, O, A);
        log("  Symbols: %zu inputs, %zu latches, %zu outputs\n", inputs.size(), latches.size(), outputs.size());
    }

    // 获取信号名称
    std::string get_signal_name(SigBit bit) {
        // 1. 先检查rtl_names
        if (rtl_names.count(bit)) {
            return rtl_names[bit];
        }
        // 2. 检查saved_names
        if (RecordRtlSignals::saved_names.count(bit)) {
            return RecordRtlSignals::saved_names[bit];
        }
        // 3. 尝试从wire获取
        for (auto wire : module->wires()) {
            if (wire->name[0] != '\\')
                continue;
            for (int i = 0; i < wire->width; i++) {
                if (sigmap(SigBit(wire, i)) == bit) {
                    std::string base_name = wire->name.str().substr(1);
                    if (wire->width == 1) {
                        return base_name;
                    } else {
                        return base_name + "[" + std::to_string(wire->start_offset + i) + "]";
                    }
                }
            }
        }
        return "";
    }

private:
    std::string escape_json(const std::string &s) {
        std::string result;
        for (char c : s) {
            if (c == '"') result += "\\\"";
            else if (c == '\\') result += "\\\\";
            else result += c;
        }
        return result;
    }
};

// Yosys Pass: 记录RTL信号名
struct RecordRtlSignalsPass : public Pass {
    RecordRtlSignalsPass() : Pass("record_rtl_signals", "Record RTL signal names for mapping") { }

    void execute(std::vector<std::string> args, RTLIL::Design *design) override {
        log_header(design, "Executing RECORD_RTL_SIGNALS pass.\n");
        extra_args(args, 1, design);

        for (auto module : design->selected_modules()) {
            SigMap sigmap(module);

            for (auto wire : module->wires()) {
                if (wire->name[0] == '\\') {
                    std::string base_name = wire->name.str().substr(1);
                    for (int i = 0; i < wire->width; i++) {
                        SigBit bit = sigmap(SigBit(wire, i));
                        if (wire->width == 1) {
                            RecordRtlSignals::saved_names[bit] = base_name;
                        } else {
                            RecordRtlSignals::saved_names[bit] = base_name + "[" + std::to_string(wire->start_offset + i) + "]";
                        }
                    }
                }
            }

            log("Recorded %zu RTL signal names from module %s\n",
                RecordRtlSignals::saved_names.size(), log_id(module));
        }
    }
} RecordRtlSignalsPass;

// Yosys Pass: 输出信号映射和AIGER
struct WriteSignalMapPass : public Pass {
    WriteSignalMapPass() : Pass("write_signal_map", "Write signal mapping JSON and AIGER file") { }

    void help() override {
        log("\n");
        log("    write_signal_map <json_filename> [aig_filename]\n");
        log("\n");
        log("Write a JSON file mapping RTL signal bits to AIG node IDs.\n");
        log("Optionally also write an AIGER file with matching node IDs.\n");
        log("\n");
    }

    void execute(std::vector<std::string> args, RTLIL::Design *design) override {
        log_header(design, "Executing WRITE_SIGNAL_MAP pass.\n");

        if (args.size() < 2 || args.size() > 3) {
            log_error("Usage: write_signal_map <json_filename> [aig_filename]\n");
        }

        std::string json_filename = args[1];
        std::string aig_filename = (args.size() >= 3) ? args[2] : "";

        for (auto module : design->selected_modules()) {
            SignalMapper mapper(module);

            mapper.rtl_names = RecordRtlSignals::saved_names;
            mapper.record_rtl_names();
            mapper.build_aig();
            mapper.export_json(json_filename);

            if (!aig_filename.empty()) {
                mapper.export_aiger(aig_filename);
            }
        }
    }
} WriteSignalMapPass;

PRIVATE_NAMESPACE_END
