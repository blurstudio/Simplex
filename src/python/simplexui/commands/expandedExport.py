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

from __future__ import absolute_import

import six
from pysimplex import PySimplex

from ..interface.mayaInterface import DCC, disconnected
from ..items import Combo, Slider, Traversal
from .alembicCommon import buildSmpx

try:
    import numpy as np
except ImportError:
    pass


def _setSliders(ctrl, val, svs):
    slis, vals = svs.setdefault(ctrl.simplex, ([], []))

    if isinstance(ctrl, Slider):
        slis.append(ctrl)
        vals.append(val)
    elif isinstance(ctrl, Combo):
        for cp in ctrl.pairs:
            slis.append(cp.slider)
            vals.append(cp.value * abs(val))
    elif isinstance(ctrl, Traversal):
        # set the ctrl.multiplierCtrl.controller to 1
        multCtrl = ctrl.multiplierCtrl.controller
        multVal = ctrl.multiplierCtrl.value if val != 0.0 else 0.0
        progCtrl = ctrl.progressCtrl.controller
        _setSliders(multCtrl, multVal, svs)
        _setSliders(progCtrl, val, svs)


def setSliderGroup(ctrls, val):
    """Set a group of controls to a given value

    Parameters
    ----------
    ctrls : [object, ...]
        A list of simplex objects
    val : float
        The value to set

    Returns
    -------

    """
    svs = {}
    for ctrl in ctrls:
        _setSliders(ctrl, val, svs)

    for smpx, (slis, vals) in six.iteritems(svs):
        smpx.setSlidersWeights(slis, vals)


def clientPartition(master, clients):
    """

    Parameters
    ----------
    master : Simplex
        The master simplex system
    clients : [Simplex, ...]
        The client simplex systems

    Returns
    -------
    : {str: [Slider, ...]}
        Dictionary of name to slider
    : {str: [Combo, ...]}
        Dictionary of name to combo
    : {str: [Traversal, ...]}
        Dictionary of name to traversal

    """
    sliders, combos, traversals = {}, {}, {}
    for cli in [master] + clients:
        for sli in cli.sliders:
            sliders.setdefault(sli.name, []).append(sli)

        for com in cli.combos:
            combos.setdefault(com.name, []).append(com)

        for trav in cli.traversals:
            traversals.setdefault(trav.name, []).append(trav)
    return sliders, combos, traversals


def zeroAll(smpxs):
    """Set all sliders on the given simplex systems to 0

    Parameters
    ----------
    smpxs : [Simplex, ...]
        A list of Simplex systems

    Returns
    -------

    """
    for smpx in smpxs:
        smpx.setSlidersWeights(smpx.sliders, [0.0] * len(smpx.sliders))


def getExpandedData(master, clients, mesh):
    """Get the fully expanded shape data for each slider, combo, and traversal
        at each of its underlying shapes

    Parameters
    ----------
    master : Simplex
        The master simplex system
    clients : [Simplex, ...]
        The client simplex systems
    mesh : str
        The name of the maya shape node

    Returns
    -------
    : np.array
        The rest shape point positions
    : np.array
        The slider shape point positions
    : np.array
        The combo shape point positions
    : np.array
        The traversal shape point positions

    """
    # zero everything
    zeroAll([master] + clients)
    sliPart, cmbPart, travPart = clientPartition(master, clients)
    sliderShapes = {}
    for slider in master.sliders:
        ss = {}
        sliderShapes[slider] = ss
        for pp in slider.prog.pairs:
            if pp.shape.isRest:
                continue
            setSliderGroup(sliPart[slider.name], pp.value)
            ss[pp] = DCC.getNumpyShape(mesh)
            setSliderGroup(sliPart[slider.name], 0.0)

    # Disable traversals
    zeroAll([master] + clients)
    travShapeThings = []
    comboShapes = {}
    for trav in master.traversals:
        for pp in trav.prog.pairs:
            if pp.shape.isRest:
                continue
            travShapeThings.append(pp.shape)
    travShapeThings = [i.thing for i in travShapeThings]

    # Get the combos with traversals disconnected
    with disconnected(travShapeThings):
        for combo in master.combos:
            ss = {}
            comboShapes[combo] = ss
            for pp in combo.prog.pairs:
                if pp.shape.isRest:
                    continue
                setSliderGroup(cmbPart[combo.name], pp.value)
                ss[pp] = DCC.getNumpyShape(mesh)
                setSliderGroup(cmbPart[combo.name], 0.0)

    zeroAll([master] + clients)
    travShapes = {}
    for trav in master.traversals:
        ss = {}
        travShapes[trav] = ss
        progCtrl = trav.progressCtrl.controller
        progVal = trav.progressCtrl.value
        for pp in progCtrl.prog.pairs:
            if pp.shape.isRest:
                continue
            if pp.value * progVal <= 0.0:
                # Traversals only activate if the progression is in the same
                # pos/neg direction as the value. Otherwise we just skip
                continue

            setSliderGroup(travPart[trav.name], pp.value)
            ss[pp] = DCC.getNumpyShape(mesh)
            setSliderGroup(travPart[trav.name], 0.0)

    zeroAll([master] + clients)
    restShape = DCC.getNumpyShape(mesh)

    return restShape, sliderShapes, comboShapes, travShapes


