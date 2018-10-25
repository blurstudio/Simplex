from Qt.QtWidgets import QAction, QProgressDialog
from Qt import QtCompat
from functools import partial

def registerTool(window, menu):
	extractExternalACT = QAction("Export Split", window)
	menu.addAction(extractExternalACT)
	extractExternalACT.triggered.connect(partial(exportSplitInterface, window))

def exportSplitInterface(window):
	path, _filter = QtCompat.QFileDialog.getSaveFileName(window, "Export Split", "", "Simplex (*.smpx)")

	if not path:
		return

	pBar = QProgressDialog("Exporting Split smpx File", "Cancel", 0, 100, window)
	pBar.show()
	split = window.simplex.split(pBar)
	split.exportAbc(path, pBar)
	pBar.close()

