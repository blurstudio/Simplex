set(MAYA_FILES
    "pluginMain.cpp"
    "simplex_mayaNode.cpp"
    "simplex_mayaNode.h"
)

find_package(Maya REQUIRED)

include_directories(${MAYA_INCLUDE_DIR})
link_directories(${MAYA_LIBRARY_DIR})
add_library(simplex_maya SHARED ${SOURCE_FILES} ${MAYA_FILES})
target_link_libraries(simplex_maya simplex_lib ${MAYA_LIBRARIES})
MAYA_PLUGIN(simplex_maya)

install(TARGETS simplex_maya RUNTIME DESTINATION plug-ins)


