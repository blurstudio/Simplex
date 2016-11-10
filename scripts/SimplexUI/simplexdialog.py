'''
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
'''

""" Simplex Dialog

This Dialog is the user facing UI for manipulating shape and combo data
in the Digital Content Creator (DCC) of your choice

Setup Structure:
	The Simplex Dialog is structured to be able to provide swappable back-ends
	for use with multiple DCC's while keeping as much of the core code intact

	There are 4 layers: System, Ui, Structure, DCC
		System:
			The System is the core of this setup. It is a class that connects and
			coordinates the other layers. Any requests from the UI to change the
			Structure, or get any information from the DCC must go through the
			System. The System also contains some basic classmethod abstractions for
			getting information in and out of the DCC (eg. getting the selected objects)
		Ui:
			The Ui layer is the front-end that the user will interact with.
			This layer will read the structure, but will not make any changes to
			the structure. All requests must go throug the System. The Ui stores
			references to the structure items in its trees.
		Structure:
			The Structure layer is an abstract representation of the solver structure,
			stored in the ".simplex" member. The abstract structure is not directly
			manipulated, and all requrests to change data in that structure must go
			through the system. All data describing the state of both the UI and
			DCC solver are stored in the Structure
		DCC:
			The DCC layer is the swappable low-level layer that contains DCC specific
			code. To support a new DCC, you should only have to write this layer, and a
			plugin that wraps the simplex.lib c++ code for your DCC.
			A Dummy/Standalone DCC layer also exists for manipulating Simplex setups
			outside of any DCC.


Ui Layer:
	Some naming conventions:
		Items vs Things:
			"Items":
				QStandardItems that live in the tree models.
			"Things":
				Structure layer objects that are referenced by the tree items.
				Have a ".thing" property if there is a DCC layer link
		New vs Create vs Build:
			"New":
				Methods called directly by buttons and actions are all prefixed with
				"New". Some of these New methods will call more generic "new" methods.
				(NewComboShape/NewSliderShape for instance)
				The purpose of these methods is to gather and prepare data to pass to
				the (hopefully generic as possible) "Create" methods.
			"Create":
				The Create methods are where system and build methods are called.
				Changes to the structure, and trees are invoked here.
			"Build":
				Any changes to the trees go through the "build" methods.

	TYPE/ROLE/COL constants:
		When dealing with Items in the UI, using the QStandardItemModel for PyQt4,
		each item has an {int: QVariant} dictionary accessible through the data()
		method. (PySide and PySide2 have {int: object} dictionaries)
		The *_ROLE constants are the integer keys I use to get/set data on
		this dictionary. The *_TYPE constants are the values stored against the
		TYPE_ROLE on each item. These types are the item-types, not necessarily the
		thing-types. The COL values show which column each type of data is stored
		for each row of the tree.

	Tree Structure:
		All items have parents, but only items in column 0 have children.
		For every item in a row, if data is visible on that row, then that item
		will have its THING_ROLE and TYPE_ROLE defined.

	The Dispatch:
		This object comes from the DCC layer where it connects to callbacks/signals
		from the DCC itself. Connect to undo/redo and scene change to keep the UI
		up to date with the DCC. If an undo/redo event is detected in the dispatch,
		the ui will grab the saved state from the Stack, and load it onto the UI.


System Layer:
	Undo/Redo Stack:
		The ability to keep track of undos is implemented in the system as a decorator.
		Every method that would change the JSON definition of the simplex must be
		decorated. This decorator handles opening and closing undo chunks, updating
		the definition in the DCC, and storing the state of the UI for each command
		to the Stack.

		# TODO
		The Stack should be instantiated only once when the simplex dialog is first
		created. After that, all instances of the dialog should grab the same stack
		But for now, I'm going to assume only one UI
"""

# Ignore a bunch of linter errors that show up because of my choice of abstraction
#pylint: disable=too-few-public-methods,superfluous-parens
#pylint: disable=unused-variable,unused-argument,too-many-public-methods
#pylint: disable=protected-access,too-many-statements,invalid-name,no-self-use
import os, sys, re, json, copy, weakref
from fnmatch import fnmatchcase
from functools import wraps

# These modules are unique to Blur Studios 
#from blurdev import prefs # Use QSettings instead

# This module imports QT from PyQt4, PySide or PySide2
# Depending on what's available
from loadUiType import (loadUiType, toPyObject, QMessageBox, QMenu, QApplication, QModelIndex,
						Slot, QSortFilterProxyModel, QMainWindow, QInputDialog, QSettings,
						QFileDialog, QShortcut, Qt, QObject, QTimer, QItemSelection,
						QStandardItemModel, QStandardItem, QKeySequence, QProgressDialog)

from dragFilter import DragFilter

from interface import (System, Combo, Slider, ComboPair, STACK,
					   ProgPair, Progression, DISPATCH, undoContext)


# If the decorated method is a slot for some Qt Signal
# and the method signature is *NOT* the same as the
# signal signature, you must double decorate the method like:
#
# @Slot(**signature)
# @stackable
# def method(**signature)

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



PRECISION = 4
COLUMNCOUNT = 3

THING_ROLE = Qt.UserRole + 1
VALUE_ROLE = Qt.UserRole + 2
WEIGHT_ROLE = Qt.UserRole + 3
TYPE_ROLE = Qt.UserRole + 4
PARENT_ROLE = Qt.UserRole + 5

