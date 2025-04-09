setlocal

SET MAYA_VERSION=2024
REM "vs" "ninja"
REM use VS for the debugger, otherwise use NINJA
REM Until I figure out how to debug using nvim
SET BACKEND=ninja
REM "debug" "debugoptimized" "release"
SET BUILDTYPE=release
SET BUILDDIR=mayabuild_%BUILDTYPE%_%MAYA_VERSION%_%BACKEND%

if not exist %BUILDDIR%\ (
    REM meson setup %BUILDDIR% -Dmaya:maya_version=%MAYA_VERSION% --buildtype %BUILDTYPE% --vsenv --backend %BACKEND%
    meson setup %BUILDDIR% -Dmaya_build=false -Dpython_build=true -Dmaya:maya_version=%MAYA_VERSION% --buildtype %BUILDTYPE% --vsenv --backend %BACKEND%
)



if exist %BUILDDIR%\ (
    REM meson compile -C %BUILDDIR%
    REM meson install --skip-subprojects -C %BUILDDIR%
)

pause
