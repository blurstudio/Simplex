pymod = import('python')
py = pymod.find_installation('python3', pure : false)
py_dep = py.dependency()

pysimplex_files = files(['pysimplex.cpp'])
rapidjson_dep = dependency('rapidjson')

lapi = '3.7'
if get_option('buildtype') == 'debug'
  lapi = ''
endif


fs = import('fs')
if fs.is_file('simplexui/_version.py')
  message('Using existing _version.py')
  py.install_sources(
    'simplexui/_version.py',
    subdir:'simplexui',
  )
else
  version_py = configure_file(
    input: 'simplexui/_version.py.in',
    output: '_version.py',
    install_dir: py.get_install_dir() / 'simplexui',
    configuration : conf_data,
  )
  py.install_sources(
    version_py,
    subdir:'simplexui',
  )
endif

pysimplex = py.extension_module(
  'pysimplex',
  pysimplex_files,
  dependencies : [simplexlib_dep, rapidjson_dep],
  install: true,
  limited_api : lapi,
  subdir : 'simplexui',
)

subdir('simplexui')
