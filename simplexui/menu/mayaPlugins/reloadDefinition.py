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
from ...Qt.QtWidgets import QAction


def registerTool(window, menu):
    reloadDefinitionACT = QAction("Reload Definition", window)
    menu.addAction(reloadDefinitionACT)
    reloadDefinitionACT.triggered.connect(partial(reloadDefinitionInterface, window))


def reloadDefinitionInterface(window):
    reloadDefinition(window.simplex)


def reloadDefinition(simplex):
    simplex.DCC.setSimplexString(simplex.DCC.op, simplex.dump())
