import maya.cmds as cmds
from SimplexUI.Qt.QtWidgets import QAction, QProgressDialog
from SimplexUI.Qt import QtCompat

def registerTool(window, menu):
	extractExternalACT = QAction("Extract External", window)
	menu.addAction(extractExternalACT)
	kick = lambda: extractExternalInterface(window)
	extractExternalACT.triggered.connect(extractExternalInterface)

def extractExternalInterface(window):
	sel = cmds.ls(sl=True)
	path, _filter = QtCompat.QFileDialog.getSaveFileName(window, "Extract External", "", "Simplex (*.smpx)")

	pBar = QProgressDialog("Extracting Simplex from External Mesh", "Cancel", 0, 100, window)
	if sel and path:
		window.simplex.extractExternal(path, sel[0], world=True, pBar=pBar)
	pBar.close()

