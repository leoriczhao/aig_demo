# Makefile for FullVision Yosys Plugin

# 查找yosys配置
YOSYS_CONFIG ?= yosys-config

# 编译选项
CXX = $(shell $(YOSYS_CONFIG) --cxx)
CXXFLAGS = $(shell $(YOSYS_CONFIG) --cxxflags) -fPIC
LDFLAGS = $(shell $(YOSYS_CONFIG) --ldflags)
LDLIBS = $(shell $(YOSYS_CONFIG) --ldlibs)
PLUGINS_DIR = $(shell $(YOSYS_CONFIG) --datdir)/plugins

# 目标
PLUGIN = signal_mapper.so
SOURCES = signal_mapper.cc

.PHONY: all clean install test

all: $(PLUGIN)

$(PLUGIN): $(SOURCES)
	$(CXX) $(CXXFLAGS) -shared -o $@ $< $(LDFLAGS) $(LDLIBS)

clean:
	rm -f $(PLUGIN)

install: $(PLUGIN)
	mkdir -p $(PLUGINS_DIR)
	cp $(PLUGIN) $(PLUGINS_DIR)/

# 测试插件
test: $(PLUGIN)
	@echo "Testing plugin loading..."
	yosys -m ./$(PLUGIN) -p "help record_rtl_signals"
	yosys -m ./$(PLUGIN) -p "help write_signal_map"
	@echo "Plugin test passed!"
