project('maya', 'cpp', meson_version : '>=1.7.0')

fs = import('fs')
py = import('python').find_installation(pure: false)
cmplr = meson.get_compiler('cpp')

# --- Zip Finder Helper Script ---
find_zip_script = '''
import sys, glob, os
base = sys.argv[1]
pattern = sys.argv[2]

bases = [b for b in base.split(';') if os.path.exists(b)]
if not bases:
    print(f"a zip file matching '{pattern}'")
    sys.exit(0)

for base in bases:
    matches = glob.glob(os.path.join(base, "**", pattern), recursive=True)
    if matches:
        print(matches[0])
        sys.exit(0)

print(f"a zip file matching '{pattern}'")
'''

maya_version = get_option('maya_version')
maya_devkit_base = get_option('maya_devkit_base')
maya_qt_extra_includes = get_option('maya_qt_extra_includes')
maya_custom_install_path = get_option('maya_custom_install_path')

alembic_opt = get_option('maya_link_alembic')
imath_opt = get_option('maya_link_imath')
ufe_opt = get_option('maya_link_ufe')
qt_opt = get_option('maya_link_qt')
gl_opt = get_option('maya_link_opengl')
numpy_opt = get_option('maya_link_numpy')

has_devkit = maya_devkit_base != ''

os_name = build_machine.system()
maya_inc_suffix = 'include'
maya_lib_suffix = 'lib'

maya_compile_args = ['-DREQUIRE_IOSTREAM', '-D_BOOL']
maya_link_args = []

if os_name == 'windows'
  maya_default_install_base = 'c:/Program Files/Autodesk'
  maya_plugin_ext = 'mll'
  maya_compile_args += ['-DNT_PLUGIN', '/Zc:__cplusplus']
  maya_link_args = ['/export:initializePlugin', '/export:uninitializePlugin', '/PDBALTPATH:%_PDB%']
elif os_name == 'darwin'
  maya_default_install_base = '/Applications/Autodesk'
  maya_plugin_ext = 'bundle'
  if not has_devkit
    maya_lib_suffix = 'Maya.app/Contents/MacOS'
    maya_bin_suffix = 'Maya.app/Contents/bin'
  endif
  maya_compile_args += ['-DOSMac_', '-Wno-inconsistent-missing-override']
  if cmplr.get_id() == 'clang'
    maya_compile_args += ['--stdlib', 'libc++', '-arch', 'x86_64']
    maya_link_args += ['-arch', 'x86_64']
    if maya_version.version_compare('>=2024')
      maya_compile_args += ['-arch', 'arm64']
      maya_link_args += ['-arch', 'arm64']
    endif
  endif
elif os_name == 'linux'
  maya_default_install_base = '/usr/autodesk'
  maya_plugin_ext = 'so'
  maya_compile_args += ['-DLINUX', '-fPIC']
else
  error('Incompatible operating system')
endif

if maya_custom_install_path != ''
  maya_install_path = maya_custom_install_path
else
  maya_install_path = maya_default_install_base / ('Maya' + maya_version)
endif

search_base = has_devkit ? maya_devkit_base : maya_install_path

# --- Define Ordered Base Search Paths ---
search_inc_dirs = []
search_lib_dirs = []
maya_bin_dir = ''
maya_py_ver = ''

has_install = maya_install_path != '' and fs.is_dir(maya_install_path)

if has_install
  search_inc_dirs += maya_install_path / maya_inc_suffix
  search_lib_dirs += maya_install_path / maya_lib_suffix
  maya_bin_dir = maya_install_path / 'bin'
  mayapy_prg = find_program('mayapy', dirs : maya_bin_dir, required : numpy_opt.enabled())
  pyverscript = 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
  maya_py_ver = run_command(mayapy_prg, '-c', pyverscript, check: false).stdout().strip()

  if mayapy_prg.found()
      meson.override_find_program('maya:mayapy', mayapy_prg)
  endif
endif

if has_devkit
  search_inc_dirs += maya_devkit_base / maya_inc_suffix
  search_lib_dirs += maya_devkit_base / maya_lib_suffix
endif

if search_inc_dirs.length() == 0
  error('Could not find any maya install or devkit paths')
endif

maya_inc_dir = search_inc_dirs[-1]
maya_lib_dir = search_lib_dirs[-1]

