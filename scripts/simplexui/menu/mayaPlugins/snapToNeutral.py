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

from functools import partial

import maya.cmds as cmds

from ...Qt.QtWidgets import QAction


def registerTool(window, menu):
    snapShapeToNeutralACT = QAction("Snap Shape To Neutral", window)
    menu.addAction(snapShapeToNeutralACT)
    snapShapeToNeutralACT.triggered.connect(
        partial(snapShapeToNeutralInterface, window)
    )


def snapShapeToNeutralInterface(window):
    sel = cmds.ls(sl=True)
    if len(sel) >= 2:
        snapShapeToNeutral(sel[0], sel[1])
    elif len(sel) == 1:
        rest = window.simplex.extractRestShape()
        snapShapeToNeutral(sel[0], rest)
        cmds.delete(rest)


def snapShapeToNeutral(source, target):
    """
    Take a mesh, and find the closest location on the target head, and snap to that
    Then set up a blendShape so the artist can "paint" in the snapping behavior
    """
    # Make a duplicate of the source and snap it to the target
    snapShape = cmds.duplicate(source, name="snp")
    cmds.transferAttributes(
        target,
        snapShape,
        transferPositions=1,
        sampleSpace=1,  # 0=World, 1=Local, 3=UV
        searchMethod=0,  # 0=Along Normal, 1=Closest Location
    )

    # Then delete history
    cmds.delete(snapShape, constructionHistory=True)
    cmds.hide(snapShape)

    # Blend the source to the snappedShape
    bs = cmds.blendShape(snapShape, source)[0]
    cmds.blendShape(bs, edit=True, weight=((0, 1)))

    # But set the weights back to 0.0 for painting
    numVerts = cmds.polyEvaluate(source, vertex=1)
    setter = "{0}.inputTarget[0].inputTargetGroup[0].targetWeights[0:{1}]".format(
        bs, numVerts - 1
    )
    weights = [0.0] * numVerts
    cmds.setAttr(setter, *weights, size=numVerts)
