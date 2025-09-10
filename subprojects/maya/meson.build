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
  maya_compile_args += ['-DNT_PLUGIN', '/Zc:__cplusplus']
  maya_link_args = [
    # Export the methods that maya requires
    '/export:initializePlugin',
    '/export:uninitializePlugin',
    # Make sure to look for pdb file in the same directory as the .mll
    '/PDBALTPATH:%_PDB%',
  ]
elif os_name == 'darwin'
  maya_install_base = '/Applications/Autodesk'
  maya_plugin_ext = 'bundle'
  if maya_devkit_base == ''
    maya_lib_suffix = 'Maya.app/Contents/MacOS'
    maya_bin_suffix = 'Maya.app/Contents/bin'
  endif
  maya_compile_args += ['-DOSMac_']
  if meson.get_compiler('cpp').get_id() == 'clang'
    maya_compile_args += ['--stdlib', 'libc++']
    maya_compile_args += ['-arch', 'x86_64']
    maya_link_args += ['-arch', 'x86_64']
    if maya_version.version_compare('>=2024')
      # build both the arm and x86 plugins when compiling for mac
      maya_compile_args += ['-arch', 'arm64']
      maya_link_args += ['-arch', 'arm64']
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

includes = []
maya_inc_dir = maya_install_path / maya_inc_suffix
message('Searching Maya Include directory:', maya_inc_dir)
includes += include_directories(maya_inc_dir)

maya_lib_dir = maya_install_path / maya_lib_suffix
message('Searching Maya lib directory:', maya_lib_dir)

maya_bin_dir = maya_install_path / 'bin'

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
# Below, I expose the bin and include dirs so I can directly invoke the
# moc exe included with maya. Saves from having to make a maya qt module

qt_moc_path = ''
if maya_link_qt
  fs = import('fs')

  if maya_version.version_compare('>=2025')
    if not fs.is_dir(maya_install_path / 'Qt' / 'include' / 'QtCore')
      error(
        'Could not find Maya QT headers with `maya_link_qt` defined\n',
        'You probably need to unzip `devkitBase/Qt.zip`\n',
        'Checking in folder: ', maya_install_path,
      )
    endif
    maya_qt_lib_names = [f'Qt6Core', f'Qt6Gui', f'Qt6Widgets']

    qt_lib_dir = maya_lib_dir
    qt_moc_path = maya_bin_dir / 'moc'
    if maya_devkit_base != ''
      qt_lib_dir = maya_devkit_base / 'Qt' / 'lib'
      qt_moc_path = maya_devkit_base / 'Qt' / 'libexec' / 'moc'
      includes += include_directories(maya_devkit_base / 'Qt' / 'include')
    endif
  else
    if not fs.is_dir(maya_inc_dir / 'QtCore')
      error(
        'Could not find Maya QT headers with `maya_link_qt` defined\n',
        'You probably need to unzip `include/qt_*-include.zip`\n',
        'Checking in folder: ', maya_inc_dir,
      )
    endif
    qt_ver = 5
    maya_qt_lib_names = [f'Qt5Core', f'Qt5Gui', f'Qt5Widgets']
    qt_lib_dir = maya_lib_dir
    qt_moc_path = maya_bin_dir / 'moc'
    if maya_devkit_base != ''
      qt_moc_path = maya_devkit_base / 'devkit' / 'bin' / 'moc'
    endif
  endif

  if maya_qt_extra_includes != ''
    maya_qt_lib_names += maya_qt_extra_includes.split(';')
  endif
  foreach lib_name : maya_qt_lib_names
      maya_libs += cmplr.find_library(lib_name, dirs : qt_lib_dir)
  endforeach

endif

maya_dep = declare_dependency(
  dependencies : maya_libs,
  include_directories : includes,
  variables : {
    'name_suffix' : maya_plugin_ext,
    'maya_version' : maya_version,
    'maya_bin_dir': maya_bin_dir,
    'maya_inc_dir': maya_inc_dir,
    'qt_moc_path': qt_moc_path,
  },
  compile_args : maya_compile_args,
  link_args : maya_link_args,
)

meson.override_dependency('maya', maya_dep)
