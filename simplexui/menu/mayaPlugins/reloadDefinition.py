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
from functools import partial

def registerTool(window, menu):
    """
    Reimplemented plugin for the inputed window. : param window | <int > || none

    Args:
        window: (todo): write your description
        menu: (todo): write your description
    """
	reloadDefinitionACT = QAction("Reload Definition", window)
	menu.addAction(reloadDefinitionACT)
	reloadDefinitionACT.triggered.connect(partial(reloadDefinitionInterface, window))

def reloadDefinitionInterface(window):
    """
    Reloads a window

    Args:
        window: (int): write your description
    """
	reloadDefinition(window.simplex)

def reloadDefinition(simplex):
    """
    Recompute a python object.

    Args:
        simplex: (todo): write your description
    """
	simplex.DCC.setSimplexString(
		simplex.DCC.op,
		simplex.dump()
	)

