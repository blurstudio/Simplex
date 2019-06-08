from ...Qt.QtWidgets import QAction, QProgressDialog, QMessageBox
from ...Qt import QtCompat
from functools import partial
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
		QMessageBox.warning(window, "No Numpy", "Numpy is not available here, an it is required to split a system")
		return
	path, _filter = QtCompat.QFileDialog.getSaveFileName(window, "Export Split", "", "Simplex (*.smpx)")

	if not path:
		return

	pBar = QProgressDialog("Exporting Split smpx File", "Cancel", 0, 100, window)
	pBar.show()
	split = window.simplex.split(pBar)
	split.exportAbc(path, pBar)
	pBar.close()

