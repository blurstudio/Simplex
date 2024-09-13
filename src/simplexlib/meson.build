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
simplexlib_inc = include_directories(['include'])

simplexlib_dep = declare_dependency(
  include_directories : simplexlib_inc,
  sources : simplexlib_files,
  dependencies : [eigen_dep, rapidjson_dep],
)
