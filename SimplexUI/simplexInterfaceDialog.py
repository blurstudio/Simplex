"""
Copyright 2016, Blur Studio

This file is part of Simplex.

Simplex is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Simplex is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with Simplex.  If not, see <http://www.gnu.org/licenses/>.

"""

# Ignore a bunch of linter warnings that show up because of my choice of abstraction
#pylint: disable=unused-argument,too-many-public-methods
#pylint: disable=too-many-statements,no-self-use
import os, sys, re, json, copy, weakref
from functools import wraps


# This module imports QT from PyQt4, PySide or PySide2
# Depending on what's available
from Qt import QtCompat
from Qt.QtCore import Slot, QModelIndex
from Qt.QtCore import Qt, QSettings
from Qt.QtWidgets import QMessageBox, QInputDialog, QFileDialog, QMenu, QApplication
from Qt.QtWidgets import QMainWindow, QProgressDialog

from utils import toPyObject, getUiFile, getNextName, singleShot

from dragFilter import DragFilter

from interfaceModel import (Falloff, Shape, ProgPair, Progression, Slider, ComboPair,
							Combo, Group, Simplex, SliderModel, ComboModel, DCC,
							ComboFilterModel, SliderFilterModel, coerceToType,
							coerceToChildType, coerceToParentType, coerceToRoots)

from interface import customSliderMenu, customComboMenu, ToolActions, undoContext

try:
	# This module is unique to Blur Studio
	import blurdev
except ImportError:
	blurdev = None


NAME_CHECK = re.compile('[A-Za-z][\w.]*')

# If the decorated method is a slot for some Qt Signal
# and the method signature is *NOT* the same as the
# signal signature, you must double decorate the method like:
#
# @Slot(**signature)
# @stackable
# def method(**signature)


# Stackable also lives in the interface, and is made for the System object
# this version of stackable is made for the UI, and calls through to the system
def stackable(method):
	@wraps(method)
	def stacked(self, *data, **kwdata):
		with undoContext():
			ret = None
			self.system.stack.depth += 1
			ret = method(self, *data, **kwdata)
			self.system.stack.depth -= 1

			if self.system.stack.depth == 0:
				srevision = self.system.incrementRevision()
				scopy = copy.deepcopy(self.system.simplex)
				self.system.stack[srevision] = (scopy, self.system, None, [], {})
			return ret
	return stacked