def _setInputs(inVec, item, indexBySlider, value):
    """Being clever
    Sliders or Combos just set the value and return
    Traversals recursively call this function with the controllers (that only either sliders or combos)
    """
    if isinstance(item, Slider):
        inVec[indexBySlider[item]] = value
        return inVec
    elif isinstance(item, Combo):
        for pair in item.pairs:
            inVec[indexBySlider[pair.slider]] = pair.value * abs(value)
        return inVec
    elif isinstance(item, Traversal):
        inVec = _setInputs(
            inVec,
            item.multiplierCtrl.controller,
            indexBySlider,
            item.multiplierCtrl.value,
        )
        inVec = _setInputs(
            inVec,
            item.progressCtrl.controller,
            indexBySlider,
            item.progressCtrl.value * value,
        )
        return inVec
    raise ValueError(
        "Not a Slider, Combo, or Traversal. Got type {0}: {1}".format(type(item), item)
    )


def _buildSolverInputs(simplex, item, value, indexBySlider):
    """Build an input vector for the solver that will
    produce a required progression value on an item
    """
    inVec = [0.0] * len(simplex.sliders)
    return _setInputs(inVec, item, indexBySlider, value)


def getTravDepth(trav):
    """Get the depth of a traversal object

    Parameters
    ----------
    trav : Traversal
        The traversal object

    Returns
    -------
    : int
        The depth of the given Traversal

    """
    inputs = []
    mult = trav.multiplierCtrl.controller
    prog = trav.progressCtrl.controller
    for item in (mult, prog):
        if isinstance(item, Slider):
            inputs.append(item)
        elif isinstance(item, Combo):
            for cp in item.pairs:
                inputs.append(cp.slider)
    return len(set(inputs))


