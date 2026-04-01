cmake_minimum_required(VERSION 3.18)
project(planner_node VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ── Dependencies ──────────────────────────────────────────────────────────────
find_package(nlohmann_json QUIET)
if(NOT nlohmann_json_FOUND)
  include(FetchContent)
  FetchContent_Declare(nlohmann_json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
    URL_HASH SHA256=d6c65aca6b1ed68e7a182f4757257b107ae403032760ed6ef121c9d55e81757d
  )
  FetchContent_MakeAvailable(nlohmann_json)
endif()

# ── Library (shared between planner_node and tests) ───────────────────────────
add_library(planner_lib STATIC
  src/pddl_parser.cpp
  src/astar_planner.cpp
  src/ga_ranker.cpp
)
target_include_directories(planner_lib PUBLIC include)
target_link_libraries(planner_lib PUBLIC nlohmann_json::nlohmann_json)
target_compile_options(planner_lib PRIVATE -Wall -Wextra -O2)

# ── Executable ────────────────────────────────────────────────────────────────
add_executable(planner_node src/main.cpp)
target_link_libraries(planner_node PRIVATE planner_lib)

# ── Tests ─────────────────────────────────────────────────────────────────────
enable_testing()

find_package(GTest QUIET)
if(NOT GTest_FOUND)
  FetchContent_Declare(googletest
    URL https://github.com/google/googletest/archive/v1.14.0.tar.gz
  )
  FetchContent_MakeAvailable(googletest)
endif()

foreach(test_name test_parser test_astar test_ga)
  add_executable(${test_name} tests/${test_name}.cpp)
  target_link_libraries(${test_name} PRIVATE planner_lib GTest::gtest_main)
  add_test(NAME ${test_name} COMMAND ${test_name})
endforeach()
