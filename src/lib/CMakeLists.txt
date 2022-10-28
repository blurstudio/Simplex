set(SOURCE_FILES
    "combo.cpp"
    "progression.cpp"
    "shape.cpp"
    "shapeController.cpp"
    "simplex.cpp"
    "slider.cpp"
    "traversal.cpp"
    "trispace.cpp"
    "utils.cpp"
)
# Just so these show up in the IDE
file(GLOB HEADER_LIST "../include/*.h")

add_library(simplex_lib STATIC ${SOURCE_FILES} ${HEADER_LIST})
target_include_directories(simplex_lib
    PUBLIC
        "../include"
        "${PROJECT_SOURCE_DIR}/include/rapidjson/include"
        "${PROJECT_SOURCE_DIR}/include/eigen"
)

