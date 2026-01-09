/**
 * Simple ALU Design - 用于验证中间节点波形补全
 *
 * 特点：
 * 1. 中间信号作为输出，不会被优化掉
 * 2. 中间信号会映射到AIG的AND gate节点
 * 3. 结构简单，便于验证
 */

module simple_alu (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  a,
    input  wire [7:0]  b,
    input  wire [2:0]  op,

    // 主输出
    output reg  [7:0]  result,
    output reg         zero,
    output reg         carry,

    // 中间信号输出 - 这些会映射到AIG AND节点
    output wire [7:0]  add_result,
    output wire [7:0]  sub_result,
    output wire [7:0]  and_result,
    output wire [7:0]  or_result,
    output wire [7:0]  xor_result,
    output wire        add_carry,
    output wire        result_is_zero
);

    // ========================================
    // 内部中间信号
    // ========================================
    wire [8:0] add_full;
    wire [8:0] sub_full;
    wire [7:0] selected_result;

    // ========================================
    // 组合逻辑 - 计算中间结果
    // ========================================

    // 基本运算
    assign add_full = {1'b0, a} + {1'b0, b};
    assign sub_full = {1'b0, a} - {1'b0, b};

    assign add_result = add_full[7:0];
    assign sub_result = sub_full[7:0];
    assign and_result = a & b;
    assign or_result  = a | b;
    assign xor_result = a ^ b;

    // 进位检测
    assign add_carry = add_full[8];

    // 结果选择 (组合逻辑MUX)
    assign selected_result = (op == 3'b000) ? add_result :
                             (op == 3'b001) ? sub_result :
                             (op == 3'b010) ? and_result :
                             (op == 3'b011) ? or_result :
                             (op == 3'b100) ? xor_result :
                                              8'b0;

    // 零检测
    assign result_is_zero = (selected_result == 8'b0);

    // ========================================
    // 时序逻辑 - 寄存器更新
    // ========================================

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result <= 8'b0;
            zero   <= 1'b0;
            carry  <= 1'b0;
        end else begin
            result <= selected_result;
            zero   <= result_is_zero;
            carry  <= (op == 3'b000) ? add_carry : 1'b0;
        end
    end

endmodule
