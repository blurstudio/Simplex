py = import('python')
py_inst = py.find_installation('python3')
py_dep = py_inst.dependency()

pysimplex_files = files(['pysimplex.cpp'])
rapidjson_dep = dependency('rapidjson')

lapi = '3.7'
if get_option('buildtype') == 'debug'
  lapi = ''
endif

pysimplex = py_inst.extension_module(
  'pysimplex',
  pysimplex_files,
  dependencies : simplexlib_dep,
  install: true,
  install_dir : meson.global_source_root() / 'output_Python',
  limited_api : lapi,
)
