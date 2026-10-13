cmake_minimum_required(VERSION 3.16)
project(openset_reid_engine CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(include)

add_library(openset_matcher STATIC
    src/openset_matcher.cpp
)

add_executable(openset_matcher_bench
    src/main.cpp
)

target_link_libraries(openset_matcher_bench PRIVATE openset_matcher)

if(MSVC)
    target_compile_options(openset_matcher PRIVATE /O2 /fp:fast)
    target_compile_options(openset_matcher_bench PRIVATE /O2 /fp:fast)
else()
    target_compile_options(openset_matcher PRIVATE -O3 -march=native -ffast-math)
    target_compile_options(openset_matcher_bench PRIVATE -O3 -march=native -ffast-math)
endif()
