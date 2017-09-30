cmake_minimum_required(VERSION 2.6)

set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/modules)
set(TARGET_DCC Maya CACHE STRING "Target Content Creation Package: Maya XSI Python")

if (${TARGET_DCC} STREQUAL "Maya")
    project(simplex_maya)
    find_package(Maya REQUIRED)
    set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/Maya${MAYA_VERSION})

    set(SOURCE_FILES
        "src/lib/stdafx.cpp"
        "src/lib/simplex.cpp"
        "src/maya/pluginMain.cpp"
        "src/maya/simplex_mayaNode.cpp"
    )

    include_directories(${MAYA_INCLUDE_DIR} include)
    link_directories(${MAYA_LIBRARY_DIR})
    add_library(${PROJECT_NAME} SHARED ${SOURCE_FILES})
    target_link_libraries(${PROJECT_NAME} ${MAYA_LIBRARIES})

    MAYA_PLUGIN(${PROJECT_NAME})
    install(TARGETS ${PROJECT_NAME} ${MAYA_TARGET_TYPE} DESTINATION plug-ins)

elseif(${TARGET_DCC} STREQUAL "XSI")
    project(simplex_xsi)
    find_package(XSI REQUIRED)
    set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output/XSI${XSI_VERSION})
    set(SOURCE_FILES
        "src/lib/stdafx.cpp"
        "src/lib/simplex.cpp"
        "src/xsi/register.cpp"
        "src/xsi/simplex_ice.cpp"
    )
    include_directories(include)

elseif(${TARGET_DCC} STREQUAL "Python")
    project(pysimplex)

    set(PY_VERSION 2.7 CACHE STRING "Minimum python version")
    find_package(PythonLibs ${PY_VERSION} REQUIRED)

    set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_BINARY_DIR}/../output)
    set(SOURCE_FILES
        "src/lib/stdafx.cpp"
        "src/lib/simplex.cpp"
        "src/python/simplex_python.cpp"
    )

    include_directories(${PYTHON_INCLUDE_DIRS} include)
    add_library(${PROJECT_NAME} SHARED ${SOURCE_FILES})
    set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".pyd")

    target_link_libraries(${PROJECT_NAME} ${PYTHON_LIBRARIES})
    message("Python Libraries: ${PYTHON_LIBRARIES}")

    install(TARGETS ${PROJECT_NAME}
        RUNTIME DESTINATION lib
        ARCHIVE DESTINATION lib
    )

else()
    message(FATAL_ERROR "Improper DCC Specified.  Must be either Maya or XSI")
endif()



