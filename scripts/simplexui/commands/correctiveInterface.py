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
from six.moves import zip

from ..Qt.QtWidgets import QApplication

try:
    import numpy as np
except ImportError:
    pass

try:
    from .mayaCorrectiveInterface import getShiftValues, resetPose, setPose

    dcc = "maya"
except ImportError:
    from .xsiCorrectiveInterface import getShiftValues, resetPose, setPose

    dcc = "xsi"


def getRefForPoses(mesh, poses, multipliers):
    """Given a set of poses and a multiplier, get the reference

    Parameters
    ----------
    mesh : object
        The DCC object
    poses : [[(str, float), ...], ...]
        Property/value pairs for different rig poses
    multiplier : float
        The percent of the pose to apply

    Returns
    -------
    : np.array
        The point reference matrices in pose

    """

    for pose, mul in zip(poses, multipliers):
        setPose(pose, mul)

    ref = getDeformReference(mesh)

    for pose in poses:
        resetPose(pose)
    return ref


def getDeformReference(mesh):
    """Build the 4x4 deformation reference matrices given a mesh

    Parameters
    ----------
    mesh : object
        The DCC mesh object

    Returns
    -------
    : np.array:
        The point reference matrices in pose

    """
    zero, oneX, oneY, oneZ = getShiftValues(mesh)

    zero = np.array(zero)
    dx = np.array(oneX) - zero
    dy = np.array(oneY) - zero
    dz = np.array(oneZ) - zero

    # Maya has numpy 1.09, but np.stack comes from 1.10
    # mats = np.stack((dx, dy, dz, zero), axis=1)

    # Make the new axis to concatenate on
    zero = zero[:, None]
    dx = dx[:, None]
    dy = dy[:, None]
    dz = dz[:, None]
    mats = np.concatenate((dx, dy, dz, zero), axis=1)

    # Turn the Nx4x3 matrix into a Nx4x4
    zzz = np.zeros((len(mats), 4, 1))
    zzz[:, 3] = 1.0
    mats = np.concatenate((mats, zzz), axis=2)

    return mats


def buildCorrectiveReferences(mesh, simplex, poses, sliders, pBar=None):
    """Take correlated poses and sliders, and expand down the
        simplex combo tree, building references for each required shape

    Parameters
    ----------
    mesh : object
        The DCC mesh object
    simplex : Simplex
        The Simplex system
    poses : [[(str, float), ...], ...]
        Property/value pairs for different rig poses
    sliders : [Slider, ...]
        Simplex slider objects that are controlled by the poses
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------
    : np.array
        The output matrix-per-point arrays
    : [Shape, ...]
        The shapes active
    : [int, ...]
        The Reference pose per shape
    """
    # cache the pose search

    # Pre-cache the combo search
    allCombosBySliderValue = {}
    for c in simplex.combos:
        for p in c.pairs:
            allCombosBySliderValue.setdefault((p.slider, p.value), []).append(c)

    # This is only my subset set of downstreams
    # Get the downstreams by slider and value
    sliderValuesByCombo = {}
    for slider in sliders:
        for p in slider.prog.pairs:
            combos = allCombosBySliderValue.get((slider, p.value), [])
            for combo in combos:
                sliderValuesByCombo.setdefault(combo, []).append((slider, p.value))

    # out = []
    refCache = {}
    refs, shapes, refIdxs = [], [], []

    # get the slider outputs
    if pBar is not None:
        pBar.setLabelText("Building Shape References")
        pBar.setValue(0)
        mv = 0
        for slider in sliders:
            for p in slider.prog.pairs:
                if not p.shape.isRest:
                    mv += 1
        pBar.setMaximum(mv)
        QApplication.processEvents()

    # Make sure to export the rest reference first
    ref = getRefForPoses(mesh, [], [])
    refIdxs.append(len(refs))
    cacheKey = frozenset([("", 0.0)])
    refCache[cacheKey] = len(refs)
    refs.append(ref)
    shapes.append(simplex.restShape)

    # Now export everything else
    poseBySlider = {}
    for slider, pose in zip(sliders, poses):
        poseBySlider[slider] = pose
        for p in slider.prog.pairs:
            if not p.shape.isRest:
                if pBar is not None:
                    pBar.setValue(pBar.value())
                    QApplication.processEvents()
                cacheKey = frozenset([(slider, p.value)])
                if cacheKey in refCache:
                    idx = refCache[cacheKey]
                    refIdxs.append(idx)
                else:
                    ref = getRefForPoses(mesh, [pose], [p.value])
                    refIdxs.append(len(refs))
                    refCache[cacheKey] = len(refs)
                    refs.append(ref)
                shapes.append(p.shape)

    # Get the combo outputs
    if pBar is not None:
        pBar.setLabelText("Building Combo References")
        pBar.setValue(0)
        mv = 0
        for combo in six.iterkeys(sliderValuesByCombo):
            for p in combo.prog.pairs:
                if not p.shape.isRest:
                    mv += 1
        pBar.setMaximum(mv)
        QApplication.processEvents()

    for combo, sliderVals in six.iteritems(sliderValuesByCombo):
        # components = frozenset(sliderVals)
        poses = [poseBySlider[s] for s, _ in sliderVals]
        for p in combo.prog.pairs:
            if not p.shape.isRest:
                if pBar is not None:
                    pBar.setValue(pBar.value())
                    QApplication.processEvents()

                cacheKey = frozenset(sliderVals)
                if cacheKey in refCache:
                    idx = refCache[cacheKey]
                    refIdxs.append(idx)
                else:
                    vals = [p.value * v[1] for v in sliderVals]
                    ref = getRefForPoses(mesh, poses, vals)
                    refIdxs.append(len(refs))
                    refCache[cacheKey] = len(refs)
                    refs.append(ref)
                shapes.append(p.shape)

    return np.array(refs), shapes, refIdxs


def outputCorrectiveReferences(
    outNames, outRefs, simplex, mesh, poses, sliders, pBar=None
):
    """Output the proper files for an external corrective application

    Parameters
    ----------
    outNames : str
        The filepath for the output shape and reference indices
    outRefs : str
        The filepath for the deformation references
    simplex : Simplex
        A simplex system
    mesh : object
        The mesh object to deform
    poses : [[(str, float), ...], ...]
        Lists of parameter
    sliders : [Slider, ...]
        The simplex sliders that correspond to the poses
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------

    """
    refs, shapes, refIdxs = buildCorrectiveReferences(
        mesh, simplex, poses, sliders, pBar
    )

    if pBar is not None:
        pBar.setLabelText("Writing Names")
        QApplication.processEvents()
    nameWrite = ["{};{}".format(s.name, r) for s, r, in zip(shapes, refIdxs)]
    with open(outNames, "w") as f:
        f.write("\n".join(nameWrite))

    if pBar is not None:
        pBar.setLabelText("Writing References")
        QApplication.processEvents()
    refs.dump(outRefs)
