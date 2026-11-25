pymod = import('python')
py = pymod.find_installation('python3', pure : false)
py_dep = py.dependency()

pysimplex_files = files(['pysimplex.cpp'])
rapidjson_dep = dependency('rapidjson')

lapi = '3.9'
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
    install_dir: pyinstall_dir,
    exclude_files: ['_version.py.in', 'meson.build'],
    # exclude_directories takes exact paths, no globs, so list every package
    exclude_directories: [
      '__pycache__',
      'commands/__pycache__',
      'interface/__pycache__',
      'items/__pycache__',
      'menu/__pycache__',
      'menu/dummyPlugins/__pycache__',
      'menu/genericPlugins/__pycache__',
      'menu/mayaPlugins/__pycache__',
    ],
  )
  if py_script_build
    # Maya runs userSetup.py from the module's scripts folder
    install_data('userSetup.py', install_dir: pyinstall_dir)
  endif
  fs = import('fs')
  if not fs.is_file('simplexui/_version.py')
    version_py = configure_file(
      input: 'simplexui/_version.py.in',
      output: '_version.py',
      install_dir: pyinstall_dir / 'simplexui',
      configuration : conf_data,
    )
  endif
endif

if not py_script_build
  # Wheel builds use the default install dir (site-packages root) so `import pysimplex` works
  install_kwargs = py_wheel_build ? {} : {'install_dir' : pyinstall_dir}
  pysimplex = py.extension_module(
    'pysimplex',
    pysimplex_files,
    dependencies : [simplexlib_dep, rapidjson_dep],
    install: true,
    limited_api : lapi,
    kwargs : install_kwargs,
  )
endif

