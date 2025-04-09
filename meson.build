project(
  'Simplex',
  'cpp',
  meson_version : '>=1.6.0',
  version : configure_file(
    capture : true,
    command : [
      find_program('git', native: true, required: true),
      'describe', '--tags', '--always', '--match', 'v[0-9]*', '--abbrev=0'
    ],
    output : 'version.txt',
  ),
  default_options: ['cpp_std=c++20'],
)

maya_build = get_option('maya_build')
python_build = get_option('python_build')

if not maya_build and not python_build
  error('No builds requested')
endif

conf_data = configuration_data()
conf_data.set('VCS_TAG', meson.project_version())

subdir('src/simplexlib')
if maya_build
  maya_dep = dependency('maya')
  maya_name_suffix = maya_dep.get_variable('name_suffix')
  maya_version = maya_dep.get_variable('maya_version')
  subdir('src/maya')
endif

if python_build
  subdir('src/python')
endif
