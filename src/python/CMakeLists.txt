# If we're compiling against Maya's included python, get the
# required python version based on the passed maya version

set(_PY_VERSION 2.7)
if (MAYA_VERSION VERSION_EQUAL "2022")
    if (MAYA_2022_PYTHON VERSION_GREATER_EQUAL 3)
        set(_PY_VERSION 3.7)
    endif()
elseif(MAYA_VERSION VERSION_EQUAL "2023")
    set(_PY_VERSION 3.9)
elseif(MAYA_VERSION VERSION_GREATER_EQUAL "2024")
    set(_PY_VERSION 3.10)
endif()
string(REPLACE "." ";" PY_MAJOR_LIST ${_PY_VERSION})
list(GET PY_MAJOR_LIST 0 PY_MAJOR)



if(${MAYA_PYTHON})
    string(REPLACE "." ";" VERSION_LIST ${MAYA_VERSION})
    list(GET VERSION_LIST 0 MAYA_VERSION)
    string(REPLACE "." "" PY_FLAT ${_PY_VERSION})
    find_package(Maya REQUIRED)

    if (WIN32)
        set(PYTHON_OS_NAME "windows")
        set(PYTHON_LIB_FILENAME "python${PY_FLAT}.lib")
        if (${MAYA_VERSION} VERSION_GREATER_EQUAL "2022")
            set(PYTHON_INCLUDE_DIR "${MAYA_LOCATION}/include/Python${PY_FLAT}/Python")
        elseif(${MAYA_VERSION} VERSION_EQUAL "2018" OR ${MAYA_VERSION} VERSION_EQUAL "2019")
            set(PYTHON_INCLUDE_DIR "${MAYA_LOCATION}/include/python${_PY_VERSION}")
        else()
            set(PYTHON_INCLUDE_DIR "${MAYA_LOCATION}/include/Python")
        endif()
    elseif(APPLE)
        set(PYTHON_OS_NAME "mac")
        if (${_PY_VERSION} VERSION_EQUAL "3.7")
            set(PYTHON_LIB_FILENAME "libpython${_PY_VERSION}m.dylib")
        else()
            set(PYTHON_LIB_FILENAME "libpython${_PY_VERSION}.dylib")
        endif()
        set(PYTHON_INCLUDE_DIR "${PROJECT_SOURCE_DIR}/os/mac/${_PY_VERSION}/include")
    else()
        set(PYTHON_OS_NAME "linux")
        if (${MAYA_VERSION} VERSION_GREATER_EQUAL "2022")
            set(PYTHON_INCLUDE_DIR "${MAYA_LOCATION}/include/Python${PY_FLAT}/Python")
        elseif(${MAYA_VERSION} VERSION_EQUAL "2018" OR ${MAYA_VERSION} VERSION_EQUAL "2019")
            set(PYTHON_INCLUDE_DIR "${MAYA_LOCATION}/include/python${_PY_VERSION}")
        else()
            set(PYTHON_INCLUDE_DIR "${MAYA_LOCATION}/include/Python")
        endif()
        if (${_PY_VERSION} VERSION_EQUAL "3.7")
            set(PYTHON_LIB_FILENAME "libpython${_PY_VERSION}m.so")
        else()
            set(PYTHON_LIB_FILENAME "libpython${_PY_VERSION}.so")
        endif()
    endif()

    set(PYTHON_LIB_PATH "${PROJECT_SOURCE_DIR}/os/${PYTHON_OS_NAME}/${_PY_VERSION}/lib/${PYTHON_LIB_FILENAME}")

    # Set these "special case" variables for the python libraries
    # because compiling against maya python is a special case
    set(Python2_INCLUDE_DIR ${PYTHON_INCLUDE_DIR})
    set(Python3_INCLUDE_DIR ${PYTHON_INCLUDE_DIR})
    set(Python2_LIBRARY ${PYTHON_LIB_PATH})
    set(Python3_LIBRARY ${PYTHON_LIB_PATH})
else()
    set(_PY_VERSION ${SYSTEM_PY_VERSON})
endif()

# Using the "special case" variables that may or may not be set above
# find the python target
# These find_package calls are what requires CMake 3.16+
set(PY_FILES "simplex_python.cpp")
if(${PY_MAJOR} STREQUAL "2")
    set(PY_NAME py2simplex)
    find_package(Python2 REQUIRED COMPONENTS Development)
    set(PY_MODULE Python2::Module)
    # Auto-handles the .pyd and .so stuff
    Python2_add_library(${PY_NAME} MODULE ${PY_FILES})

elseif(${PY_MAJOR} STREQUAL "3")
    set(PY_NAME py3simplex)
    find_package(Python3 REQUIRED COMPONENTS Development)
    set(PY_MODULE Python3::Module)
    # Auto-handles the .pyd and .so stuff
    Python3_add_library(${PY_NAME} MODULE ${PY_FILES})
endif()

# Link to python
target_link_libraries(${PY_NAME}
    PRIVATE
        ${PY_MODULE}
        simplex_lib
)
target_include_directories(${PY_NAME}
    PRIVATE
        ${PY_MODULE}
    PUBLIC
        "${CMAKE_CURRENT_BINARY_DIR}"
        "${CMAKE_CURRENT_SOURCE_DIR}"
)
