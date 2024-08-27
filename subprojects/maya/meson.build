project('maya', 'cpp')

maya_version = get_option('maya_version')
maya_devkit_base = get_option('maya_devkit_base')
maya_link_qt = get_option('maya_link_qt')
maya_qt_extra_includes = get_option('maya_qt_extra_includes')

os_name = build_machine.system()

maya_inc_suffix = 'include'
maya_lib_suffix = 'lib'

maya_compile_args = ['-DREQUIRE_IOSTREAM', '-D_BOOL']
maya_link_args = []

if os_name == 'windows'
  maya_install_base = 'c:/Program Files/Autodesk'
  maya_plugin_ext = 'mll'
  maya_compile_args += ['-DNT_PLUGIN']
  maya_link_args = ['/export:initializePlugin', '/export:uninitializePlugin']
elif os_name == 'darwin'
  maya_install_base = '/Applications/Autodesk'
  maya_plugin_ext = 'bundle'
  if maya_devkit_base == ''
    maya_lib_suffix = 'Maya.app/Contents/MacOS'
    maya_bin_suffix = 'Maya.app/Contents/bin'
  endif
  maya_compile_args += ['-DOSMac_']
  if meson.get_compiler('cpp').get_id() == 'clang'
    maya_compile_args += ['--std', 'c++17', '--stdlib', 'libc++']
    maya_compile_args += ['-arch', 'x86_64']
    maya_link_args += ['-arch', 'x86_64']
    if maya_version.version_compare('>=2024')
      # build both the arm and x86 plugins when compiling for mac
      maya_compile_args += ['-arch', 'arm64']
      maya_link_args += ['-arch', 'arm64']
    else
    endif
  endif

  # ignore this warning that comes from maya's headers
  maya_compile_args += ['-Wno-inconsistent-missing-override']
elif os_name == 'linux'
  maya_install_base = '/usr/autodesk'
  maya_plugin_ext = 'so'
  maya_compile_args += ['-DLINUX', '-fPIC']
else
  error('Incompatible operating system')
endif
maya_install_path = maya_install_base / ('Maya' + maya_version)

if maya_devkit_base != ''
  message('Using Maya Devkit:', maya_devkit_base)
  maya_install_path = maya_devkit_base
endif

maya_inc_dir = maya_install_path / maya_inc_suffix
message('Searching Maya Include directory:', maya_inc_dir)
maya_inc = include_directories(maya_inc_dir)

maya_lib_dir = maya_install_path / maya_lib_suffix
message('Searching Maya lib directory:', maya_lib_dir)

# Get all the maya libraries
cmplr = meson.get_compiler('cpp')
maya_libs = [
  cmplr.find_library('Foundation', dirs : maya_lib_dir),
  cmplr.find_library('OpenMaya', dirs : maya_lib_dir),
  cmplr.find_library('OpenMayaAnim', dirs : maya_lib_dir),
  cmplr.find_library('OpenMayaFX', dirs : maya_lib_dir),
  cmplr.find_library('OpenMayaRender', dirs : maya_lib_dir),
  cmplr.find_library('OpenMayaUI', dirs : maya_lib_dir),
  cmplr.find_library('clew', dirs : maya_lib_dir),
]

# Link to maya's qt libs if required
# This doesn't do MOC stuff ... yet
if maya_link_qt
  fs = import('fs')
  if not fs.is_dir(maya_inc_dir / 'QtCore')
    error(
      'Could not find Maya QT headers with `maya_link_qt` defined\n',
      'You probably need to unzip `include/qt_*-include.zip`\n',
      'Checking in folder: ', maya_inc_dir,
    )
  endif

  maya_qt_lib_names = ['Qt5Core', 'Qt5Gui', 'Qt5Widgets']
  if maya_qt_extra_includes != ''
    maya_qt_lib_names += maya_qt_extra_includes.split(';')
  endif

  foreach lib_name : maya_qt_lib_names
      maya_libs += cmplr.find_library(lib_name, dirs : maya_lib_dir)
  endforeach
endif

maya_dep = declare_dependency(
  dependencies : maya_libs,
  include_directories : maya_inc,
  variables : {'name_suffix' : maya_plugin_ext, 'maya_version' : maya_version},
  compile_args : maya_compile_args,
  link_args : maya_link_args,

)

meson.override_dependency('maya', maya_dep)
