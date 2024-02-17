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

""" Get the corrective deltas from a rig in Maya """

from __future__ import absolute_import

from ctypes import c_float

from maya import OpenMaya as om
from maya import cmds
from six.moves import range

try:
    import numpy as np
except ImportError:
    pass


def setPose(pvp, multiplier):
    """Set a percentage of a pose

    Parameters
    ----------
    pvp : [(str, float), ...]
        A list of property/value pairs
    multiplier : float
        The percentage multiplier of the pose
    """
    for prop, val in pvp:
        cmds.setAttr(prop, val * multiplier)


def resetPose(pvp):
    """Reset everything back to rest

    Parameters
    ----------
    pvp : [(str, float), ...]
        A list of property/value pairs
    """
    for prop, val in pvp:
        cmds.setAttr(prop, 0)


def _getDagPath(mesh):
    sl = om.MSelectionList()
    sl.add(mesh)
    dagPath = om.MDagPath()
    sl.getDagPath(0, dagPath)
    return dagPath


def _getMayaPoints(meshFn):
    rawPts = meshFn.getRawPoints()
    ptCount = meshFn.numVertices()
    cta = (c_float * 3 * ptCount).from_address(int(rawPts))
    out = np.ctypeslib.as_array(cta)
    out = np.copy(out)
    out = out.reshape((-1, 3))
    return out


def getDeformerChain(chkObj):
    # Follow the deformer chain
    memo = []
    while chkObj and chkObj not in memo:
        memo.append(chkObj)

        typ = cmds.nodeType(chkObj)
        if typ == "mesh":
            cnx = cmds.listConnections(
                chkObj + ".inMesh", destination=False, shapes=True
            ) or [None]
            chkObj = cnx[0]
        elif typ == "groupParts":
            cnx = cmds.listConnections(
                chkObj + ".inputGeometry", destination=False, shapes=True
            ) or [None]
            chkObj = cnx[0]
        elif typ == "polySoftEdge":
            cnx = cmds.listConnections(
                chkObj + ".inputPolymesh", destination=False, shapes=True
            ) or [None]
            chkObj = cnx[0]
        elif typ == "AlembicNode":
            # Alembic nodes aren't part of the deformer chain
            # Cut it off, and return
            return memo[:-1]
        else:
            cnx = cmds.ls(chkObj, type="geometryFilter") or [None]
            chkObj = cnx[0]
            if chkObj:  # we have a deformer
                # Get the mesh index of this deformer
                cnx = cmds.listConnections(
                    chkObj, connections=True, plugs=True, source=False
                )
                prev = cmds.ls(memo[-2])[0]  # Get the minimal unique name for testing
                defIdx = 0
                for i in range(0, len(cnx), 2):
                    if cnx[i + 1].startswith(prev):
                        defIdx = int(cnx[i].split("[")[-1][:-1])
                        break
                # Use that mesh index to get the output
                cnx = cmds.listConnections(
                    chkObj + ".input[{0}].inputGeometry".format(defIdx),
                    destination=False,
                    shapes=True,
                ) or [None]
                chkObj = cnx[0]

    return memo


def getShiftValues(thing):
    """Shift the vertices along each axis *before* the skinning
    op in the deformer history

    Parameters
    ----------
    mesh : str
        The name of a mesh

    Returns
    -------
    : [vert, ...]
        A list of un-shifted vertices
    : [vert, ...]
        A list of vertices pre-shifted by 1 along the X axis
    : [vert, ...]
        A list of vertices pre-shifted by 1 along the Y axis
    : [vert, ...]
        A list of vertices pre-shifted by 1 along the Z axis
    """
    orig = getDeformerChain(thing)[-1]

    dp = _getDagPath(thing)
    meshFn = om.MFnMesh(dp)
    allVerts = "{0}.vtx[*]".format(orig)

    zero = _getMayaPoints(meshFn)
    cmds.move(1, 0, 0, allVerts, relative=1, objectSpace=1)
    oneX = _getMayaPoints(meshFn)
    cmds.move(-1, 1, 0, allVerts, relative=1, objectSpace=1)
    oneY = _getMayaPoints(meshFn)
    cmds.move(0, -1, 1, allVerts, relative=1, objectSpace=1)
    oneZ = _getMayaPoints(meshFn)
    cmds.move(0, 0, -1, allVerts, relative=1, objectSpace=1)

    return zero, oneX, oneY, oneZ
