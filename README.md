# SIMPLEX SOLVER

This is the suite of compiled C++ plugins that the [Simplex UI](https://github.com/blurstudio/Simplex) interfaces with.
There are builds for for Maya, Softimage (RIP), and Python. All builds are currently targeting Windows, and are untested on Linux. However, Linux support is coming soon.

## Building on Windows
* Get all the build prerequisites:
    * Get and install Visual Studio. (The Express and Community editions are free online)
        * At least Visual Studio 2012 is required for Maya 2016 and 2017
        * At least Visual Studio 2015 is required for Maya 2018
        * I've compiled for Maya 2016-2018 using Visual Studio 2017 without issue.
    * Get and install CMake from https://cmake.org/download/
        * Make sure you can run `cmake` from the command line. Look online to show you how

#### Build for Maya
1. For Windows, Right-click and **EDIT** the mayaConfigure.bat
    * Change the line with `SET MAYA_VERSION=` to whatever version you're compiling for
    * Change the `SET COMPILER=` to your compiler version.
        * You can get the available compilers by running `cmake --help` in the command line
    * Remove the word `REM` from the line starting `REM cmake --build`
2. Run the mayaConfigure.bat file. You should see a line saying "Build succeeded" when it completes.
3. If all goes well, there should now be 2 new folders in SimplexCPP called "mayabuild" and "output"
    * Go into the output folder, click through all the other folders, and find simplex_maya.mll

Building for Python or XSI follows a similar procedure using the respective .bat files

## Building on Linux

* Get all the build prerequisites:
    * Minimum requirement for linux build is a gcc version which supports C++ 11 Standard
        * Prefered GCC version from Maya 2019, 2020 and probably 2021, will be 6.3.1 
    * Get and install CMake from https://cmake.org/download/
        * Make sure you can run `cmake` from the command line. Look online to show you how

_Note: Linux support is tested only with Maya 2019 and 2020, also Python 2.7. Plugin is not tested with XSI in linux. There is a possibilty for this not to work as the latest version of XSI build using an older gcc(4.2.4), which doesn't support C++ 11._

### Setup

Clone the repository into your development path.

```bash
$ cd <development_path>
$ git clone --recurse-submodules git@github.com:blurstudio/SimplexPlugins.git
$ cd SimplexPlugins
$ make --help
```

#### Build for Maya

##### CMake

* Create build directory (default: mayabuild)
* Generate the build files inside the directory
```bash
$ rm -rf mayabuild # Remove the directory if exists
$ mkdir mayabuild
$ cd mayabuild
$ cmake -DMAYA_VERSION=<version_of_maya> -DMAYA_LOCATION=<maya_path_optional> ..
```
* Build the maya plugin
```bash
$ cd mayabuild
$ cmake --build . --config Release
```
* Install the plugin
```bash
$ cmake --build . --target install
```

##### Gnu Make

Gnu make have some simple wrapper command to do the above steps (CMake)

* `make generate_maya` -> Genrate the build files for maya plugin inside `mayabuild` directory 
* `make build_maya` -> Command to compile the source code
* `make install_maya` -> Command to compile the source code

_Note: Change the `MAYA_VERSION` inside the Makefile to build for a different version of maya_

#### Build for Python

##### CMake

* Create build directory (default: pybuild)
* Generate the build files inside the directory
```bash
$ rm -rf pybuild # Remove the directory if exists
$ mkdir pybuild
$ cd pybuild
$ cmake -DPY_VERSION=<version_of_python> -DTARGET_DCC=Python ..
```
* Build the python c++ extension
```bash
$ cd pybuild
$ cmake --build . --config Release
```
* Install the extesion
```bash
$ cmake --build . --target install
```

##### Gnu Make

* `make generate_python` -> Genrate the build files for maya plugin inside `mayabuild` directory 
* `make build_python` -> Command to compile the source code
* `make install_python` -> Command to compile the source code

## TODO

* Write `make.bat` batch file to standardize the build commands
* Test XSI linux support
* Add build support for MacOS
