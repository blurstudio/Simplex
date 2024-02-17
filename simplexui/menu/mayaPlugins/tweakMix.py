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
import six
from six.moves import range, zip

from ...interface.mayaInterface import disconnected
from ...interfaceModel import coerceIndexToType
from ...items import Combo
from ...Qt.QtWidgets import QAction


def registerTool(window, menu):
    tweakMixACT = QAction("Tweak Mix", window)
    menu.addAction(tweakMixACT)
    tweakMixACT.triggered.connect(partial(tweakMixInterface, window))


def tweakMixInterface(window):
    if not window.simplex:
        return
    live = window.uiLiveShapeConnectionACT.isChecked()

    indexes = window.uiComboTREE.selectedIndexes()
    indexes = coerceIndexToType(indexes, Combo)
    if not indexes:
        return
    combos = [idx.model().itemFromIndex(idx) for idx in indexes]
    combos = list(set(combos))
    tweakMix(window.simplex, combos, live)


def registerContext(tree, clickIdx, indexes, menu):
    window = tree.window()
    live = window.uiLiveShapeConnectionACT.isChecked()
    indexes = coerceIndexToType(indexes, Combo)
    if indexes:
        indexes = list(set(indexes))
        tweakMixACT = menu.addAction("Tweak Mix")
        tweakMixACT.triggered.connect(partial(tweakMixContext, window, indexes, live))
        return True
    return False


def tweakMixContext(window, indexes, live):
    combos = [idx.model().itemFromIndex(idx) for idx in indexes]
    combos = list(set(combos))
    tweakMix(window.simplex, combos, live)


def tweakMix(simplex, combos, live):
    # first extract the rest shape non-live
    restGeo = simplex.extractRestShape()

    floatShapes = simplex.getFloatingShapes()
    floatShapes = [i.thing for i in floatShapes]

    offset = 5
    for combo in combos:
        offset += 5

        shape = None
        for pp in combo.prog.pairs:
            if pp.value == 1.0:
                shape = pp.shape
                break
        else:
            continue

        geo = combo.extractShape(shape, live=live, offset=offset)
        # disconnect the controller from the operator
        tweakShapes = []
        with disconnected(simplex.DCC.op) as sliderCnx:
            # disconnect any float shapes
            with disconnected(floatShapes):
                cnx = sliderCnx[simplex.DCC.op]
                for a in six.itervalues(cnx):
                    cmds.setAttr(a, 0.0)

                # set the combo values
                for pair in combo.pairs:
                    cmds.setAttr(cnx[pair.slider.thing], pair.value)

                for shape in simplex.shapes[1:]:  # skip the restShape
                    shapeVal = cmds.getAttr(shape.thing)
                    if shapeVal != 0.0:  # maybe handle floating point errors
                        tweakShapes.append((shape, shapeVal))

        tweakMeshes = []
        with disconnected(simplex.DCC.shapeNode) as shapeCnx:
            cnx = shapeCnx[simplex.DCC.shapeNode]
            for a in six.itervalues(cnx):
                cmds.setAttr(a, 0.0)
            for tshape, shapeVal in tweakShapes:
                cmds.setAttr(tshape.thing, shapeVal)
                # print "setAttr", tshape.thing, shapeVal
                tweakMesh = cmds.duplicate(
                    simplex.DCC.mesh, name="{0}_Tweak".format(tshape.name)
                )[0]
                tweakMeshes.append(tweakMesh)
                cmds.setAttr(tshape.thing, 0.0)

        # Yeah, yeah, this is REALLY ugly, but it's quick and it works
        tempBS = cmds.blendShape(geo, name="Temp_BS")
        cmds.blendShape(tempBS, edit=True, target=(geo, 0, restGeo, 1.0))
        cmds.blendShape(tempBS, edit=True, weight=[(0, 1.0)])
        cmds.delete(geo, constructionHistory=True)

        # build the actual blendshape
        tweakBS = cmds.blendShape(geo, name="Tweak_BS")
        for i, tm in enumerate(tweakMeshes):
            cmds.blendShape(tweakBS, edit=True, target=(geo, i, tm, 1.0))
        tmLen = len(tweakMeshes)
        cmds.blendShape(
            tweakBS, edit=True, weight=list(zip(list(range(tmLen)), [1.0] * tmLen))
        )

        cmds.delete(tweakMeshes)
    cmds.delete(restGeo)
