cmake_minimum_required(VERSION 3.14)
project(fullvision_demo VERSION 1.0 LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# 设置mockturtle路径
set(MOCKTURTLE_DIR ${CMAKE_SOURCE_DIR}/../mockturtle)

# 添加mockturtle头文件目录
include_directories(${MOCKTURTLE_DIR}/include)
include_directories(${MOCKTURTLE_DIR}/lib/kitty)
include_directories(${MOCKTURTLE_DIR}/lib/lorina)
include_directories(${MOCKTURTLE_DIR}/lib/fmt)
include_directories(${MOCKTURTLE_DIR}/lib/parallel_hashmap)
include_directories(${MOCKTURTLE_DIR}/lib/percy)
include_directories(${MOCKTURTLE_DIR}/lib/rang)

# JSON库 (header-only)
include(FetchContent)
FetchContent_Declare(
    json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.2
)
FetchContent_MakeAvailable(json)

# 波形补全模块
add_executable(waveform_completion
    waveform_completion/src/main.cpp
    waveform_completion/src/aig_simulator.cpp
    waveform_completion/src/vcd_writer.cpp
    waveform_completion/src/signal_propagator.cpp
    waveform_completion/src/trace_reader.cpp
)

target_include_directories(waveform_completion PRIVATE
    waveform_completion/include
)

target_link_libraries(waveform_completion PRIVATE
    nlohmann_json::nlohmann_json
)

# 设置输出目录
set_target_properties(waveform_completion PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/build
)
