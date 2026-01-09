// Testbench for mini_cpu
// 生成测试激励并提供VPI采集入口

`timescale 1ns/1ps

module testbench;

    // 时钟和复位
    reg         clk;
    reg         rst_n;

    // CPU接口
    reg  [31:0] instr_in;
    reg  [31:0] data_in;
    wire [31:0] pc_out;
    wire [31:0] data_out;
    wire        mem_read;
    wire        mem_write;

    // 实例化DUT
    mini_cpu dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .instr_in  (instr_in),
        .data_in   (data_in),
        .pc_out    (pc_out),
        .data_out  (data_out),
        .mem_read  (mem_read),
        .mem_write (mem_write)
    );

    // 简单的指令存储器 (ROM)
    reg [31:0] imem [0:255];

    // 简单的数据存储器 (RAM)
    reg [31:0] dmem [0:255];

    // 时钟生成
    initial begin
        clk = 0;
        forever #5 clk = ~clk;  // 100MHz
    end

    // 指令读取
    always @(*) begin
        instr_in = imem[pc_out[9:2]];  // 字对齐
    end

    // 数据存储器访问
    always @(posedge clk) begin
        if (mem_write) begin
            dmem[data_out[9:2]] <= data_out;
        end
    end

    always @(*) begin
        data_in = dmem[data_out[9:2]];
    end

    // 循环变量
    integer i;

    // 初始化和测试序列
    initial begin
        // 初始化存储器
        for (i = 0; i < 256; i = i + 1) begin
            imem[i] = 32'h00000013;  // NOP (addi x0, x0, 0)
            dmem[i] = 32'b0;
        end

        // 加载测试程序
        // ADDI x1, x0, 10     ; x1 = 10
        imem[0]  = 32'h00a00093;
        // ADDI x2, x0, 20     ; x2 = 20
        imem[1]  = 32'h01400113;
        // ADD  x3, x1, x2     ; x3 = x1 + x2 = 30
        imem[2]  = 32'h002081b3;
        // SUB  x4, x2, x1     ; x4 = x2 - x1 = 10
        imem[3]  = 32'h40110233;
        // AND  x5, x1, x2     ; x5 = x1 & x2
        imem[4]  = 32'h0020f2b3;
        // OR   x6, x1, x2     ; x6 = x1 | x2
        imem[5]  = 32'h0020e333;
        // XOR  x7, x1, x2     ; x7 = x1 ^ x2
        imem[6]  = 32'h0020c3b3;
        // SLL  x1, x1, x2     ; x1 = x1 << x2
        imem[7]  = 32'h00209093;
        // NOP padding
        imem[8]  = 32'h00000013;
        imem[9]  = 32'h00000013;
        imem[10] = 32'h00000013;

        // 复位序列
        rst_n = 0;
        #20;
        rst_n = 1;

        // 运行100个周期
        #1000;

        $display("Simulation finished");
        $finish;
    end

    // VCD波形记录 (golden reference)
    initial begin
`ifdef GOLDEN_VCD
        $dumpfile(`GOLDEN_VCD_FILE);
`else
        $dumpfile("golden.vcd");
`endif
        $dumpvars(0, testbench);
    end

    // VPI Trace初始化 (由VPI插件提供)
    // 在实际运行时，VPI会通过系统任务采集信号
    // $trace_init("signal_list.txt", "testbench.dut.clk", "output/traces/trace.txt");

endmodule
