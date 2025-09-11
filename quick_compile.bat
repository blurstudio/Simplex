setlocal

SET MAYA_VERSION=2026
REM "vs" "ninja"
REM use VS for the debugger, otherwise use NINJA
REM Until I figure out how to debug using nvim
SET BACKEND=ninja
REM "debug" "debugoptimized" "release"
SET BUILDTYPE=release
SET BUILDDIR=mayabuild_%BUILDTYPE%_%MAYA_VERSION%_%BACKEND%

if not exist %BUILDDIR%\ (
    meson setup %BUILDDIR% ^
    -Dmaya:maya_version=%MAYA_VERSION% ^
    -Dmaya:maya_devkit_base=D:\Autodesk\MayaDev\Maya2026_2\devkitBase ^
    -Dmaya_build=true ^
    -Dpython_build=true  ^
    --buildtype %BUILDTYPE% --vsenv --backend %BACKEND%
)

if exist %BUILDDIR%\ (
    meson compile -C %BUILDDIR% -j 8
    meson install --skip-subprojects -C %BUILDDIR%
)

pause
