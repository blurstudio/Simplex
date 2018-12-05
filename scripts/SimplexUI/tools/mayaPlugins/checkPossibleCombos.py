import maya.cmds as cmds
from SimplexUI.Qt.QtWidgets import QAction, QProgressDialog, QFileDialog
from SimplexUI.Qt import QtCompat
from SimplexUI.comboCheckDialog import ComboCheckDialog
from functools import partial

def registerTool(window, menu):
	checkPossibleCombosACT = QAction("Check Possible Combos ...", window)
	menu.addAction(checkPossibleCombosACT)
	checkPossibleCombosACT.triggered.connect(partial(checkPossibleCombosInterface, window))

def checkPossibleCombosInterface(window):
	ccd = ComboCheckDialog(sliders, window)
	ccd.show()









