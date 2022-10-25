include_directories(../../include/rapidjson/include ../../include/eigen)

set(SOURCE_FILES
    "combo.cpp"
    "combo.h"
    "enums.h"
    "floater.h"
    "progression.cpp"
    "progression.h"
    "shape.cpp"
    "shape.h"
    "shapeBase.h"
    "shapeController.cpp"
    "shapeController.h"
    "simplex.cpp"
    "simplex.h"
    "slider.cpp"
    "slider.h"
    "traversal.cpp"
    "traversal.h"
    "trispace.cpp"
    "trispace.h"
    "utils.cpp"
    "utils.h"
)

add_library(simplex_lib OBJECT ${SOURCE_FILES})

