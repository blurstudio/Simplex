setlocal

SET PY_VERSION=3.9
SET BUILD=pybuild_%PY_VERSION%
SET COMPILER=Visual Studio 17 2022

SET PFX=%~dp0
cd %PFX%
rmdir %BUILD% /s /q
mkdir %BUILD%
cd %BUILD%

cmake ^
    -DBUILD_MAYA=NO ^
    -DMAYA_PYTHON=NO ^
    -DSYSTEM_PY_VERSION=%PY_VERSION% ^
    -G "%COMPILER%" ..\

cmake --build . --config RelWithDebInfo --target ALL_BUILD

pause
