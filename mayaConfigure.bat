setlocal

SET MAYA_VERSION=2023
SET BUILD=mayabuild_%MAYA_VERSION%
SET COMPILER=Visual Studio 17 2022

SET PFX=%~dp0
cd %PFX%
rmdir %BUILD% /s /q
mkdir %BUILD%
cd %BUILD%


REM -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

cmake ^
    -DMAYA_VERSION=%MAYA_VERSION% ^
    -G "%COMPILER%" ..\

cmake --build . --config RelWithDebInfo --target ALL_BUILD

pause
