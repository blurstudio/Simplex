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

""" Get the corrective deltas from a rig in XSI """

from __future__ import absolute_import

from dcc.xsi import constants, xsi
from dcc.xsi.ice import ICETree  # pylint:disable=import-error
from six.moves import zip


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
        xsi.setValue(prop, val * multiplier)


def resetPose(pvp):
    """Reset everything back to rest

    Parameters
    ----------
    pvp : [(str, float), ...]
        A list of property/value pairs
    """
    for prop, val in pvp:
        xsi.setValue(prop, 0)


def getMeshVerts(mesh):
    """Get the verts of the given mesh object

    Parameters
    ----------
    mesh : XSIObject
        A native xsi mesh object

    Returns
    -------
    : [vert, ...]
        A list of vertices
    """
    vts = mesh.ActivePrimitive.Geometry.Points.PositionArray
    return list(zip(*vts))


def buildTree(mesh):
    """Build the ICE tree that allows for this procedure

    Parameters
    ----------
    mesh : XSIObject
        A native xsi mesh object

    Returns
    -------
    : XSIObject
        The ICE Tree object
    : XSIObject
        The vector node in the ICE Tree
    """
    iceTree = ICETree(None, mesh, "Test", constants.siConstructionModePrimaryShape)

    getter = iceTree.addGetDataNode("Self.PointPosition")
    adder = iceTree.addNode("Add")
    vector = iceTree.addNode("ScalarTo3DVector")
    setter = iceTree.addSetDataNode("Self.PointPosition")

    getter.value.connect(adder.value1)
    vector.vector.connect(adder.value2)
    adder.result.connect(setter.Value)
    iceTree.connect(setter.Execute, 2)

    return iceTree, vector


def getShiftValues(mesh):
    """Shift the vertices along each axis *before* the skinning
    op in the deformer history

    Parameters
    ----------
    mesh : XSIObject
        A native xsi mesh object

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
    tree, vector = buildTree(mesh)
    zero = getMeshVerts(mesh)

    vector.x.value = 1.0
    oneX = getMeshVerts(mesh)
    vector.x.value = 0.0

    vector.y.value = 1.0
    oneY = getMeshVerts(mesh)
    vector.y.value = 0.0

    vector.z.value = 1.0
    oneZ = getMeshVerts(mesh)
    vector.z.value = 0.0

    tree.delete()
    return zero, oneX, oneY, oneZ
