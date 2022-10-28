set(MAYA_FILES
    "pluginMain.cpp"
    "simplex_mayaNode.cpp"
    "simplex_mayaNode.h"
)

find_package(Maya REQUIRED)

add_library(simplex_maya SHARED ${MAYA_FILES})

target_link_libraries(simplex_maya PRIVATE Maya::Maya simplex_lib)
target_include_directories(simplex_maya 
    PRIVATE Maya::Maya
    PUBLIC "${CMAKE_CURRENT_BINARY_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}"
)
MAYA_PLUGIN(simplex_maya)