def parseExpandedData(smpx, restShape, sliderShapes, comboShapes, travShapes):
    """Turn the expanded data into shapeDeltas connected to the actual Shape objects

    Parameters
    ----------
    smpx : Simplex
        A simplex system
    restShape : np.array
        The rest point positions
    sliderShapes : np.array
        The slider shape point positions
    comboShapes : np.array
        The combo shape point positions
    travShapes : np.array
        The traversal shape point positions

    Returns
    -------
    : np.array
        The point positions for a new set of shapes

    """
    solver = PySimplex(smpx.dump())
    shapeArray = np.zeros((len(smpx.shapes), len(restShape), 3))

    indexBySlider = {s: i for i, s in enumerate(smpx.sliders)}
    indexByShape = {s: i for i, s in enumerate(smpx.shapes)}

    floatShapeSet = set(smpx.getFloatingShapes())
    floatIdxs = sorted(set([indexByShape[s] for s in floatShapeSet]))
    travShapeSet = set([pp.shape for t in smpx.traversals for pp in t.prog.pairs])
    travIdxs = sorted(set([indexByShape[s] for s in travShapeSet]))

    # Sliders are simple, just set their shapes directly
    for ppDict in six.itervalues(sliderShapes):
        for pp, shp in six.iteritems(ppDict):
            shapeArray[indexByShape[pp.shape]] = shp - restShape

    # First sort the combos by depth
    comboByDepth = {}
    for combo in smpx.combos:
        comboByDepth.setdefault(len(combo.pairs), []).append(combo)

    for depth in sorted(comboByDepth.keys()):
        for combo in comboByDepth[depth]:
            for pp, shp in six.iteritems(comboShapes[combo]):
                inVec = _buildSolverInputs(smpx, combo, pp.value, indexBySlider)
                outVec = np.array(solver.solve(inVec))
                outVec[np.where(np.isclose(outVec, 0.0))] = 0.0
                outVec[np.where(np.isclose(outVec, 1.0))] = 1.0
                outVec[indexByShape[pp.shape]] = 0.0

                # ignore any traversals
                outVec[travIdxs] = 0.0

                # ignore floaters if we're not currently checking floaters
                if pp.shape not in floatShapeSet:
                    outVec[floatIdxs] = 0.0

                # set the shape delta to the output
                baseShape = np.dot(outVec, shapeArray.swapaxes(0, 1))
                shapeArray[indexByShape[pp.shape]] = shp - restShape - baseShape

    # First the traversals by depth
    travByDepth = {}
    for trav in smpx.traversals:
        travByDepth.setdefault(getTravDepth(trav), []).append(trav)

    for depth in sorted(travByDepth.keys()):
        for trav in travByDepth[depth]:
            for pp, shp in six.iteritems(travShapes[trav]):
                inVec = _buildSolverInputs(smpx, trav, pp.value, indexBySlider)
                outVec = np.array(solver.solve(inVec))
                outVec[np.where(np.isclose(outVec, 0.0))] = 0.0
                outVec[np.where(np.isclose(outVec, 1.0))] = 1.0
                outVec[indexByShape[pp.shape]] = 0.0

                # set the shape delta to the output
                baseShape = np.dot(outVec, shapeArray.swapaxes(0, 1))
                shapeArray[indexByShape[pp.shape]] = shp - restShape - baseShape
    return shapeArray


def buildShapeArray(mesh, master, clients):
    """Build the outpu shape array

    Parameters
    ----------
    mesh : str
        The maya shape node name
    master : Simplex
        The master simplex system
    clients :
        The client simplex systems

    Returns
    -------
    : np.array
        The full output shape array

    """
    restShape, sliderShapes, comboShapes, travShapes = getExpandedData(
        master, clients, mesh
    )
    shapeArray = parseExpandedData(
        master, restShape, sliderShapes, comboShapes, travShapes
    )
    shapeArray += restShape[None, ...]
    return shapeArray


def expandedExportAbc(path, mesh, master, clients=()):
    """Export the alembic by re-building the deltas from all of the full shapes
        This is required for delta-mushing a system, because the sum of mushed shapes
        is not the same as the mushed sum-of-shapes

    Parameters
    ----------
    path : str
        Output path for the .smpx
    mesh : str
        The maya shape node name
    master : Simplex
        The master simplex system
    clients : [Simplex, ...]
        The client simplex systems

    Returns
    -------

    """
    # Convert clients to a list if need be
    if not clients:
        clients = []
    elif not isinstance(clients, list):
        if isinstance(clients, tuple):
            clients = list(clients)
        else:
            clients = [clients]

    faces, counts, uvs = DCC.getAbcFaces(mesh)
    shapeArray = buildShapeArray(mesh, master, clients)
    jsString = str(master.dump())

    buildSmpx(
        path,
        shapeArray,
        faces,
        jsString,
        master.name,
        faceCounts=counts,
        uvs=uvs,
    )


if __name__ == "__main__":
    # get the smpx from the UI
    master = Simplex.buildSystemFromMesh("Face_SIMPLEX", "Face")
    client = Simplex.buildSystemFromMesh("Face_SIMPLEX2", "Face2")
    outPath = r"D:\Users\tyler\Desktop\TEST\expanded.smpx"
    expandedExportAbc(outPath, "Face_SIMPLEX", master, client)