THING_NAME_COL = 0
SLIDER_VALUE_COL = 1
SHAPE_WEIGHT_COL = 2

S_SHAPE_TYPE = 10
S_SLIDER_TYPE = 9
S_GROUP_TYPE = 8
S_SYSTEM_TYPE = 7

C_SHAPE_TYPE = 6
C_SHAPE_PAR_TYPE = 5
C_SLIDER_TYPE = 4
C_SLIDER_PAR_TYPE = 3
C_COMBO_TYPE = 2
C_GROUP_TYPE = 1
C_SYSTEM_TYPE = 0


class singleShot(QObject):
	""" Decorator class used to implement a QTimer.singleShot(0, function)

	This is useful so your refresh function only gets called once even if
	its connected to a signal that gets emitted several times at once.

	Note:
		The values passed to the decorated method will be accumulated
		and run all at once, then reset for the next go-round

	From the Qt Docs:
		As a special case, a QTimer with a timeout of 0 will time out as
		soon as all the events in the window system's event queue have
		been processed. This can be used to do heavy work while providing
		a snappy user interface
	"""
	def __init__(self):
		super(singleShot, self).__init__()
		self._function = None
		self._callScheduled = False
		self._args = []
		self._inst = None

	def __call__(self, function):
		self._function = function
		def newFunction(inst, *args):
			self._args.extend(args)
			if not self._callScheduled:
				self._inst = inst
				self._callScheduled = True
				QTimer.singleShot(0, self.callback)
		newFunction.__name__ = function.__name__
		newFunction.__doc__ = function.__doc__
		return newFunction

	def callback(self):
		""" Calls the decorated function and resets singleShot for the next group of calls
		"""
		self._callScheduled = False
		# self._args needs to be cleared before we call self._function
		args = self._args
		inst = self._inst
		self._inst = None
		self._args = []
		self._function(inst, args)






