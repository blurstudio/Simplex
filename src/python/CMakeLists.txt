
set(PY_FILES "simplex_python.cpp")
set(TARGET_PYTHON 2 CACHE STRING "Target Python Version: 2 3")

if(${TARGET_PYTHON} STREQUAL "2")
    find_package(Python2 REQUIRED COMPONENTS Development)
    set(PY_NAME pysimplex)
    set(PY_INC ${Python2_INCLUDE_DIRS})
    set(PY_LIB ${Python2_LIBRARIES})
elseif(${TARGET_PYTHON} STREQUAL "3")
    find_package(Python3 REQUIRED COMPONENTS Development)
    set(PY_NAME pysimplex3)
    set(PY_INC ${Python3_INCLUDE_DIRS})
    set(PY_LIB ${Python3_LIBRARIES})
else()
    message(FATAL_ERROR "TARGET_PYTHON must be either 2 or 3")
endif()


include_directories(${PY_INC})
add_library(${PY_NAME} SHARED ${SOURCE_FILES} ${PY_FILES})
if(WIN32)
    set_target_properties(${PY_NAME} PROPERTIES SUFFIX ".pyd")
else()
    set_target_properties(${PY_NAME} PROPERTIES PREFIX "")
    set_target_properties(${PY_NAME} PROPERTIES SUFFIX ".x86_64-linux-gnu.so")
endif()

target_link_libraries(${PY_NAME} ${PY_LIB} simplex_lib)

install(TARGETS ${PY_NAME}
    RUNTIME DESTINATION lib
    ARCHIVE DESTINATION lib
)

