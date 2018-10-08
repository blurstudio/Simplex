import maya.cmds as cmds
from Qt.QtWidgets import QAction, QProgressDialog
from Qt import QtCompat

def registerTool(window, menu):
	extractExternalACT = QAction("Extract External", window)
	menu.addAction(extractExternalACT)
	extractExternalACT.triggered.connect(extractExternalInterface)

def extractExternalInterface(self):
	sel = cmds.ls(sl=True)
	path, _filter = QtCompat.QFileDialog.getSaveFileName(self.window, "Extract External", "", "Simplex (*.smpx)")

	pBar = QProgressDialog("Extracting Simplex from External Mesh", "Cancel", 0, 100, self.window)
	if sel and path:
		extractExternal(self.system, sel[0], path, pBar)
	pBar.close()

def extractExternal(system, mesh, path, pBar):
	system.extractExternal(path, mesh, world=True, pBar=pBar)

