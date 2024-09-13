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

os_name = build_machine.system()
compile_args = []
link_args = []

# Make sure to compile for both arm and x86 if I'm on an M1
if os_name == 'darwin'
  if meson.get_compiler('cpp').get_id() == 'clang'
    compile_args += ['-arch', 'x86_64']
    link_args += ['-arch', 'x86_64']
    if build_machine.cpu_family() == 'aarch64'
      compile_args += ['-arch', 'arm64']
      link_args += ['-arch', 'arm64']
    endif
  endif
  compile_args += [
    '-Wno-delete-non-abstract-non-virtual-dtor',
    '-Wno-deprecated-declarations',
    '-Wno-reorder-ctor',
    '-Wno-unused-variable',
  ]
endif


message('SIMPLEX COMPILE ARGS', compile_args)
message('SIMPLEX LINK ARGS', link_args)


simplexlib = static_library(
  'simplexlib', 
  simplexlib_files,
  include_directories : inc,
  dependencies : [
    rapidjson_dep,
    eigen_dep,
  ],
  link_args : link_args,
)

simplexlib_dep = declare_dependency(
  include_directories : inc,
  link_with : simplexlib,
  link_args : link_args,
  compile_args : compile_args,
)
