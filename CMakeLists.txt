cmake_minimum_required(VERSION 3.16)

project(simplex VERSION 1.0 DESCRIPTION "Blur Studio's Simplex Blendshape Combination System" LANGUAGES CXX)

set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/modules)

# (defined in FindMaya.cmake, copied here for reference)
# set(MAYA_INSTALL_BASE_PATH "" CACHE STRING
#     "Root path containing your maya installations, e.g. /usr/autodesk or /Applications/Autodesk/"
# )
set(MAYA_VERSION 2020 CACHE STRING "Maya version")
set(MAYA_PYTHON YES CACHE STRING "Link the python module to mayapy")
set(MAYA_2022_PYTHON 2 CACHE STRING "Major Version of python when compiling for Maya 2022")
set(SYSTEM_PY_VERSON 3 CACHE STRING "If Not linking to mayapy, the installed version of python to use")
set(BUILD_MAYA YES CACHE STRING "Build the maya plugin")
set(BUILD_PYTHON YES CACHE STRING "Build the python module")

if(NOT (${BUILD_MAYA} OR ${BUILD_PYTHON}))
    message(FATAL_ERROR "You have to build for either the python or maya")
endif()

# The static simplex library linked into the other projects
add_subdirectory("src/lib")

if (${BUILD_MAYA})
    # Build the maya plugin
    add_subdirectory("src/maya")
endif()

if (${BUILD_PYTHON})
    # Build the python plugin
    add_subdirectory("src/python")
endif()


