# VPI Trace Collector Makefile

# iverilog VPI编译工具
IVERILOG_VPI = iverilog-vpi

# 目标
TARGET = trace_collector.vpi
SRC = trace_collector.c

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	$(IVERILOG_VPI) $(SRC) -o $(TARGET)

clean:
	rm -f $(TARGET) *.o
