# Copyright 2016, Blur Studio
#
# This file is part of Simplex.
#
# Simplex is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Simplex is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.

# pylint:disable=unused-variable
from __future__ import absolute_import, print_function

import itertools
import os

from pysimplex import PySimplex
from six.moves import map, zip

from ..items import Combo, Simplex, Slider
from ..Qt.QtWidgets import QApplication
from .alembicCommon import (
    buildSmpx,
    getSmpxArchiveData,
    getStaticMeshArrays,
    getUvSample,
    readSmpx,
)

try:
    import numpy as np
except ImportError:
    pass


def invertAll(matrixArray):
    """Invert all the square sub-matrices in a numpy array

    Parameters
    ----------
    matrixArray : np.array
        An M*N*N numpy array

    Returns
    -------
    : np.array
        An M*N*N numpy array
    """
    # Look into numpy to see if there is a way to ignore
    # all the repeated sanity checks, and do them ourselves, once
    return np.array([np.linalg.inv(a) for a in matrixArray])


def applyReference(pts, restPts, restDelta, inv):
    """Given a shape and an array of pre-inverted
        per-point matrices return the deltas

    Parameters
    ----------
    pts : np.array
        Deformed point positions
    restPts : np.array
        Rest point positions
    restDelta : np.array
        The delta from rest
    inv : np.array
        An M*4*4 array of matrices

    Returns
    -------
    : np.array
        The new point positions

    """
    pts = pts + restPts + restDelta
    preSize = pts.shape[-1]
    if inv.shape[-2] > pts.shape[-1]:
        oneShape = list(pts.shape)
        oneShape[-1] = inv.shape[-2] - pts.shape[-1]
        pts = np.concatenate((pts, np.ones(oneShape)), axis=-1)

    # Return the 3d points
    return np.einsum("ij,ijk->ik", pts, inv)[..., :preSize]


def loadSimplex(shapePath):
    """Load and parse all the data from a simplex file

    Parameters
    ----------
    shapePath : str
        The path to the .smpx file

    Returns
    -------
    : str
        The simplex JSON string
    : Simplex
        The simplex system
    : pySimplex
        The instantiated simplex solver
    : np.array
        A Numpy array of the shape point positions
    : np.array
        A Numpy array of the rest pose of the system

    """
    if not os.path.isfile(str(shapePath)):
        raise IOError("File does not exist: " + str(shapePath))

    jsString, counts, verts, faces, uvs, uvFaces = readSmpx(shapePath)

    simplex = Simplex.buildSystemFromJsonString(jsString, None, forceDummy=True)
    solver = PySimplex(jsString)

    # return as delta shapes
    restIdx = simplex.shapes.index(simplex.restShape)
    restPts = verts[restIdx]
    verts = verts - restPts[None, ...]  # reshape for broadcasting

    return jsString, simplex, solver, verts, restPts


def writeSimplex(inPath, outPath, newShapes, name="Face", pBar=None):
    """Write a simplex file with new shapes

    Parameters
    ----------
    inPath : str
        The input .smpx file path
    outPath : str
        The output .smpx file path
    newShapes : np.array
        A numpy array of shapes to write
    name : str
        The name of the new system
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------

    """
    if not os.path.isfile(str(inPath)):
        raise IOError("File does not exist: " + str(inPath))

    iarch, abcMesh, jsString = getSmpxArchiveData(inPath)
    faces, counts = getStaticMeshArrays(abcMesh)
    uvs = getUvSample(abcMesh)
    del iarch, abcMesh

    buildSmpx(
        outPath,
        newShapes,
        faces,
        jsString,
        name,
        faceCounts=counts,
        uvs=uvs,
    )


#########################################################################
####                        Deform Reference                         ####
#########################################################################


def _buildSolverInputs(simplex, item, value, indexBySlider):
    """Build an input vector for the solver that will
    produce a required progression value on an item
    """
    inVec = [0.0] * len(simplex.sliders)
    if isinstance(item, Slider):
        inVec[indexBySlider[item]] = value
        return inVec
    elif isinstance(item, Combo):
        for pair in item.pairs:
            inVec[indexBySlider[pair.slider]] = pair.value * abs(value)
        return inVec
    else:
        raise ValueError(
            "Not a slider or combo. Got type {0}: {1}".format(type(item), item)
        )


