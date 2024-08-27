simplexlib_files = files([
  'src/progression.cpp',
  'src/shape.cpp',
  'src/simplex.cpp',
  'src/shapeController.cpp',
  'src/slider.cpp',
  'src/utils.cpp',
  'src/trispace.cpp',
  'src/combo.cpp',
  'src/traversal.cpp',
])

rapidjson_dep = dependency('rapidjson')
eigen_dep = dependency('eigen3')
inc = include_directories(['include'])

simplexlib = static_library(
  'simplexlib', 
  simplexlib_files,
  include_directories : inc,
  dependencies : [
    rapidjson_dep,
    eigen_dep,
  ]
)

simplexlib_dep = declare_dependency(
  include_directories : inc,
  link_with : simplexlib,
)
