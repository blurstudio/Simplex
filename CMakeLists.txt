cmake_minimum_required(VERSION 2.6)

set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/modules)
set(TARGET_DCC Maya CACHE STRING "Target Content Creation Package: Maya XSI Python")

include_directories(src/lib include/rapidjson/include include/eigen)

file(GLOB SOURCE_FILES
    "src/lib/*.h"
    "src/lib/*.cpp"
)

if (${TARGET_DCC} STREQUAL "Maya")
    project(simplex_maya)
    find_package(Maya REQUIRED)
    set_property(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR} PROPERTY VS_STARTUP_PROJECT ${PROJECT_NAME})
    set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/${MAYA_VERSION})

    file(GLOB MAYA_FILES
        "src/maya/*.h"
        "src/maya/*.cpp"
    )

    include_directories(${MAYA_INCLUDE_DIR})
    link_directories(${MAYA_LIBRARY_DIR})
    add_library(${PROJECT_NAME} SHARED ${SOURCE_FILES} ${MAYA_FILES})
    target_link_libraries(${PROJECT_NAME} ${MAYA_LIBRARIES})

    MAYA_PLUGIN(${PROJECT_NAME})
    install(TARGETS ${PROJECT_NAME} DESTINATION blur/plug-ins)
elseif(${TARGET_DCC} STREQUAL "XSI")
    project(simplex_ice)
    set(XSI_VERSION "2014 SP2" CACHE STRING "The XSI version")

    # XSI is dead, so not worth a cmake find
    # So, just set the data directly
    set(SI_HOME "C:/Program Files/Autodesk/Softimage ${XSI_VERSION}")
    set(XSISDK_ROOT ${SI_HOME}/XSISDK)
    set(XSI_LIB_DIR ${XSISDK_ROOT}/lib/nt-x86-64)

    set(XSI_INCLUDE_DIRS ${XSISDK_ROOT}/include)
    set(XSI_LIBRARIES
        "${XSI_LIB_DIR}/sicppsdk.lib"
        "${XSI_LIB_DIR}/sicoresdk.lib"
    )

    set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/XSI${XSI_VERSION})
    file(GLOB XSI_FILES
        "src/xsi/*.h"
        "src/xsi/*.cpp"
    )
    include_directories(${XSI_INCLUDE_DIRS})
    add_library(${PROJECT_NAME} SHARED ${SOURCE_FILES} ${XSI_FILES})
    target_link_libraries(${PROJECT_NAME} ${XSI_LIBRARIES})
    install(TARGETS ${PROJECT_NAME} RUNTIME DESTINATION plug-ins)
elseif(${TARGET_DCC} STREQUAL "BlurPython")
    project(pysimplex)

    # Blergh, I can't do the normal find_package(PythonLibs REQUIRED)
    # we have to support 32 and 64 bit builds with strange paths
    # start annoying hard-coding
    set(PY_VERSION 27_64 CACHE STRING "The python version as part of the path")
    set(PY_PATH C:/Python${PY_VERSION})
    string(REPLACE "_" ";" _PY_VLIST ${PY_VERSION})
    list(GET _PY_VLIST 0 PY_SIMPLE_VERSION)
    set(PYTHON_INCLUDE_DIRS ${PY_PATH}/include)
    set(PYTHON_LIBRARIES ${PY_PATH}/libs/python${PY_SIMPLE_VERSION}.lib)
    # End annoying hard-coding

    set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/Python${PY_VERSION})
    file(GLOB PY_FILES
        "src/python/*.h"
        "src/python/*.cpp"
    )
    include_directories(${PYTHON_INCLUDE_DIRS})
    add_library(${PROJECT_NAME} SHARED ${SOURCE_FILES} ${PY_FILES})
    set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".pyd")

    if(WIN32)
        set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".pyd")
    else()
        set_target_properties(${PROJECT_NAME} PROPERTIES PREFIX "")
        set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".so")
        set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/python${PY_VERSION})
    endif()

    target_link_libraries(${PROJECT_NAME} ${PYTHON_LIBRARIES})
    message("Python Libraries: ${PYTHON_LIBRARIES}")

    install(TARGETS ${PROJECT_NAME}
        RUNTIME DESTINATION lib
        ARCHIVE DESTINATION lib
    )
elseif(${TARGET_DCC} STREQUAL "Python")
    project(pysimplex)
    find_package(Python2 REQUIRED COMPONENTS Development)

    set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/Python${PY_VERSION})
    file(GLOB PY_FILES
        "src/python/*.h"
        "src/python/*.cpp"
    )
    include_directories(${Python2_INCLUDE_DIRS})
    add_library(${PROJECT_NAME} SHARED ${SOURCE_FILES} ${PY_FILES})
    if(WIN32)
        set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".pyd")
    else()
        set_target_properties(${PROJECT_NAME} PROPERTIES PREFIX "")
        set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".x86_64-linux-gnu.so")
        set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/python${PY_VERSION})
    endif()

    target_link_libraries(${PROJECT_NAME} ${Python2_LIBRARIES})
    message("Python Libraries: ${Python2_LIBRARIES}")

    install(TARGETS ${PROJECT_NAME}
        RUNTIME DESTINATION lib
        ARCHIVE DESTINATION lib
    )

elseif(${TARGET_DCC} STREQUAL "Python3")
    project(pysimplex3)
    find_package(Python3 REQUIRED COMPONENTS Development)

    set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/Python${PY_VERSION})
    file(GLOB PY_FILES
        "src/python/*.h"
        "src/python/*.cpp"
    )
    include_directories(${Python3_INCLUDE_DIRS})
    add_library(${PROJECT_NAME} SHARED ${SOURCE_FILES} ${PY_FILES})
    if(WIN32)
        set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".pyd")
    else()
        set_target_properties(${PROJECT_NAME} PROPERTIES PREFIX "")
        set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".x86_64-linux-gnu.so")
        set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/python${PY_VERSION})
    endif()

    target_link_libraries(${PROJECT_NAME} ${Python3_LIBRARIES})
    message("Python Libraries: ${Python3_LIBRARIES}")

    install(TARGETS ${PROJECT_NAME}
        RUNTIME DESTINATION lib
        ARCHIVE DESTINATION lib
    )

elseif(${TARGET_DCC} STREQUAL "Test")
    project(pysimplex)
    file(GLOB TEST_FILES
        "src/test/*.h"
        "src/test/*.cpp"
    )
    add_executable(${PROJECT_NAME} ${SOURCE_FILES} ${TEST_FILES})
else()
    message(FATAL_ERROR "Improper DCC Specified.  Must be either Maya or XSI")
endif()
