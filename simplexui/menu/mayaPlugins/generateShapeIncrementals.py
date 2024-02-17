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
from six.moves import range

from ...interfaceModel import coerceIndexToType
from ...items import Combo, Slider
from ...Qt.QtWidgets import QInputDialog, QMessageBox


def registerContext(tree, clickIdx, indexes, menu):
    window = tree.window()
    sliders = coerceIndexToType(indexes, Slider)
    combos = coerceIndexToType(indexes, Combo)
    multis = []
    for grp in [sliders, combos]:
        for idx in grp:
            item = idx.model().itemFromIndex(idx)
            if len(item.prog.pairs) == 2:
                multis.append(idx)

    if not multis:
        return False

    extractACT = menu.addAction("Generate Incrementals ...")
    extractACT.triggered.connect(
        partial(generateShapeIncrementalsContext, multis, window)
    )
    return True


def generateShapeIncrementalsContext(indexes, window):
    idx = indexes[0]  # Only on the click index
    slider = idx.model().itemFromIndex(idx)
    if len(slider.prog.pairs) > 2:
        QMessageBox.warning(window, "Warning", "Slider already has incrementals")
        return

    increments, good = QInputDialog.getInt(
        window, "Increments", "Number of Increments", 4, 1, 100
    )
    if not good:
        return

    rest = None
    target = None
    maxval = -1.0

    for pp in slider.prog.pairs:
        if pp.shape.isRest:
            rest = pp.shape
        elif abs(pp.value) > maxval:
            target = pp.shape

    target.name = target.name + "_100"

    startObj = slider.extractShape(rest, live=False)
    endObj = slider.extractShape(target)
    shapeDup = cmds.duplicate(endObj, name="shapeDup")[0]

    bs = cmds.blendShape(startObj, shapeDup)

    incs = []
    for i in range(1, increments):
        val = float(increments - i) / increments
        percent = int(float(i) * 100 / increments)
        cmds.blendShape(bs, edit=True, weight=((0, val)))

        nne = endObj.replace("_100_", "_{0}_".format(percent))
        nn = nne.replace("_Extract", "")
        inc = cmds.duplicate(shapeDup, name=nne)
        incs.append((percent, nn, nne))

    for perc, inc, ince in incs:
        pp = slider.createShape(shapeName=inc, tVal=perc / 100.0)
        pp.shape.connectShape(mesh=ince, live=True)

    window.uiSliderTREE.model().invalidateFilter()

    cmds.delete((shapeDup, startObj))
    cmds.select(endObj)
