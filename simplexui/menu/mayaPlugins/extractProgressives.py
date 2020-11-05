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
from ...Qt.QtWidgets import QAction
from ...items import Slider
from ...interfaceModel import coerceIndexToType
from functools import partial

def registerTool(window, menu):
    """
    Reimplemented to qt.

    Args:
        window: (todo): write your description
        menu: (todo): write your description
    """
	extractProgressivesACT = QAction("Extract Progressive", window)
	menu.addAction(extractProgressivesACT)
	extractProgressivesACT.triggered.connect(partial(extractProgressivesInterface, window))

def registerContext(tree, clickIdx, indexes, menu):
    """
    Sets a new menu.

    Args:
        tree: (str): write your description
        clickIdx: (todo): write your description
        indexes: (list): write your description
        menu: (todo): write your description
    """
	window = tree.window()
	live = window.uiLiveShapeConnectionACT.isChecked()
	sliders = coerceIndexToType(indexes, Slider)

	multis = []
	for slidx in sliders:
		slider = slidx.model().itemFromIndex(slidx)
		if len(slider.prog.pairs) > 2:
			multis.append(slidx)

	if multis:
		extractACT = menu.addAction('Extract Progressive')
		extractACT.triggered.connect(partial(extractProgressivesContext, multis, live))
		return True
	return False

def extractProgressivesContext(indexes, live):
    """
    Extracts the index of the indexes

    Args:
        indexes: (todo): write your description
        live: (array): write your description
    """
	sliders = [idx.model().itemFromIndex(idx) for idx in indexes]
	sliders = list(set(sliders))
	for sli in sliders:
		sli.extractProgressive(live=live)

def extractProgressivesInterface(window):
    """
    Extractsliives

    Args:
        window: (int): write your description
    """
	live = window.uiLiveShapeConnectionACT.isChecked()
	indexes = window.uiSliderTREE.getSelectedIndexes()
	indexes = coerceIndexToType(indexes, Slider)
	sliders = [idx.model().itemFromIndex(idx) for idx in indexes]
	sliders = list(set(sliders))
	for sli in sliders:
		sli.extractProgressive(live=live)

