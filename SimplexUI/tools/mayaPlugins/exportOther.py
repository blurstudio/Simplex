import maya.cmds as cmds
from SimplexUI.Qt.QtWidgets import QAction, QProgressDialog
from SimplexUI.Qt import QtCompat
from functools import partial

def registerTool(window, menu):
	exportOtherACT = QAction("Export Other", window)
	menu.addAction(exportOtherACT)
	exportOtherACT.triggered.connect(partial(exportOtherInterface, window))

def exportOtherInterface(window):
	sel = cmds.ls(sl=True)
	path, _filter = QtCompat.QFileDialog.getSaveFileName(window, "Export Other", "", "Simplex (*.smpx)")

	pBar = QProgressDialog("Exporting Simplex from Other Mesh", "Cancel", 0, 100, window)
	if sel and path:
		window.simplex.exportOther(path, sel[0], world=True, pBar=pBar)
	pBar.close()

