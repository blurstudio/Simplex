setlocal

SET MAYA_VERSION=2024
REM "vs" "ninja"
REM use VS for the debugger, otherwise use NINJA
REM Until I figure out how to debug using nvim
SET BACKEND=vs
REM "debug" "debugoptimized" "release"
SET BUILDTYPE=debug
SET BUILDDIR=mayabuild_%BUILDTYPE%_%MAYA_VERSION%_%BACKEND%

if not exist %BUILDDIR%\ (
    meson setup %BUILDDIR% -Dmaya:maya_version=%MAYA_VERSION% --buildtype %BUILDTYPE% --vsenv --backend %BACKEND%
)

if exist %BUILDDIR%\ (
    meson compile -C %BUILDDIR%
    meson install -C %BUILDDIR%
)

pause
