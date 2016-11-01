I haven't had to deal with actually distributing
a plugin and tool before, so this may be a little rough

Most of the development we are currently doing is in Windows, 
so all instructions will be given assuming that platform.
However, much of this *should* work for other platforms.

Install:
    Open "simplex.mod" and replace all instances of <FILEPATH> with the path to your "Simplex" top level folder

    Copy "simplex.mod" to "%USERPROFILE%\Documents\maya\2016\modules" (or the 2017 folder if you're using 2017)

    Then, (After restarting maya) load the simplex_maya.mll plugin from the plugin manager
    and run these two commands in Python to start the tool:

    from SimplexUI import runSimplexUI
    runSimplexUI()



IF YOU NEED TO REBUILD THE PLUGIN:
    Get all the prerequisites:
        Get and install the devkit:
            Download the maya devkit zip file from their website
            Unzip somewhere
            Look for the folders: cmake, devkit, include, mkspecs
            Copy those folders directly into your maya install directory

        Get and install Visual Studio 2013.
        The Express and Community editions are free

        Get and install CMake from https://cmake.org/download/

    Navigate to the SimplexCPP folder and make an empty folder inside called "build"
    Open a command prompt and navigate to this newly created folder
    Run These two commands, substituting your maya version number (2016 shown):

    cmake -G "Visual Studio 12 2013 Win64" -DMAYA_VERSION=2016 ../
    cmake --build . --config Release --target Install

    If there are no errors, then there should now be a "maya2016" folder in the "Simplex" folder