def buildFullShapes(simplex, shapeObjs, shapes, solver, pBar=None):
    """Given shape inputs, build the full output shape from the deltas
        We use shapes here because a shape implies both the progression
        and the value of the inputs (with a little figuring)

    Parameters
    ----------
    simplex : Simplex
        A Simplex system
    shapeObjs : [Shape, ...]
        The Simplex system Shape objects
    shapes : np.array
        A numpy array of the shapes
    solver : PySimplex
        An instantiated simplex solver
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------
    : {Shape: np.array, ...}
        A dictionary of point positions indexed by the shape
    : {Shape: [float, ...], ...}
        A dictionary of solver inputs indexed by the shape
    """
    ###########################################
    # Manipulate all the input lists and caches
    indexBySlider = {s: i for i, s in enumerate(simplex.sliders)}
    indexByShape = {s: i for i, s in enumerate(simplex.shapes)}
    floaters = set(simplex.getFloatingShapes())
    floatIdxs = set([indexByShape[s] for s in floaters])

    shapeDict = {}
    for item in itertools.chain(simplex.sliders, simplex.combos):
        for pair in item.prog.pairs:
            if not pair.shape.isRest:
                shapeDict[pair.shape] = (item, pair.value)

    ######################
    # Actually do the work
    vecByShape = {}  # store this for later use
    ptsByShape = {}

    if pBar is not None:
        pBar.setMaximum(len(shapeObjs))
        pBar.setValue(0)
        QApplication.processEvents()

    flatShapes = shapes.reshape((len(shapes), -1))
    for i, shape in enumerate(shapeObjs):
        if pBar is not None:
            pBar.setValue(i)
            QApplication.processEvents()
        else:
            print("Building {0} of {1}\r".format(i + 1, len(shapeObjs)), end=" ")

        item, value = shapeDict[shape]
        inVec = _buildSolverInputs(simplex, item, value, indexBySlider)
        outVec = solver.solve(inVec)
        if shape not in floaters:
            for fi in floatIdxs:
                outVec[fi] = 0.0
        outVec = np.array(outVec)
        outVec[np.where(np.isclose(outVec, 0))] = 0
        outVec[np.where(np.isclose(outVec, 1))] = 1
        vecByShape[shape] = outVec
        pts = np.dot(outVec, flatShapes)
        pts = pts.reshape((-1, 3))
        ptsByShape[shape] = pts
    if pBar is None:
        print()

    return ptsByShape, vecByShape


def collapseFullShapes(simplex, allPts, ptsByShape, vecByShape, pBar=None):
    """Given a set of shapes that are full-on shapes (not just deltas)
        Collapse them back into deltas in the simplex shape list

    Parameters
    ----------
    simplex : Simplex
        A simplex system
    allPts : np.array
        All the point positions
    ptsByShape : {Shape: np.array, ...}
        A dictionary of point positions indexed by the shape
    vecByShape : {Shape: [float, ...], ...}
        A dictionary of solver inputs indexed by the shape
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------
    : np.array
        The collapsed shapes

    """
    # Figure out what order to build the deltas
    # so that the deltas exist when I try to combine them
    ctrlOrder = simplex.controllersByDepth()
    shapeOrder = [pp.shape for ctrl in ctrlOrder for pp in ctrl.prog.pairs]
    shapeOrder = [i for i in shapeOrder if not i.isRest]

    # Incrementally Build the numpy array of delta shapes
    # build deltaShapeArray as a 2d array because numpy is like 10x faster on 2d arrays
    indexByShape = {v: k for k, v in enumerate(simplex.shapes)}
    deltaShapeArray = np.zeros((len(simplex.shapes), allPts.shape[1] * 3))

    if pBar is not None:
        pBar.setValue(0)
        pBar.setMaximum(len(shapeOrder))
        pBar.setLabelText("Building Corrected Deltas")
        QApplication.processEvents()

    for shpOrderIdx, shape in enumerate(shapeOrder):

        if pBar is not None:
            pBar.setValue(shpOrderIdx)
            pBar.setLabelText("Building Corrected Deltas\n{}".format(shape.name))
            QApplication.processEvents()
        else:
            print(
                "Collapsing {0} of {1}\r".format(shpOrderIdx + 1, len(shapeOrder)),
                end=" ",
            )

        shpIdx = indexByShape[shape]
        if shape in ptsByShape:
            base = np.dot(vecByShape[shape], deltaShapeArray)
            deltaShapeArray[shpIdx] = (
                ptsByShape[shape] - base.reshape((-1, 3))
            ).flatten()
        else:
            deltaShapeArray[shpIdx] = allPts[shpIdx].flatten()

    return deltaShapeArray.reshape((len(deltaShapeArray), -1, 3))


