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
from functools import partial

from ...commands.unsubdivide import unsubdivideSimplex
from ...Qt import QtCompat
from ...Qt.QtWidgets import QAction, QMessageBox, QProgressDialog

try:
    import imathnumpy
except ImportError:
    imathnumpy = None


def registerTool(window, menu):
    if imathnumpy is not None:
        exportUnsubACT = QAction("Un Subdivide Smpx ...", window)
        menu.addAction(exportUnsubACT)
        exportUnsubACT.triggered.connect(partial(exportUnsubInterface, window))


def exportUnsubInterface(window):
    if imathnumpy is None:
        QMessageBox.warning(
            window,
            "No ImathToNumpy",
            "ImathToNumpy is not available here, and it is required to unsubdivide a system",
        )
        return

    path, _filter = QtCompat.QFileDialog.getOpenFileName(
        window, "Un Subdivide", "", "Simplex (*.smpx)"
    )

    if not path:
        return

    outPath = path.replace(".smpx", "_UNSUB.smpx")
    if path == outPath:
        QMessageBox.warning(window, "Unable to rename smpx file: {}".format(path))
        return

    if os.path.isfile(outPath):
        btns = QMessageBox.Ok | QMessageBox.Cancel
        msg = "Unsub file already exists.\n{0}\nOverwrite?".format(outPath)
        response = QMessageBox.question(window, "File already exists", msg, btns)
        if not response & QMessageBox.Ok:
            return

    pBar = QProgressDialog("Exporting Unsubdivided smpx File", "Cancel", 0, 100, window)
    pBar.show()
    unsubdivideSimplex(path, outPath, pBar=pBar)
    pBar.close()
