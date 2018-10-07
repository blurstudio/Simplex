setlocal

SET BUILD=mayabuild
SET MAYA_VERSION=2018
SET COMPILER=Visual Studio 15 2017 Win64

SET PFX=%~dp0
cd %PFX%
rmdir %BUILD% /s /q
mkdir %BUILD%
cd %BUILD%

cmake ^
    -DMAYA_VERSION=%MAYA_VERSION% ^
    -G "%COMPILER%" ..\

REM cmake --build . --config Release --target INSTALL

pause
