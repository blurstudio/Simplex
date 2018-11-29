import maya.cmds as cmds
from SimplexUI.Qt.QtWidgets import QAction, QProgressDialog, QFileDialog
from SimplexUI.Qt import QtCompat
from functools import partial

def registerTool(window, menu):
	importObjsACT = QAction("Import Obj Folder", window)
	menu.addAction(importObjsACT)
	importObjsACT.triggered.connect(partial(importObjsInterface, window))

def importObjsInterface(window):
	sel = cmds.ls(sl=True)
	folder = QFileDialog.getExistingDirectory(window, "Import Obj Folder", "")

	if sel and folder:
		window.importObjFolder(folder)

