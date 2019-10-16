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

import maya.cmds as cmds
from ...utils import makeUnique, naturalSortKey
from ...Qt.QtWidgets import QAction, QInputDialog, QMessageBox
from ...items import Slider, Combo, Traversal, ProgPair
from ...interfaceModel import coerceIndexToType, coerceIndexToChildType
from functools import partial

def registerTool(window, menu):
	lineTravACT = QAction("Linearize Traversal", window)
	menu.addAction(lineTravACT)
	lineTravACT.triggered.connect(partial(lineTrav, window))

def lineTrav(window):
	simplex = window.simplex
	travDialog = window.travDialog
	sel = travDialog.uiTraversalTREE.getSelectedIndexes()
	travIdx = sel[0]
	trav = travIdx.model().itemFromIndex(travIdx)
	extracted = window.shapeIndexExtract([travIdx])
	rest = simplex.DCC.extractTraversalShape(trav, simplex.restShape, live=False)

	end = extracted[-1]
	val = len(extracted)
	for i, mesh in enumerate(extracted[:-1]):
		startDup = cmds.duplicate(rest, name="startDup")[0]
		absBlend = cmds.blendShape(end, startDup)
		cmds.blendShape(absBlend, edit=True, weight=((0, (i+1.0)/val)))

		finBlend = cmds.blendShape(startDup, mesh)
		cmds.blendShape(finBlend, edit=True, weight=((0, 1)))
		cmds.delete(startDup)
	cmds.delete(rest)


