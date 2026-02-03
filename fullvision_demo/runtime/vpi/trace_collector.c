/**
 * VPI Trace Collector - iverilog VPI插件
 *
 * 功能：在每个时钟上升沿采集所有寄存器和top输入的值
 *
 * 使用方法：
 * 1. 编译: iverilog-vpi trace_collector.c
 * 2. 仿真: vvp -M. -mtrace_collector sim.vvp
 *
 * 在testbench中调用:
 *   initial begin
 *     $trace_init("signal_list.txt", "dut.clk", "trace.txt");
 *   end
 *
 *   // 仿真结束时
 *   initial begin
 *     #1000;
 *     $trace_finish;
 *     $finish;
 *   end
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vpi_user.h>

/* 配置 */
#define MAX_SIGNALS 2048
#define MAX_NAME_LEN 512

/* 全局状态 */
static vpiHandle signal_handles[MAX_SIGNALS];
static char signal_names[MAX_SIGNALS][MAX_NAME_LEN];
static int signal_widths[MAX_SIGNALS];
static int num_signals = 0;

static FILE* trace_file = NULL;
static PLI_INT64 current_time = 0;
static int last_clk_value = 0;
static int initialized = 0;

/**
 * 从配置文件加载需要采集的信号列表
 * 文件格式：每行一个信号，格式为 <signal_name> <width>
 */
static int load_signal_list(const char* config_file) {
    FILE* f = fopen(config_file, "r");
    if (!f) {
        vpi_printf("ERROR: Cannot open signal config file: %s\n", config_file);
        return 0;
    }

    char line[MAX_NAME_LEN];
    while (fgets(line, sizeof(line), f) && num_signals < MAX_SIGNALS) {
        /* 去除换行符 */
        line[strcspn(line, "\n\r")] = 0;
        if (strlen(line) == 0) continue;

        /* 解析信号名和位宽 */
        char name[MAX_NAME_LEN];
        int width = 1;
        if (sscanf(line, "%s %d", name, &width) < 1) {
            continue;
        }

        /* 获取信号句柄 */
        vpiHandle handle = vpi_handle_by_name(name, NULL);
        if (handle == NULL) {
            vpi_printf("WARNING: Signal not found: %s\n", name);
            continue;
        }

        signal_handles[num_signals] = handle;
        strncpy(signal_names[num_signals], name, MAX_NAME_LEN - 1);
        signal_widths[num_signals] = vpi_get(vpiSize, handle);

        vpi_printf("Registered signal: %s (width=%d)\n",
                   signal_names[num_signals], signal_widths[num_signals]);
        num_signals++;
    }

    fclose(f);
    vpi_printf("Total signals to trace: %d\n", num_signals);
    return 1;
}

/**
 * 采集一次所有信号值
 */
static void sample_signals(void) {
    if (!trace_file) return;

    s_vpi_value value;
    value.format = vpiBinStrVal;

    /* 写入时间戳 */
    fprintf(trace_file, "#%lld\n", (long long)current_time);

    /* 采集每个信号 */
    for (int i = 0; i < num_signals; i++) {
        vpi_get_value(signal_handles[i], &value);
        fprintf(trace_file, "%s %s\n", signal_names[i], value.value.str);
    }

    fflush(trace_file);
}

/**
 * 时钟变化回调
 */
static PLI_INT32 clock_callback(p_cb_data cb_data) {
    (void)cb_data;

    /* 获取当前仿真时间 */
    s_vpi_time time_s;
    time_s.type = vpiSimTime;
    vpi_get_time(NULL, &time_s);
    current_time = ((PLI_INT64)time_s.high << 32) | time_s.low;

    /* 获取时钟当前值 */
    s_vpi_value clk_value;
    clk_value.format = vpiIntVal;
    vpi_get_value(cb_data->obj, &clk_value);

    /* 检测上升沿 */
    if (clk_value.value.integer == 1 && last_clk_value == 0) {
        sample_signals();
    }

    last_clk_value = clk_value.value.integer;

    return 0;
}

/**
 * 注册时钟边沿监听
 */
static int register_clock_callback(const char* clk_name) {
    vpiHandle clk_handle = vpi_handle_by_name((PLI_BYTE8*)clk_name, NULL);
    if (clk_handle == NULL) {
        vpi_printf("ERROR: Clock signal not found: %s\n", clk_name);
        return 0;
    }

    s_cb_data cb_data;
    s_vpi_time time_s;
    s_vpi_value value_s;

    time_s.type = vpiSuppressTime;
    value_s.format = vpiSuppressVal;

    cb_data.reason = cbValueChange;
    cb_data.cb_rtn = clock_callback;
    cb_data.obj = clk_handle;
    cb_data.time = &time_s;
    cb_data.value = &value_s;
    cb_data.user_data = NULL;

    vpiHandle cb_handle = vpi_register_cb(&cb_data);
    if (cb_handle == NULL) {
        vpi_printf("ERROR: Failed to register clock callback\n");
        return 0;
    }

    vpi_printf("Registered clock callback on: %s\n", clk_name);
    return 1;
}

