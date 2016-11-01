set(SOURCE_FILES
    "lib/stdafx.cpp"
    "lib/simplex.cpp"
    "maya/pluginMain.cpp"
    "maya/simplex_mayaNode.cpp"
)

include_directories(${MAYA_INCLUDE_DIR} include)
link_directories(${MAYA_LIBRARY_DIR})
add_library(${PROJECT_NAME} SHARED ${SOURCE_FILES})
target_link_libraries(${PROJECT_NAME} ${MAYA_LIBRARIES})

MAYA_PLUGIN(${PROJECT_NAME})
install(TARGETS ${PROJECT_NAME} ${MAYA_TARGET_TYPE} DESTINATION plug-ins)

