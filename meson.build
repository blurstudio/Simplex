project(
  'Simplex',
  'cpp',
  meson_version : '>=1.7.0',
  version : configure_file(
    capture : true,
    command : [
      find_program('python', required: true),
      meson.project_source_root() / 'get_version.py',
      meson.project_source_root(),
      find_program('git', native: true, required: true).full_path(),
    ],
    output : 'version.txt',
  ),
  default_options: ['cpp_std=c++20'],
)

maya_build = get_option('maya_build')
python_build = get_option('python_build')
imath_bridge_build = get_option('imath_bridge_build')

if not maya_build and not python_build and not imath_bridge_build
  error('No builds requested')
endif

conf_data = configuration_data()
conf_data.set('VCS_TAG', meson.project_version())


if maya_build or imath_bridge_build
  subproject('maya')
endif

if imath_bridge_build
  subdir('src/imathbridge')
endif

if maya_build or python_build
  subdir('src/simplexlib')
  if maya_build
    subdir('src/maya')
  endif

  if python_build
    subdir('src/python')
  endif
endif



