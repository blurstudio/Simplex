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

