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

from ...Qt import QtCompat
from ...Qt.QtWidgets import QAction, QMessageBox, QProgressDialog

try:
    import numpy as np
except ImportError:
    np = None


def registerTool(window, menu):
    if np is not None:
        exportSplitACT = QAction("Export Split", window)
        menu.addAction(exportSplitACT)
        exportSplitACT.triggered.connect(partial(exportSplitInterface, window))


def exportSplitInterface(window):
    if np is None:
        QMessageBox.warning(
            window,
            "No Numpy",
            "Numpy is not available here, an it is required to split a system",
        )
        return
    path, _filter = QtCompat.QFileDialog.getSaveFileName(
        window, "Export Split", "", "Simplex (*.smpx)"
    )

    if not path:
        return

    pBar = QProgressDialog("Exporting Split smpx File", "Cancel", 0, 100, window)
    pBar.show()
    try:
        split = window.simplex.split(pBar)
        split.exportAbc(path, pBar)
    except ValueError as e:
        QMessageBox.warning(window, "Unsplittable", str(e))
    finally:
        pBar.close()