/**
 * $trace_init 系统任务
 * 参数: config_file, clock_signal, output_file
 */
static PLI_INT32 trace_init_calltf(PLI_BYTE8* user_data) {
    (void)user_data;

    if (initialized) {
        vpi_printf("WARNING: trace_init already called\n");
        return 0;
    }

    vpiHandle systf_handle = vpi_handle(vpiSysTfCall, NULL);
    vpiHandle args_iter = vpi_iterate(vpiArgument, systf_handle);
    if (args_iter == NULL) {
        vpi_printf("ERROR: $trace_init requires 3 arguments\n");
        return 0;
    }

    s_vpi_value val;
    val.format = vpiStringVal;

    /* 参数1: 配置文件路径 */
    vpiHandle arg = vpi_scan(args_iter);
    if (arg == NULL) {
        vpi_printf("ERROR: Missing config file argument\n");
        return 0;
    }
    vpi_get_value(arg, &val);
    char config_file[MAX_NAME_LEN];
    strncpy(config_file, val.value.str, MAX_NAME_LEN - 1);

    /* 参数2: 时钟信号名 */
    arg = vpi_scan(args_iter);
    if (arg == NULL) {
        vpi_printf("ERROR: Missing clock signal argument\n");
        return 0;
    }
    vpi_get_value(arg, &val);
    char clk_name[MAX_NAME_LEN];
    strncpy(clk_name, val.value.str, MAX_NAME_LEN - 1);

    /* 参数3: 输出文件路径 */
    arg = vpi_scan(args_iter);
    if (arg == NULL) {
        vpi_printf("ERROR: Missing output file argument\n");
        return 0;
    }
    vpi_get_value(arg, &val);
    char output_file[MAX_NAME_LEN];
    strncpy(output_file, val.value.str, MAX_NAME_LEN - 1);

    vpi_free_object(args_iter);

    /* 打开输出文件 */
    trace_file = fopen(output_file, "w");
    if (!trace_file) {
        vpi_printf("ERROR: Cannot open trace file: %s\n", output_file);
        return 0;
    }

    /* 加载信号列表 */
    if (!load_signal_list(config_file)) {
        fclose(trace_file);
        trace_file = NULL;
        return 0;
    }

    /* 写入header */
    fprintf(trace_file, "$signals %d\n", num_signals);
    for (int i = 0; i < num_signals; i++) {
        fprintf(trace_file, "%s %d\n", signal_names[i], signal_widths[i]);
    }
    fprintf(trace_file, "$end\n");
    fflush(trace_file);

    /* 注册时钟回调 */
    if (!register_clock_callback(clk_name)) {
        fclose(trace_file);
        trace_file = NULL;
        return 0;
    }

    initialized = 1;
    vpi_printf("Trace collection initialized\n");

    /* 立即采集初始状态 (t=0) */
    current_time = 0;
    sample_signals();
    vpi_printf("Sampled initial state at t=0\n");

    return 0;
}

/**
 * $trace_finish 系统任务
 */
static PLI_INT32 trace_finish_calltf(PLI_BYTE8* user_data) {
    (void)user_data;

    if (trace_file) {
        fclose(trace_file);
        trace_file = NULL;
    }

    vpi_printf("Trace collection finished. Total time: %lld\n", (long long)current_time);
    initialized = 0;

    return 0;
}

/**
 * 注册系统任务
 */
static void register_system_tasks(void) {
    s_vpi_systf_data tf_data;

    /* $trace_init */
    tf_data.type = vpiSysTask;
    tf_data.tfname = "$trace_init";
    tf_data.calltf = trace_init_calltf;
    tf_data.compiletf = NULL;
    tf_data.sizetf = NULL;
    tf_data.user_data = NULL;
    vpi_register_systf(&tf_data);

    /* $trace_finish */
    tf_data.tfname = "$trace_finish";
    tf_data.calltf = trace_finish_calltf;
    vpi_register_systf(&tf_data);
}

/**
 * VPI入口点
 */
void (*vlog_startup_routines[])(void) = {
    register_system_tasks,
    NULL
};
