cmake_minimum_required(VERSION 3.14)

project(simplex)

include_directories(include/rapidjson/include include/eigen src/lib)
set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/modules)
set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/simplex)

add_subdirectory("src/lib")
add_subdirectory("src/maya")
add_subdirectory("src/python")




