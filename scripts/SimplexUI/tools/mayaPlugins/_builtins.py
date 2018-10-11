#pylint:disable=unused-variable
import maya.cmds as cmds
from functools import partial
from Qt.QtWidgets import QAction, QMenu
from SimplexUI.interfaceItems import Slider, Combo, ComboPair, ProgPair, Group
from SimplexUI.interfaceModel import coerceIndexToType


def registerContext(tree, indexes, menu):
	self = tree.window()
	if tree == self.uiComboTREE:
		registerComboTree(self, indexes, menu)
	if tree == self.uiSliderTREE:
		registerSliderTree(self, indexes, menu)

def registerSliderTree(window, indexes, menu):
	self = window
	live = self.uiLiveShapeConnectionACT.isChecked()
	items = [i.model().itemFromIndex(i) for i in indexes]
	types = {}	
	for i in items:
		types.setdefault(type(i), []).append(i)

	activeCount = 0
	for s in self.simplex.sliders:
		if s.value != 0.0:
			activeCount += 1
	sel = cmds.ls(sl=True)

	# anywhere
	addGroupACT = menu.addAction("Add Group")
	addGroupACT.triggered.connect(self.newSliderGroup)
	# anywhere
	if indexes:
		addSliderACT = menu.addAction("Add Slider")
		addSliderACT.triggered.connect(self.newSlider)
	# on/under slider in slider tree
	if ProgPair in types or Slider in types:
		addShapeACT = menu.addAction("Add Shape")
		addShapeACT.triggered.connect(self.newSliderShape)

	'''
	menu.addSeparator()
	if Slider in types:
		#setGroupACT = menu.addAction("Add Shape")
		#setGroupACT.triggered.connect(self.newSliderShape)
		sliders = [i for i in items if isinstance(i, Slider)]
		setGroupMenu = menu.addMenu("Set Group")
		for group in window.simplex.sliderGroups:
			gAct = setGroupMenu.addAction(group.name)
			#gAct.triggered.connect(lambda: Group.take(group, sliders))
			gAct.triggered.connect(partial(Group.take, group, sliders))
	'''

	menu.addSeparator()

	sep = False
	if activeCount >= 2:
		# if 2 or more are active
		comboActiveACT = menu.addAction("Combo Active")
		comboActiveACT.triggered.connect(self.newActiveCombo)
		sep = True

	if len(types.get(Slider, [])) >= 2:
		# if 2 or more are selected
		comboSelectedACT = menu.addAction("Combo Selected")
		comboSelectedACT.triggered.connect(self.newSelectedCombo)
		sep = True

	if sep:
		menu.addSeparator()

	# anywhere
	if indexes:
		deleteACT = menu.addAction("Delete Selected")
		deleteACT.triggered.connect(self.sliderTreeDelete)

		menu.addSeparator()
	
	if indexes:
		# anywhere
		zeroACT = menu.addAction("Zero Selected")
		zeroACT.triggered.connect(self.zeroSelectedSliders)
	# anywhere
	zeroAllACT = menu.addAction("Zero All")
	zeroAllACT.triggered.connect(self.zeroAllSliders)

	menu.addSeparator()

	if ProgPair in types or Slider in types:
		# on shape/slider
		extractShapeACT = menu.addAction("Extract")
		extractShapeACT.triggered.connect(self.shapeExtract)
		# on shape/slider
		connectShapeACT = menu.addAction("Connect By Name")
		connectShapeACT.triggered.connect(self.shapeConnect)
		if sel:
			# on shape/slider, if there's a selection
			matchShapeACT = menu.addAction("Match To Scene Selection")
			matchShapeACT.triggered.connect(self.shapeMatch)
		# on shape/slider
		clearShapeACT = menu.addAction("Clear")
		clearShapeACT.triggered.connect(self.shapeClear)

		menu.addSeparator()

	if indexes:
		# Anywhere
		isolateSelectedACT = menu.addAction("Isolate Selected")
		isolateSelectedACT.triggered.connect(self.sliderIsolateSelected)

	if self.isSliderIsolate():
		# Anywhere
		exitIsolationACT = menu.addAction("Exit Isolation")
		exitIsolationACT.triggered.connect(self.sliderTreeExitIsolate)

	menu.addSeparator()

def registerComboTree(window, indexes, menu):
	self = window
	live = self.uiLiveShapeConnectionACT.isChecked()
	items = [i.model().itemFromIndex(i) for i in indexes]
	types = {}
	for i in items:
		types.setdefault(type(i), []).append(i)
	sel = cmds.ls(sl=True)

	# anywhere
	addGroupACT = menu.addAction("Add Group")
	addGroupACT.triggered.connect(self.newComboGroup)

	if Combo in types or ComboPair in types or ProgPair in types:
		# on combo, comboPair, or shape
		addShapeACT = menu.addAction("Add Shape")
		addShapeACT.triggered.connect(self.newComboShape)

		menu.addSeparator()

		# on combo, comboPair, or shape
		deleteACT = menu.addAction("Delete Selected")
		deleteACT.triggered.connect(self.comboTreeDelete)

		menu.addSeparator()

		# combo or below
		setValsACT = menu.addAction("Set Selected Values")
		setValsACT.triggered.connect(self.setSliderVals)

		menu.addSeparator()

		# combo or below
		extractShapeACT = menu.addAction("Extract")
		extractShapeACT.triggered.connect(self.shapeExtract)
		# combo or below
		connectShapeACT = menu.addAction("Connect By Name")
		connectShapeACT.triggered.connect(self.shapeConnect)
		if sel:
			# combo or below, if there's a selection
			matchShapeACT = menu.addAction("Match To Scene Selection")
			matchShapeACT.triggered.connect(self.shapeMatch)
		# combo or below
		clearShapeACT = menu.addAction("Clear")
		clearShapeACT.triggered.connect(self.shapeClear)

	menu.addSeparator()

	sep = False
	if indexes:
		# anywhere
		isolateSelectedACT = menu.addAction("Isolate Selected")
		isolateSelectedACT.triggered.connect(self.comboIsolateSelected)
		sep = True

	if self.isComboIsolate():
		# anywhere
		exitIsolationACT = menu.addAction("Exit Isolation")
		exitIsolationACT.triggered.connect(self.comboTreeExitIsolate)
		sep = True

	if sep:
		menu.addSeparator()



