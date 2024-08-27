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

import os

from ...Qt.QtWidgets import QAction

dn = os.path.dirname
SHELF_DEV_BUTTON = """
import os, sys

path = r'{0}'
path = os.path.normcase(os.path.normpath(path))
if sys.path[0] != path:
    sys.path.insert(0, path)

import simplexui
if simplexui.SIMPLEX_UI is not None:
    try:
        simplexui.SIMPLEX_UI.close()
    except RuntimeError:
        # In case I closed it myself
        pass
del simplexui

for key, value in sys.modules.items():
    try:
        packPath = value.__file__
    except AttributeError:
        continue

    packPath = os.path.normcase(os.path.normpath(packPath))
    if packPath.startswith(path):
        sys.modules.pop(key)

import simplexui
simplexui.runSimplexUI()

sys.path.pop(0)
""".format(
    dn(dn(dn(dn(__file__))))
)


def registerTool(window, menu):
    makeShelfBtnACT = QAction("Make Shelf Button", window)
    menu.addAction(makeShelfBtnACT)
    makeShelfBtnACT.triggered.connect(makeShelfButton)


def makeShelfButton():
    pass
    # TODO: Actually, ya know, Add the button to the shelf
