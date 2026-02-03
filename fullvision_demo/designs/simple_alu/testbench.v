/**
 * Testbench for Simple ALU
 */

`timescale 1ns/1ps

module testbench;

    reg        clk;
    reg        rst_n;
    reg  [7:0] a;
    reg  [7:0] b;
    reg  [2:0] op;

    // 主输出
    wire [7:0] result;
    wire       zero;
    wire       carry;

    // 中间信号输出
    wire [7:0] add_result;
    wire [7:0] sub_result;
    wire [7:0] and_result;
    wire [7:0] or_result;
    wire [7:0] xor_result;
    wire       add_carry;
    wire       result_is_zero;

    // 实例化DUT
    simple_alu dut (
        .clk(clk),
        .rst_n(rst_n),
        .a(a),
        .b(b),
        .op(op),
        .result(result),
        .zero(zero),
        .carry(carry),
        .add_result(add_result),
        .sub_result(sub_result),
        .and_result(and_result),
        .or_result(or_result),
        .xor_result(xor_result),
        .add_carry(add_carry),
        .result_is_zero(result_is_zero)
    );

    // 时钟生成
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // VCD波形输出
    initial begin
`ifdef GOLDEN_VCD
        $dumpfile(`GOLDEN_VCD_FILE);
`else
        $dumpfile("simple_alu.vcd");
`endif
        $dumpvars(0, testbench);
    end

`ifdef TRACE_SIGNAL_LIST
    initial begin
        $trace_init(`TRACE_SIGNAL_LIST, "testbench.clk", `TRACE_OUTPUT_FILE);
    end
`endif

    // 测试序列
    initial begin
        // 初始化
        rst_n = 0;
        a = 8'h00;
        b = 8'h00;
        op = 3'b000;

        // 复位
        #20;
        rst_n = 1;

        // 测试ADD操作
        #10;
        a = 8'h05;
        b = 8'h03;
        op = 3'b000;  // ADD: 5 + 3 = 8

        #10;
        a = 8'hFF;
        b = 8'h01;
        op = 3'b000;  // ADD: 255 + 1 = 0 (with carry)

        #10;
        a = 8'h7F;
        b = 8'h01;
        op = 3'b000;  // ADD: 127 + 1 = 128

        // 测试SUB操作
        #10;
        a = 8'h10;
        b = 8'h05;
        op = 3'b001;  // SUB: 16 - 5 = 11

        #10;
        a = 8'h05;
        b = 8'h10;
        op = 3'b001;  // SUB: 5 - 16 = 245 (wrap around)

        // 测试AND操作
        #10;
        a = 8'hAA;
        b = 8'h55;
        op = 3'b010;  // AND: 0xAA & 0x55 = 0x00

        #10;
        a = 8'hFF;
        b = 8'h0F;
        op = 3'b010;  // AND: 0xFF & 0x0F = 0x0F

        // 测试OR操作
        #10;
        a = 8'hAA;
        b = 8'h55;
        op = 3'b011;  // OR: 0xAA | 0x55 = 0xFF

        // 测试XOR操作
        #10;
        a = 8'hAA;
        b = 8'hAA;
        op = 3'b100;  // XOR: 0xAA ^ 0xAA = 0x00

        #10;
        a = 8'hAA;
        b = 8'h55;
        op = 3'b100;  // XOR: 0xAA ^ 0x55 = 0xFF

        // 测试零检测
        #10;
        a = 8'h00;
        b = 8'h00;
        op = 3'b000;  // ADD: 0 + 0 = 0 (zero flag)

        // 结束
        #50;
        $finish;
    end

endmodule