def applyCorrectives(
    simplex, allShapePts, restPts, solver, shapes, refIdxs, references, pBar=None
):
    """Loop over the shapes and references, apply them, and return a new np.array
        of shape points

    Parameters
    ----------
    simplex : Simplex
        Simplex system
    allShapePts : np.array
        deltas per shape
    restPts : np.array
        The rest point positions
    solver : PySimplex
        The Python Simplex solver object
    shapes : [Shape, ...]
        The simplex shape objects we care about
    refIdxs : [int, ...]
        The reference index per shape
    references : np.array
        A list of matrix-per-points
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------
    : np.array
        The new shape points with correctives applied

    """
    # The rule of thumb is "THE SHAPE IS ALWAYS A DELTA"

    if pBar is not None:
        pBar.setLabelText("Inverting References")
        pBar.setValue(0)
        pBar.setMaximum(len(references))
        QApplication.processEvents()
    else:
        print("Inverting References")

    # The initial reference is the rig rest shape
    # This way we can handle a difference between
    # The .smpx rest shape, and the rig rest shape

    # shape 0, all points, the tranform row of the matrix, the first 3 values in that row
    rigRest = references[0, :, 3, :3]
    restDelta = rigRest - restPts

    inverses = []
    for i, r in enumerate(references):
        if pBar is not None:
            pBar.setValue(i)
            QApplication.processEvents()
        inverses.append(invertAll(r))

    if pBar is not None:
        pBar.setLabelText("Building Full Shapes")
        QApplication.processEvents()
    else:
        print("Building Full Shapes")
    ptsByShape, vecByShape = buildFullShapes(simplex, shapes, allShapePts, solver, pBar)

    if pBar is not None:
        pBar.setLabelText("Correcting Shapes")
        pBar.setValue(0)
        pBar.setMaximum(len(shapes))
    newPtsByShape = {}
    for i, (shape, refIdx) in enumerate(zip(shapes, refIdxs)):
        if pBar is not None:
            pBar.setValue(i)
            QApplication.processEvents()
        else:
            print("Correcting {0} of {1}: {2}".format(i + 1, len(shapes), shape.name))

        inv = inverses[refIdx]
        pts = ptsByShape[shape]
        newPts = applyReference(pts, restPts, restDelta, inv)
        newPtsByShape[shape] = newPts

    newShapePts = collapseFullShapes(
        simplex, allShapePts, newPtsByShape, vecByShape, pBar
    )
    newShapePts = newShapePts + restPts[None, ...]

    return newShapePts


def readAndApplyCorrectives(inPath, namePath, refPath, outPath, pBar=None):
    """Read the provided files, apply the correctives, then output a new file

    Parameters
    ----------
    inPath : str
        The input path
    namePath : str
        A file correlating the shape names and indices
    refPath : str
        The reference matrices per point of deformation
    outPath : str
        The output path
    pBar : QProgressDialog, optional
        An optional progress dialog
    """

    if pBar is not None:
        pBar.setLabelText("Reading reference data")
        QApplication.processEvents()

    jsString, simplex, solver, allShapePts, restPts = loadSimplex(inPath)
    with open(namePath, "r") as f:
        nr = f.read()
    nr = [i.split(";") for i in nr.split("\n") if i]
    nr = nr[1:]  # ignore the rest shape for this stuff
    names, refIdxs = list(zip(*nr))
    refIdxs = list(map(int, refIdxs))
    refs = np.load(refPath, allow_pickle=True)
    shapeByName = {i.name: i for i in simplex.shapes}
    shapes = [shapeByName[n] for n in names]
    newPts = applyCorrectives(
        simplex, allShapePts, restPts, solver, shapes, refIdxs, refs, pBar
    )
    writeSimplex(inPath, outPath, newPts, pBar=pBar)
    print("DONE")
