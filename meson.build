project('Simplex', 'cpp', default_options: ['cpp_std=c++20'])

maya_dep = dependency('maya')
maya_name_suffix = maya_dep.get_variable('name_suffix')
maya_version = maya_dep.get_variable('maya_version')

maya_build = get_option('maya_build')
python_build = get_option('python_build')

if not maya_build and not python_build
  error('No builds requested')
endif

subdir('src/simplexlib')
if maya_build
  subdir('src/maya')
endif

if python_build
  subdir('src/python')
endif
