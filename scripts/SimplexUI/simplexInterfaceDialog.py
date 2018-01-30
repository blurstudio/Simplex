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
#pylint: disable=too-few-public-methods,superfluous-parens
#pylint: disable=unused-variable,unused-argument,too-many-public-methods
#pylint: disable=protected-access,too-many-statements,invalid-name,no-self-use
import os, sys, re, json, copy, weakref
from functools import wraps


# This module imports QT from PyQt4, PySide or PySide2
# Depending on what's available
from Qt import QtCompat
from Qt.QtCore import Slot, QModelIndex
from Qt.QtCore import Qt, QItemSelection, QSettings
from Qt.QtWidgets import QMessageBox, QInputDialog, QFileDialog, QMenu, QApplication
from Qt.QtWidgets import QMainWindow, QProgressDialog

from utils import toPyObject, getUiFile, getNextName, singleShot

from dragFilter import DragFilter

#from interface import (System, Combo, Slider, ComboPair, STACK, ToolActions,
					   #ProgPair, Progression, DISPATCH, undoContext, Simplex)

from interfaceModel import (Falloff, Shape, ProgPair, Progression, Slider, ComboPair,
							Combo, Group, Simplex, SimplexModel, SimplexFilterModel,
							ComboFilterModel, SliderFilterModel)

from interface import customSliderMenu, customComboMenu, ToolActions, undoContext

try:
	# This module is unique to Blur Studio
	import blurdev
