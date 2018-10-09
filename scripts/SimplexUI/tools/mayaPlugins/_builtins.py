#pylint:disable=unused-variable
import maya.cmds as cmds
from Qt.QtWidgets import QAction, QMenu
from SimplexUI.interfaceItems import Slider
from SimplexUI.interfaceModel import coerceIndexToType


def registerContext(window, tree, indexes, menu):
	if tree == window.uiComboTREE:
		registerComboTree(window, indexes, menu)

	if tree == window.uiSliderTREE:
		registerSliderTree(window, indexes, menu)

def registerSliderTree(window, indexes, menu):
	live = window.uiLiveShapeConnectionACT.isChecked()
	items = [i.model().itemFromIndex(i) for i in indexes]
	# anywhere
	addGroupACT = menu.addAction("Add Group")
	# anywhere
	addSliderACT = menu.addAction("Add Slider")
	# on/under slider in slider tree
	addShapeACT = menu.addAction("Add Shape")

	menu.addSeparator()

	# if 2 or more are active
	comboActiveACT = menu.addAction("Combo Active")
	# if 2 or more are selected
	comboSelectedACT = menu.addAction("Combo Selected")

	menu.addSeparator()

	# anywhere
	deleteACT = menu.addAction("Delete Selected")

	menu.addSeparator()
	
	# anywhere
	zeroACT = menu.addAction("Zero Selected")
	# anywhere
	zeroAllACT = menu.addAction("Zero All")

	menu.addSeparator()

	# on shape/slider
	extractShapeACT = menu.addAction("Extract")
	# on shape/slider
	connectShapeACT = menu.addAction("Connect By Name")
	# on shape/slider, if there's a selection
	matchShapeACT = menu.addAction("Match To Scene Selection")
	# on shape/slider
	clearShapeACT = menu.addAction("Clear")

	menu.addSeparator()

	# Anywhere
	isolateSelectedACT = menu.addAction("Isolate Selected")
	# Anywhere
	exitIsolationACT = menu.addAction("Exit Isolation")

def registerComboTree(window, indexes, menu):
	live = window.uiLiveShapeConnectionACT.isChecked()
	items = [i.model().itemFromIndex(i) for i in indexes]

	# anywhere
	addGroupACT = menu.addAction("Add Group")
	# anywhere
	addShapeACT = menu.addAction("Add Shape")

	menu.addSeparator()

	# on combo, comboPair, or shape
	deleteACT = menu.addAction("Delete Selected")

	menu.addSeparator()

	# combo or below
	setValsACT = menu.addAction("Set Selected Values")

	menu.addSeparator()

	# combo or below
	extractShapeACT = menu.addAction("Extract")
	# combo or below
	connectShapeACT = menu.addAction("Connect By Name")
	# combo or below, if there's a selection
	matchShapeACT = menu.addAction("Match To Scene Selection")
	# combo or below
	clearShapeACT = menu.addAction("Clear")

	menu.addSeparator()

	# anywhere
	isolateSelectedACT = menu.addAction("Isolate Selected")
	# anywhere
	exitIsolationACT = menu.addAction("Exit Isolation")



