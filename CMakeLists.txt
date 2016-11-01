cmake_minimum_required(VERSION 2.6)

set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/modules)
set(TARGET_DCC Maya CACHE STRING "Target Content Creation Package: Maya XSI")

if (${TARGET_DCC} STREQUAL "Maya")
    project(simplex_maya)
    find_package(Maya REQUIRED)
    set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../../Maya${MAYA_VERSION})
elseif(${TARGET_DCC} STREQUAL "XSI")
    project(simplex_xsi)
    find_package(XSI REQUIRED)
    set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../../XSI${XSI_VERSION})
else()
    message(FATAL_ERROR "Improper DCC Specified.  Must be either Maya or XSI")
endif()

include_directories(include)
add_subdirectory(src)