core_includes = []
foreach inc_dir : search_inc_dirs
  if fs.is_dir(inc_dir)
    core_includes += include_directories(inc_dir)
  endif
endforeach

# --- Retrieve Core Libraries ---
core_libs = []
core_lib_names = ['Foundation', 'OpenMaya', 'OpenMayaAnim', 'OpenMayaFX', 'OpenMayaRender', 'OpenMayaUI', 'clew']
foreach lib_name : core_lib_names
  core_libs += cmplr.find_library(lib_name, dirs : search_lib_dirs)
endforeach

# ==============================================================================
# DEPENDENCY 1: Core Maya (For Python Modules / Standalone Apps)
# ==============================================================================
maya_core_dep = declare_dependency(
  dependencies : core_libs,
  include_directories : core_includes,
  variables : {
    'maya_version' : maya_version,
    'maya_bin_dir': maya_bin_dir,
    'maya_inc_dir': maya_inc_dir,
    'maya_install_path': maya_install_path,
    'maya_using_devkit': has_devkit.to_string(),
  }
)
meson.override_dependency('maya-core', maya_core_dep)

# ==============================================================================
# DEPENDENCY 2: Maya Plugin (For MLL/SO/Bundle compilation)
# ==============================================================================
maya_plugin_dep = declare_dependency(
  dependencies: [maya_core_dep],
  compile_args : maya_compile_args,
  link_args : maya_link_args,
  variables : {
    'name_suffix' : maya_plugin_ext,
  }
)
meson.override_dependency('maya', maya_plugin_dep)
meson.override_dependency('maya-plugin', maya_plugin_dep)

# ==============================================================================
# OPTIONAL GRANULAR DEPENDENCIES
# ==============================================================================
build_numpy = false
build_alembic = false
build_imath = false
build_ufe = false
build_qt = false
build_opengl = false

# --- Numpy ---
if not numpy_opt.disabled()
  if not has_install
    error('The numpy install comes from the maya install. No install path found')
  endif
  build_numpy = true
  np_include_script = 'import numpy;print(numpy.get_include())'
  np_include_path = run_command(mayapy_prg, '-c', np_include_script, check: false).stdout().strip()

  maya_numpy_dep = declare_dependency(
    include_directories: np_include_path,
    variables : {
      'mayapy_version': maya_py_ver,
    }
  )
  meson.override_dependency('maya-numpy', maya_numpy_dep)
endif

# --- Alembic & Imath ---
check_alembic = not alembic_opt.disabled()
check_imath = not imath_opt.disabled()

if check_alembic or check_imath
  if (alembic_opt.enabled() or imath_opt.enabled()) and not has_devkit
    error('Alembic and Imath dependencies require maya_devkit_base')
  endif

  if has_devkit
    alembic_base = maya_devkit_base / 'devkit' / 'Alembic'

    if fs.is_dir(alembic_base / 'include')
      alembic_inc = include_directories(alembic_base / 'include')
      alembic_lib_dir = alembic_base / 'lib'

      if check_alembic
        maya_alembic_dep = declare_dependency(
          dependencies: [cmplr.find_library('Alembic', dirs : alembic_lib_dir)],
          include_directories: alembic_inc
        )
        meson.override_dependency('maya-alembic', maya_alembic_dep)
        build_alembic = true
      endif

      if check_imath
        imath_lib = cmplr.find_library('Imath-3_2-maya', dirs : alembic_lib_dir, required: false)
        if not imath_lib.found()
          imath_lib = cmplr.find_library('Imath', dirs : alembic_lib_dir, required: false)
        endif
        imath_inc = include_directories(alembic_base / 'include' / 'Imath')
        maya_imath_dep = declare_dependency(dependencies: [imath_lib], include_directories: imath_inc)
        meson.override_dependency('maya-imath', maya_imath_dep)
        build_imath = true
      endif

    else
      if alembic_opt.enabled() or imath_opt.enabled()
        zip_hint = run_command(py, '-c', find_zip_script, search_base, '*Alembic*.zip', check: false).stdout().strip()
        error('Could not find Alembic/Imath headers at: ' + alembic_base + '\nYou probably need to unzip: ' + zip_hint)
      endif
    endif
  endif
endif

