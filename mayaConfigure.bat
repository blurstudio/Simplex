setlocal

SET MAYA_VERSION=2022
SET BUILD=mayabuild_%MAYA_VERSION%
SET COMPILER=Visual Studio 15 2017 Win64

SET PFX=%~dp0
cd %PFX%
rmdir %BUILD% /s /q
mkdir %BUILD%
cd %BUILD%

cmake ^
    -DMAYA_VERSION=%MAYA_VERSION% ^
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON ^
    -G "%COMPILER%" ..\

cmake --build . --config Release --target INSTALL

pause
