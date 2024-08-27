maya_dep = dependency('maya')
maya_name_suffix = maya_dep.get_variable('name_suffix')
maya_version = maya_dep.get_variable('maya_version')

simplex_maya_files = files([
    'src/basicBlendShape.cpp',
    'src/pluginMain.cpp',
    'src/simplex_mayaNode.cpp',
])

fs = import('fs')
if fs.is_file('src/version.h')
  message('Using existing version.h')
else
  git = find_program('git', native: true, required: true)
  version_h = vcs_tag(
    command: [git, 'describe', '--tags', '--always', '--match', 'v[0-9]*', '--dirty=+'],
    fallback: 'v0.0.1',
    input: 'src/version.h.in',
    output: 'version.h',
  )
  simplex_maya_files = simplex_maya_files + version_h
endif

simplex_maya_inc = include_directories(['include'])
rapidjson_dep = dependency('rapidjson')

simplex_maya = shared_library(
  'simplex_maya',
  simplex_maya_files,
  install: true,
  install_dir : meson.global_source_root() / 'output_Maya' + maya_version,
  include_directories : simplex_maya_inc,
  dependencies : [maya_dep, simplexlib_dep, rapidjson_dep],
  name_prefix : '',
  name_suffix : maya_name_suffix,
)
