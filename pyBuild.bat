setlocal

SET PFX=%~dp0
SET BUILD=pybuild

cd %PFX%
rmdir %BUILD% /s /q
mkdir %BUILD%
cd %BUILD%

cmake -DTARGET_DCC=Python -G "Visual Studio 15 2017 Win64" ..\
cmake --build . --config Release --target INSTALL

pause

