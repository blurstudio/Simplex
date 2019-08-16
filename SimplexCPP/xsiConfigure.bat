setlocal

SET BUILD=xsibuild
SET COMPILER=Visual Studio 10 2010 Win64

SET PFX=%~dp0
cd %PFX%
rmdir %BUILD% /s /q
mkdir %BUILD%
cd %BUILD%


rem -DXSI_VERSION="2014 SP2" ^
rem -DXSI_VERSION="2015" ^

cmake ^
    -DTARGET_DCC=XSI ^
    -DXSI_VERSION="2015" ^
    -G "%COMPILER%" ..\

cmake --build . --config Release --target INSTALL

pause