# LOAD THE UI base classes
FormClass, BaseClass = loadUiType(__file__)
class SimplexDialog(FormClass, BaseClass):
	def __init__(self, parent=None, dispatch=None):
		super(SimplexDialog, self).__init__(parent)
		self.setupUi(self)

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
		self._itemMap = {}
		self._sliderTreeMap = {}
		self._comboTreeMap = {}

		self._sliderDrag = None
		self._comboDrag = None

		self.makeConnections()
		self.connectMenus()

		self.uiSettingsGRP.setChecked(False)
		self.system = System() #null system

		if self.system.DCC.program == "dummy":
			self.getSelectedObject()
			self.uiObjectGRP.setEnabled(False)
			self.uiSystemGRP.setEnabled(False)
			if dispatch is not None:
				pass
				# Should keep track of the actual "stops"
				# when dealing with the dummy interface
				#self._undoShortcut = QShortcut(QKeySequence("Ctrl+z"), self)
				#self._undoShortcut.activated.connect(self.dispatch.emitUndo)
				#self._undoShortcut = QShortcut(QKeySequence("Ctrl+y"), self)
				#self._undoShortcut.activated.connect(self.dispatch.emitRedo)

	# Undo/Redo
	def handleUndo(self):
		rev = self.system.getRevision()
		data = self.system.stack.getRevision(rev)
		if data is not None:
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
				dispatch.undo.disconnect(self.handleUndo)
				dispatch.redo.disconnect(self.handleUndo)
				dispatch.beforeNew.disconnect(self.newScene)
				dispatch.beforeOpen.disconnect(self.newScene)

	# UI Setup
	def makeConnections(self):
		# Setup Trees!
		sliderModel = QStandardItemModel(self)
		sliderModel.setColumnCount(3)
		sliderModel.itemChanged.connect(self.treeItemChanged)
		sliderProxyModel = SliderFilterModel(self)
		sliderProxyModel.setSourceModel(sliderModel)
		#sliderProxyModel.setDynamicSortFilter(True)
		self.uiSliderTREE.setModel(sliderProxyModel)
		self.uiSliderTREE.setColumnWidth(1, 50)
		self.uiSliderTREE.setColumnWidth(2, 20)
		sliderModel.setHorizontalHeaderLabels(["Items", "Slide", "Value"])
		self.uiSliderFilterLINE.editingFinished.connect(self.sliderStringFilter)
		self.uiSliderFilterClearBTN.clicked.connect(self.uiSliderFilterLINE.clear)
		self.uiSliderFilterClearBTN.clicked.connect(self.sliderStringFilter)

		comboModel = QStandardItemModel(self)
		#comboProxyModel.setDynamicSortFilter(True)
		comboModel.setColumnCount(3)
		comboProxyModel = ComboFilterModel(self)
		comboProxyModel.setSourceModel(comboModel)
		#comboProxyModel.setDynamicSortFilter(True)
		self.uiComboTREE.setModel(comboProxyModel)
		self.uiComboTREE.setColumnWidth(1, 50)
		self.uiComboTREE.setColumnWidth(2, 20)
		comboModel.setHorizontalHeaderLabels(["Items", "Slide", "Value"])
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
		sliderDrag.dragTick.connect(self.sliderDragTick)

		comboDrag = DragFilter(self.uiComboTREE.viewport())
		self._comboDrag = weakref.ref(comboDrag)
		self.uiComboTREE.viewport().installEventFilter(comboDrag)
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

		# Settings connections
		sliderSelModel.selectionChanged.connect(self.loadSettings)
		self.uiWeightNameTXT.editingFinished.connect(self.setSliderName)
		self.uiWeightGroupCBOX.currentIndexChanged.connect(self.setSliderGroup)

		# Falloff connections
		foModel = QStandardItemModel()
		self.uiWeightFalloffCBOX.setModel(foModel)
		foModel.dataChanged.connect(self.populateFalloffLine)
		foModel.dataChanged.connect(self.setSliderFalloffs)

		self.uiShapeFalloffNewBTN.clicked.connect(self.newFalloff)
		self.uiShapeFalloffDuplicateBTN.clicked.connect(self.duplicateFalloff)
		self.uiShapeFalloffDeleteBTN.clicked.connect(self.deleteFalloff)

		self.uiFalloffTypeCBOX.currentIndexChanged.connect(self._updateFalloffData)
		self.uiFalloffAxisCBOX.currentIndexChanged.connect(self._updateFalloffData)
		self.uiFalloffMinSPN.valueChanged.connect(self._updateFalloffData)
		self.uiFalloffMinHandleSPN.valueChanged.connect(self._updateFalloffData)
		self.uiFalloffMaxHandleSPN.valueChanged.connect(self._updateFalloffData)
		self.uiFalloffMaxSPN.valueChanged.connect(self._updateFalloffData)

		# Make the falloff combobox display consistently with the others, but
		# retain the ability to change the top line
		line = self.uiWeightFalloffCBOX.lineEdit()
		line.setReadOnly(True) # not editable
		#line.setStyleSheet('background-color: rgba(0,0,0,0)') # Be transparent
		#line.setEchoMode(QLineEdit.NoEcho) # don't display text (the sub class shows it)
		self.uiShapeFalloffCBOX.currentIndexChanged.connect(self.loadFalloffData)

		# System level
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

	def hideRedundant(self):
		check = self.uiHideRedundantACT.isChecked()
		comboModel = self.uiComboTREE.model()
		comboModel.filterShapes = check
		comboModel.invalidateFilter()
		sliderModel = self.uiSliderTREE.model()
		sliderModel.doFilter = check
		sliderModel.invalidateFilter()

	def sliderStringFilter(self):
		filterString = str(self.uiSliderFilterLINE.text())
		sliderModel = self.uiSliderTREE.model()
		sliderModel.filterString = str(filterString)
		sliderModel.invalidateFilter()

	def comboStringFilter(self):
		filterString = str(self.uiComboFilterLINE.text())
		comboModel = self.uiComboTREE.model()
		comboModel.filterString = str(filterString)
		comboModel.invalidateFilter()

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
		else: # tree == self.uiComboTREE
			cutoff = C_COMBO_TYPE
		
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

	def shapeExtract(self):
		# Create meshes that are possibly live-connected to the shapes
		live = self.uiLiveShapeConnectionACT.isChecked()

		shapeIndexes = self.getFilteredChildSelection(self.uiSliderTREE, S_SHAPE_TYPE)
		comboIndexes = self.getFilteredChildSelection(self.uiComboTREE, C_SHAPE_TYPE)

		# Build lists of things to extract so we can get a good count
		sliderShapes = []
		for i in shapeIndexes:
			progPair = toPyObject(i.model().data(i, THING_ROLE))
			if not progPair.shape.isRest:
				sliderShapes.append(progPair.shape)

		comboShapes = []
		for i in comboIndexes:
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

	def shapeConnect(self):
		sliderIndexes = self.getSelectedIndexes(self.uiSliderTREE, filtered=False)
		sliderIndexes = [i for i in sliderIndexes if i.column() == 0]
		sliderShapes = []
		for i in sliderIndexes:
			ss = self.searchTreeForTypeIndex(self.uiSliderTREE, S_SHAPE_TYPE, par=i, filtered=False)
			sliderShapes.extend(ss)
		self.shapeConnectIndexes(sliderShapes)

		comboIndexes = self.getSelectedIndexes(self.uiComboTREE, filtered=False)
		comboIndexes = [i for i in comboIndexes if i.column() == 0]
		comboShapes = []
		for i in comboIndexes:
			ss = self.searchTreeForTypeIndex(self.uiComboTREE, C_SHAPE_TYPE, par=i, filtered=False)
			comboShapes.extend(ss)

		self.comboConnectIndexes(comboShapes)

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

	def shapeMatch(self):
		# Connect objects by selection and leave the DCC meshes alone
		shapeIndexes = getFilteredChildSelection(self.uiSliderTREE, S_SHAPE_TYPE)
		if not shapeIndexes:
			return
		sel = self.system.getSelectedObjects()
		if not sel:
			return
		mesh = sel[0]
		for si in shapeIndexes:
			progPair = toPyObject(si.model().data(si, THING_ROLE))
			if not progPair.shape.isRest:
				self.system.connectShape(progPair.shape, mesh=mesh)

	def shapeClear(self):
		# set the current shape to be equal to the rest shape
		shapeIndexes = getFilteredChildSelection(self.uiSliderTREE, S_SHAPE_TYPE)
		for si in shapeIndexes:
			progPair = toPyObject(si.model().data(si, THING_ROLE))
			if not progPair.shape.isRest:
				self.system.zeroShape(progPair.shape)

	# File IO
	def importSystemFromFile(self):
		if self._currentObject is None:
			impTypes = ['smpx']
		else:
			impTypes = ['smpx', 'json']


		pref = QSettings("Blur", "Simplex2")
		defaultPath = str(toPyObject(pref.value('systemImport', os.path.join(os.path.expanduser('~')))))
		path, ftype = self.fileDialog("Import Template", defaultPath, impTypes, save=False)
		if not path:
			return
		pref.setValue('systemImport', os.path.dirname(path))
		pref.sync()

		# Blur Prefs
		#pref = prefs.find('tools/simplex2')
		#defaultPath = pref.restoreProperty('systemImport', os.path.join(os.path.expanduser('~')))
		#path, ftype = self.fileDialog("Import Template", defaultPath, impTypes, save=False)
		#if not path:
			#return
		#pref.recordProperty('systemImport', os.path.dirname(path))
		#pref.save()

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
			newSystem.buildFromJson(self._currentObject, path)

		pBar.close()

		self.uiCurrentSystemCBOX.blockSignals(True)
		self.uiCurrentSystemCBOX.addItem(newSystem.name)
		self.uiCurrentSystemCBOX.setCurrentIndex(self.uiCurrentSystemCBOX.count()-1)
		self.setCurrentSystem(newSystem)
		self.uiCurrentSystemCBOX.blockSignals(False)

	def exportSystemTemplate(self):
		if self._currentObject is None:
			QMessageBox.warning(self, 'Warning', 'Must have a current object selection')
			return

		# Blur Prefs
		#pref = prefs.find('tools/simplex2')
		#defaultPath = pref.restoreProperty('systemExport', os.path.join(os.path.expanduser('~')))
		#path, ftype = self.fileDialog("Export Template", defaultPath, ["smpx", "json"], save=True)
		#if not path:
			#return
		#pref.recordProperty('systemExport', os.path.dirname(path))
		#pref.save()

		pref = QSettings("Blur", "Simplex2")
		defaultPath = str(toPyObject(pref.value('systemExport', os.path.join(os.path.expanduser('~')))))
		path, ftype = self.fileDialog("Export Template", defaultPath, impTypes, save=False)
		if not path:
			return
		pref.setValue('systemExport', os.path.dirname(path))
		pref.sync()

		if "(*.smpx)" in ftype:
			if not path.endswith(".smpx"):
				path = path + ".smpx"
			self.system.exportABC(path)
		elif "(*.json)" in ftype:
			if not path.endswith(".json"):
				path = path + ".json"
			dump = self.system.simplex.dump()
			with open(path, 'w') as f:
				f.write(dump)

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

	# system level
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
		nn = self.getNextName(nn, sysNames)
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

	def newScene(self):
		self._currentObject = None
		self._currentObjectName = None
		self.uiCurrentObjectTXT.setText("")
		self.currentObjectChanged()


	@Slot(int)
	@stackable
	def currentSystemChanged(self, idx):
		self.clearCurrentSystem()

		if idx == -1:
			return
		name = str(self.uiCurrentSystemCBOX.currentText())
		if not name:
			return

		system = System()
		system.loadFromMesh(self._currentObject, name)
		self.setCurrentSystem(system)

	def setCurrentSystem(self, system):
		self.clearCurrentSystem()
		self.system = system
		self.forceSimplexUpdate()

	def clearCurrentSystem(self):
		self.system = System()
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
		nn = self.getNextName(nn, foNames)
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
		nn = self.getNextName(nn, foNames)
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
	def setAllComboRequirement(self):
		if self.uiComboDependAnyCHK.isChecked():
			self.uiComboDependAnyCHK.blockSignals(True)
			self.uiComboDependAnyCHK.setChecked(False)
			self.uiComboDependAnyCHK.blockSignals(False)
		self.enableComboRequirements()

	def setAnyComboRequirement(self):
		if self.uiComboDependAllCHK.isChecked():
			self.uiComboDependAllCHK.blockSignals(True)
			self.uiComboDependAllCHK.setChecked(False)
			self.uiComboDependAllCHK.blockSignals(False)
		self.enableComboRequirements()

	def enableComboRequirements(self):
		comboModel = self.uiComboTREE.model()
		comboModel.filterRequiresAll = False
		comboModel.filterRequiresAny = False
		if self.uiComboDependAllCHK.isChecked():
			comboModel.filterRequiresAll = True
		elif self.uiComboDependAnyCHK.isChecked():
			comboModel.filterRequiresAny = True
		comboModel.invalidateFilter()

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

		if comboModel.filterRequiresAll or comboModel.filterRequiresAny:
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
		nn = self.getNextName(userName, sliderNames)
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
		self.system.renameSlider(slider, name)
		if len(slider.prog.pairs) == 2:
			for pp in slider.prog.pairs:
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
				nn = self.getNextName(disp, [i.name for i in self.system.simplex.shapes])
				if thing.shape.name != nn:
					self.system.renameShape(thing.shape, nn)
					self.updateLinkedItems(thing)
			elif t == S_SLIDER_TYPE or t == C_SLIDER_TYPE:

				nn = self.getNextName(disp, [i.name for i in self.system.simplex.sliders])
				if thing.name != nn:
					self.renameSlider(thing, nn)
					self.updateLinkedItems(thing)
			elif t == S_GROUP_TYPE or t == C_GROUP_TYPE:
				nn = self.getNextName(disp, [i.name for i in self.system.simplex.groups])
				if thing.name != nn:
					self.system.renameGroup(thing, nn)
					self.updateLinkedItems(thing)
			elif t == C_COMBO_TYPE:
				nn = self.getNextName(disp, [i.name for i in self.system.simplex.combos])
				if thing.name != nn:
					self.system.renameCombo(thing, nn)
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
		groupThings = list(set(toPyObject(i.parent().data(THING_ROLE)) for i in items))
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
	def newSliderShape(self):
		sel = self.getSelectedItems(self.uiSliderTREE)
		pars = self.filterItemsByType(sel, S_SLIDER_TYPE)
		if not pars:
			return
		parItem = pars[0]
		parThing = toPyObject(parItem.data(THING_ROLE))
		return self.newShape(parItem, parThing, self.uiSliderTREE)

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
		name = self.getNextName(name, shapeNames)
		thing = self.system.createShape(name, prog, value)

		if tree is self.uiSliderTREE:
			shapeItem = self.buildSliderShapeItem(parItem, thing)
			self.updateSliderRange(parThing)
		else:
			shapeItem = self.buildComboShapeItem(parItem, thing)
		self.expandTo(shapeItem, tree)
		self.buildItemMap()


	# Sliders
	@Slot()
	@stackable
	def newSlider(self):
		# get the new slider name
		newName, good = QInputDialog.getText(self, "New Slider", "Enter a name for the new slider", text="Slider")
		if not good:
			return

		newName = str(newName)
		sliderNames = [i.name for i in self.system.simplex.sliders]
		newName = self.getNextName(newName, sliderNames)

		# get the parent group
		sel = self.getSelectedItems(self.uiSliderTREE)
		if sel:
			groupItem = self.searchParentsForType(sel[0], S_GROUP_TYPE)
		else:
			groupItem = QStandardItem()

		if not groupItem.index().isValid():
			groupItem, group = self.createGroup("{0}_GROUP".format(newName), self.uiSliderTREE)

		self.createSlider(newName, groupItem)

	def createSlider(self, name, parItem):
		group = toPyObject(parItem.data(THING_ROLE))

		# Build the slider
		slider = self.system.createSlider(name, group)

		# Build the slider tree items
		sliderItem = self.buildSliderSliderTree(parItem, slider)
		self.expandTo(sliderItem, self.uiSliderTREE)
		self.buildItemMap()


	# Combos
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

	def newSelectedCombo(self):
		selItems = self.getSelectedItems(self.uiSliderTREE)
		selItems = [i for i in selItems if i.column() == 0]
		sliderItems = []
		for item in selItems:
			thing = toPyObject(item.data(THING_ROLE))
			if isinstance(thing, Slider):
				sliderItems.append(item)
		self.newCombo(sliderItems)

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
		combo = self.system.createCombo(name, sliders, values, group)
		comboItem = self.buildComboComboTree(groupItem, combo)
		self.expandTo(comboItem, self.uiComboTREE)
		self.buildItemMap()


	# Group manipulation
	def newSliderGroup(self):
		newName, good = QInputDialog.getText(self, "New Group", "Enter a name for the new group", text="Group")
		if not good:
			return
		selItems = self.getSelectedItems(self.uiSliderTREE)
		selItems = [i for i in selItems if i.column() == 0]
		selItems = self.filterItemsByType(selItems, S_SLIDER_TYPE)

		self.createGroup(str(newName), self.uiSliderTREE, selItems)

	def newComboGroup(self):
		newName, good = QInputDialog.getText(self, "New Group", "Enter a name for the new group", text="Group")
		if not good:
			return
		self.createGroup(str(newName), self.uiComboTREE)

	@stackable
	def createGroup(self, name, tree, items=None):
		groupNames = [i.name for i in self.system.simplex.groups]
		newName = self.getNextName(name, groupNames)
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

		sm = self.uiSliderTREE.selectionModel()
		fm = self.uiSliderTREE.model()
		sel = QItemSelection()
		sliderItems = []
		for thing in comboThings:
			for pair in thing.pairs:
				for si in self._sliderTreeMap[pair.slider]:
					sliderItems.append(si)
					idx = fm.mapFromSource(si.index())
					sel.merge(QItemSelection(idx, idx), sm.Select)

		for item in sliderItems:
			self.expandTo(item, self.uiSliderTREE)

		sm.select(sel, sm.ClearAndSelect|sm.Rows)

	# Value buttons
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


	# Utility Buttons
	def selectCtrl(self):
		self.system.selectCtrl()


	# Tree expansion/collapse code
	def expandSliderTree(self, index):
		self.toggleTree(index, self.uiSliderTREE, True)

	def collapseSliderTree(self, index):
		self.toggleTree(index, self.uiSliderTREE, False)

	def expandComboTree(self, index):
		self.toggleTree(index, self.uiComboTREE, True)

	def collapseComboTree(self, index):
		self.toggleTree(index, self.uiComboTREE, False)

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
					try:
						thing.expanded = expand
					except AttributeError:
						pass
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
			try:
				thing.expanded = True
			except AttributeError:
				pass
			index = index.parent()
			if not index or not index.isValid():
				break
		self.resizeColumns(tree)

	def setItemExpansion(self, tree):
		# Part of the data put into the undo state graph is
		# the expansion of the individual items in the graph
		# Load those expansions onto the tree
		self.uiSliderTREE.blockSignals(True)
		queue = [self.getTreeRoot(tree)]
		model = tree.model()
		while queue:
			item = queue.pop()
			thing = toPyObject(item.data(THING_ROLE))
			index = model.mapFromSource(item.index())
			try:
				exp = thing.expanded
			except AttributeError:
				continue
			tree.setExpanded(index, exp)
			for row in xrange(item.rowCount()):
				queue.append(item.child(row, 0))
		self.uiSliderTREE.blockSignals(False)


	# Tree dragging
	def sliderDragTick(self, ticks, mul):
		self.dragTick(self.uiSliderTREE, ticks, mul)

	def comboDragTick(self, ticks, mul):
		self.dragTick(self.uiComboTREE, ticks, mul)

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

		self._comboMenu.exec_(self.uiComboTREE.viewport().mapToGlobal(pos))

		return self._comboMenu


	# Tree building
	def buildTrees(self):
		self.clearTree(self.uiSliderTREE)
		self.clearTree(self.uiComboTREE)
		if not self.system:
			return
		self.uiWeightGroupCBOX.addItem("")
		sliderTree = self.buildSliderTree()
		comboTree = self.buildComboTree()
		self.buildItemMap()
		return sliderTree, comboTree

	def clearTree(self, tree):
		model = tree.model().sourceModel()
		topRoot = model.invisibleRootItem()
		model.removeRows(0, 1, topRoot.index())

	def buildTreeRoot(self, tree, thing):
		model = tree.model().sourceModel()
		topRoot = model.invisibleRootItem()

		topRoot.setFlags(topRoot.flags() ^ Qt.ItemIsDropEnabled)

		root = QStandardItem(thing.name)
		root.setFlags(root.flags() ^ Qt.ItemIsDragEnabled)
		if tree is self.uiSliderTREE:
			sysType = S_SYSTEM_TYPE
		else:
			sysType = C_SYSTEM_TYPE
		root.setData(sysType, TYPE_ROLE)
		root.setData(thing, THING_ROLE)
		topRoot.setChild(0, 0, root)
		return root

	def buildSliderTree(self):
		simplex = self.system.simplex
		if not simplex:
			return
		rest = simplex.buildRestShape()

		self.clearTree(self.uiSliderTREE)
		root = self.buildTreeRoot(self.uiSliderTREE, simplex)

		sliderGroups = set()
		for s in simplex.sliders:
			sliderGroups.add(s.group)

		#sliderGroups = sorted(list(sliderGroups), key=lambda x: x.name)
		sliderGroups = [i for i in simplex.groups if i in sliderGroups]


		for g in sliderGroups:
			self.buildSliderGroupTree(root, g)
		return root

	def buildSliderGroupTree(self, parItem, groupThing):
		groupItem = self.buildSliderGroupItem(parItem, groupThing)
		for slider in groupThing.sliders:
			self.buildSliderSliderTree(groupItem, slider)
		return groupItem

	def buildSliderSliderTree(self, parItem, sliderThing):
		sliderItem = self.buildSliderSliderItem(parItem, sliderThing)

		for pair in sliderThing.prog.pairs:
			self.buildSliderShapeItem(sliderItem, pair)

		self.updateSliderRange(sliderThing)
		return sliderItem

	def updateSliderRange(self, sliderThing):
		values = [0.0] # take the rest value into account
		for pair in sliderThing.prog.pairs:
			values.append(pair.value) # for doing min/max stuff
		sliderThing.minValue = min(values)
		sliderThing.maxValue = max(values)

		# If the slider is part of a combo
		# make sure to update the range of the comboPair as well
		try:
			cpairItems = self._comboTreeMap[sliderThing]
		except KeyError:
			pass
		else:
			for cpairItem in cpairItems:
				cpair = toPyObject(cpairItem.data(THING_ROLE))
				cpair.minValue = min(values)
				cpair.maxValue = max(values)

	def buildSliderGroupItem(self, parItem, groupThing):
		grpItem = QStandardItem(groupThing.name)
		grpItem.setData(groupThing, THING_ROLE)
		grpItem.setData(S_GROUP_TYPE, TYPE_ROLE)
		grpItem.setData(S_SYSTEM_TYPE, PARENT_ROLE)
		parItem.appendRow([grpItem, QStandardItem(), QStandardItem()])

		self.uiWeightGroupCBOX.blockSignals(True)
		self.uiWeightGroupCBOX.addItem(groupThing.name, groupThing)
		self.uiWeightGroupCBOX.blockSignals(False)

		return grpItem

	def buildSliderSliderItem(self, parItem, sliderThing):
		sliderItem = QStandardItem(sliderThing.name)
		sliderItem.setData(sliderThing, THING_ROLE)
		sliderItem.setData(S_SLIDER_TYPE, TYPE_ROLE)
		sliderItem.setData(S_GROUP_TYPE, PARENT_ROLE)

		sliderValueItem = QStandardItem()
		sliderValueItem.setData(float(sliderThing.value), Qt.EditRole)
		sliderValueItem.setData(True, VALUE_ROLE)
		sliderValueItem.setData(sliderThing, THING_ROLE)
		sliderValueItem.setData(S_SLIDER_TYPE, TYPE_ROLE)
		sliderValueItem.setData(S_GROUP_TYPE, PARENT_ROLE)

		parItem.appendRow([sliderItem, sliderValueItem, QStandardItem()])
		return sliderItem

	def buildSliderShapeItem(self, parItem, pairThing):
		pairItem = QStandardItem(pairThing.shape.name)
		pairItem.setData(pairThing, THING_ROLE)
		pairItem.setData(S_SHAPE_TYPE, TYPE_ROLE)
		pairItem.setData(S_SLIDER_TYPE, PARENT_ROLE)
		pairValueItem = QStandardItem()
		pairValueItem.setData(float(pairThing.value), Qt.EditRole)
		pairValueItem.setData(True, WEIGHT_ROLE)
		pairValueItem.setData(pairThing, THING_ROLE)
		pairValueItem.setData(S_SHAPE_TYPE, TYPE_ROLE)
		pairValueItem.setData(S_SLIDER_TYPE, PARENT_ROLE)

		parItem.appendRow([pairItem, QStandardItem(), pairValueItem])
		return pairItem

	def buildComboTree(self):
		simplex = self.system.simplex
		if not simplex:
			return
		rest = simplex.buildRestShape()

		self.clearTree(self.uiComboTREE)
		root = self.buildTreeRoot(self.uiComboTREE, simplex)

		comboGroups = set()
		for s in simplex.combos:
			comboGroups.add(s.group)
		comboGroups = sorted(list(comboGroups), key=lambda x: x.name)

		for g in comboGroups:
			self.buildComboGroupTree(root, g)
		return root

	def buildComboGroupTree(self, parItem, groupThing):
		grpItem = self.buildComboGroupItem(parItem, groupThing)
		ordered = sorted(groupThing.combos, key=lambda x: len(x.pairs))
		for combo in ordered:
			self.buildComboComboTree(grpItem, combo)
		return grpItem

	def buildComboComboTree(self, parItem, comboThing):
		comboItem = self.buildComboComboItem(parItem, comboThing)
		for pair in comboThing.pairs:
			self.buildComboSliderItem(comboItem, pair)

		self.buildComboShapeParTree(comboItem, comboThing.prog)
		return comboItem

	def buildComboShapeParTree(self, parItem, progThing):
		shapesItem = self.buildComboParItem(parItem, "SHAPES", progThing)
		for pair in progThing.pairs:
			self.buildComboShapeItem(shapesItem, pair)
		return shapesItem

	def buildComboGroupItem(self, parItem, groupThing):
		grpItem = QStandardItem(groupThing.name)
		grpItem.setData(groupThing, THING_ROLE)
		grpItem.setData(C_GROUP_TYPE, TYPE_ROLE)
		grpItem.setData(C_SYSTEM_TYPE, PARENT_ROLE)
		parItem.appendRow([grpItem, QStandardItem(), QStandardItem()])

		self.uiWeightGroupCBOX.blockSignals(True)
		self.uiWeightGroupCBOX.addItem(groupThing.name, groupThing)
		self.uiWeightGroupCBOX.blockSignals(False)

		return grpItem

	def buildComboComboItem(self, parItem, comboThing):
		comboItem = QStandardItem(comboThing.name)
		comboItem.setData(comboThing, THING_ROLE)
		comboItem.setData(C_COMBO_TYPE, TYPE_ROLE)
		comboItem.setData(C_GROUP_TYPE, PARENT_ROLE)
		parItem.appendRow([comboItem, QStandardItem(), QStandardItem()])
		return comboItem

	def buildComboParItem(self, parItem, name, parThing):
		slidersItem = QStandardItem(name)
		slidersItem.setData(parThing, THING_ROLE)
		slidersItem.setData(C_SHAPE_PAR_TYPE, TYPE_ROLE)
		slidersItem.setData(C_COMBO_TYPE, PARENT_ROLE)
		parItem.appendRow([slidersItem, QStandardItem(), QStandardItem()])
		return slidersItem

	def buildComboSliderItem(self, parItem, comboPair):
		pairItem = QStandardItem(comboPair.slider.name)
		pairItem.setData(comboPair, THING_ROLE)
		pairItem.setData(C_SLIDER_TYPE, TYPE_ROLE)
		pairItem.setData(C_SLIDER_PAR_TYPE, PARENT_ROLE)
		comboPair.minValue = comboPair.slider.minValue
		comboPair.maxValue = comboPair.slider.maxValue
		pairValueItem = QStandardItem()
		pairValueItem.setData(float(comboPair.value), Qt.EditRole)
		pairValueItem.setData(True, VALUE_ROLE)
		pairValueItem.setData(comboPair, THING_ROLE)
		pairValueItem.setData(C_SLIDER_TYPE, TYPE_ROLE)
		pairValueItem.setData(C_SLIDER_PAR_TYPE, PARENT_ROLE)

		parItem.appendRow([pairItem, pairValueItem, QStandardItem()])
		return pairItem

	def buildComboShapeItem(self, parItem, progThing):
		pairItem = QStandardItem(progThing.shape.name)
		pairItem.setData(progThing, THING_ROLE)
		pairItem.setData(C_SHAPE_TYPE, TYPE_ROLE)
		pairItem.setData(C_SHAPE_PAR_TYPE, PARENT_ROLE)
		progThing.minValue = 0.0
		progThing.maxValue = 1.0
		pairValueItem = QStandardItem()
		pairValueItem.setData(float(progThing.value), Qt.EditRole)
		pairValueItem.setData(True, WEIGHT_ROLE)
		pairValueItem.setData(progThing, THING_ROLE)
		pairValueItem.setData(C_SHAPE_TYPE, TYPE_ROLE)
		pairValueItem.setData(C_SHAPE_PAR_TYPE, PARENT_ROLE)
		parItem.appendRow([pairItem, QStandardItem(), pairValueItem])
		return pairItem


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

	# Item Mapping
	def buildItemMap(self):
		sRoot = self.getTreeRoot(self.uiSliderTREE)
		cRoot = self.getTreeRoot(self.uiComboTREE)
		self._itemMap = {}
		self._sliderTreeMap = {}
		self._comboTreeMap = {}
		for par in [sRoot, cRoot]:
			if par is sRoot:
				treeMap = self._sliderTreeMap
			else:
				treeMap = self._comboTreeMap
			queue = [par]
			ret = []
			while queue:
				item = queue.pop()
				if not item:
					continue
				for row in xrange(item.rowCount()):
					queue.append(item.child(row, 0))

				thing = toPyObject(item.data(THING_ROLE))
				if thing:
					if isinstance(thing, ProgPair):
						self._itemMap.setdefault(thing.shape, []).append(item)
						treeMap.setdefault(thing.shape, []).append(item)
					elif isinstance(thing, ComboPair):
						self._itemMap.setdefault(thing.slider, []).append(item)
						treeMap.setdefault(thing.slider, []).append(item)
					else:
						self._itemMap.setdefault(thing, []).append(item)
						treeMap.setdefault(thing, []).append(item)

		self.uiSliderTREE.model().invalidateFilter()
		self.uiComboTREE.model().invalidateFilter()

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

	# Utility
	@staticmethod
	def getNextName(name, currentNames):
		i = 0
		s = set(currentNames)
		while True:
			if not i:
				nn = name
			else:
				nn = name + str(i)
			if nn not in s:
				return nn
			i += 1



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

	def tree(self):
		return self._tree


