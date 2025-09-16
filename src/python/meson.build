pymod = import('python')
py = pymod.find_installation('python3', pure : false)
py_dep = py.dependency()

pysimplex_files = files(['pysimplex.cpp'])
rapidjson_dep = dependency('rapidjson')

lapi = '3.7'
if get_option('buildtype') == 'debug'
  lapi = ''
endif

py_wheel_build = get_option('python_wheel_build')
py_script_build = get_option('python_script_build')

if py_script_build
  pyinstall_dir = meson.project_source_root() / 'scripts'
elif py_wheel_build
  pyinstall_dir = py.get_install_dir()
else
  pyinstall_dir = meson.project_source_root() / 'output_Python'
endif

if py_script_build or py_wheel_build
  install_subdir(
    'simplexui',
    install_dir: meson.project_source_root() / 'scripts',
    exclude_files: ['_version.py.in', 'meson.build'],
  )
  fs = import('fs')
  if not fs.is_file('simplexui/_version.py')
    version_py = configure_file(
      input: 'simplexui/_version.py.in',
      output: '_version.py',
      install_dir: meson.project_source_root() / 'scripts' / 'simplexui',
      configuration : conf_data,
    )
  endif
endif

if not py_script_build
  if py_wheel_build
    install_kwargs = {'subdir' : 'simplexui'}
  else
    install_kwargs = {'install_dir' : pyinstall_dir}
  endif
  pysimplex = py.extension_module(
    'pysimplex',
    pysimplex_files,
    dependencies : [simplexlib_dep, rapidjson_dep],
    install: true,
    limited_api : lapi,
    kwargs : install_kwargs,
  )
endif

