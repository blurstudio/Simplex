# SIMPLEX UI
---

![Example Simplex UI](img/simplexUiExample.png)

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
    * In the future, I *do* have ideas for building an interface to an advanced deformer for dynamically previewing arbitrary splits, but the final output will always have the ability to bake down to a basic blendshape.

### Basic Usage
Follow this youtube link to a basic walkthrough of Simplex usage. This video highlights an older version of Simplex, but the interaction remains basically the same. [https://www.youtube.com/watch?v=Hc79sDi3f0U](https://www.youtube.com/watch?v=Hc79sDi3f0U)

## INSTALLATION

1. Download the latest release
2. Copy the `modules` folder from the zip file into your maya directory. On windows, that would mean copying into `%USERPROFILE%\Documents\maya` so that the module file sits at `%USERPROFILE%\Documents\maya\modules\simplex.mod`
3. Run these two Python commands in Maya to start the tool. (This is probably what you should put into a shelf button)
```python
from simplexui import runSimplexUI
runSimplexUI()
```

## Compiling
Hopefully you don't need to do this, but if you have to, just take a look at `.github/workflows/main.yml` and you should be able to piece together how to get a compile working using CMake. You aren't required to download the devkit or set its path for CMake if you've got maya installed on your machine. Also note, I use features from CMake 3.16+ so I can target python 2 and 3 separately.
