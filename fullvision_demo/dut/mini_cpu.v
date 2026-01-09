// Mini CPU - 简化的RISC处理器，用于FullVision Demo
// 约500个单比特信号，包含寄存器和组合逻辑

module mini_cpu (
    input         clk,
    input         rst_n,
    input  [31:0] instr_in,     // 指令输入
    input  [31:0] data_in,      // 数据输入
    output [31:0] pc_out,       // 程序计数器输出
    output [31:0] data_out,     // 数据输出
    output        mem_read,     // 内存读使能
    output        mem_write     // 内存写使能
);

    // ============================================================
    // 寄存器定义 (需要采集的信号)
    // ============================================================

    // 程序计数器 (32 bits)
    reg [31:0] pc;

    // 寄存器文件 (8x32 = 256 bits)
    reg [31:0] regfile [0:7];

    // IF/ID 流水线寄存器 (64 bits)
    reg [31:0] if_id_instr;
    reg [31:0] if_id_pc;

    // ID/EX 流水线寄存器 (139 bits)
    reg [31:0] id_ex_rs1_data;
    reg [31:0] id_ex_rs2_data;
    reg [31:0] id_ex_imm;
    reg [31:0] id_ex_pc;
    reg [4:0]  id_ex_rd;
    reg [2:0]  id_ex_rs1;
    reg [2:0]  id_ex_rs2;
    reg [3:0]  id_ex_alu_op;
    reg        id_ex_mem_read;
    reg        id_ex_mem_write;
    reg        id_ex_reg_write;
    reg        id_ex_alu_src;    // 0: rs2, 1: imm
    reg        id_ex_branch;
    reg        id_ex_jump;

    // EX/MEM 流水线寄存器 (105 bits)
    reg [31:0] ex_mem_alu_result;
    reg [31:0] ex_mem_rs2_data;
    reg [31:0] ex_mem_pc_plus_4;
    reg [4:0]  ex_mem_rd;
    reg        ex_mem_mem_read;
    reg        ex_mem_mem_write;
    reg        ex_mem_reg_write;
    reg        ex_mem_zero;
    reg        ex_mem_branch;

    // MEM/WB 流水线寄存器 (70 bits)
    reg [31:0] mem_wb_read_data;
    reg [31:0] mem_wb_alu_result;
    reg [4:0]  mem_wb_rd;
    reg        mem_wb_reg_write;
    reg        mem_wb_mem_to_reg;

    // 控制状态寄存器 (8 bits)
    reg [2:0] state;
    reg [4:0] stall_counter;

    // ============================================================
    // 指令解码 (组合逻辑)
    // ============================================================

    wire [6:0] opcode   = if_id_instr[6:0];
    wire [2:0] funct3   = if_id_instr[14:12];
    wire [6:0] funct7   = if_id_instr[31:25];
    wire [2:0] rs1_addr = if_id_instr[17:15];  // 简化为3位
    wire [2:0] rs2_addr = if_id_instr[22:20];  // 简化为3位
    wire [2:0] rd_addr  = if_id_instr[9:7];    // 简化为3位

    // 立即数生成
    wire [31:0] imm_i = {{20{if_id_instr[31]}}, if_id_instr[31:20]};
    wire [31:0] imm_s = {{20{if_id_instr[31]}}, if_id_instr[31:25], if_id_instr[11:7]};
    wire [31:0] imm_b = {{19{if_id_instr[31]}}, if_id_instr[31], if_id_instr[7],
                         if_id_instr[30:25], if_id_instr[11:8], 1'b0};
    wire [31:0] imm_u = {if_id_instr[31:12], 12'b0};
    wire [31:0] imm_j = {{11{if_id_instr[31]}}, if_id_instr[31], if_id_instr[19:12],
                         if_id_instr[20], if_id_instr[30:21], 1'b0};

    // ============================================================
    // 控制信号生成 (组合逻辑)
    // ============================================================

    // 操作码定义
    localparam OP_LOAD   = 7'b0000011;
    localparam OP_STORE  = 7'b0100011;
    localparam OP_BRANCH = 7'b1100011;
    localparam OP_JAL    = 7'b1101111;
    localparam OP_JALR   = 7'b1100111;
    localparam OP_IMM    = 7'b0010011;
    localparam OP_REG    = 7'b0110011;
    localparam OP_LUI    = 7'b0110111;
    localparam OP_AUIPC  = 7'b0010111;

    // 控制信号
    wire ctrl_mem_read;
    wire ctrl_mem_write;
    wire ctrl_reg_write;
    wire ctrl_alu_src;
    wire ctrl_branch;
    wire ctrl_jump;
    wire [3:0] ctrl_alu_op;
    wire [31:0] ctrl_imm;

    assign ctrl_mem_read  = (opcode == OP_LOAD);
    assign ctrl_mem_write = (opcode == OP_STORE);
    assign ctrl_reg_write = (opcode == OP_LOAD)   || (opcode == OP_IMM)  ||
                            (opcode == OP_REG)    || (opcode == OP_JAL)  ||
                            (opcode == OP_JALR)   || (opcode == OP_LUI)  ||
                            (opcode == OP_AUIPC);
    assign ctrl_alu_src   = (opcode == OP_LOAD)   || (opcode == OP_STORE) ||
                            (opcode == OP_IMM)    || (opcode == OP_JALR);
    assign ctrl_branch    = (opcode == OP_BRANCH);
    assign ctrl_jump      = (opcode == OP_JAL) || (opcode == OP_JALR);

    // ALU操作码生成
    assign ctrl_alu_op = (opcode == OP_REG && funct7[5]) ? 4'b0001 :  // SUB
                         (funct3 == 3'b000) ? 4'b0000 :  // ADD
                         (funct3 == 3'b001) ? 4'b0101 :  // SLL
                         (funct3 == 3'b010) ? 4'b1000 :  // SLT
                         (funct3 == 3'b011) ? 4'b1001 :  // SLTU
                         (funct3 == 3'b100) ? 4'b0100 :  // XOR
                         (funct3 == 3'b101) ? 4'b0110 :  // SRL/SRA
                         (funct3 == 3'b110) ? 4'b0011 :  // OR
                         (funct3 == 3'b111) ? 4'b0010 :  // AND
                         4'b0000;

    // 立即数选择
    assign ctrl_imm = (opcode == OP_STORE)  ? imm_s :
                      (opcode == OP_BRANCH) ? imm_b :
                      (opcode == OP_JAL)    ? imm_j :
                      (opcode == OP_LUI)    ? imm_u :
                      (opcode == OP_AUIPC)  ? imm_u :
                      imm_i;

    // ============================================================
    // 寄存器文件读取 (组合逻辑)
    // ============================================================

    wire [31:0] rs1_data = regfile[rs1_addr];
    wire [31:0] rs2_data = regfile[rs2_addr];

    // 数据前递
    wire [31:0] fwd_rs1_data;
    wire [31:0] fwd_rs2_data;
    wire fwd_ex_rs1  = ex_mem_reg_write && (ex_mem_rd[2:0] == rs1_addr) && (ex_mem_rd != 0);
    wire fwd_ex_rs2  = ex_mem_reg_write && (ex_mem_rd[2:0] == rs2_addr) && (ex_mem_rd != 0);
    wire fwd_mem_rs1 = mem_wb_reg_write && (mem_wb_rd[2:0] == rs1_addr) && (mem_wb_rd != 0);
    wire fwd_mem_rs2 = mem_wb_reg_write && (mem_wb_rd[2:0] == rs2_addr) && (mem_wb_rd != 0);

    assign fwd_rs1_data = fwd_ex_rs1  ? ex_mem_alu_result :
                          fwd_mem_rs1 ? (mem_wb_mem_to_reg ? mem_wb_read_data : mem_wb_alu_result) :
                          rs1_data;
    assign fwd_rs2_data = fwd_ex_rs2  ? ex_mem_alu_result :
                          fwd_mem_rs2 ? (mem_wb_mem_to_reg ? mem_wb_read_data : mem_wb_alu_result) :
                          rs2_data;

    // ============================================================
    // ALU (组合逻辑)
    // ============================================================

    wire [31:0] alu_a = id_ex_rs1_data;
    wire [31:0] alu_b = id_ex_alu_src ? id_ex_imm : id_ex_rs2_data;
    wire [31:0] alu_result;
    wire        alu_zero;

    // ALU运算
    wire [31:0] alu_add  = alu_a + alu_b;
    wire [31:0] alu_sub  = alu_a - alu_b;
    wire [31:0] alu_and  = alu_a & alu_b;
    wire [31:0] alu_or   = alu_a | alu_b;
    wire [31:0] alu_xor  = alu_a ^ alu_b;
    wire [31:0] alu_sll  = alu_a << alu_b[4:0];
    wire [31:0] alu_srl  = alu_a >> alu_b[4:0];
    wire [31:0] alu_sra  = $signed(alu_a) >>> alu_b[4:0];
    wire [31:0] alu_slt  = ($signed(alu_a) < $signed(alu_b)) ? 32'd1 : 32'd0;
    wire [31:0] alu_sltu = (alu_a < alu_b) ? 32'd1 : 32'd0;

    assign alu_result = (id_ex_alu_op == 4'b0000) ? alu_add  :
                        (id_ex_alu_op == 4'b0001) ? alu_sub  :
                        (id_ex_alu_op == 4'b0010) ? alu_and  :
                        (id_ex_alu_op == 4'b0011) ? alu_or   :
                        (id_ex_alu_op == 4'b0100) ? alu_xor  :
                        (id_ex_alu_op == 4'b0101) ? alu_sll  :
                        (id_ex_alu_op == 4'b0110) ? alu_srl  :
                        (id_ex_alu_op == 4'b0111) ? alu_sra  :
                        (id_ex_alu_op == 4'b1000) ? alu_slt  :
                        (id_ex_alu_op == 4'b1001) ? alu_sltu :
                        32'b0;

    assign alu_zero = (alu_result == 32'b0);

    // ============================================================
    // 分支判断 (组合逻辑)
    // ============================================================

    wire branch_taken;
    wire [31:0] branch_target = id_ex_pc + id_ex_imm;
    wire [31:0] jump_target   = id_ex_jump ? (id_ex_rs1_data + id_ex_imm) : branch_target;

    assign branch_taken = id_ex_branch && (
        (id_ex_alu_op[2:0] == 3'b000 && alu_zero)  ||  // BEQ
        (id_ex_alu_op[2:0] == 3'b001 && !alu_zero) ||  // BNE
        (id_ex_alu_op[2:0] == 3'b100 && alu_result[0]) ||  // BLT
        (id_ex_alu_op[2:0] == 3'b101 && !alu_result[0]) || // BGE
        (id_ex_alu_op[2:0] == 3'b110 && alu_result[0]) ||  // BLTU
        (id_ex_alu_op[2:0] == 3'b111 && !alu_result[0])    // BGEU
    );

    // ============================================================
    // PC计算 (组合逻辑)
    // ============================================================

    wire [31:0] pc_plus_4 = pc + 32'd4;
    wire [31:0] next_pc = (id_ex_jump || branch_taken) ? jump_target : pc_plus_4;

    // ============================================================
    // 冒险检测 (组合逻辑)
    // ============================================================

    wire load_use_hazard = id_ex_mem_read &&
                           ((id_ex_rd[2:0] == rs1_addr) || (id_ex_rd[2:0] == rs2_addr));
    wire stall = load_use_hazard;
    wire flush = branch_taken || id_ex_jump;

    // ============================================================
    // 写回数据选择 (组合逻辑)
    // ============================================================

    wire [31:0] wb_data = mem_wb_mem_to_reg ? mem_wb_read_data : mem_wb_alu_result;

    // ============================================================
    // 输出
    // ============================================================

    assign pc_out    = pc;
    assign data_out  = ex_mem_rs2_data;
    assign mem_read  = ex_mem_mem_read;
    assign mem_write = ex_mem_mem_write;

    // ============================================================
    // 时序逻辑
    // ============================================================

    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // 复位所有寄存器
            pc <= 32'b0;

            for (i = 0; i < 8; i = i + 1) begin
                regfile[i] <= 32'b0;
            end

            if_id_instr <= 32'b0;
            if_id_pc    <= 32'b0;

            id_ex_rs1_data  <= 32'b0;
            id_ex_rs2_data  <= 32'b0;
            id_ex_imm       <= 32'b0;
            id_ex_pc        <= 32'b0;
            id_ex_rd        <= 5'b0;
            id_ex_rs1       <= 3'b0;
            id_ex_rs2       <= 3'b0;
            id_ex_alu_op    <= 4'b0;
            id_ex_mem_read  <= 1'b0;
            id_ex_mem_write <= 1'b0;
            id_ex_reg_write <= 1'b0;
            id_ex_alu_src   <= 1'b0;
            id_ex_branch    <= 1'b0;
            id_ex_jump      <= 1'b0;

            ex_mem_alu_result <= 32'b0;
            ex_mem_rs2_data   <= 32'b0;
            ex_mem_pc_plus_4  <= 32'b0;
            ex_mem_rd         <= 5'b0;
            ex_mem_mem_read   <= 1'b0;
            ex_mem_mem_write  <= 1'b0;
            ex_mem_reg_write  <= 1'b0;
            ex_mem_zero       <= 1'b0;
            ex_mem_branch     <= 1'b0;

            mem_wb_read_data  <= 32'b0;
            mem_wb_alu_result <= 32'b0;
            mem_wb_rd         <= 5'b0;
            mem_wb_reg_write  <= 1'b0;
            mem_wb_mem_to_reg <= 1'b0;

            state         <= 3'b0;
            stall_counter <= 5'b0;

        end else begin

            // ---- IF Stage ----
            if (!stall) begin
                pc <= next_pc;
            end

            // ---- IF/ID Pipeline Register ----
            if (flush) begin
                if_id_instr <= 32'b0;  // NOP
                if_id_pc    <= 32'b0;
            end else if (!stall) begin
                if_id_instr <= instr_in;
                if_id_pc    <= pc;
            end

            // ---- ID/EX Pipeline Register ----
            if (flush || stall) begin
                id_ex_rs1_data  <= 32'b0;
                id_ex_rs2_data  <= 32'b0;
                id_ex_imm       <= 32'b0;
                id_ex_pc        <= 32'b0;
                id_ex_rd        <= 5'b0;
                id_ex_rs1       <= 3'b0;
                id_ex_rs2       <= 3'b0;
                id_ex_alu_op    <= 4'b0;
                id_ex_mem_read  <= 1'b0;
                id_ex_mem_write <= 1'b0;
                id_ex_reg_write <= 1'b0;
                id_ex_alu_src   <= 1'b0;
                id_ex_branch    <= 1'b0;
                id_ex_jump      <= 1'b0;
            end else begin
                id_ex_rs1_data  <= fwd_rs1_data;
                id_ex_rs2_data  <= fwd_rs2_data;
                id_ex_imm       <= ctrl_imm;
                id_ex_pc        <= if_id_pc;
                id_ex_rd        <= {2'b0, rd_addr};
                id_ex_rs1       <= rs1_addr;
                id_ex_rs2       <= rs2_addr;
                id_ex_alu_op    <= ctrl_alu_op;
                id_ex_mem_read  <= ctrl_mem_read;
                id_ex_mem_write <= ctrl_mem_write;
                id_ex_reg_write <= ctrl_reg_write;
                id_ex_alu_src   <= ctrl_alu_src;
                id_ex_branch    <= ctrl_branch;
                id_ex_jump      <= ctrl_jump;
            end

            // ---- EX/MEM Pipeline Register ----
            ex_mem_alu_result <= alu_result;
            ex_mem_rs2_data   <= id_ex_rs2_data;
            ex_mem_pc_plus_4  <= id_ex_pc + 32'd4;
            ex_mem_rd         <= id_ex_rd;
            ex_mem_mem_read   <= id_ex_mem_read;
            ex_mem_mem_write  <= id_ex_mem_write;
            ex_mem_reg_write  <= id_ex_reg_write;
            ex_mem_zero       <= alu_zero;
            ex_mem_branch     <= id_ex_branch;

            // ---- MEM/WB Pipeline Register ----
            mem_wb_read_data  <= data_in;
            mem_wb_alu_result <= ex_mem_alu_result;
            mem_wb_rd         <= ex_mem_rd;
            mem_wb_reg_write  <= ex_mem_reg_write;
            mem_wb_mem_to_reg <= ex_mem_mem_read;

            // ---- Write Back ----
            if (mem_wb_reg_write && mem_wb_rd[2:0] != 3'b0) begin
                regfile[mem_wb_rd[2:0]] <= wb_data;
            end

            // ---- State & Counter ----
            state <= state + 1;
            if (stall)
                stall_counter <= stall_counter + 1;
            else
                stall_counter <= 5'b0;
        end
    end

endmodule
