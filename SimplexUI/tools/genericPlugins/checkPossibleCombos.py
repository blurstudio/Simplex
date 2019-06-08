from ...Qt.QtWidgets import QAction, QProgressDialog, QFileDialog
from ...Qt import QtCompat
from ...comboCheckDialog import ComboCheckDialog
from ...interfaceItems import Slider
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
	ccd = ComboCheckDialog(sliders, parent=window)
	ccd.show()