except ImportError:
	blurdev = None

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

		self.system = None

		self._sliderMul = 1.0
		self._itemMap = {}
		self._sliderTreeMap = {}
		self._comboTreeMap = {}

		self._sliderDrag = None
		self._comboDrag = None

		self.uiSliderExitIsolateBTN.hide()
		self.uiComboExitIsolateBTN.hide()

		self.makeConnections()
		self.connectMenus()

		self.uiSettingsGRP.setChecked(False)

		self.toolActions = ToolActions(self, self.system)

		if self.system.DCC.program == "dummy":
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
		rev = self.system.getRevision()
		data = self.system.stack.getRevision(rev)
		if data is not None:
			self.storeExpansion(self.uiSliderTREE)
			self.storeExpansion(self.uiComboTREE)
			self.pairExpansion(self.system.simplex, data[0])
			self.system.setSimplex(data[0])
			self.forceSimplexUpdate()
			self.setItemExpansion(self.uiSliderTREE)
			self.setItemExpansion(self.uiComboTREE)

	# UI Setup
	def makeConnections(self):
		# Setup Trees!
		sliderModel = SimplexModel(self.system, 'Slider', None)
		sliderProxModel = SliderFilterModel()
		sliderProxModel.setSourceModel(sliderModel)
		self.uiSliderTREE.setModel(sliderProxModel)
		self.uiSliderTREE.setColumnWidth(1, 50)
		self.uiSliderTREE.setColumnWidth(2, 20)
		self.uiSliderFilterLINE.editingFinished.connect(self.sliderStringFilter)
		self.uiSliderFilterClearBTN.clicked.connect(self.uiSliderFilterLINE.clear)
		self.uiSliderFilterClearBTN.clicked.connect(self.sliderStringFilter)

		comboModel = SimplexModel(self.system, 'Combo', None)
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

		# collapse/expand
		self.uiSliderTREE.expanded.connect(self.expandSliderTree)
		self.uiSliderTREE.collapsed.connect(self.collapseSliderTree)
		self.uiComboTREE.expanded.connect(self.expandComboTree)
		self.uiComboTREE.collapsed.connect(self.collapseComboTree)

		# Middle-click Drag
		sliderDrag = DragFilter(self.uiSliderTREE.viewport())
		self._sliderDrag = weakref.ref(sliderDrag)
		self.uiSliderTREE.viewport().installEventFilter(sliderDrag)
		sliderDrag.dragPressed.connect(self.sliderDragStart)
		sliderDrag.dragReleased.connect(self.sliderDragStop)
		sliderDrag.dragTick.connect(self.sliderDragTick)

		comboDrag = DragFilter(self.uiComboTREE.viewport())
		self._comboDrag = weakref.ref(comboDrag)
		self.uiComboTREE.viewport().installEventFilter(comboDrag)
		comboDrag.dragPressed.connect(self.comboDragStart)
		comboDrag.dragReleased.connect(self.comboDragStop)
		comboDrag.dragTick.connect(self.comboDragTick)

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
		self.uiDeleteSystemBTN.clicked.connect(self.deleteSystem)
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


	def collapseComboTree(self, index):
		self.toggleTree(index, self.uiComboTREE, False)

	def collapseSliderTree(self, index):
		self.toggleTree(index, self.uiSliderTREE, False)

	def comboDragStart(self):
		self.system.DCC.undoOpen()

	def comboDragStop(self):
		self.system.DCC.undoClose()

	def comboDragTick(self, ticks, mul):
		self.dragTick(self.uiComboTREE, ticks, mul)

	def comboStringFilter(self):
		filterString = str(self.uiComboFilterLINE.text())
		comboModel = self.uiComboTREE.model()
		comboModel.filterString = str(filterString)
		comboModel.invalidateFilter()

	@Slot()
	@stackable
	def comboTreeDelete(self):
		delItems = self._getDeleteItems(self.uiComboTREE)
		typedDelItems = self.partitionItemsByType(delItems)
		for itype, ditems in typedDelItems.iteritems():
			if itype == C_GROUP_TYPE:
				self.deleteComboGroupItems(ditems)
			elif itype == C_SHAPE_TYPE:
				self.deleteProgPairItems(ditems)
			elif itype == C_COMBO_TYPE:
				self.deleteComboItems(ditems)
			elif itype == C_SLIDER_TYPE:
				self.deleteComboPairItems(ditems)
		self.buildItemMap()

	def comboTreeExitIsolate(self):
		self.comboIsolate([])
		self.uiComboExitIsolateBTN.hide()

	def expandComboTree(self, index):
		self.toggleTree(index, self.uiComboTREE, True)

	def expandSliderTree(self, index):
		self.toggleTree(index, self.uiSliderTREE, True)

	def exportSystemTemplate(self):
		if self._currentObject is None:
			QMessageBox.warning(self, 'Warning', 'Must have a current object selection')
			return

		if blurdev is None:
			pref = QSettings("Blur", "Simplex2")
			defaultPath = str(toPyObject(pref.value('systemExport', os.path.join(os.path.expanduser('~')))))
			path, ftype = self.fileDialog("Export Template", defaultPath, ["smpx", "json"], save=False)
			if not path:
				return
			pref.setValue('systemExport', os.path.dirname(path))
			pref.sync()
		else:
			# Blur Prefs
			pref = blurdev.prefs.find('tools/simplex2')
			defaultPath = pref.restoreProperty('systemExport', os.path.join(os.path.expanduser('~')))
			path, ftype = self.fileDialog("Export Template", defaultPath, ["smpx", "json"], save=True)
			if not path:
				return
			pref.recordProperty('systemExport', os.path.dirname(path))
			pref.save()

		if "(*.smpx)" in ftype:
			if not path.endswith(".smpx"):
				path = path + ".smpx"
			pBar = QProgressDialog("Exporting smpx File", "Cancel", 0, 100, self)
			self.system.exportAbc(path, pBar)
			pBar.close()
		elif "(*.json)" in ftype:
			if not path.endswith(".json"):
				path = path + ".json"
			dump = self.system.simplex.dump()
			with open(path, 'w') as f:
				f.write(dump)

	def hideRedundant(self):
		check = self.uiHideRedundantACT.isChecked()
		comboModel = self.uiComboTREE.model()
		comboModel.filterShapes = check
		comboModel.invalidateFilter()
		sliderModel = self.uiSliderTREE.model()
		sliderModel.doFilter = check
		sliderModel.invalidateFilter()

	def importSystemFromFile(self):
		if self._currentObject is None:
			impTypes = ['smpx']
		else:
			impTypes = ['smpx', 'json']

		if blurdev is None:
			pref = QSettings("Blur", "Simplex2")
			defaultPath = str(toPyObject(pref.value('systemImport', os.path.join(os.path.expanduser('~')))))
			path, ftype = self.fileDialog("Import Template", defaultPath, impTypes, save=False)
			if not path:
				return
			pref.setValue('systemImport', os.path.dirname(path))
			pref.sync()
		else:
			# Blur Prefs
			pref = blurdev.prefs.find('tools/simplex2')
			defaultPath = pref.restoreProperty('systemImport', os.path.join(os.path.expanduser('~')))
			path, ftype = self.fileDialog("Import Template", defaultPath, impTypes, save=False)
			if not path:
				return
			pref.recordProperty('systemImport', os.path.dirname(path))
			pref.save()

		pBar = QProgressDialog("Loading Shapes", "Cancel", 0, 100, self)

		if "(*.smpx)" in ftype:
			newSystem = System()
			if self._currentObject is None:
				obj = newSystem.buildBaseAbc(path)
				self.loadObject(obj)
			else:
				obj = self._currentObject
			newSystem.buildFromAbc(obj, path, pBar)

		elif "(*.json)" in ftype:
			newSystem = System()
			newSystem.buildFromJson(self._currentObject, path, pBar)

		pBar.close()

		self.uiCurrentSystemCBOX.blockSignals(True)
		self.uiCurrentSystemCBOX.addItem(newSystem.name)
		self.uiCurrentSystemCBOX.setCurrentIndex(self.uiCurrentSystemCBOX.count()-1)
		self.setCurrentSystem(newSystem)
		self.uiCurrentSystemCBOX.blockSignals(False)

	def newActiveCombo(self):
		root = self.uiSliderTREE.model().sourceModel().invisibleRootItem()
		queue = [root]
		sliderItems = []
		while queue:
			item = queue.pop()
			# ignore any items without children
			if not item.hasChildren():
				continue

			for row in xrange(item.rowCount()):
				queue.append(item.child(row, 0))

			thing = toPyObject(item.data(THING_ROLE))
			if isinstance(thing, Slider):
				if thing.value != 0.0:
					sliderItems.append(item)
		self.newCombo(sliderItems)

	def newComboGroup(self):
		newName, good = QInputDialog.getText(self, "New Group", "Enter a name for the new group", text="Group")
		if not good:
			return
		self.createGroup(str(newName), self.uiComboTREE)

	def newComboShape(self):
		sel = self.getSelectedItems(self.uiComboTREE)
		comboItems = self.filterItemsByType(sel, C_COMBO_TYPE)
		if not comboItems:
			return

		comboItem = comboItems[0]
		tp = self.searchTreeForType(self.uiComboTREE, C_SHAPE_PAR_TYPE, comboItem)
		parItem = tp[0]
		comboThing = toPyObject(comboItem.data(THING_ROLE))
		return self.newShape(parItem, comboThing, self.uiComboTREE)

	def newSelectedCombo(self):
		selItems = self.getSelectedItems(self.uiSliderTREE)
		selItems = [i for i in selItems if i.column() == 0]
		sliderItems = []
		for item in selItems:
			thing = toPyObject(item.data(THING_ROLE))
			if isinstance(thing, Slider):
				sliderItems.append(item)
		self.newCombo(sliderItems)

	@Slot()
	@stackable
	def newSlider(self):
		# get the new slider name
		newName, good = QInputDialog.getText(self, "New Slider", "Enter a name for the new slider", text="Slider")
		if not good:
			return

		newName = str(newName)
		sliderNames = [i.name for i in self.system.simplex.sliders]
		newName = getNextName(newName, sliderNames)

		# get the parent group
		sel = self.getSelectedItems(self.uiSliderTREE)
		if sel:
			groupItem = self.searchParentsForType(sel[0], S_GROUP_TYPE)
		else:
			groupItem = QStandardItem()

		if not groupItem.index().isValid():
			groupItem, group = self.createGroup("{0}_GROUP".format(newName), self.uiSliderTREE)

		self.createSlider(newName, groupItem)

	def newSliderGroup(self):
		newName, good = QInputDialog.getText(self, "New Group", "Enter a name for the new group", text="Group")
		if not good:
			return
		selItems = self.getSelectedItems(self.uiSliderTREE)
		selItems = [i for i in selItems if i.column() == 0]
		selItems = self.filterItemsByType(selItems, S_SLIDER_TYPE)

		self.createGroup(str(newName), self.uiSliderTREE, selItems)

	def newSliderShape(self):
		sel = self.getSelectedItems(self.uiSliderTREE)
		pars = self.filterItemsByType(sel, S_SLIDER_TYPE)
		if not pars:
			return
		parItem = pars[0]
		parThing = toPyObject(parItem.data(THING_ROLE))
		return self.newShape(parItem, parThing, self.uiSliderTREE)

	def populateComboRequirements(self):
		selItems = self.getSelectedItems(self.uiSliderTREE)
		selItems = [i for i in selItems if i]
		selItems = [i for i in selItems if i.column() == 0]
		sliderItems = []
		for sel in selItems:
			sliderItems.append(self.searchParentsForType(sel, S_SLIDER_TYPE))

		things = [toPyObject(i.data(THING_ROLE)) for i in sliderItems]
		comboModel = self.uiComboTREE.model()
		comboModel.requires = things

		if comboModel.filterRequiresAll or comboModel.filterRequiresAny or comboModel.filterRequiresOnly:
			comboModel.invalidateFilter()

	def selectCtrl(self):
		self.system.selectCtrl()

	def selectSliders(self):
		selItems = self.getSelectedItems(self.uiComboTREE)
		selItems = [i for i in selItems if i.column() == 0]
		comboItems = []
		for item in selItems:
			ci = self.searchParentsForType(item, C_COMBO_TYPE)
			if ci.index().isValid():
				comboItems.append(ci)

		if not comboItems:
			return

		comboThings = [toPyObject(i.data(THING_ROLE)) for i in comboItems]
		comboThings = list(set(comboThings))

		sliderItems = []
		for thing in comboThings:
			for pair in thing.pairs:
				for si in self._sliderTreeMap[pair.slider]:
					sliderItems.append(si)

		self.setSelection(self.uiSliderTREE, sliderItems)

	def setAllComboRequirement(self):
		for item in (self.uiComboDependAnyCHK, self.uiComboDependOnlyCHK):
			if item.isChecked():
				item.blockSignals(True)
				item.setChecked(False)
				item.blockSignals(False)
		self.enableComboRequirements()

	def setAnyComboRequirement(self):
		for item in (self.uiComboDependAllCHK, self.uiComboDependOnlyCHK):
			if item.isChecked():
				item.blockSignals(True)
				item.setChecked(False)
				item.blockSignals(False)
		self.enableComboRequirements()

	def setOnlyComboRequirement(self):
		for item in (self.uiComboDependAnyCHK, self.uiComboDependAllCHK):
			if item.isChecked():
				item.blockSignals(True)
				item.setChecked(False)
				item.blockSignals(False)
		self.enableComboRequirements()

	def setSliderRange(self):
		self._sliderMul = 2.0 if self.uiDoubleSliderRangeACT.isChecked() else 1.0
		self.system.setAllSliderRanges(self._sliderMul)

	@Slot()
	@stackable
	def setSliderVals(self):
		selItems = self.getSelectedItems(self.uiComboTREE)
		selItems = [i for i in selItems if i.column() == 0]
		comboItems = []
		for item in selItems:
			ci = self.searchParentsForType(item, C_COMBO_TYPE)
			if ci.index().isValid():
				comboItems.append(ci)

		if not comboItems:
			return

		comboThings = [toPyObject(i.data(THING_ROLE)) for i in comboItems]
		comboThings = list(set(comboThings))

		self.zeroAllSliders()
		values = []
		sliders = []
		for thing in comboThings:
			for pair in thing.pairs:
				sliderItems = self._sliderTreeMap[pair.slider]
				sliders.append(pair.slider)
				values.append(pair.value)
				for si in sliderItems:
					par = si.parent()
					valueItem = par.child(si.row(), SLIDER_VALUE_COL)
					valueItem.setData(pair.value, Qt.EditRole)
		self.system.setSlidersWeights(sliders, values)

	def shapeClear(self):
		# set the current shape to be equal to the rest shape
		shapeIndexes = self.getFilteredChildSelection(self.uiSliderTREE, S_SHAPE_TYPE)
		shapeIndexes.extend(self.getFilteredChildSelection(self.uiComboTREE, C_SHAPE_TYPE))
		for si in shapeIndexes:
			progPair = toPyObject(si.model().data(si, THING_ROLE))
			if not progPair.shape.isRest:
				self.system.zeroShape(progPair.shape)

	def shapeConnect(self):
		sliderIndexes = self.getSelectedIndexes(self.uiSliderTREE, filtered=False)
		sliderIndexes = [i for i in sliderIndexes if i.column() == 0]
		sliderShapes = []
		for i in sliderIndexes:
			ss = self.searchTreeForTypeIndex(self.uiSliderTREE, S_SHAPE_TYPE, parIdx=i, filtered=False)
			sliderShapes.extend(ss)
		self.shapeConnectIndexes(sliderShapes)

		comboIndexes = self.getSelectedIndexes(self.uiComboTREE, filtered=False)
		comboIndexes = [i for i in comboIndexes if i.column() == 0]
		comboShapes = []
		for i in comboIndexes:
			ss = self.searchTreeForTypeIndex(self.uiComboTREE, C_SHAPE_TYPE, parIdx=i, filtered=False)
			comboShapes.extend(ss)

		self.comboConnectIndexes(comboShapes)

	def shapeConnectAll(self):
		# Connect objects by name and remove the DCC meshes
		allShapeIndexes = self.searchTreeForTypeIndex(self.uiSliderTREE, S_SHAPE_TYPE, filtered=False)
		allCShapeIndexes = self.searchTreeForTypeIndex(self.uiComboTREE, C_SHAPE_TYPE, filtered=False)
		allShapeIndexes.extend(allCShapeIndexes)
		self.shapeConnectIndexes(allShapeIndexes)

	def shapeConnectScene(self):
		# make a dict of name:object
		sel = self.system.getSelectedObjects()
		selDict = {}
		for s in sel:
			name = self.system.getObjectName(s)
			if name.endswith("_Extract"):
				nn = name.rsplit("_Extract", 1)[0]
				selDict[nn] = s

		# make a dict of name:item

		# Should I take filtering into consideration
		#sliderShapeIndexes = getFilteredChildSelection(self.uiSliderTREE, S_SHAPE_TYPE)
		#comboShapeIndexes = getFilteredChildSelection(self.uiComboTREE, C_SHAPE_TYPE)
		# Or not?
		sliderShapeIndexes = self.searchTreeForTypeIndex(self.uiSliderTREE, S_SHAPE_TYPE, filtered=False)
		comboShapeIndexes = self.searchTreeForTypeIndex(self.uiComboTREE, C_SHAPE_TYPE, filtered=False)

		shapeIndexes = sliderShapeIndexes + comboShapeIndexes

		shapeDict = {}
		for si in shapeIndexes:
			pp = toPyObject(si.model().data(si, THING_ROLE))
			shapeDict[pp.shape.name] = si

		# get all common names
		selKeys = set(selDict.iterkeys())
		shapeKeys = set(shapeDict.iterkeys())
		common = selKeys & shapeKeys

		# get those items
		items = [shapeDict[i] for i in common]

		# and connect
		self.shapeConnectIndexes(items)

	def shapeExtract(self):
		# Create meshes that are possibly live-connected to the shapes
		live = self.uiLiveShapeConnectionACT.isChecked()

		shapeIndexes = self.getFilteredChildSelection(self.uiSliderTREE, S_SHAPE_TYPE)
		comboIndexes = self.getFilteredChildSelection(self.uiComboTREE, C_SHAPE_TYPE)

		# Build lists of things to extract so we can get a good count
		sliderShapes = []
		for i in shapeIndexes:
			if not i.isValid():
				continue
			progPair = toPyObject(i.model().data(i, THING_ROLE))
			if not progPair.shape.isRest:
				sliderShapes.append(progPair.shape)

		comboShapes = []
		for i in comboIndexes:
			if not i.isValid():
				continue
			progPair = toPyObject(i.model().data(i, THING_ROLE))
			combo = progPair.prog.parent
			if not progPair.shape.isRest:
				comboShapes.append((combo, progPair.shape))

		# Set up the progress bar
		pBar = QProgressDialog("Loading Shapes", "Cancel", 0, 100, self)
		pBar.setMaximum(len(sliderShapes) + len(comboShapes))

		# Do the extractions
		offset = 10
		for shape in sliderShapes:
			self.system.extractShape(shape, live=live, offset=offset)
			offset += 5

			# ProgressBar
			pBar.setValue(pBar.value() + 1)
			pBar.setLabelText("Extracting:\n{0}".format(shape.name))
			QApplication.processEvents()
			if pBar.wasCanceled():
				return

		for combo, shape in comboShapes:
			self.system.extractComboShape(combo, shape, live=live, offset=offset)
			offset += 5

			# ProgressBar
			pBar.setValue(pBar.value() + 1)
			pBar.setLabelText("Extracting:\n{0}".format(shape.name))
			QApplication.processEvents()
			if pBar.wasCanceled():
				return

		pBar.close()

	def shapeMatch(self):
		# Connect objects by selection and leave the DCC meshes alone
		sel = self.system.getSelectedObjects()
		if not sel:
			return
		mesh = sel[0]

		shapeIndexes = self.getFilteredChildSelection(self.uiSliderTREE, S_SHAPE_TYPE)
		if shapeIndexes:
			for si in shapeIndexes:
				progPair = toPyObject(si.model().data(si, THING_ROLE))
				if not progPair.shape.isRest:
					self.system.connectShape(progPair.shape, mesh=mesh)

		comboIndexes = self.getFilteredChildSelection(self.uiComboTREE, C_SHAPE_TYPE)
		if comboIndexes:
			for ci in comboIndexes:
				progPair = toPyObject(ci.model().data(ci, THING_ROLE))
				if not progPair.shape.isRest:
					combo = progPair.prog.parent
					self.system.connectComboShape(combo, progPair.shape, mesh=mesh)

	def sliderDragStart(self):
		self.system.DCC.undoOpen()

	def sliderDragStop(self):
		self.system.DCC.undoClose()

	def sliderDragTick(self, ticks, mul):
		self.dragTick(self.uiSliderTREE, ticks, mul)

	def sliderStringFilter(self):
		filterString = str(self.uiSliderFilterLINE.text())
		sliderModel = self.uiSliderTREE.model()
		sliderModel.filterString = str(filterString)
		sliderModel.invalidateFilter()

	@Slot()
	@stackable
	def sliderTreeDelete(self):
		delItems = self._getDeleteItems(self.uiSliderTREE)
		typedDelItems = self.partitionItemsByType(delItems)
		for itype, ditems in typedDelItems.iteritems():
			if itype == S_GROUP_TYPE:
				self.deleteSliderGroupItems(ditems)
			elif itype == S_SLIDER_TYPE:
				self.deleteSliderItems(ditems)
			elif itype == S_SHAPE_TYPE:
				self.deleteProgPairItems(ditems)
		self.buildItemMap()

	def sliderTreeExitIsolate(self):
		self.sliderIsolate([])
		self.uiSliderExitIsolateBTN.hide()

	def unifyComboSelection(self):
		mods = QApplication.keyboardModifiers()
		if not (mods & (Qt.ControlModifier | Qt.ShiftModifier)):
			sliderSelModel = self.uiSliderTREE.selectionModel()
			sliderSelModel.blockSignals(True)
			try:
				sliderSelModel.clearSelection()
			finally:
				sliderSelModel.blockSignals(False)
			self.uiSliderTREE.viewport().update()

	def unifySliderSelection(self):
		mods = QApplication.keyboardModifiers()
		if not (mods & (Qt.ControlModifier | Qt.ShiftModifier)):
			comboSelModel = self.uiComboTREE.selectionModel()
			comboSelModel.blockSignals(True)
			try:
				comboSelModel.clearSelection()
			finally:
				comboSelModel.blockSignals(False)
			self.uiComboTREE.viewport().update()

	@Slot()
	@stackable
	def zeroAllSliders(self):
		root = self.uiSliderTREE.model().sourceModel().invisibleRootItem()
		queue = [root]
		sliders = []
		while queue:
			item = queue.pop()
			# having this check here ignores shapes
			if not item.hasChildren():
				continue
			for row in xrange(item.rowCount()):
				queue.append(item.child(row, 0))

			thing = toPyObject(item.data(THING_ROLE))
			if isinstance(thing, Slider):
				thing.value = 0.0
				sliders.append(thing)
				par = item.parent()
				valueItem = par.child(item.row(), SLIDER_VALUE_COL)
				valueItem.setData(0.0, Qt.EditRole)

		values = [0.0] * len(sliders)
		self.system.setSlidersWeights(sliders, values)

	@Slot()
	@stackable
	def zeroSelectedSliders(self):
		sel = self.uiSliderTREE.selectedIndexes()
		model = self.uiSliderTREE.model()
		sliders = []
		for idx in sel:
			isVal = toPyObject(model.data(idx, VALUE_ROLE))
			if not isVal:
				continue
			thing = toPyObject(model.data(idx, THING_ROLE))
			if isinstance(thing, Slider):
				sliders.append(thing)
				thing.value = 0.0
				model.setData(idx, 0.0, Qt.EditRole)

		values = [0.0] * len(sliders)
		self.system.setSlidersWeights(sliders, values)




	def currentObjectChanged(self):
		name = str(self.uiCurrentObjectTXT.text())
		if self._currentObjectName == name:
			return

		newObject = self.system.getObjectByName(name)
		self.loadObject(newObject)

	def getSelectedObject(self):
		sel = self.system.getSelectedObjects()
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
		if re.match(r'^[A-Za-z][A-Za-z0-9_]*$', newName) is None:
			message = 'System name can only contain letters and numbers, and cannot start with a number'
			QMessageBox.warning(self, 'Warning', message)
			return

		newSystem = System()
		newSystem.createBlank(self._currentObject, newName)
		self.uiCurrentSystemCBOX.blockSignals(True)
		self.uiCurrentSystemCBOX.addItem(newName)
		self.uiCurrentSystemCBOX.setCurrentIndex(self.uiCurrentSystemCBOX.count()-1)
		self.setCurrentSystem(newSystem)
		self.uiCurrentSystemCBOX.blockSignals(False)

	def deleteSystem(self):
		pass #TODO

	def renameSystem(self):
		nn, good = QInputDialog.getText(self, "New System Name", "Enter a name for the System", text=self.system.name)
		if not good:
			return
		# TODO ... check *ALL* system names
		sysNames = [str(self.uiCurrentSystemCBOX.itemText(i)) for i in range(self.uiCurrentSystemCBOX.count())]
		nn = getNextName(nn, sysNames)
		self.system.renameSystem(str(nn))

		idx = self.uiCurrentSystemCBOX.currentIndex()
		self.uiCurrentSystemCBOX.setItemText(idx, nn)

		self.currentSystemChanged(idx)

		# for tree in [self.uiSliderTREE, self.uiComboTREE]:
		#	model = tree.model().sourceModel()
		#	topRoot = model.invisibleRootItem()
		#	child = topRoot.child(0,0)
		#	child.setData(str(nn), Qt.DisplayRole)

	def forceSimplexUpdate(self):
		self.buildTrees()
		self.buildFalloffLists()

	@Slot(int)
	@stackable
	def currentSystemChanged(self, idx):
		self.clearCurrentSystem()

		if idx == -1:
			return
		name = str(self.uiCurrentSystemCBOX.currentText())
		if not name:
			return
		pBar = QProgressDialog("Loading from Mesh", "Cancel", 0, 100, self)

		system = System()
		system.loadFromMesh(self._currentObject, name, pBar)
		self.setCurrentSystem(system)
		pBar.close()






	# system level





