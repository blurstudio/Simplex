# SIMPLEX SOLVER
---

![Example Simplex UI](docs/images/SimplexExample.png)

---

### For Artitsts

Simplex aims to provide an intuitive, cross-package UI that allows for building, editing, and controlling complex shapes, combos, and transitions for use in high-end blendshape facial rigs, or even PSD systems.

This tool was built with the full **F**acial **A**ction **C**oding **S**ystem (FACS) in mind. As such, it easily handles hundreds of shapes with arbitrary combo depth. Spline interpolation for in-between shapes, positive-negative shapes, and in-between combo shapes are supported. Arbitrary value combinations are also fully supported (eg. ComboX activates when SliderA is at 0.25 and SliderB is at 0.33).

### For TD's

Simplex aims to be fully scriptable so that it can easily be inserted into any pipeline. The UI and API are fully Python, all content creation commands are abstracted (for multi-package use), and all systems are built as human readable JSON strings.

There is a suite of tools included that allow for manipulating .smpx files Most of which can be run completely outside of a DCC. This includes vertex reordering, un-subdividing, splitting, and even shape-inversion. 

There is a python interface to the simplex solver as well. As long as your package supports Plugins, Python, and Qt (or PySide), you can use Simplex.

#### Simplex is NOT

* Simplex is not a modeling toolkit
    * Modeling is done using whatever tools you choose on your current package
* Simplex is not a deformer
    * It only informs a native blendshape deformer what values the current shapes should have

### Documentation

Check out the wiki for documentation and usage. We are still in the process of writing it, so please be patient.

## INSTALLATION

* These instructions are for Windows. Unfortunately, I don't have a Linux box to test on, but I will welcome changes from anybody working to get this compiling and running on Linux. 
1. Download the latest release and unzip the folder where you want Simplex to live
2. Copy the "SimplexUI" folder into a maya scripts directory. Like `%USERPROFILE%\Documents\maya\2018\scripts`
3. Put "simplex_maya.mll" in a plugins folder. Like `%USERPROFILE%\Documents\maya\2018\plug-ins`
4. Load the simplex_maya.mll plugin from the plugin manager and run these two commands in Python to start the tool. This can easily be made a shelf button.
```python
from SimplexUI import runSimplexUI
runSimplexUI()
```

## Building for Maya on Windows
1. Get all the build prerequisites:
    * Get and install the maya devkit:
        1. Download the maya devkit zip file from their website
        2. Unzip somewhere
        3. Look for the folders: cmake, devkit, include, mkspecs
        4. Copy/merge those folders directly into your maya install directory
    * Get and install Visual Studio. (The Express and Community editions are free online)
        * At least Visual Studio 2012 is required for Maya 2016 and 2017
        * At least Visual Studio 2015 is required for Maya 2018
        * I've compiled for Maya 2016-2018 using Visual Studio 2017 without issue.
    * Get and install CMake from https://cmake.org/download/
        * Make sure you can run `cmake` from the command line. Look online to show you how
2. For Windows, Navigate to the SimplexCPP folder. Right-click and **EDIT** the mayaConfigure.bat
    * Change the line with `SET MAYA_VERSION=` to whatever version you're compiling for
    * Change the `SET COMPILER=` to your compiler version.
        * You can get the available compilers by running `cmake --help` in the command line
    * Remove the word `REM` from the line starting `REM cmake --build`
3. Run the mayaConfigure.bat file. You should see a line saying "Build succeeded" when it completes.
4. If all goes well, there should now be 2 new folders in SimplexCPP called "mayabuild" and "output"
    * Go into the output folder, click through all the other folders, and find simplex_maya.mll



