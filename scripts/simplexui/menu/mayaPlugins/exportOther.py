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

from ...Qt import QtCompat
from ...Qt.QtWidgets import QAction, QProgressDialog


def registerTool(window, menu):
    exportOtherACT = QAction("Export Other", window)
    menu.addAction(exportOtherACT)
    exportOtherACT.triggered.connect(partial(exportOtherInterface, window))


def exportOtherInterface(window):
    sel = cmds.ls(sl=True)
    path, _filter = QtCompat.QFileDialog.getSaveFileName(
        window, "Export Other", "", "Simplex (*.smpx)"
    )

    pBar = QProgressDialog(
        "Exporting Simplex from Other Mesh", "Cancel", 0, 100, window
    )
    if sel and path:
        window.simplex.exportOther(path, sel[0], world=True, pBar=pBar)
    pBar.close()