# LOAD THE UI base classes
class SimplexDialogOLD(QMainWindow):
	def __init__(self, parent=None, dispatch=None):
		super(SimplexDialog, self).__init__(parent)
		QtCompat.loadUi(getUiFile(__file__), self)

		self._sliderMenu = None
		self._comboMenu = None
		self._currentObject = None
		self._currentObjectName = None

		# Make sure to connect the dispatcher to the undo control
		# But *Don't* keep the reference to the dispatcher in-file
		# That means it'll stick around
		self.dispatch = None
		if dispatch is not None:
			self.dispatch = weakref.ref(dispatch)
			dispatch.undo.connect(self.handleUndo)
			dispatch.redo.connect(self.handleUndo)
			dispatch.beforeNew.connect(self.newScene)
			dispatch.beforeOpen.connect(self.newScene)

		self.system = None

		self._sliderMul = 1.0
		self._itemMap = {}
		self._sliderTreeMap = {}
		self._comboTreeMap = {}

		self._sliderDrag = None
		self._comboDrag = None

		self.uiSliderExitIsolateBTN.hide()
		self.uiComboExitIsolateBTN.hide()

		self.makeConnections()
		self.connectMenus()

		self.uiSettingsGRP.setChecked(False)
		self.system = System() #null system

		self.toolActions = ToolActions(self, self.system)

		if self.system.DCC.program == "dummy":
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
		rev = self.system.getRevision()
		data = self.system.stack.getRevision(rev)
		if data is not None:
			self.storeExpansion(self.uiSliderTREE)
			self.storeExpansion(self.uiComboTREE)
			self.pairExpansion(self.system.simplex, data[0])
			self.system.setSimplex(data[0])
			self.forceSimplexUpdate()
			self.setItemExpansion(self.uiSliderTREE)
			self.setItemExpansion(self.uiComboTREE)

	def closeEvent(self, e):
		self.shutdown()
		super(SimplexDialog, self).closeEvent(e)

	def __del__(self):
		self.shutdown()

	def shutdown(self):
		if self._sliderDrag is not None:
			sliderDrag = self._sliderDrag()
			if sliderDrag is not None:
				self.uiSliderTREE.viewport().removeEventFilter(sliderDrag)
		if self._comboDrag is not None:
			comboDrag = self._comboDrag()
			if comboDrag is not None:
				self.uiComboTREE.viewport().removeEventFilter(comboDrag)
		if self.dispatch is not None:
			dispatch = self.dispatch()
			if dispatch is not None:
				cnxPairs = [
					(dispatch.undo, self.handleUndo),
					(dispatch.redo, self.handleUndo),
					(dispatch.beforeNew, self.newScene),
					(dispatch.beforeOpen, self.newScene),
				]
				for sig, slot in cnxPairs:
					try:
						sig.disconnect(slot)
					except RuntimeError:
						pass
						#print "Runtime Disconnect Fail:", sig, slot
					except TypeError:
						pass
						#print "Type Disconnect Fail:", sig, slot

	def blurShutdown(self):
		blurdev.core.aboutToClearPaths.disconnect(self.blurShutdown)
		self.shutdown()
		self.close()

	def sliderIsolate(self, sliderNames):
		sliderModel = self.uiSliderTREE.model()
		sliderModel.isolateList = sliderNames
		sliderModel.invalidateFilter()

	def comboIsolate(self, comboNames):
		comboModel = self.uiComboTREE.model()
		comboModel.isolateList = comboNames
		comboModel.invalidateFilter()

	def sliderTreeIsolate(self):
		items = self.getSelectedItems(self.uiSliderTREE)
		isoList = []
		for item in items:
			isoList.append(str(toPyObject(item.data(Qt.DisplayRole))))
		self.sliderIsolate(isoList)
		self.uiSliderExitIsolateBTN.show()

	def comboTreeIsolate(self):
		items = self.getSelectedItems(self.uiComboTREE)
		isoList = []
		for item in items:
			isoList.append(str(toPyObject(item.data(Qt.DisplayRole))))
		self.comboIsolate(isoList)
		self.uiComboExitIsolateBTN.show()

	# Shape and combo Extraction and connection
	def getFilteredChildSelection(self, tree, role):
		selIdxs = self.getSelectedIndexes(tree, filtered=True)
		selIdxs = [i for i in selIdxs if i.column() == 0]
		typDict = {}
		for idx in selIdxs:
			typ = toPyObject(idx.model().data(idx, TYPE_ROLE))
			if typ is not None:
				typDict.setdefault(typ, []).append(idx)

		if tree == self.uiSliderTREE:
			cutoff = S_SLIDER_TYPE
		elif tree == self.uiComboTREE:
			cutoff = C_COMBO_TYPE
		else:
			raise RuntimeError("BAD TREE PASSED")

		shapeIdxs = []
		for typ in sorted(typDict.keys()):
			idxs = typDict[typ]
			if typ > role:
				ext = [self.searchParentsForTypeIndex(idx, role) for idx in idxs]
				shapeIdxs.extend(ext)
			elif typ == role:
				shapeIdxs.extend(idxs) # It's a proper selection, easy peasy
			elif typ < role:
				if typ < cutoff:
					# if the parent is above the filtering cutoff for the tree
					# search filtered down to that cutoff
					filtSearch = []
					for idx in idxs:
						filtSearch.extend(self.searchTreeForTypeIndex(tree, cutoff, idx, filtered=True))
				else:
					filtSearch = idxs
				# Then search unfiltered past the cutoff
				unfiltSearch = [i.model().mapToSource(i) for i in filtSearch]
				for idx in unfiltSearch:
					shapeIdxs.extend(self.searchTreeForTypeIndex(tree, role, idx, filtered=False))
		shapeIdxs = list(set(shapeIdxs)) #TODO Possibly reorder by system list
		return shapeIdxs

	def shapeConnectIndexes(self, indexes):
		# sort shapes
		comboIndexes = []
		for index in indexes:
			progPair = toPyObject(index.model().data(index, THING_ROLE))
			par = progPair.prog.parent
			if isinstance(par, Combo):
				comboIndexes.append(index)

			elif isinstance(par, Slider):
				if not progPair.shape.isRest:
					self.system.connectShape(progPair.shape, delete=True)

		self.comboConnectIndexes(comboIndexes)

	def comboConnectIndexes(self, indexes):
		comboDepthDict = {}
		for index in indexes:
			progPair = toPyObject(index.model().data(index, THING_ROLE))
			par = progPair.prog.parent
			depth = len(par.pairs)
			comboDepthDict.setdefault(depth, []).append(progPair)

		keys = sorted(comboDepthDict.keys())
		sortedComboProgPairs = []
		for key in keys:
			sortedComboProgPairs.extend(comboDepthDict[key])

		for progPair in sortedComboProgPairs:
			if not progPair.shape.isRest:
				combo = progPair.prog.parent
				self.system.connectComboShape(combo, progPair.shape, delete=True)

	# File IO
	def fileDialog(self, title, initPath, filters, save=True):
		filters = ["%s (*.%s)"%(f,f) for f in filters]
		if not save:
			filters += ["All files (*.*)"]
		filters = ";;".join(filters)
		fileDialog = QFileDialog(self, title, initPath, filters)

		if save:
			fileDialog.setAcceptMode(QFileDialog.AcceptSave)
		else:
			fileDialog.setAcceptMode(QFileDialog.AcceptOpen)

		fileDialog.exec_()
		if not fileDialog.result():
			return None, None

		path = str(fileDialog.selectedFiles()[0])
		if not save and not os.path.exists(path):
			return None, None

		return path, fileDialog.selectedFilter()



	def setCurrentSystem(self, system):
		self.clearCurrentSystem()
		self.system = system
		self.toolActions.system = self.system
		self.forceSimplexUpdate()

	def clearCurrentSystem(self):
		self.system = System()
		self.toolActions.system = self.system
		self.forceSimplexUpdate()

	# Falloff Editing
	def buildFalloffLists(self):
		# Setup Falloff CBox
		model = self.uiWeightFalloffCBOX.model()
		model.clear()
		model.appendRow(QStandardItem(""))
		self.uiShapeFalloffCBOX.clear()
		simp = self.system.simplex

		if simp:
			for fo in simp.falloffs:
				item = QStandardItem(fo.name)
				item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsUserCheckable)
				item.setData(Qt.Unchecked, Qt.CheckStateRole)
				item.setData(fo, THING_ROLE)
				model.appendRow(item)

			# setup Falloff editor area
			for fo in self.system.simplex.falloffs:
				self.uiShapeFalloffCBOX.addItem(fo.name, fo)

	def populateFalloffLine(self):
		model = self.uiWeightFalloffCBOX.model()
		line = self.uiWeightFalloffCBOX.lineEdit()
		fulls = []
		partials = []
		for i in xrange(model.rowCount()):
			item = model.item(i, 0)
			checked = toPyObject(item.data(Qt.CheckStateRole))
			if checked == Qt.Checked:
				fulls.append(str(toPyObject(item.data(Qt.EditRole))))
			elif checked == Qt.PartiallyChecked:
				partials.append(str(toPyObject(item.data(Qt.EditRole))))
		if partials:
			title = "{0} <<{1}>>".format(",".join(fulls), ",".join(partials))
		else:
			title = ",".join(fulls)
		line.setText(title)

	def loadFalloffData(self):
		idx = self.uiShapeFalloffCBOX.currentIndex()
		thing = toPyObject(self.uiShapeFalloffCBOX.itemData(idx))

		widList = (self.uiFalloffTypeCBOX, self.uiFalloffAxisCBOX,
					self.uiFalloffMinSPN, self.uiFalloffMinHandleSPN,
					self.uiFalloffMaxHandleSPN, self.uiFalloffMaxSPN)

		for wid in widList:
			wid.blockSignals(True)

		if not thing:
			return
		if thing.splitType == "planar":
			for wid in widList:
				wid.setEnabled(True)

			self.uiFalloffTypeCBOX.setCurrentIndex(0)
			self.uiFalloffAxisCBOX.setCurrentIndex("XYZ".index(thing.axis.upper()))
			self.uiFalloffMinSPN.setValue(thing.minVal)
			self.uiFalloffMinHandleSPN.setValue(thing.minHandle)
			self.uiFalloffMaxHandleSPN.setValue(thing.maxHandle)
			self.uiFalloffMaxSPN.setValue(thing.maxVal)

		elif thing.splitType == "map":
			#thing.mapName
			self.uiFalloffTypeCBOX.setCurrentIndex(1)
			for wid in widList:
				wid.setEnabled(False)
			self.uiFalloffTypeCBOX.setEnabled(True)

		for wid in widList:
			wid.blockSignals(False)

	@stackable
	def updateFalloffData(self):
		self._updateFalloffData()

	def _updateFalloffData(self):
		idx = self.uiShapeFalloffCBOX.currentIndex()
		thing = toPyObject(self.uiShapeFalloffCBOX.itemData(idx))

		splitType = str(self.uiFalloffTypeCBOX.currentText()).lower()
		axis = str(self.uiFalloffAxisCBOX.currentText()).upper()
		minVal = self.uiFalloffMinSPN.value()
		minHandle = self.uiFalloffMinHandleSPN.value()
		maxHandle = self.uiFalloffMaxHandleSPN.value()
		maxVal = self.uiFalloffMaxSPN.value()
		mapName = None
		self.system.setFalloffData(thing, splitType, axis, minVal, minHandle, maxHandle, maxVal, mapName)

	@Slot()
	@stackable
	def newFalloff(self):
		nn, good = QInputDialog.getText(self, "New Falloff", "Enter a name for the new Falloff", text="Falloff")
		if not good:
			return
		nn = str(nn)
		foNames = [i.name for i in self.system.simplex.falloffs]
		nn = getNextName(nn, foNames)
		newFo = self.system.createFalloff(nn)
		self.buildFalloffLists()

	@Slot()
	@stackable
	def duplicateFalloff(self):
		nn, good = QInputDialog.getText(self, "Duplicate Falloff", "Enter a name for the new Falloff", text="Falloff")
		if not good:
			return
		nn = str(nn)
		foNames = [i.name for i in self.system.simplex.falloffs]
		nn = getNextName(nn, foNames)
		falloff = toPyObject(self.uiShapeFalloffCBOX.itemData(self.uiShapeFalloffCBOX.currentindex()))
		self.system.duplicateFalloff(falloff, nn)
		self.buildFalloffLists()

	@Slot()
	@stackable
	def deleteFalloff(self):
		falloff = toPyObject(self.uiShapeFalloffCBOX.itemData(self.uiShapeFalloffCBOX.currentindex()))
		self.system.deleteFalloff(falloff)
		self.buildFalloffLists()

	# Show Dependent Combos
	def enableComboRequirements(self):
		comboModel = self.uiComboTREE.model()
		comboModel.filterRequiresAll = False
		comboModel.filterRequiresAny = False
		comboModel.filterRequiresOnly = False
		if self.uiComboDependAllCHK.isChecked():
			comboModel.filterRequiresAll = True
		elif self.uiComboDependAnyCHK.isChecked():
			comboModel.filterRequiresAny = True
		elif self.uiComboDependOnlyCHK.isChecked():
			comboModel.filterRequiresOnly = True
		comboModel.invalidateFilter()

	# Settings Helper
	def _blockSettingsSignals(self, value):
		self.uiShapeNameTXT.blockSignals(value)
		self.uiWeightNameTXT.blockSignals(value)
		self.uiWeightGroupCBOX.blockSignals(value)
		self.uiWeightFalloffCBOX.blockSignals(value)
		self.uiWeightFalloffCBOX.model().blockSignals(value)

	# settings editing
	def setSliderGroup(self):
		cbGroup = self.uiWeightGroupCBOX.itemData(self.uiWeightGroupCBOX.currentIndex())
		cbGroup = toPyObject(cbGroup)
		if cbGroup is None:
			return
		groupItems = self._sliderTreeMap[cbGroup]
		groupItem = groupItems[0]

		selItems = self.getSelectedItems(self.uiSliderTREE)
		selItems = self.filterItemsByType(selItems, S_SLIDER_TYPE)
		# get the group item from the combobox.
		self.setItemsGroup(selItems, groupItem)

	@stackable
	def setItemsGroup(self, items, groupItem):
		group = toPyObject(groupItem.data(THING_ROLE))
		things = []
		groups = []
		for item in items:
			thing = toPyObject(item.data(THING_ROLE))
			if not isinstance(thing, (Slider, Combo)):
				continue
			things.append(thing)
			groups.append(group)
			par = item.parent()
			row = par.takeRow(item.row())
			groupItem.appendRow(row)

		self.system.setSlidersGroups(things, groups)

	def setSliderName(self):
		userName = str(self.uiWeightNameTXT.text())
		sliderNames = [i.name for i in self.system.simplex.sliders]
		selItems = self.getSelectedItems(self.uiSliderTREE)
		selItems = [i for i in selItems if i.column() == 0]
		if not selItems:
			return
		thing = toPyObject(selItems[0].data(THING_ROLE))
		oldName = thing.name
		if oldName == userName: #Don't double-change the name
			return
		nn = getNextName(userName, sliderNames)
		sliderNames.append(nn)
		self.renameSlider(thing, nn)
		self.updateLinkedItems(thing)

	@stackable
	def setSliderFalloffs(self, topIdx, bottomIdx):
		model = self.uiWeightFalloffCBOX.model()
		foItem = model.item(topIdx.row())
		foThing = toPyObject(foItem.data(THING_ROLE))
		check = toPyObject(foItem.data(Qt.CheckStateRole)) == Qt.Checked

		selItems = self.getSelectedItems(self.uiSliderTREE)
		selItems = self.filterItemsByType(selItems, S_SLIDER_TYPE)

		for item in selItems:
			thing = toPyObject(item.data(THING_ROLE))
			if check:
				if foThing not in thing.prog.falloffs:
					self.system.addProgFalloff(thing.prog, foThing)
			else:
				if foThing in thing.prog.falloffs:
					self.system.removeProgFalloff(thing.prog, foThing)

	@stackable
	def renameSlider(self, slider, name):
		oldName = slider.name
		self.system.renameSlider(slider, name, multiplier=self._sliderMul)
		if len(slider.prog.pairs) == 2:
			for pp in slider.prog.pairs:
				if pp.shape.isRest:
					continue

				if pp.shape.name.startswith(oldName):
					newShapeName = pp.shape.name.replace(oldName, name, 1)
					self.system.renameShape(pp.shape, newShapeName)
					self.updateLinkedItems(pp)

	@stackable
	def renameCombo(self, combo, name):
		oldName = combo.name
		self.system.renameCombo(combo, name)
		if len(combo.prog.pairs) == 2:
			for pp in combo.prog.pairs:
				if pp.shape.isRest:
					continue
				if pp.shape.name.startswith(oldName):
					newShapeName = pp.shape.name.replace(oldName, name, 1)
					self.system.renameShape(pp.shape, newShapeName)
					self.updateLinkedItems(pp)

	# treeItem updates
	@stackable
	def treeItemChanged(self, item):
		v = toPyObject(item.data(VALUE_ROLE))
		w = toPyObject(item.data(WEIGHT_ROLE))
		if not (v or w):
			t = toPyObject(item.data(TYPE_ROLE))
			thing = toPyObject(item.data(THING_ROLE))
			if thing is None:
				return
			disp = str(toPyObject(item.data(Qt.DisplayRole)))
			if t == S_SHAPE_TYPE or t == C_SHAPE_TYPE:
				nn = getNextName(disp, [i.name for i in self.system.simplex.shapes])
				if thing.shape.name != nn:
					self.system.renameShape(thing.shape, nn)
					self.updateLinkedItems(thing)
			elif t == S_SLIDER_TYPE or t == C_SLIDER_TYPE:

				nn = getNextName(disp, [i.name for i in self.system.simplex.sliders])
				if thing.name != nn:
					self.renameSlider(thing, nn)
					self.updateLinkedItems(thing)
			elif t == S_GROUP_TYPE or t == C_GROUP_TYPE:
				nn = getNextName(disp, [i.name for i in self.system.simplex.groups])
				if thing.name != nn:
					self.system.renameGroup(thing, nn)
					self.updateLinkedItems(thing)
			elif t == C_COMBO_TYPE:
				nn = getNextName(disp, [i.name for i in self.system.simplex.combos])
				if thing.name != nn:
					self.renameCombo(thing, nn)
					self.updateLinkedItems(thing)

		else:
			if item.column() == SHAPE_WEIGHT_COL:
				pp = toPyObject(item.data(THING_ROLE))
				weight = toPyObject(item.data(Qt.EditRole))
				self.system.setShapesValues([pp], [weight])
				if isinstance(pp.prog.parent, Slider):
					self.updateSliderRange(pp.prog.parent)
			elif item.column() == SLIDER_VALUE_COL:
				slider = toPyObject(item.data(THING_ROLE))
				value = toPyObject(item.data(Qt.EditRole))
				self.system.setSlidersWeights([slider], [value])

	def updateLinkedItems(self, thing):
		# because I've kept track of what items my things are stored inside
		# I can just say that a thing has been updated, and easily refresh
		# all of the items
		if isinstance(thing, ProgPair):
			for item in self._itemMap[thing.shape]:
				item.model().blockSignals(True)
				item.setData(thing.shape.name, Qt.DisplayRole)
				item.model().blockSignals(False)
		elif isinstance(thing, ComboPair):
			for item in self._itemMap[thing.slider]:
				item.model().blockSignals(True)
				item.setData(thing.slider.name, Qt.DisplayRole)
				item.model().blockSignals(False)
		else:
			for item in self._itemMap[thing]:
				item.model().blockSignals(True)
				item.setData(thing.name, Qt.DisplayRole)
				item.model().blockSignals(False)

		# Because I killed the signals, I gotta do this
		self.uiSliderTREE.viewport().update()
		self.uiComboTREE.viewport().update()

	# settings population
	def loadSettings(self):
		# TODO get the combo types properly
		selIdx = self.uiSliderTREE.selectionModel().selectedIndexes()
		sliders = []
		progPairs = []

		for idx in selIdx:
			typ = toPyObject(self.uiSliderTREE.model().data(idx, TYPE_ROLE))
			if typ == S_SLIDER_TYPE:
				thing = toPyObject(self.uiSliderTREE.model().data(idx, THING_ROLE))
				sliders.append(thing)
			elif typ == S_SHAPE_TYPE:
				thing = toPyObject(self.uiSliderTREE.model().data(idx, THING_ROLE))
				progPairs.append(thing)

		self.loadSliderSettings(sliders)
		self.loadShapeSettings(progPairs)

	def loadSliderSettings(self, sliders):
		self._blockSettingsSignals(True)
		names = set()
		weights = set()
		groups = set()
		doSplits = set()
		interps = set()
		falloffs = []

		for slider in sliders:
			names.add(slider.name)
			weights.add(slider.value)
			groups.add(slider.group)
			interps.add(slider.prog.interp)
			falloffs.append(slider.prog.falloffs)

		if len(names) == 1:
			name = names.pop()
			self.uiWeightNameTXT.setEnabled(True)
			self.uiWeightNameTXT.setText(name)
		elif len(names) == 0:
			self.uiWeightNameTXT.setEnabled(False)
			self.uiWeightNameTXT.setText("None ...")
		else:
			self.uiWeightNameTXT.setEnabled(False)
			self.uiWeightNameTXT.setText("Multi ...")

		self.uiWeightGroupCBOX.setCurrentIndex(0)
		if len(groups) == 1:
			group = groups.pop()
			for i in xrange(self.uiWeightGroupCBOX.count()):
				chk = toPyObject(self.uiWeightGroupCBOX.itemData(i))
				if chk == group:
					self.uiWeightGroupCBOX.setCurrentIndex(i)
					break

		#uiWeightFalloffCBOX
		foModel = self.uiWeightFalloffCBOX.model()
		for i in xrange(self.uiWeightFalloffCBOX.count()):
			item = foModel.item(i)
			thing = toPyObject(item.data(THING_ROLE))
			if not thing:
				continue
			membership = [thing in f for f in falloffs]
			if all(membership):
				item.setData(Qt.Checked, Qt.CheckStateRole)
			elif any(membership):
				item.setData(Qt.PartiallyChecked, Qt.CheckStateRole)
			else:
				item.setData(Qt.Unchecked, Qt.CheckStateRole)
		self.populateFalloffLine()

		#uiWeightInterpCBOX
		self.uiWeightInterpCBOX.setCurrentIndex(0)
		if len(interps) == 1:
			interp = interps.pop()
			for i in xrange(self.uiWeightInterpCBOX.count()):
				if interp == str(self.uiWeightInterpCBOX.itemText(i)).lower():
					self.uiWeightInterpCBOX.setCurrentIndex(i)
					break
		self._blockSettingsSignals(False)

	def loadShapeSettings(self, progPairs):
		self._blockSettingsSignals(True)
		names = set()
		values = set()
		for pp in progPairs:
			names.add(pp.shape.name)
			values.add(pp.value)

		if len(names) == 1:
			name = names.pop()
			self.uiShapeNameTXT.setEnabled(True)
			self.uiShapeNameTXT.setText(name)
		elif len(names) == 0:
			self.uiShapeNameTXT.setEnabled(False)
			self.uiShapeNameTXT.setText("None ...")
		else:
			self.uiShapeNameTXT.setEnabled(False)
			self.uiShapeNameTXT.setText("Multi ...")

		self._blockSettingsSignals(False)

	# Deleting
	def _sliderDeleteCheck(self, sliderItems):
		# Get the combos dependent on these sliderItems
		combos = []
		for sliderItem in sliderItems:
			sliderThing = toPyObject(sliderItem.data(THING_ROLE))
			try:
				cpairItems = self._comboTreeMap[sliderThing]
			except KeyError:
				pass
			else:
				cpairThings = [toPyObject(i.data(THING_ROLE)) for i in cpairItems]
				combos.extend([i.combo for i in cpairThings])

		combos = list(set(combos))
		comboItems = []
		for c in combos:
			comboItems.extend(self._comboTreeMap[c])

		# check if sliders are part of combos, asks the user whether
		# they want to delete those combos, and returns the list
		if comboItems:
			comboThings = [toPyObject(i.data(THING_ROLE))for i in comboItems]
			msg = "Are you sure?\n\nThis will delete these combos as well:\n{0}"
			msg = msg.format(', '.join([i.name for i in comboThings]))
			test = QMessageBox.question(self, "Warning", msg, QMessageBox.Ok, QMessageBox.No)
			if test == QMessageBox.No:
				return False, comboItems
		return True, comboItems

	def _getDeleteItems(self, tree):
		# Sort selected items by type, then only delete
		# the topmost type in the hierarchy
		# This protects against double-deleting
		sel = self.getSelectedItems(tree)
		seps = {}
		for item in sel:
			if item.column() == 0:
				typ = toPyObject(item.data(TYPE_ROLE))
				if typ is not None:
					seps.setdefault(typ, []).append(item)
		if not seps:
			return []

		parkey = min(seps.iterkeys()) # gets the highest level selection
		delItems = sorted(seps[parkey], key=lambda x: x.row(), reverse=True)
		delItems = [i for i in delItems if i.column() == 0]
		return delItems

	def _deleteTreeItems(self, items):
		# removes these items from their UI tree
		for item in items:
			par = item.parent()
			par.takeRow(item.row())

	def deleteSliderGroupItems(self, items):
		# Don't delete the last group
		groupItems = self.searchTreeForType(self.uiSliderTREE, S_GROUP_TYPE)
		if len(groupItems) == 1:
			QMessageBox.warning(self, 'warning', "Cannot delete the last group")
			return
		self.deleteGroupItems(items)

	def deleteComboGroupItems(self, items):
		QMessageBox.warning(self, 'warning', "Cannot delete depth groups")

	def deleteGroupItems(self, items):
		# If I'm deleting a slider group, make sure
		# to delete the combos with it
		for groupItem in items:
			typ = toPyObject(groupItem.data(TYPE_ROLE))
			if typ == S_GROUP_TYPE:
				sliderItems = []
				for row in xrange(groupItem.rowCount()):
					sliderItems.append(groupItem.child(row, 0))
				doit, comboItems = self._sliderDeleteCheck(sliderItems)
				if not doit:
					return
				self.deleteComboItems(comboItems)

		# Delete the group item from the settings box
		things = []
		for groupItem in items:
			thing = toPyObject(groupItem.data(THING_ROLE))
			things.append(thing)
			for row in xrange(self.uiWeightGroupCBOX.count()):
				if thing == toPyObject(self.uiWeightGroupCBOX.itemData(row)):
					self.uiWeightGroupCBOX.removeItem(row)
					break

		self.system.deleteGroups(things)
		self._deleteTreeItems(items)

	def deleteSliderItems(self, items):
		doit, comboItems = self._sliderDeleteCheck(items)
		if not doit:
			return
		self.deleteComboItems(comboItems)
		things = [toPyObject(i.data(THING_ROLE)) for i in items]
		self.system.deleteSliders(things)
		self._deleteTreeItems(items)

	def deleteProgPairItems(self, items):
		things = [toPyObject(i.data(THING_ROLE)) for i in items]
		sliderThings = [i.prog.parent for i in things]
		self.system.deleteProgPairs(things)
		for slider in sliderThings:
			self.updateSliderRange(slider)
		self._deleteTreeItems(items)

	def deleteComboItems(self, items):
		# check if the parent group is empty
		# and if so, delete that group
		groupThings = list(set(toPyObject(i.parent().data(THING_ROLE)) for i in items if i.parent() is not None))
		groupItems = [] # ugh, pyside items/indexes aren't hashable
		for gt in groupThings:
			groupItems.extend(self._comboTreeMap[gt])

		things = [toPyObject(i.data(THING_ROLE)) for i in items]
		self.system.deleteCombos(things)
		self._deleteTreeItems(items)

		groupDel = [i for i in groupItems if not i.hasChildren()]
		if groupDel:
			self.deleteGroupItems(groupDel)

	def deleteComboPairItems(self, items):
		things = [toPyObject(i.data(THING_ROLE)) for i in items]
		self.system.deleteComboPairs(things)
		self._deleteTreeItems(items)

	# Shapes
	def newShape(self, parItem, parThing, tree):
		if tree is self.uiSliderTREE:
			if parThing.value == 0.0:
				vals = [i.value for i in parThing.prog.pairs]
				if 1.0 not in vals:
					tVal = 1.0
				elif -1.0 not in vals:
					tVal = -1.0
				elif 0.5 not in vals:
					tVal = 0.5
				else:
					tVal = -0.5
			else:
				tVal = parThing.value
		else:
			tVal = 1.0
		if abs(tVal) == 1.0:
			newName = parThing.name
		else:
			newName = "{0}_{1}".format(parThing.name, int(abs(tVal)*100))
		self.createShape(newName, tVal, parItem, parThing, tree)

	@stackable
	def createShape(self, name, value, parItem, parThing, tree):
		prog = parThing.prog

		shapeNames = [i.name for i in self.system.simplex.shapes]
		name = getNextName(name, shapeNames)
		thing = self.system.createShape(name, prog, value)

		if tree is self.uiSliderTREE:
			shapeItem = self.buildSliderShapeItem(parItem, thing)
			self.updateSliderRange(parThing)
		else:
			shapeItem = self.buildComboShapeItem(parItem, thing)
		self.expandTo(shapeItem, tree)
		self.buildItemMap()

	# Sliders
	def createSlider(self, name, parItem):
		group = toPyObject(parItem.data(THING_ROLE))

		# Build the slider
		slider = self.system.createSlider(name, group, multiplier=self._sliderMul)

		# Build the slider tree items
		sliderItem = self.buildSliderSliderTree(parItem, slider)
		self.expandTo(sliderItem, self.uiSliderTREE)
		self.buildItemMap()

	# Combos
	@stackable
	def newCombo(self, sliderItems):
		if len(sliderItems) < 2:
			QMessageBox.warning(self, 'warning', "Combos must have at least two sliders")
			return

		# TODO check if this combo already exists

		# build the new combo NAME based on the *SHAPES* that are active
		# get shapes that are "next" in line
		shapeNames = []
		for sliderItem in sliderItems:
			slider = toPyObject(sliderItem.data(THING_ROLE))
			sVal = slider.value
			if sVal == 0.0:
				sVal = 1.0
			sign = sVal / abs(sVal)
			shapeVals = [sign * (i.value - sVal) for i in slider.prog.pairs]
			pruneVals = [i for i in shapeVals if i >= 0.0]
			shapeIdx = shapeVals.index(min(pruneVals))
			shapeNames.append(str(slider.prog.pairs[shapeIdx].shape.name))
		shapeNames.sort()
		name = "_".join([s for s in shapeNames])

		# find/build a group for the new combo
		gNames = [g.name for g in self.system.simplex.groups]
		gName = "DEPTH_{0}".format(len(sliderItems))
		try:
			gIdx = gNames.index(gName)
		except ValueError:
			groupItem, group = self.createGroup(gName, self.uiComboTREE)
		else:
			group = self.system.simplex.groups[gIdx]
			root = self.getTreeRoot(self.uiComboTREE)
			for c in xrange(root.rowCount()):
				child = root.child(c, 0)
				if toPyObject(child.data(THING_ROLE)) == group:
					groupItem = child
					break
			else:
				groupItem = self.buildComboGroupItem(root, group)
		self.createCombo(name, sliderItems, groupItem)

	def createCombo(self, name, sliderItems, groupItem):
		sliders = []
		values = []
		for si in sliderItems:
			thing = toPyObject(si.data(THING_ROLE))
			sliders.append(thing)
			if thing.value == 0.0:
				values.append(1.0)
			else:
				values.append(thing.value)

		group = toPyObject(groupItem.data(THING_ROLE))

		combo = self.system.comboExists(sliders, values)
		if not combo:
			combo = self.system.createCombo(name, sliders, values, group)
			comboItem = self.buildComboComboTree(groupItem, combo)
			self.buildItemMap()
		else:
			comboItem = self._comboTreeMap[combo][0]

		self.setSelection(self.uiComboTREE, [comboItem])

	# Group manipulation
	@stackable
	def createGroup(self, name, tree, items=None):
		groupNames = [i.name for i in self.system.simplex.groups]
		newName = getNextName(name, groupNames)
		systemGroup = self.system.createGroup(newName)
		root = self.getTreeRoot(tree)
		if tree is self.uiSliderTREE:
			groupItem = self.buildSliderGroupItem(root, systemGroup)
		else:
			groupItem = self.buildComboGroupItem(root, systemGroup)

		if items:
			self.setItemsGroup(items, groupItem)

		self.expandTo(groupItem, tree)
		self.buildItemMap()

		return groupItem, systemGroup

	def setSelection(self, tree, items):
		sm = tree.selectionModel()
		fm = tree.model()
		sel = QItemSelection()
		for si in items:
			idx = fm.mapFromSource(si.index())
			sel.merge(QItemSelection(idx, idx), sm.Select)

		for item in items:
			self.expandTo(item, tree)

		sm.select(sel, sm.ClearAndSelect|sm.Rows)

	def resizeColumns(self, tree):
		filterModel = tree.model()
		for i in xrange(filterModel.columnCount()-1):
			oldcw = tree.columnWidth(i)
			tree.resizeColumnToContents(i)
			newcw = tree.columnWidth(i) + 10
			tree.setColumnWidth(i, max(oldcw, newcw, 30))
		tree.setColumnWidth(filterModel.columnCount()-1, 5)

	def toggleTree(self, index, tree, expand):
		# Separate function to deal with filtering capability
		if not index.isValid():
			return

		filterModel = tree.model()
		model = filterModel.sourceModel()
		mods = QApplication.keyboardModifiers()
		clickItem = model.itemFromIndex(filterModel.mapToSource(index))

		thing = toPyObject(clickItem.data(THING_ROLE))
		try:
			thing.expanded = expand
		except AttributeError:
			pass

		if mods & Qt.ControlModifier:
			queue = [clickItem]
			tree.blockSignals(True)
			try:
				while queue:
					item = queue.pop()
					thing = toPyObject(item.data(THING_ROLE))
					thing.expanded = expand
					tree.setExpanded(filterModel.mapFromSource(item.index()), expand)
					for i in xrange(item.rowCount()):
						child = item.child(i, 0)
						if child:
							queue.append(child)
			finally:
				tree.blockSignals(False)

		if expand:
			self.resizeColumns(tree)

	def expandTo(self, item, tree):
		model = tree.model()
		index = model.mapFromSource(item.index())

		while index:
			tree.setExpanded(index, True)
			thing = toPyObject(model.data(index, THING_ROLE))
			thing.expanded = True
			index = index.parent()
			if not index or not index.isValid():
				break
		self.resizeColumns(tree)

	def storeExpansion(self, tree):
		# Part of the data put into the undo state graph is
		# the expansion of the individual items in the graph
		# Load those expansions onto the tree
		queue = [self.getTreeRoot(tree)]
		model = tree.model()
		while queue:
			item = queue.pop()
			thing = toPyObject(item.data(THING_ROLE))
			index = model.mapFromSource(item.index())
			thing.expanded = tree.isExpanded(index)
			if isinstance(thing, Simplex):
				if tree == self.uiComboTREE:
					thing.comboExpanded = tree.isExpanded(index)
				elif tree == self.uiSliderTREE:
					thing.sliderExpanded = tree.isExpanded(index)

			for row in xrange(item.rowCount()):
				queue.append(item.child(row, 0))

	def setItemExpansion(self, tree):
		# Part of the data put into the undo state graph is
		# the expansion of the individual items in the graph
		# Load those expansions onto the tree
		queue = [self.getTreeRoot(tree)]
		model = tree.model()
		tree.blockSignals(True)
		while queue:
			item = queue.pop()
			thing = toPyObject(item.data(THING_ROLE))
			index = model.mapFromSource(item.index())
			exp = thing.expanded

			if isinstance(thing, Simplex):
				if tree == self.uiComboTREE:
					exp = thing.comboExpanded
				elif tree == self.uiSliderTREE:
					exp = thing.sliderExpanded

			tree.setExpanded(index, exp)
			for row in xrange(item.rowCount()):
				queue.append(item.child(row, 0))
		tree.blockSignals(False)

	def pairExpansion(self, oldSimp, newSimp):
		""" Copy the expansion values from 'old' to 'new' based on name """
		newSimp.comboExpanded = oldSimp.comboExpanded
		newSimp.sliderExpanded = oldSimp.sliderExpanded

		mains = (
			(oldSimp.combos, newSimp.combos),
			(oldSimp.sliders, newSimp.sliders),
			(oldSimp.groups, newSimp.groups),
		)

		for old, new in mains:
			newDict = {i.name: i for i in new}
			oldDict = {i.name: i for i in old}
			keys = set(newDict.keys()) & set(oldDict.keys())
			for key in keys:
				kNew = newDict[key]
				kOld = oldDict[key]
				kNew.expanded = kOld.expanded

				if isinstance(kNew, Combo):
					knpDict = {i.slider.name:i for i in kNew.pairs}
					kopDict = {i.slider.name:i for i in kOld.pairs}
					kkeys = set(knpDict.keys()) & set(kopDict.keys())
					for kk in kkeys:
						knpDict[kk].expadned = kopDict[kk].expanded
						n = knpDict[kk]
						o = knpDict[kk]

					knpDict = {i.shape.name:i for i in kNew.prog.pairs}
					kopDict = {i.shape.name:i for i in kOld.prog.pairs}
					kkeys = set(knpDict.keys()) & set(kopDict.keys())
					for kk in kkeys:
						knpDict[kk].expadned = kopDict[kk].expanded

	# Tree dragging
	def dragTick(self, tree, ticks, mul):
		sel = self.getSelectedItems(tree)
		dragRole = None
		for item in sel:
			if toPyObject(item.data(VALUE_ROLE)):
				dragRole = VALUE_ROLE
				break
			elif toPyObject(item.data(WEIGHT_ROLE)):
				dragRole = WEIGHT_ROLE

		if dragRole is None:
			return
		model = tree.model().sourceModel()
		model.blockSignals(True)
		for item in sel:
			if toPyObject(item.data(dragRole)):
				val = toPyObject(item.data(Qt.EditRole))
				val += (0.05) * ticks * mul
				if abs(val) < 0.00001:
					val = 0.0
				thing = toPyObject(item.data(THING_ROLE))
				val = max(min(val, thing.maxValue), thing.minValue)
				item.setData(val, Qt.EditRole)
				self.updateTickValues((thing, val))
		model.blockSignals(False)

	@singleShot()
	def updateTickValues(self, updatePairs):
		# Don't make this mouse-tick be stackable. That way
		# we don't update the whole System for a slider value changes
		sliderList = []
		progs = []
		for i in updatePairs:
			if isinstance(i[0], Slider):
				sliderList.append(i)
			elif isinstance(i[0], ProgPair):
				progs.append(i)

		if progs:
			progPairs, values = zip(*progs)
			self.system.setShapesValues(progPairs, values)
			for pp in progPairs:
				if isinstance(pp.prog.parent, Slider):
					self.updateSliderRange(pp.prog.parent)

		if sliderList:
			sliders, values = zip(*sliderList)
			self.system.setSlidersWeights(sliders, values)

		self.uiSliderTREE.viewport().update()
		self.uiComboTREE.viewport().update()

	# Menus and Actions
	def connectMenus(self):
		self.uiSliderTREE.setContextMenuPolicy(Qt.CustomContextMenu)
		self.uiSliderTREE.customContextMenuRequested.connect(self.openSliderMenu)

		self.uiComboTREE.setContextMenuPolicy(Qt.CustomContextMenu)
		self.uiComboTREE.customContextMenuRequested.connect(self.openComboMenu)

	def openSliderMenu(self, pos):
		if self._sliderMenu is None:
			self._sliderMenu = SliderContextMenu(self.uiSliderTREE)

			self._sliderMenu.uiAddGroupACT.triggered.connect(self.newSliderGroup)
			self._sliderMenu.uiAddSliderACT.triggered.connect(self.newSlider)
			self._sliderMenu.uiAddShapeACT.triggered.connect(self.newSliderShape)

			self._sliderMenu.uiComboActiveACT.triggered.connect(self.newActiveCombo)
			self._sliderMenu.uiComboSelectedACT.triggered.connect(self.newSelectedCombo)

			self._sliderMenu.uiDeleteACT.triggered.connect(self.sliderTreeDelete)

			self._sliderMenu.uiZeroACT.triggered.connect(self.zeroSelectedSliders)
			self._sliderMenu.uiZeroAllACT.triggered.connect(self.zeroAllSliders)

			#self._sliderMenu.uiExtractShapeACT.triggered.connect() # extract shape
			#self._sliderMenu.uiConnectShapeACT.triggered.connect() # connect shape
			#self._sliderMenu.uiMatchShapeACT.triggered.connect() # match shape
			#self._sliderMenu.uiClearShapeACT.triggered.connect() # clear shape

			self._sliderMenu.uiIsolateSelectedACT.triggered.connect(self.sliderTreeIsolate)
			self._sliderMenu.uiExitIsolationACT.triggered.connect(self.sliderTreeExitIsolate)

		self._sliderMenu.exec_(self.uiSliderTREE.viewport().mapToGlobal(pos))

		return self._sliderMenu

	def openComboMenu(self, pos):
		if self._comboMenu is None:
			self._comboMenu = ComboContextMenu(self.uiComboTREE)

			self._comboMenu.uiAddGroupACT.triggered.connect(self.newComboGroup)
			self._comboMenu.uiAddShapeACT.triggered.connect(self.newComboShape)

			self._comboMenu.uiDeleteACT.triggered.connect(self.comboTreeDelete)

			self._comboMenu.uiSetValsACT.triggered.connect(self.setSliderVals)

			#self._comboMenu.uiExtractShapeACT.triggered.connect() # extract shape
			#self._comboMenu.uiConnectShapeACT.triggered.connect() # connect shape
			#self._comboMenu.uiMatchShapeACT.triggered.connect() # match shape
			#self._comboMenu.uiClearShapeACT.triggered.connect() # clear shape

			self._comboMenu.uiIsolateSelectedACT.triggered.connect(self.comboTreeIsolate)
			self._comboMenu.uiExitIsolationACT.triggered.connect(self.comboTreeExitIsolate)

		self._comboMenu.exec_(self.uiComboTREE.viewport().mapToGlobal(pos))

		return self._comboMenu

	# Selection
	def getSelectedItems(self, tree):
		selIdxs = tree.selectionModel().selectedIndexes()
		filterModel = tree.model()
		model = filterModel.sourceModel()
		items = []
		for selIdx in selIdxs:
			items.append(model.itemFromIndex(filterModel.mapToSource(selIdx)))
		return items

	def getSelectedIndexes(self, tree, filtered=False):
		selIdxs = tree.selectionModel().selectedIndexes()
		if filtered:
			return selIdxs

		filterModel = tree.model()
		model = filterModel.sourceModel()
		indexes = []
		for selIdx in selIdxs:
			indexes.append(filterModel.mapToSource(selIdx))
		return indexes

	# Tree traversal
	def partitionItemsByType(self, items):
		out = {}
		for item in items:
			t = toPyObject(item.data(TYPE_ROLE))
			out.setdefault(t, []).append(item)
		return out

	def filterItemsByType(self, items, role):
		out = []
		for item in items:
			t = toPyObject(item.data(TYPE_ROLE))
			if t == role:
				out.append(item)
		return out

	def getTreeRoot(self, tree):
		model = tree.model().sourceModel()
		topRoot = model.invisibleRootItem()
		root = topRoot.child(0, 0)
		return root

	def searchTreeForType(self, tree, role, par=None):
		if par is None:
			par = self.getTreeRoot(tree)
			if par is None:
				return []
		queue = [par]
		ret = []
		while queue:
			item = queue.pop()
			for row in xrange(item.rowCount()):
				queue.append(item.child(row, 0))

			typ = toPyObject(item.data(TYPE_ROLE))
			if typ == role:
				ret.append(item)
		return ret

	def searchParentsForType(self, item, typeRole):
		while True:
			if toPyObject(item.data(TYPE_ROLE)) == typeRole:
				return item
			item = item.parent()
			if not item or not item.index().isValid():
				break
		return QStandardItem()

	# Tree Index Traversal
	def getTreeRootIndex(self, tree, filtered):
		filterModel = tree.model()
		model = filterModel.sourceModel()
		topRoot = model.invisibleRootItem()
		root = topRoot.child(0, 0)
		rootIndex = root.index()
		if filtered and rootIndex.isValid():
			return filterModel.mapFromSource(rootIndex)
		return rootIndex

	def searchTreeForTypeIndex(self, tree, role, parIdx=None, filtered=False):
		if parIdx is None:
			parIdx = self.getTreeRootIndex(tree, filtered)
			if not parIdx.isValid():
				return []

		queue = [parIdx]
		ret = []
		while queue:
			index = queue.pop()
			if not index.isValid():
				continue
			model = index.model()
			for row in xrange(model.rowCount(index)):
				queue.append(index.child(row, 0))
			typ = toPyObject(model.data(index, TYPE_ROLE))
			if typ == role:
				ret.append(index)
		return ret

	def searchParentsForTypeIndex(self, index, typeRole):
		while True:
			if toPyObject(index.model().data(index, TYPE_ROLE)) == typeRole:
				return index
			index = index.parent()
			if not index or not index.isValid():
				break
		return QModelIndex()

	def loadObject(self, obj):
		if not obj:
			return

		self.uiCurrentSystemCBOX.clear()
		objName = System.getObjectName(obj)
		self._currentObject = obj
		self._currentObjectName = objName
		self.uiCurrentObjectTXT.setText(objName)

		ops = System.getSimplexOperatorsOnObject(self._currentObject)
		for op in ops:
			js = System.getSimplexString(op)
			if not js:
				continue
			d = json.loads(js)
			name = d["systemName"]
			self.uiCurrentSystemCBOX.addItem(name, (self._currentObject, name))

	def newScene(self):
		self._currentObject = None
		self._currentObjectName = None
		self.uiCurrentObjectTXT.setText("")
		self.currentObjectChanged()







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