class SimplexFilterModel(QSortFilterProxyModel):
	def __init__(self, parent=None):
		super(SimplexFilterModel, self).__init__(parent)
		self.filterString = ""

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			if self.filterString:
				data = toPyObject(self.sourceModel().data(sourceIndex, THING_ROLE))
				if isinstance(data, (ProgPair, Slider, Combo)):
					sourceItem = self.sourceModel().itemFromIndex(sourceIndex)
					if not self.checkChildren(sourceItem):
						return False

		return super(SimplexFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)

	def checkChildren(self, sourceItem):
		# Recursively check the children of this object.
		# If any child matches the filter, then this object should be shown
		itemString = str(toPyObject(sourceItem.data(Qt.DisplayRole)))
		if fnmatchcase(itemString, "*{0}*".format(self.filterString)):
			return True
		if sourceItem.hasChildren():
			for row in xrange(sourceItem.rowCount()):
				if self.checkChildren(sourceItem.child(row, 0)):
					return True
		return False


class ComboFilterModel(SimplexFilterModel):
	""" Filter by slider when Show Dependent Combos is checked """
	def __init__(self, parent=None):
		super(ComboFilterModel, self).__init__(parent)
		self.requires = []
		self.filterRequiresAll = False
		self.filterRequiresAny = False
		self.filterShapes = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			data = toPyObject(self.sourceModel().data(sourceIndex, THING_ROLE))
			if self.filterShapes:
				# ignore the SHAPE par if there's nothing under there
				if isinstance(data, Progression):
					if len(data.pairs) <= 2:
						return False
				# Ignore shape things if requested
				if isinstance(data, ProgPair):
					if len(data.prog.pairs) <= 2:
						return False
					elif data.shape.isRest:
						return False
			if (self.filterRequiresAny or self.filterRequiresAll) and self.requires:
				# Ignore items that don't use the required sliders if requested
				if isinstance(data, Combo):
					sliders = [i.slider for i in data.pairs]
					if self.filterRequiresAll:
						if not all(r in sliders for r in self.requires):
							return False
					elif self.filterRequiresAny:
						if not any(r in sliders for r in self.requires):
							return False
		return super(ComboFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)


class SliderFilterModel(SimplexFilterModel):
	""" Hide single shapes under a slider """
	def __init__(self, parent=None):
		super(SliderFilterModel, self).__init__(parent)
		self.doFilter = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			if self.doFilter:
				data = toPyObject(self.sourceModel().data(sourceIndex, THING_ROLE))
				if isinstance(data, ProgPair):
					if len(data.prog.pairs) <= 2:
						return False
					elif data.shape.isRest:
						return False

		return super(SliderFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)




def _test():
	app = QApplication(sys.argv)
	d = SimplexDialog()
	d.show()
	sys.exit(app.exec_())

if __name__ == '__main__':
	_test()


