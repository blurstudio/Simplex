py = import('python')
py_inst = py.find_installation('python3')
py_dep = py_inst.dependency()

simplex_python_files = files(['simplex_python.cpp'])
rapidjson_dep = dependency('rapidjson')

lapi = '3.7'
if get_option('buildtype') == 'debug'
  lapi = ''
endif

simplex_python = py_inst.extension_module(
  'simplex_python',
  simplex_python_files,
  dependencies : simplexlib_dep,
  install: true,
  install_dir : meson.global_source_root() / 'output_Python',
  limited_api : lapi,
)