# --- UFE ---
if not ufe_opt.disabled()
  if ufe_opt.enabled() and not has_devkit
    error('maya_link_ufe requires maya_devkit_base')
  endif

  if has_devkit
    ufe_base = maya_devkit_base / 'devkit' / 'ufe'
    if fs.is_dir(ufe_base / 'include')
      ufe_lib = cmplr.find_library('ufe_7', dirs : ufe_base / 'lib', required: false)
      if not ufe_lib.found()
        ufe_lib = cmplr.find_library('ufe', dirs : ufe_base / 'lib')
      endif
      maya_ufe_dep = declare_dependency(
        dependencies: [ufe_lib],
        include_directories: include_directories(ufe_base / 'include')
      )
      meson.override_dependency('maya-ufe', maya_ufe_dep)
      build_ufe = true
    elif ufe_opt.enabled()
      zip_hint = run_command(py, '-c', find_zip_script, search_base, '*ufe*.zip', check: false).stdout().strip()
      error('Could not find UFE headers at: ' + ufe_base + '\nYou probably need to unzip: ' + zip_hint)
    endif
  endif
endif

# --- Qt ---
if not qt_opt.disabled()
  search_paths = [
    maya_inc_dir, maya_inc_dir / 'Qt', maya_inc_dir / 'Qt' / 'include',
    maya_install_path, maya_install_path / 'Qt', maya_install_path / 'Qt' / 'include',
  ]
  qt_include_dir = ''
  foreach search_path: search_paths
    if fs.is_dir(search_path / 'QtCore')
      qt_include_dir = search_path
      break
    endif
  endforeach

  if qt_include_dir != ''
    mocdirs = maya_bin_dir != '' ? [maya_bin_dir] : []
    mocdirs += [maya_install_path / 'Qt' / 'bin', maya_install_path / 'Qt' / 'libexec', maya_install_path / 'devkit' / 'bin']
    moc_prg = find_program('moc', dirs : mocdirs, required : qt_opt.enabled())

    if moc_prg.found()
      meson.override_find_program('maya:moc', moc_prg)
      maya_qt_lib_names = maya_version.version_compare('>=2025') ? ['Qt6Core', 'Qt6Gui', 'Qt6Widgets'] : ['Qt5Core', 'Qt5Gui', 'Qt5Widgets']
      if maya_qt_extra_includes != ''
        maya_qt_lib_names += maya_qt_extra_includes.split(';')
      endif

      qt_libs = []
      foreach lib_name : maya_qt_lib_names
        qt_libs += cmplr.find_library(lib_name, dirs : search_lib_dirs)
      endforeach

      maya_qt_dep = declare_dependency(
        dependencies: qt_libs,
        include_directories: include_directories(qt_include_dir),
      )
      meson.override_dependency('maya-qt', maya_qt_dep)
      build_qt = true
    endif
  elif qt_opt.enabled()
    baselist = ';'.join(search_paths)
    zip_hint = run_command(py, '-c', find_zip_script, baselist, 'qt_*include.zip', check: false).stdout().strip()
    error('Could not find Maya QT headers. Unzip: ' + zip_hint)
  endif
endif

# --- OpenGL ---
if not gl_opt.disabled()
  gl_dep = dependency('gl', method : 'system', required: gl_opt.enabled())
  if gl_dep.found()
    glu_dep = os_name == 'windows' ? cmplr.find_library('glu32', required : gl_opt.enabled()) : dependency('glu', required: gl_opt.enabled())
    if glu_dep.found()
      maya_opengl_dep = declare_dependency(dependencies: [gl_dep, glu_dep])
      meson.override_dependency('maya-opengl', maya_opengl_dep)
      build_opengl = true
    endif
  endif
endif

# ==============================================================================
# SUMMARY
# ==============================================================================
summary(
  {
    'Maya Version': maya_version,
    'Found Install Path': has_install,
    'Using Devkit': has_devkit,
  },
  section: 'Maya Subproject Configuration',
  bool_yn: true
)

summary(
  {
    'maya-core': true,
    'maya-plugin': true,
    'maya-qt': build_qt,
    'maya-numpy': build_numpy,
    'maya-opengl': build_opengl,
    'maya-alembic': build_alembic,
    'maya-imath': build_imath,
    'maya-ufe': build_ufe,
  },
  section: 'Exported Dependencies',
  bool_yn: true
)