class SimplexDialog(QMainWindow):
	''' The main ui for simplex '''
	def __init__(self, parent=None, dispatch=None):
		super(SimplexDialog, self).__init__(parent)
		QtCompat.loadUi(getUiFile(__file__), self)

		self._sliderMenu = None
		self._comboMenu = None
		self._currentObject = None
		self._currentObjectName = None

		# Make sure to connect the dispatcher to the undo control
		# but only keep a weakref to it
		self.dispatch = None
		if dispatch is not None:
			self.dispatch = weakref.ref(dispatch)
			dispatch.undo.connect(self.handleUndo)
			dispatch.redo.connect(self.handleUndo)
			dispatch.beforeNew.connect(self.newScene)
			dispatch.beforeOpen.connect(self.newScene)

		self.simplex = None

		self._sliderMul = 1.0
		self._itemMap = {}
		self._sliderTreeMap = {}
		self._comboTreeMap = {}

		self._sliderDrag = None
		self._comboDrag = None

		self.uiSliderExitIsolateBTN.hide()
		self.uiComboExitIsolateBTN.hide()

		self._makeConnections()
		self.connectMenus()

		self.uiSettingsGRP.setChecked(False)

		self.toolActions = ToolActions(self, self.simplex)

		if self.simplex.DCC.program == "dummy":
			self.getSelectedObject()
			self.uiObjectGRP.setEnabled(False)
			self.uiSystemGRP.setEnabled(False)
			if dispatch is not None:
				pass

				# Should keep track of the actual "stops"
				# when dealing with the dummy interface
				#from Qt.QtWidgets import QShortcut
				#from Qt.QtGui import QKeySequence
				#self._undoShortcut = QShortcut(QKeySequence("Ctrl+z"), self)
				#self._undoShortcut.activated.connect(self.dispatch.emitUndo)
				#self._undoShortcut = QShortcut(QKeySequence("Ctrl+y"), self)
				#self._undoShortcut.activated.connect(self.dispatch.emitRedo)

	# Undo/Redo
	def handleUndo(self):
		''' Call this after an undo/redo action. Usually called from the stack '''
		pass
		# With this update, we need to handle undo/redo completely differently

		#rev = self.system.getRevision()
		#data = self.system.stack.getRevision(rev)
		#if data is not None:
			#self.storeExpansion(self.uiSliderTREE)
			#self.storeExpansion(self.uiComboTREE)
			#self.pairExpansion(self.system, data[0])
			#self.system.setSimplex(data[0])
			#self.forceSimplexUpdate()
			#self.setItemExpansion(self.uiSliderTREE)
			#self.setItemExpansion(self.uiComboTREE)



	# UI Setup
	def _makeConnections(self):
		''' Make all the ui connections '''
		# Setup Trees!
		sliderModel = SliderModel(self.simplex, None)
		sliderProxModel = SliderFilterModel()
		sliderProxModel.setSourceModel(sliderModel)
		self.uiSliderTREE.setModel(sliderProxModel)
		self.uiSliderTREE.setColumnWidth(1, 50)
		self.uiSliderTREE.setColumnWidth(2, 20)
		self.uiSliderFilterLINE.editingFinished.connect(self.sliderStringFilter)
		self.uiSliderFilterClearBTN.clicked.connect(self.uiSliderFilterLINE.clear)
		self.uiSliderFilterClearBTN.clicked.connect(self.sliderStringFilter)

		comboModel = ComboModel(self.simplex, None)
		comboProxModel = ComboFilterModel()
		comboProxModel.setSourceModel(comboModel)
		self.uiComboTREE.setModel(comboProxModel)
		self.uiComboTREE.setColumnWidth(1, 50)
		self.uiComboTREE.setColumnWidth(2, 20)
		self.uiComboFilterLINE.editingFinished.connect(self.comboStringFilter)
		self.uiComboFilterClearBTN.clicked.connect(self.uiComboFilterLINE.clear)
		self.uiComboFilterClearBTN.clicked.connect(self.comboStringFilter)

		# selection setup
		sliderSelModel = self.uiSliderTREE.selectionModel()
		sliderSelModel.selectionChanged.connect(self.unifySliderSelection)
		comboSelModel = self.uiComboTREE.selectionModel()
		comboSelModel.selectionChanged.connect(self.unifyComboSelection)

		# dependency setup
		self.uiComboDependAllCHK.stateChanged.connect(self.setAllComboRequirement)
		self.uiComboDependAnyCHK.stateChanged.connect(self.setAnyComboRequirement)
		self.uiComboDependOnlyCHK.stateChanged.connect(self.setOnlyComboRequirement)
		sliderSelModel.selectionChanged.connect(self.populateComboRequirements)

		# Bottom Left Corner Buttons
		self.uiZeroAllBTN.clicked.connect(self.zeroAllSliders)
		self.uiZeroSelectedBTN.clicked.connect(self.zeroSelectedSliders)
		self.uiSelectCtrlBTN.clicked.connect(self.selectCtrl)

		# Top Left Corner Buttons
		self.uiNewGroupBTN.clicked.connect(self.newSliderGroup)
		self.uiNewSliderBTN.clicked.connect(self.newSlider)
		self.uiNewShapeBTN.clicked.connect(self.newSliderShape)
		self.uiSliderDeleteBTN.clicked.connect(self.sliderTreeDelete)

		# Top Right Corner Buttons
		self.uiDeleteComboBTN.clicked.connect(self.comboTreeDelete)
		self.uiNewComboActiveBTN.clicked.connect(self.newActiveCombo)
		self.uiNewComboSelectBTN.clicked.connect(self.newSelectedCombo)
		self.uiNewComboShapeBTN.clicked.connect(self.newComboShape)
		self.uiNewComboGroupBTN.clicked.connect(self.newComboGroup)

		# Bottom right corner buttons
		self.uiSetSliderValsBTN.clicked.connect(self.setSliderVals)
		self.uiSelectSlidersBTN.clicked.connect(self.selectSliders)

		## Settings connections
		#sliderSelModel.selectionChanged.connect(self.loadSettings)
		#self.uiWeightNameTXT.editingFinished.connect(self.setSliderName)
		#self.uiWeightGroupCBOX.currentIndexChanged.connect(self.setSliderGroup)

		## Falloff connections
		#foModel = QStandardItemModel()
		#self.uiWeightFalloffCBOX.setModel(foModel)
		#foModel.dataChanged.connect(self.populateFalloffLine)
		#foModel.dataChanged.connect(self.setSliderFalloffs)

		#self.uiShapeFalloffNewBTN.clicked.connect(self.newFalloff)
		#self.uiShapeFalloffDuplicateBTN.clicked.connect(self.duplicateFalloff)
		#self.uiShapeFalloffDeleteBTN.clicked.connect(self.deleteFalloff)

		#self.uiFalloffTypeCBOX.currentIndexChanged.connect(self._updateFalloffData)
		#self.uiFalloffAxisCBOX.currentIndexChanged.connect(self._updateFalloffData)
		#self.uiFalloffMinSPN.valueChanged.connect(self._updateFalloffData)
		#self.uiFalloffMinHandleSPN.valueChanged.connect(self._updateFalloffData)
		#self.uiFalloffMaxHandleSPN.valueChanged.connect(self._updateFalloffData)
		#self.uiFalloffMaxSPN.valueChanged.connect(self._updateFalloffData)

		## Make the falloff combobox display consistently with the others, but
		## retain the ability to change the top line
		#line = self.uiWeightFalloffCBOX.lineEdit()
		#line.setReadOnly(True) # not editable
		#self.uiShapeFalloffCBOX.currentIndexChanged.connect(self.loadFalloffData)

		## System level
		self.uiCurrentObjectTXT.editingFinished.connect(self.currentObjectChanged)
		self.uiGetSelectedObjectBTN.clicked.connect(self.getSelectedObject)
		self.uiNewSystemBTN.clicked.connect(self.newSystem)
		#self.uiDeleteSystemBTN.clicked.connect(self.deleteSystem)
		self.uiRenameSystemBTN.clicked.connect(self.renameSystem)
		self.uiUpdateSystemBTN.clicked.connect(self.forceSimplexUpdate)
		self.uiCurrentSystemCBOX.currentIndexChanged[int].connect(self.currentSystemChanged)

		# Extraction/connection
		self.uiShapeExtractBTN.clicked.connect(self.shapeExtract)
		self.uiShapeConnectBTN.clicked.connect(self.shapeConnect)
		self.uiShapeConnectAllBTN.clicked.connect(self.shapeConnectAll)
		self.uiShapeConnectSceneBTN.clicked.connect(self.shapeConnectScene)
		self.uiShapeMatchBTN.clicked.connect(self.shapeMatch)
		self.uiShapeClearBTN.clicked.connect(self.shapeClear)

		# File Menu
		self.uiImportACT.triggered.connect(self.importSystemFromFile)
		self.uiExportACT.triggered.connect(self.exportSystemTemplate)

		# Edit Menu
		self.uiHideRedundantACT.toggled.connect(self.hideRedundant)
		self.uiDoubleSliderRangeACT.toggled.connect(self.setSliderRange)

		# Isolation
		self.uiSliderExitIsolateBTN.clicked.connect(self.sliderTreeExitIsolate)
		self.uiComboExitIsolateBTN.clicked.connect(self.comboTreeExitIsolate)

		#if blurdev is not None:
			#blurdev.core.aboutToClearPaths.connect(self.blurShutdown)



	# Helpers
	def getSelectedItems(self, tree, typ=None):
		sel = tree.selectedIndexes()
		sel = [i for i in sel if i.column() == 0]
		model = tree.model()
		items = [model.itemFromIndex(i) for i in sel]
		if typ is not None:
			items = [i for i in items if isinstance(i, typ)]
		return items



	# Setup Trees!
	def sliderStringFilter(self):
		''' Set the filter for the slider tree '''
		filterString = str(self.uiSliderFilterLINE.text())
		sliderModel = self.uiSliderTREE.model()
		sliderModel.filterString = str(filterString)
		sliderModel.invalidateFilter()

	def comboStringFilter(self):
		''' Set the filter for the combo tree '''
		filterString = str(self.uiComboFilterLINE.text())
		comboModel = self.uiComboTREE.model()
		comboModel.filterString = str(filterString)
		comboModel.invalidateFilter()

	# selection setup
	def unifySliderSelection(self):
		''' Clear the selection of the combo tree when
		an item on the slider tree is selected '''
		mods = QApplication.keyboardModifiers()
		if not mods & (Qt.ControlModifier | Qt.ShiftModifier):
			comboSelModel = self.uiComboTREE.selectionModel()
			comboSelModel.blockSignals(True)
			try:
				comboSelModel.clearSelection()
			finally:
				comboSelModel.blockSignals(False)
			self.uiComboTREE.viewport().update()

	def unifyComboSelection(self):
		''' Clear the selection of the slider tree when
		an item on the combo tree is selected '''
		mods = QApplication.keyboardModifiers()
		if not mods & (Qt.ControlModifier | Qt.ShiftModifier):
			sliderSelModel = self.uiSliderTREE.selectionModel()
			sliderSelModel.blockSignals(True)
			try:
				sliderSelModel.clearSelection()
			finally:
				sliderSelModel.blockSignals(False)
			self.uiSliderTREE.viewport().update()

	# dependency setup
	def setAllComboRequirement(self):
		''' Handle the clicking of the "All" checkbox '''
		for item in (self.uiComboDependAnyCHK, self.uiComboDependOnlyCHK):
			if item.isChecked():
				item.blockSignals(True)
				item.setChecked(False)
				item.blockSignals(False)
		self.enableComboRequirements()

	def setAnyComboRequirement(self):
		''' Handle the clicking of the "Any" checkbox '''
		for item in (self.uiComboDependAllCHK, self.uiComboDependOnlyCHK):
			if item.isChecked():
				item.blockSignals(True)
				item.setChecked(False)
				item.blockSignals(False)
		self.enableComboRequirements()

	def setOnlyComboRequirement(self):
		''' Handle the clicking of the "Only" checkbox '''
		for item in (self.uiComboDependAnyCHK, self.uiComboDependAllCHK):
			if item.isChecked():
				item.blockSignals(True)
				item.setChecked(False)
				item.blockSignals(False)
		self.enableComboRequirements()

	def populateComboRequirements(self):
		''' Let the combo tree know the requirements from the slider tree '''
		items = self.uiSliderTREE.getSelectedItems(Slider)
		comboModel = self.uiComboTREE.model()
		comboModel.requires = items
		if comboModel.filterRequiresAll or comboModel.filterRequiresAny or comboModel.filterRequiresOnly:
			comboModel.invalidateFilter()

	# Bottom Left Corner Buttons
	def zeroAllSliders(self):
		sliders = self.simplex.sliders
		weights = [0.0] * len(sliders)
		self.simplex.setSlidersWeights(sliders, weights)

	def zeroSelectedSliders(self):
		items = self.uiSliderTREE.getSelectedItems(Slider)
		values = [0.0] * len(items)
		self.simplex.setSlidersWeights(items, values)

	def selectCtrl(self):
		self.simplex.DCC.selectCtrl()

	# Top Left Corner Buttons
	def newSliderGroup(self):
		newName, good = QInputDialog.getText(self, "New Group", "Enter a name for the new group", text="Group")
		if not good:
			return
		if not NAME_CHECK.match(newName):
			message = 'Group name can only contain letters and numbers, and cannot start with a number'
			QMessageBox.warning(self, 'Warning', message)
			return

		items = self.uiSliderTREE.getSelectedItems(Slider)
		Group.createGroup(str(newName), self.simplex, items)

	def newSlider(self):
		# get the new slider name
		newName, good = QInputDialog.getText(self, "New Slider", "Enter a name for the new slider", text="Slider")
		if not good:
			return

		if not NAME_CHECK.match(newName):
			message = 'Slider name can only contain letters and numbers, and cannot start with a number'
			QMessageBox.warning(self, 'Warning', message)
			return

		items = self.uiSliderTREE.getSelectedItems()
		groups = coerceToParentType(items, Group, 'Slider')
		group = groups[0] if groups else None
		Slider.createSlider(str(newName), self.simplex, group=group)

	def newSliderShape(self):
		pars = self.uiSliderTREE.getSelectedItems(Slider)
		if not pars:
			return
		parItem = pars[0]
		parItem.prog.createShape()

	def sliderTreeDelete(self):
		items = self.uiSliderTREE.getSelectedItems()
		roots = coerceToRoots(items, 'Slider') # keeps from double-deleting
		for r in roots:
			r.delete()

	# Top Right Corner Buttons
	def comboTreeDelete(self):
		items = self.uiSliderTREE.getSelectedItems()
		roots = coerceToRoots(items, 'Combo') # keeps from double-deleting
		for r in roots:
			r.delete()

	def newActiveCombo(self):
		sliders = []
		values = []
		for s in self.simplex.sliders:
			if s.value != 0.0:
				sliders.append(s)
				values.append(s.value)
		name = "_".join([s.name for s in sliders])
		Combo.createCombo(name, self.simplex, sliders, values)

	def newSelectedCombo(self):
		sliders = self.uiSliderTREE.getSelectedItems(Slider)
		values = [1.0] * len(sliders)
		name = "_".join([s.name for s in sliders])
		Combo.createCombo(name, self.simplex, sliders, values)

	def newComboShape(self):
		pars = self.uiComboTREE.getSelectedItems(Combo)
		if not pars:
			return
		parItem = pars[0]
		parItem.prog.createShape()

	def newComboGroup(self):
		newName, good = QInputDialog.getText(self, "New Group", "Enter a name for the new group", text="Group")
		if not good:
			return
		if not NAME_CHECK.match(newName):
			message = 'Group name can only contain letters and numbers, and cannot start with a number'
			QMessageBox.warning(self, 'Warning', message)
			return
		Group(newName, self.simplex, Combo)

	# Bottom right corner buttons
	def setSliderVals(self):
		combos = self.uiComboTREE.getSelectedItems(Combo)
		# maybe coerce to type instead??
		self.zeroAllSliders()
		values = []
		sliders = []
		for combo in combos:
			for pair in combo.pairs:
				if pair.slider in sliders:
					continue
				sliders.append(pair.slider)
				values.append(pair.value)
		self.simplex.setSlidersWeights(sliders, values)

	def selectSliders(self):
		combos = self.uiComboTREE.getSelectedItems(Combo)
		sliders = []
		for combo in combos:
			for pair in combo.pairs:
				sliders.append(pair.slider)
		self.uiSliderTREE.setItemSelection(sliders)

	# Extraction/connection
	def shapeExtract(self):
		# Create meshes that are possibly live-connected to the shapes
		live = self.uiLiveShapeConnectionACT.isChecked()

		sliderItems = self.uiSliderTREE.getSelectedItems()
		comboItems = self.uiComboTREE.getSelectedItems()

		sliderPairs = coerceToChildType(sliderItems, ProgPair, 'Slider')
		comboPairs = coerceToChildType(comboItems, ProgPair, 'Combo')

		# Set up the progress bar
		pBar = QProgressDialog("Extracting Shapes", "Cancel", 0, 100, self)
		pBar.setMaximum(len(sliderPairs) + len(comboPairs))

		# Do the extractions
		offset = 10
		for pair in sliderPairs + comboPairs:
			c = pair.prog.controller
			c.extractShape(pair.shape, live=live, offset=offset)
			offset += 5

			# ProgressBar
			pBar.setValue(pBar.value() + 1)
			pBar.setLabelText("Extracting:\n{0}".format(pair.shape.name))
			QApplication.processEvents()
			if pBar.wasCanceled():
				return

		pBar.close()

	def shapeConnect(self):
		sliderItems = self.uiSliderTREE.getSelectedItems()
		comboItems = self.uiComboTREE.getSelectedItems()

		sliderPairs = coerceToChildType(sliderItems, ProgPair, 'Slider')
		comboPairs = coerceToChildType(comboItems, ProgPair, 'Combo')

		# Set up the progress bar
		pBar = QProgressDialog("Connecting Shapes", "Cancel", 0, 100, self)
		pBar.setMaximum(len(sliderPairs) + len(comboPairs))

		# Do the extractions
		for pair in sliderPairs + comboPairs:
			c = pair.prog.controller
			c.connectShape(pair.shape, delete=True)

			# ProgressBar
			pBar.setValue(pBar.value() + 1)
			pBar.setLabelText("Extracting:\n{0}".format(pair.shape.name))
			QApplication.processEvents()
			if pBar.wasCanceled():
				return

		pBar.close()

	def shapeConnectScene(self):
		# make a dict of name:object
		sel = self.simplex.DCC.getSelectedObjects()
		selDict = {}
		for s in sel:
			name = self.simplex.getObjectName(s)
			if name.endswith("_Extract"):
				nn = name.rsplit("_Extract", 1)[0]
				selDict[nn] = s

		pairDict = {}
		for p in self.simplex.progs:
			for pp in p.pairs:
				pairDict[pp.shape.name] = pp

		# get all common names
		selKeys = set(selDict.iterkeys())
		pairKeys = set(pairDict.iterkeys())
		common = selKeys & pairKeys

		# get those items
		pairs = [pairDict[i] for i in common]

		# Set up the progress bar
		pBar = QProgressDialog("Connecting Shapes", "Cancel", 0, 100, self)
		pBar.setMaximum(len(pairs))

		# Do the extractions
		for pair in pairs:
			c = pair.prog.controller
			c.connectShape(pair.shape, delete=True)

			# ProgressBar
			pBar.setValue(pBar.value() + 1)
			pBar.setLabelText("Connecting:\n{0}".format(pair.shape.name))
			QApplication.processEvents()
			if pBar.wasCanceled():
				return

		pBar.close()

	def shapeMatch(self):
		# make a dict of name:object
		sel = self.simplex.DCC.getSelectedObjects()
		if not sel:
			return
		mesh = sel[0]

		sliderItems = self.uiSliderTREE.getSelectedItems()
		comboItems = self.uiComboTREE.getSelectedItems()

		sliderPairs = coerceToChildType(sliderItems, ProgPair, 'Slider')
		comboPairs = coerceToChildType(comboItems, ProgPair, 'Combo')

		pairs = sliderPairs + comboPairs

		# Set up the progress bar
		pBar = QProgressDialog("Matching Shapes", "Cancel", 0, 100, self)
		pBar.setMaximum(len(pairs))

		# Do the extractions
		for pair in pairs:
			c = pair.prog.controller
			c.connectShape(pair.shape, mesh=mesh)

			# ProgressBar
			pBar.setValue(pBar.value() + 1)
			pBar.setLabelText("Matching:\n{0}".format(pair.shape.name))
			QApplication.processEvents()
			if pBar.wasCanceled():
				return

		pBar.close()

	def shapeClear(self):
		# set the current shape to be equal to the rest shape
		sliderItems = self.uiSliderTREE.getSelectedItems()
		comboItems = self.uiComboTREE.getSelectedItems()

		sliderPairs = coerceToChildType(sliderItems, ProgPair, 'Slider')
		comboPairs = coerceToChildType(comboItems, ProgPair, 'Combo')

		pairs = sliderPairs + comboPairs
		for pair in pairs:
			pair.shape.zeroShape()

	## System level
	def clearCurrentSystem(self):
		# TODO: Properly update the models and trees
		self.simplex = None
		self.toolActions.system = self.simplex
		self.forceSimplexUpdate()

	def setCurrentSystem(self, simplex):
		# TODO: Properly update the models and trees
		self.simplex = simplex
		self.toolActions.simplex = self.simplex
		self.forceSimplexUpdate()

	def loadObject(self, thing):
		if not obj:
			return

		self.uiCurrentSystemCBOX.clear()
		objName = DCC.getObjectName(obj)
		self._currentObject = obj
		self._currentObjectName = objName
		self.uiCurrentObjectTXT.setText(objName)

		ops = DCC.getSimplexOperatorsOnObject(self._currentObject)
		for op in ops:
			js = DCC.getSimplexString(op)
			if not js:
				continue
			d = json.loads(js)
			name = d["systemName"]
			self.uiCurrentSystemCBOX.addItem(name, (self._currentObject, name))

	def currentObjectChanged(self):
		name = str(self.uiCurrentObjectTXT.text())
		if self._currentObjectName == name:
			return

		newObject = self.simplex.DCC.getObjectByName(name)
		self.loadObject(newObject)

	def getSelectedObject(self):
		sel = self.simplex.DCC.getSelectedObjects()
		if not sel:
			return
		newObj = sel[0]
		if not newObj:
			return
		self.loadObject(newObj)

	def newSystem(self):
		if self._currentObject is None:
			QMessageBox.warning(self, 'Warning', 'Must have a current object selection')
			return

		newName, good = QInputDialog.getText(self, "New System", "Enter a name for the new system")
		if not good:
			return

		newName = str(newName)
		if not NAME_CHECK.match(newName):
			message = 'System name can only contain letters and numbers, and cannot start with a number'
			QMessageBox.warning(self, 'Warning', message)
			return

		newSystem = Simplex.buildBlank(self._currentObject, newName)
		self.uiCurrentSystemCBOX.blockSignals(True)
		self.uiCurrentSystemCBOX.addItem(newName)
		self.uiCurrentSystemCBOX.setCurrentIndex(self.uiCurrentSystemCBOX.count()-1)
		self.setCurrentSystem(newSystem)
		self.uiCurrentSystemCBOX.blockSignals(False)

	def renameSystem(self):
		nn, good = QInputDialog.getText(self, "New System Name", "Enter a name for the System", text=self.simplex.name)
		if not good:
			return

		if not NAME_CHECK.match(nn):
			message = 'System name can only contain letters and numbers, and cannot start with a number'
			QMessageBox.warning(self, 'Warning', message)
			return

		sysNames = [str(self.uiCurrentSystemCBOX.itemText(i)) for i in range(self.uiCurrentSystemCBOX.count())]
		nn = getNextName(nn, sysNames)
		self.simplex.name = nn

		idx = self.uiCurrentSystemCBOX.currentIndex()
		self.uiCurrentSystemCBOX.setItemText(idx, nn)

		self.currentSystemChanged(idx)

	def currentSystemChanged(self, idx):
		if idx == -1:
			return
		name = str(self.uiCurrentSystemCBOX.currentText())
		if not name:
			return
		if self.simplex.name == name:
			return

		pBar = QProgressDialog("Loading from Mesh", "Cancel", 0, 100, self)
		system = Simplex.buildFromMesh(self._currentObject, name)
		self.setCurrentSystem(system)
		pBar.close()

	# File Menu
	def importSystemFromFile(self):
		if self._currentObject is None:
			impTypes = ['smpx']
		else:
			impTypes = ['smpx', 'json']

		if blurdev is None:
			pref = QSettings("Blur", "Simplex2")
			defaultPath = str(toPyObject(pref.value('systemImport', os.path.join(os.path.expanduser('~')))))
			path = self.fileDialog("Import Template", defaultPath, impTypes, save=False)
			if not path:
				return
			pref.setValue('systemImport', os.path.dirname(path))
			pref.sync()
		else:
			# Blur Prefs
			pref = blurdev.prefs.find('tools/simplex2')
			defaultPath = pref.restoreProperty('systemImport', os.path.join(os.path.expanduser('~')))
			path = self.fileDialog("Import Template", defaultPath, impTypes, save=False)
			if not path:
				return
			pref.recordProperty('systemImport', os.path.dirname(path))
			pref.save()

		pBar = QProgressDialog("Loading Shapes", "Cancel", 0, 100, self)

		# TODO: Come up with a better list of possibilites for loading
		# simplex files, and make the appropriate methods on the Simplex
		if path.endswith('.smpx'):
			if self._currentObject is None:
				newSystem = Simplex.buildFromAbc(path)
			else:
				self.simplex.loadFromAbcPath(self._currentObject, path)
				newSystem = self.simplex

		elif path.endswith('.json'):
			newSystem = Simplex.buildFromJson(self._currentObject, path)

		pBar.close()

		self.uiCurrentSystemCBOX.blockSignals(True)
		self.uiCurrentSystemCBOX.addItem(newSystem.name)
		self.uiCurrentSystemCBOX.setCurrentIndex(self.uiCurrentSystemCBOX.count()-1)
		self.setCurrentSystem(newSystem)
		self.uiCurrentSystemCBOX.blockSignals(False)

	def fileDialog(self, title, initPath, filters, save=True):
		filters = ["{0} (*.{0})".format(f) for f in filters]
		if not save:
			filters += ["All files (*.*)"]
		filters = ";;".join(filters)

		if save:
			path, _ = QtCompat.QFileDialog.getSaveFileName(self, title, initPath, filters)
		else:
			path, _ = QtCompat.QFileDialog.getOpenFileName(self, title, initPath, filters)

		if not path:
			return ''

		if not save and not os.path.exists(path):
			return ''

		return path

	def exportSystemTemplate(self):
		if self._currentObject is None:
			QMessageBox.warning(self, 'Warning', 'Must have a current object selection')
			return

		if blurdev is None:
			pref = QSettings("Blur", "Simplex2")
			defaultPath = str(toPyObject(pref.value('systemExport', os.path.join(os.path.expanduser('~')))))
			path = self.fileDialog("Export Template", defaultPath, ["smpx", "json"], save=False)
			if not path:
				return
			pref.setValue('systemExport', os.path.dirname(path))
			pref.sync()
		else:
			# Blur Prefs
			pref = blurdev.prefs.find('tools/simplex2')
			defaultPath = pref.restoreProperty('systemExport', os.path.join(os.path.expanduser('~')))
			path = self.fileDialog("Export Template", defaultPath, ["smpx", "json"], save=True)
			if not path:
				return
			pref.recordProperty('systemExport', os.path.dirname(path))
			pref.save()

		if path.endswith('.smpx'):
			pBar = QProgressDialog("Exporting smpx File", "Cancel", 0, 100, self)
			self.simplex.exportAbc(path, pBar)
			pBar.close()
		elif path.endswith('.json'):
			dump = self.simplex.dump()
			with open(path, 'w') as f:
				f.write(dump)

	# Edit Menu
	def hideRedundant(self):
		check = self.uiHideRedundantACT.isChecked()
		comboModel = self.uiComboTREE.model()
		comboModel.filterShapes = check
		comboModel.invalidateFilter()
		sliderModel = self.uiSliderTREE.model()
		sliderModel.doFilter = check
		sliderModel.invalidateFilter()

	def setSliderRange(self):
		self._sliderMul = 2.0 if self.uiDoubleSliderRangeACT.isChecked() else 1.0
		for slider in self.simplex.sliders:
			slider.setRange(self._sliderMul)

	# Isolation
	def sliderTreeExitIsolate(self):
		self.sliderIsolate([])
		self.uiSliderExitIsolateBTN.hide()

	def comboTreeExitIsolate(self):
		self.comboIsolate([])
		self.uiComboExitIsolateBTN.hide()












