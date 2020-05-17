# SIMPLEX UI
---

![Example Simplex UI](docs/images/SimplexExample.png)

---

### For Artitsts

Simplex aims to provide an intuitive, cross-package UI that allows for building, editing, and controlling complex shapes, combos, and transitions for use in high-end blendshape facial rigs, or even PSD systems.

This tool was built with the full **F**acial **A**ction **C**oding **S**ystem (FACS) in mind. As such, it easily handles hundreds of shapes with arbitrary combo depth. Spline interpolation for in-between shapes, positive-negative shapes, in-between combo shapes, and combo transitions are supported. Arbitrary value combinations are also fully supported (eg. ComboX activates when SliderA is at 0.25 and SliderB is at 0.33).

### For TD's

Simplex aims to be fully scriptable so that it can easily be inserted into any pipeline. The UI and API are fully Python, all content creation commands are abstracted (for multi-package use), and all systems are built as human readable JSON strings.

There is a suite of tools included that allow for manipulating .smpx files. Most of which can be run completely outside of a DCC. This includes vertex reordering, un-subdividing, splitting, and even shape-inversion. These .smpx files are nothing more than specially structured alembic caches

As long as your package supports Plugins, Python, and Qt (or PySide), you can use Simplex.

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
2. Copy the "SimplexUI" folder into a maya scripts directory. For instance `%USERPROFILE%\Documents\maya\2018\scripts`
3. Get the simplex plugin either from the releases here, or from the [SimplexPlugins](https://github.com/blurstudio/SimplexPlugins) repository. Put "simplex_maya.mll" in a plugins folder. Like `%USERPROFILE%\Documents\maya\2018\plug-ins`
4. Run these two Python commands in Maya to start the tool.
```python
from SimplexUI import runSimplexUI
runSimplexUI()
```

## (WIP) Pip installation
I am working on making Simplex pip installable. It's not done yet, but for the adventurous out there, you can give this a try.

Pip is the Python package manager. Mayapy doesn't come with pip by default, however, it *does* come with a command that installs pip, so we can ensure pip is there then install simplex as a package. So open your command prompt and do this:

This only ever has to be done once (but doing it more than once doesn't hurt anything). It just makes sure that mayapy has pip.
```
/path/to/mayapy -m ensurepip --default-pip
/path/to/mayapy -m pip install --upgrade pip
```

Then you can install Simplex. I don't have Simplex packaged properly yet. But for now, you can try a development install.
```
/path/to/mayapy -m pip install -e /other/path/to/simplexFolder
```

