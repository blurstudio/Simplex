import maya.cmds as cmds
from SimplexUI.Qt.QtWidgets import QAction, QProgressDialog, QFileDialog
from SimplexUI.Qt import QtCompat
from SimplexUI.comboCheckDialog import ComboCheckDialog
from SimplexUI.interfaceItems import Slider
from functools import partial

def registerTool(window, menu):
	checkPossibleCombosACT = QAction("Check Possible Combos ...", window)
	menu.addAction(checkPossibleCombosACT)
	checkPossibleCombosACT.triggered.connect(partial(checkPossibleCombosInterface, window))

def registerContext(tree, clickIdx, indexes, menu):
	window = tree.window()
	checkPossibleCombosACT = QAction("Check Possible Combos ...", tree)
	menu.addAction(checkPossibleCombosACT)
	checkPossibleCombosACT.triggered.connect(partial(checkPossibleCombosInterface, window))

def checkPossibleCombosInterface(window):
	sliders = window.uiSliderTREE.getSelectedItems(typ=Slider)
	ccd = ComboCheckDialog(sliders, window)
	ccd.show()