class SliderContextMenu(QMenu):
	def __init__(self, tree, parent=None):
		super(SliderContextMenu, self).__init__(parent)
		self._tree = tree

		self.uiAddGroupACT = self.addAction("Add Group")
		self.uiAddSliderACT = self.addAction("Add Slider")
		self.uiAddShapeACT = self.addAction("Add Shape")

		self.addSeparator()

		self.uiComboActiveACT = self.addAction("Combo Active")
		self.uiComboSelectedACT = self.addAction("Combo Selected")

		self.addSeparator()

		self.uiDeleteACT = self.addAction("Delete Selected")

		self.addSeparator()

		self.uiZeroACT = self.addAction("Zero Selected")
		self.uiZeroAllACT = self.addAction("Zero All")

		self.addSeparator()

		self.uiExtractShapeACT = self.addAction("Extract Shape")
		self.uiConnectShapeACT = self.addAction("Connect Shape")
		self.uiMatchShapeACT = self.addAction("Match Shape")
		self.uiClearShapeACT = self.addAction("Clear Shape")

		self.addSeparator()

		self.uiIsolateSelectedACT = self.addAction("Isolate Selected")
		self.uiExitIsolationACT = self.addAction("Exit Isolation")

		# Add the custom DCC menu itesm
		customSliderMenu(self)

	def tree(self):
		return self._tree

class ComboContextMenu(QMenu):
	def __init__(self, tree, parent=None):
		super(ComboContextMenu, self).__init__(parent)
		self._tree = tree

		self.uiAddGroupACT = self.addAction("Add Group")
		self.uiAddShapeACT = self.addAction("Add Shape")

		self.addSeparator()

		self.uiDeleteACT = self.addAction("Delete Selected")

		self.addSeparator()

		self.uiSetValsACT = self.addAction("Set Selected Values")

		self.addSeparator()

		self.uiExtractShapeACT = self.addAction("Extract Shape")
		self.uiConnectShapeACT = self.addAction("Connect Shape")
		self.uiMatchShapeACT = self.addAction("Match Shape")
		self.uiClearShapeACT = self.addAction("Clear Shape")

		self.addSeparator()

		self.uiIsolateSelectedACT = self.addAction("Isolate Selected")
		self.uiExitIsolationACT = self.addAction("Exit Isolation")

		# Add the custom DCC menu itesm
		customComboMenu(self)

	def tree(self):
		return self._tree






def _test():
	app = QApplication(sys.argv)
	d = SimplexDialog()
	d.show()
	sys.exit(app.exec_())

if __name__ == '__main__':
	_test()


