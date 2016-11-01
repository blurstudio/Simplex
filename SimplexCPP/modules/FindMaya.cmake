# The MIT License (MIT)
# 
# Copyright (c) 2015 Chad Vernon
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# - Maya finder module
#
# Variables that will be defined:
# MAYA_FOUND          Defined if a Maya installation has been detected
# MAYA_EXECUTABLE     Path to Maya's executable
# MAYA_<lib>_FOUND    Defined if <lib> has been found
# MAYA_<lib>_LIBRARY  Path to <lib> library
# MAYA_INCLUDE_DIR    Path to the devkit's include directories
# MAYA_LIBRARIES      All the Maya libraries
#

# Set a default Maya version if not specified
if(NOT DEFINED MAYA_VERSION)
    set(MAYA_VERSION 2016 CACHE STRING "Maya version")
endif()

# OS Specific environment setup
set(MAYA_COMPILE_DEFINITIONS "REQUIRE_IOSTREAM;_BOOL")
set(MAYA_INSTALL_BASE_SUFFIX "")
set(MAYA_INC_SUFFIX "include")
set(MAYA_LIB_SUFFIX "lib")
set(MAYA_BIN_SUFFIX "bin")
set(MAYA_TARGET_TYPE LIBRARY)
if(WIN32)
    # Windows
    set(MAYA_INSTALL_BASE_DEFAULT "C:/Program Files/Autodesk")
    set(MAYA_COMPILE_DEFINITIONS "${MAYA_COMPILE_DEFINITIONS};NT_PLUGIN")
    set(OPENMAYA OpenMaya.lib)
    set(MAYA_PLUGIN_EXTENSION ".mll")
    set(MAYA_TARGET_TYPE RUNTIME)
elseif(APPLE)
    # Apple
    set(MAYA_INSTALL_BASE_DEFAULT /Applications/Autodesk)
    set(MAYA_INC_SUFFIX "devkit/include")
    set(MAYA_LIB_SUFFIX "Maya.app/Contents/MacOS")
    set(MAYA_BIN_SUFFIX "Maya.app/Contents/bin/")
    set(MAYA_COMPILE_DEFINITIONS "${MAYA_COMPILE_DEFINITIONS};OSMac_")
    set(OPENMAYA libOpenMaya.dylib)
    set(MAYA_PLUGIN_EXTENSION ".bundle")
else()
    # Linux
    set(MAYA_COMPILE_DEFINITIONS "${MAYA_COMPILE_DEFINITIONS};LINUX")
    set(MAYA_INSTALL_BASE_DEFAULT /usr/autodesk)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fPIC")
    if(MAYA_VERSION LESS 2016)
        SET(MAYA_INSTALL_BASE_SUFFIX -x64)
    endif()
    set(OPENMAYA libOpenMaya.so)
    set(MAYA_PLUGIN_EXTENSION ".so")
endif()

set(MAYA_INSTALL_BASE_PATH ${MAYA_INSTALL_BASE_DEFAULT} CACHE STRING
    "Root path containing your maya installations, e.g. /usr/autodesk or /Applications/Autodesk/")

set(MAYA_LOCATION ${MAYA_INSTALL_BASE_PATH}/Maya${MAYA_VERSION}${MAYA_INSTALL_BASE_SUFFIX})

# Maya library directory
find_path(MAYA_LIBRARY_DIR ${OPENMAYA}
    PATHS
        ${MAYA_LOCATION}
        $ENV{MAYA_LOCATION}
    PATH_SUFFIXES
        "${MAYA_LIB_SUFFIX}/"
    DOC "Maya library path"
)

# Maya include directory
find_path(MAYA_INCLUDE_DIR maya/MFn.h
    PATHS
        ${MAYA_LOCATION}
        $ENV{MAYA_LOCATION}
    PATH_SUFFIXES
        "${MAYA_INC_SUFFIX}/"
    DOC "Maya include path"
)

# Maya libraries
set(_MAYA_LIBRARIES OpenMaya OpenMayaAnim OpenMayaFX OpenMayaRender OpenMayaUI Foundation clew)
foreach(MAYA_LIB ${_MAYA_LIBRARIES})
    find_library(MAYA_${MAYA_LIB}_LIBRARY NAMES ${MAYA_LIB} PATHS ${MAYA_LIBRARY_DIR}
        NO_DEFAULT_PATH)
    if (MAYA_${MAYA_LIB}_LIBRARY)
        set(MAYA_LIBRARIES ${MAYA_LIBRARIES} ${MAYA_${MAYA_LIB}_LIBRARY})
    endif()
endforeach()

if (APPLE AND ${CMAKE_CXX_COMPILER_ID} MATCHES "Clang")
    # Clang and Maya needs to use libstdc++
    set(MAYA_CXX_FLAGS "-std=c++0x -stdlib=libstdc++")
endif()

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(Maya DEFAULT_MSG MAYA_INCLUDE_DIR MAYA_LIBRARIES)

function(MAYA_PLUGIN _target)
    if (WIN32)
        set_target_properties(${_target} PROPERTIES
            LINK_FLAGS "/export:initializePlugin /export:uninitializePlugin"
        )
    endif()
    set_target_properties(${_target} PROPERTIES
        COMPILE_DEFINITIONS "${MAYA_COMPILE_DEFINITIONS}"
        PREFIX ""
        SUFFIX ${MAYA_PLUGIN_EXTENSION})
endfunction()
