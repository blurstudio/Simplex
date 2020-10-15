# Copyright 2016, Blur Studio
#
# This file is part of Simplex.
#
# Simplex is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Simplex is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.


# Ignore a bunch of linter warnings that show up because of my choice of abstraction
#pylint: disable=unused-argument,too-many-public-methods,relative-import
#pylint: disable=too-many-statements,no-self-use,missing-docstring
import os
import re
import json
import weakref
from contextlib import contextmanager

from .Qt import QtCompat
from .Qt.QtCore import Signal
from .Qt.QtCore import Qt, QSettings
from .Qt.QtGui import QStandardItemModel, QIcon, QColor
from .Qt.QtWidgets import QMessageBox, QInputDialog, QApplication
from .Qt.QtWidgets import QProgressDialog, QPushButton, QToolButton, QRadioButton, \
						  QComboBox, QCheckBox, QGroupBox, QWidget, QMenu, QMenuBar, \
						  QLineEdit, QLabel, QSplitter, QSizePolicy, QAction
from .Qt.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout

from .utils import toPyObject, getNextName, makeUnique, naturalSortKey
from .comboCheckDialog import ComboCheckDialog
from .items import (ProgPair, Slider, Combo, Group, Simplex, Stack, Shape, Traversal)
from .interfaceModel import (SliderModel, ComboModel, ComboFilterModel, SliderFilterModel,
							coerceIndexToChildType, coerceIndexToParentType, coerceIndexToRoots,
							SimplexModel)

from .interface import DCC
from .menu import loadPlugins, buildToolMenu
from .interfaceModelTrees import SliderTree, ComboTree
from . import stylesheets

from .traversalDialog import TraversalDialog
from .falloffDialog import FalloffDialog

try:
	# This module is unique to Blur Studio
	import blurdev
	from blurdev.gui import Window
except ImportError:
	blurdev = None
	from .Qt.QtWidgets import QMainWindow as Window

NAME_CHECK = re.compile(r'[A-Za-z][\w.]*')

# If the decorated method is a slot for some Qt Signal
# and the method signature is *NOT* the same as the
# signal signature, you must double decorate the method like:
#
# @Slot(**signature)
# @stackable
# def method(**signature)

@contextmanager
def signalsBlocked(item):
	''' Context manager to block the qt signals on an item '''
	item.blockSignals(True)
	try:
		yield
	finally:
		item.blockSignals(False)


class SimplexDialog(Window):

	WindowTitle = "Simplex"
	Version = 3.0

	simplexLoaded = Signal()
	openedDialogs = []

	def __init__(self, parent=None, dispatch=None):
		super(SimplexDialog, self).__init__(parent=parent)

		self.uiMenuBar = None
		self.uiFileMenu = None
		self.uiEditMenu = None
		self.uiCurrentObjectLBL = None
		self.uiCurrentObjectTXT = None
		self.uiGetSelectedObjectBTN = None
		self.uiClearSelectedObjectBTN = None

		self.uiCurrentSystemLBL = None
		self.uiCurrentSystemCBOX = None
		self.uiNewSystemBTN = None
		self.uiDeleteSystemBTN = None
		self.uiRenameSystemBTN = None

		self.uiNewGroupBTN = None
		self.uiNewSliderBTN = None
		self.uiNewShapeBTN = None
		self.uiSliderDeleteBTN = None
		self.uiAutoSetSlidersCHK = None
		self.uiSelectCtrlBTN = None
		self.uiZeroAllBTN = None
		self.uiZeroSelectedBTN = None

		self.uiMainShapesGRP = None
		self.uiSliderTREE = None
		self.uiSliderFilterLINE = None
		self.uiSliderExitIsolateBTN = None

		self.uiComboShapesGRP = None
		self.uiComboTREE = None
		self.uiComboFilterLINE = None
		self.uiComboExitIsolateBTN = None

		self.uiNewComboActiveBTN = None
		self.uiNewComboSelectBTN = None
		self.uiNewComboGroupBTN = None
		self.uiNewComboShapeBTN = None
		self.uiDeleteComboBTN = None
		self.uiShowDependentGRP = None
		self.uiComboDependAnyRDO = None
		self.uiComboDependOnlyRDO = None
		self.uiComboDependAllRDO = None
		self.uiComboDependLockCHK = None
		self.uiAutoSetCombosCHK = None
		self.uiSelectSlidersBTN = None
		self.uiSetSliderValsBTN = None

		self.uiConnectionGroupWID = None
		self.uiShapeExtractBTN = None
		self.uiShapeConnectBTN = None
		self.uiShapeConnectSceneBTN = None

		# Actions
		self.uiImportACT = None
		self.uiExportACT = None
		self.uiLiveShapeConnectionACT = None
		self.uiExtractOnCreateACT = None
		self.uiHideRedundantACT = None
		self.uiDoubleSliderRangeACT = None
		self.uiLegacyJsonACT = None

		self._sliderMenu = None
		self._comboMenu = None
		self._currentObject = None
		self._currentObjectName = None

		# Connect the combo boxes and spinners to the data model
		# TODO: Figure out how to deal with the type/axis "enum" cboxes
		# see: http://doc.qt.io/qt-5/qtwidgets-itemviews-combowidgetmapper-example.html
		'''
		self._falloffMapper = QDataWidgetMapper()
		self.uiShapeFalloffCBOX.currentIndexChanged.connect(self._falloffMapper.setCurrentIndex)
		'''

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

		self._itemMap = {}
		self._sliderTreeMap = {}
		self._comboTreeMap = {}

		self._sliderDrag = None
		self._comboDrag = None

		self.initWidgets()
		self.initConnections()
		self.initUI()

	def initWidgets(self):
		centralWidget = QWidget()
		centralLayout = QVBoxLayout()
		centralLayout.setContentsMargins(4, 4, 4, 4)
		centralLayout.setSpacing(6)

		# MenuBar
		self.uiMenuBar = QMenuBar(centralWidget)

		# File
		self.uiFileMenu = QMenu("File", centralWidget)
		self.uiImportACT = QAction("Import", self)
		self.uiFileMenu.addAction(self.uiImportACT)
		self.uiExportACT = QAction("Export", self)
		self.uiFileMenu.addAction(self.uiExportACT)
		self.uiMenuBar.addMenu(self.uiFileMenu)

		# Edit
		self.uiEditMenu = QMenu("Edit", centralWidget)
		self.uiHideRedundantACT = QAction("Hide Redundant", self)
		self.uiHideRedundantACT.setCheckable(True)
		self.uiHideRedundantACT.setChecked(True)
		self.uiEditMenu.addAction(self.uiHideRedundantACT)

		self.uiLiveShapeConnectionACT = QAction("Live Shape Connection", self)
		self.uiLiveShapeConnectionACT.setCheckable(True)
		self.uiLiveShapeConnectionACT.setChecked(True)
		self.uiEditMenu.addAction(self.uiLiveShapeConnectionACT)

		self.uiExtractOnCreateACT = QAction("Extract On Create", self)
		self.uiExtractOnCreateACT.setCheckable(True)
		self.uiEditMenu.addAction(self.uiExtractOnCreateACT)

		self.uiDoubleSliderRangeACT = QAction("Double Slider Range", self)
		self.uiDoubleSliderRangeACT.setCheckable(True)
		self.uiEditMenu.addAction(self.uiDoubleSliderRangeACT)

		self.uiLegacyJsonACT = QAction("Legacy JSON", self)
		self.uiLegacyJsonACT.setCheckable(True)
		self.uiEditMenu.addAction(self.uiLegacyJsonACT)

		self.uiMenuBar.addMenu(self.uiEditMenu)
		self.setMenuBar(self.uiMenuBar)

		# Object
		self.initObjectSystemWidgets(centralLayout)

		# Shapes
		self.initShapesWidgets(centralLayout)

		# Extraction/Connection
		self.initConnectionsWidgets(centralLayout)

		centralWidget.setLayout(centralLayout)
		self.setCentralWidget(centralWidget)

	def initObjectSystemWidgets(self, centralLayout):
		headerLay = QHBoxLayout()
		headerLay.setAlignment(Qt.AlignTop)
		headerLay.setSpacing(4)

		objectGrp = QGroupBox("Geometry")
		objectLay = QHBoxLayout()
		objectLay.setContentsMargins(4, 1, 4, 1)
		objectLay.setSpacing(4)
		objectLay.setStretch(1, 10)

		self.uiCurrentObjectLBL = QLabel("Current Object")
		objectLay.addWidget(self.uiCurrentObjectLBL)
		self.uiCurrentObjectTXT = QLineEdit()
		self.uiCurrentObjectTXT.setMinimumWidth(200)
		objectLay.addWidget(self.uiCurrentObjectTXT)
		self.uiGetSelectedObjectBTN = QToolButton()
		self.uiGetSelectedObjectBTN.setText("Get Selected")
		objectLay.addWidget(self.uiGetSelectedObjectBTN)
		self.uiClearSelectedObjectBTN = QToolButton()
		self.uiClearSelectedObjectBTN.setText("Clear")
		objectLay.addWidget(self.uiClearSelectedObjectBTN)

		objectGrp.setLayout(objectLay)
		headerLay.addWidget(objectGrp)

		# System
		systemGrp = QGroupBox("System")
		systemLay = QHBoxLayout()
		systemLay.setContentsMargins(4, 1, 4, 1)
		systemLay.setSpacing(4)

		self.uiCurrentSystemLBL = QLabel("Current System")
		systemLay.addWidget(self.uiCurrentSystemLBL)
		self.uiCurrentSystemCBOX = QComboBox()
		systemLay.addWidget(self.uiCurrentSystemCBOX)
		self.uiNewSystemBTN = QToolButton()
		self.uiNewSystemBTN.setText("New")
		systemLay.addWidget(self.uiNewSystemBTN)
		self.uiRenameSystemBTN = QToolButton()
		self.uiRenameSystemBTN.setText("Rename")
		systemLay.addWidget(self.uiRenameSystemBTN)
		self.uiDeleteSystemBTN = QToolButton()
		self.uiDeleteSystemBTN.setText("Delete")
		systemLay.addWidget(self.uiDeleteSystemBTN)

		systemGrp.setLayout(systemLay)

		headerLay.addWidget(systemGrp)
		headerLay.addStretch(1)

		centralLayout.addItem(headerLay)

	def initShapesWidgets(self, centralLayout):
		splitter = QSplitter()
		splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

		self.uiMainShapesGRP = QGroupBox("Main Shapes")
		mainLay = QGridLayout()
		mainLay.setContentsMargins(4, 1, 4, 1)
		mainLay.setSpacing(4)

		mainToolLay = QVBoxLayout()
		mainToolLay.setContentsMargins(0, 0, 0, 0)
		mainToolLay.setSpacing(4)

		self.uiNewGroupBTN = QPushButton("Group")
		mainToolLay.addWidget(self.uiNewGroupBTN)
		self.uiNewSliderBTN = QPushButton("Slider")
		mainToolLay.addWidget(self.uiNewSliderBTN)
		self.uiNewShapeBTN = QPushButton("Shape")
		mainToolLay.addWidget(self.uiNewShapeBTN)
		self.uiSliderDeleteBTN = QPushButton("Delete")
		mainToolLay.addWidget(self.uiSliderDeleteBTN)
		mainToolLay.addStretch(1)
		self.uiAutoSetSlidersCHK = QCheckBox("Auto Set")
		mainToolLay.addWidget(self.uiAutoSetSlidersCHK)
		self.uiZeroAllBTN = QPushButton("Zero All")
		mainToolLay.addWidget(self.uiZeroAllBTN)
		self.uiZeroSelectedBTN = QPushButton("Zero Selected")
		mainToolLay.addWidget(self.uiZeroSelectedBTN)
		self.uiSelectCtrlBTN = QPushButton("Select Ctl")
		mainToolLay.addWidget(self.uiSelectCtrlBTN)
		mainLay.addItem(mainToolLay, 0, 0)

		self.uiSliderTREE = SliderTree(parent=None)
		self.uiSliderTREE.setAlternatingRowColors(True)
		self.uiSliderTREE.setDragEnabled(False)
		self.uiSliderTREE.setDragDropMode(SliderTree.NoDragDrop)
		self.uiSliderTREE.setSelectionMode(SliderTree.ExtendedSelection)
		self.uiSliderTREE.dragFilter.dragPressed.connect(self.dragStart)
		self.uiSliderTREE.dragFilter.dragReleased.connect(self.dragStop)
		mainLay.addWidget(self.uiSliderTREE, 0, 1)

		mainFilterLay = QHBoxLayout()
		mainFilterLay.setContentsMargins(0, 0, 0, 0)
		self.uiSliderFilterLINE = QLineEdit()
		self.uiSliderFilterLINE.setPlaceholderText("Filter Sliders...")
		self.uiSliderFilterLINE.setClearButtonEnabled(True)
		mainFilterLay.addWidget(self.uiSliderFilterLINE)
		self.uiSliderExitIsolateBTN = QPushButton("Exit Isolate")
		self.uiSliderExitIsolateBTN.setHidden(True)
		mainFilterLay.addWidget(self.uiSliderExitIsolateBTN)
		mainLay.addItem(mainFilterLay, 1, 1)

		self.uiMainShapesGRP.setLayout(mainLay)

		# Combo Shapes
		self.uiComboShapesGRP = QGroupBox("Combo Shapes")
		comboLay = QGridLayout()
		comboLay.setContentsMargins(4, 1, 4, 1)
		comboLay.setSpacing(4)

		self.uiComboTREE = ComboTree(parent=None)
		self.uiComboTREE.setAlternatingRowColors(True)
		self.uiComboTREE.setDragEnabled(False)
		self.uiComboTREE.setDragDropMode(ComboTree.NoDragDrop)
		self.uiComboTREE.setSelectionMode(ComboTree.ExtendedSelection)
		self.uiComboTREE.dragFilter.dragPressed.connect(self.dragStart)
		self.uiComboTREE.dragFilter.dragReleased.connect(self.dragStop)
		comboLay.addWidget(self.uiComboTREE, 0, 0)

		comboFilterLay = QHBoxLayout()
		comboFilterLay.setContentsMargins(0, 0, 0, 0)
		self.uiComboFilterLINE = QLineEdit()
		self.uiComboFilterLINE.setPlaceholderText("Filter Combos...")
		self.uiComboFilterLINE.setClearButtonEnabled(True)
		comboFilterLay.addWidget(self.uiComboFilterLINE)
		self.uiComboExitIsolateBTN = QPushButton("Exit Isolate")
		self.uiComboExitIsolateBTN.setHidden(True)
		comboFilterLay.addWidget(self.uiComboExitIsolateBTN)
		comboLay.addItem(comboFilterLay, 1, 0)

		comboToolLay = QVBoxLayout()
		comboToolLay.setContentsMargins(0, 0, 0, 0)
		comboToolLay.setSpacing(4)

		self.uiNewComboActiveBTN = QPushButton("Combo Active")
		comboToolLay.addWidget(self.uiNewComboActiveBTN)
		self.uiNewComboSelectBTN = QPushButton("Combo Selected")
		comboToolLay.addWidget(self.uiNewComboSelectBTN)
		self.uiNewComboGroupBTN = QPushButton("Group")
		comboToolLay.addWidget(self.uiNewComboGroupBTN)
		self.uiNewComboShapeBTN = QPushButton("Shape")
		comboToolLay.addWidget(self.uiNewComboShapeBTN)
		self.uiDeleteComboBTN = QPushButton("Delete")
		comboToolLay.addWidget(self.uiDeleteComboBTN)

		self.uiShowDependentGRP = QGroupBox("Slider Filter")
		self.uiShowDependentGRP.setCheckable(True)
		self.uiShowDependentGRP.setChecked(False)
		sliderFilterLay = QVBoxLayout()
		sliderFilterLay.setAlignment(Qt.AlignTop)
		sliderFilterLay.setContentsMargins(4, 2, 4, 0)
		sliderFilterLay.setSpacing(2)
		self.uiComboDependAnyRDO = QRadioButton("Contains Any")
		self.uiComboDependAnyRDO.setAutoExclusive(True)
		self.uiComboDependAnyRDO.setChecked(True)
		sliderFilterLay.addWidget(self.uiComboDependAnyRDO)
		self.uiComboDependOnlyRDO = QRadioButton("Contains Only")
		self.uiComboDependOnlyRDO.setAutoExclusive(True)
		sliderFilterLay.addWidget(self.uiComboDependOnlyRDO)
		self.uiComboDependAllRDO = QRadioButton("Contains All")
		self.uiComboDependAllRDO.setAutoExclusive(True)
		sliderFilterLay.addWidget(self.uiComboDependAllRDO)
		self.uiComboDependLockCHK = QCheckBox("Lock Filter")
		sliderFilterLay.addWidget(self.uiComboDependLockCHK)
		self.uiShowDependentGRP.setLayout(sliderFilterLay)
		comboToolLay.addWidget(self.uiShowDependentGRP)
		comboToolLay.addStretch(1)
		self.uiAutoSetCombosCHK = QCheckBox("Auto Set")
		comboToolLay.addWidget(self.uiAutoSetCombosCHK)
		self.uiSelectSlidersBTN = QPushButton("Select Sliders")
		comboToolLay.addWidget(self.uiSelectSlidersBTN)
		self.uiSetSliderValsBTN = QPushButton("Set Slider Values")
		comboToolLay.addWidget(self.uiSetSliderValsBTN)

		comboLay.addItem(comboToolLay, 0, 1)

		self.uiComboShapesGRP.setLayout(comboLay)

		splitter.addWidget(self.uiMainShapesGRP)
		splitter.addWidget(self.uiComboShapesGRP)
		centralLayout.addWidget(splitter)

	def initConnectionsWidgets(self, centralLayout):
		self.uiConnectionGroupWID = QWidget()
		extractLay = QHBoxLayout()
		extractLay.setContentsMargins(0, 0, 0, 0)
		extractLay.setSpacing(4)

		self.uiShapeExtractBTN = QPushButton("Extract Shape")
		extractLay.addWidget(self.uiShapeExtractBTN)
		self.uiShapeConnectBTN = QPushButton("Connect From Simplex Selection")
		extractLay.addWidget(self.uiShapeConnectBTN)
		self.uiShapeConnectSceneBTN = QPushButton("Connect From Scene Selection")
		extractLay.addWidget(self.uiShapeConnectSceneBTN)

		self.uiConnectionGroupWID.setLayout(extractLay)

		centralLayout.addWidget(self.uiConnectionGroupWID)

	def initConnections(self):
		''' Make all the ui connections '''

		# Setup Trees!
		self.uiSliderTREE.setColumnWidth(1, 50)
		self.uiSliderTREE.setColumnWidth(2, 20)
		self.uiSliderFilterLINE.textChanged.connect(self.sliderStringFilter)

		self.uiComboTREE.setColumnWidth(1, 50)
		self.uiComboTREE.setColumnWidth(2, 20)
		self.uiComboFilterLINE.textChanged.connect(self.comboStringFilter)

		# dependency filter setup
		self.uiShowDependentGRP.toggled.connect(self.enableComboRequirements)
		self.uiComboDependAllRDO.toggled.connect(self.enableComboRequirements)
		self.uiComboDependAnyRDO.toggled.connect(self.enableComboRequirements)
		self.uiComboDependOnlyRDO.toggled.connect(self.enableComboRequirements)
		self.uiComboDependLockCHK.toggled.connect(self.setLockComboRequirement)
		#self.uiShowDependentGRP.toggled.connect(self.uiShowDependentWID.setVisible)
		#self.uiShowDependentWID.setVisible(False)

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

		## System level
		self.uiCurrentObjectTXT.editingFinished.connect(self.currentObjectChanged)
		self.uiCurrentObjectTXT.editingFinished.connect(lambda: self.uiCurrentObjectTXT.resize(self.uiCurrentObjectTXT.sizeHint()))
		self.uiGetSelectedObjectBTN.clicked.connect(self.getSelectedObject)
		self.uiClearSelectedObjectBTN.clicked.connect(self.clearSelectedObject)

		self.uiNewSystemBTN.clicked.connect(self.newSystem)
		self.uiRenameSystemBTN.clicked.connect(self.renameSystem)
		self.uiCurrentSystemCBOX.currentIndexChanged[int].connect(self.currentSystemChanged)

		# Extraction/connection
		self.uiShapeExtractBTN.clicked.connect(self.shapeExtract)
		self.uiShapeConnectBTN.clicked.connect(self.shapeConnect)
		self.uiShapeConnectSceneBTN.clicked.connect(self.shapeConnectScene)

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

		self.uiLegacyJsonACT.toggled.connect(self.setSimplexLegacy)

	def initUI(self):
		self.setWindowTitle("{} {}".format(self.WindowTitle, self.Version))
		self.setStyleSheet(stylesheets.Default)
		# self.setStyleSheet(stylesheets.Solarized)

		self.uiSliderExitIsolateBTN.hide()
		self.uiComboExitIsolateBTN.hide()

		self._toolPlugins, self._contextPlugins = loadPlugins()
		buildToolMenu(self, self._toolPlugins)
		self.uiSliderTREE.setPlugins(self._contextPlugins)
		self.uiComboTREE.setPlugins(self._contextPlugins)

		if DCC.program == "dummy":
			#self.getSelectedObject()
			self.uiObjectGRP.setEnabled(False)
			self.uiSystemGRP.setEnabled(False)

		self.uiClearSelectedObjectBTN.hide()
		self.uiMainShapesGRP.setEnabled(False)
		self.uiComboShapesGRP.setEnabled(False)
		self.uiConnectionGroupWID.setEnabled(False)
		self.loadSettings()
		self._sliderMul = 2.0 if self.uiDoubleSliderRangeACT.isChecked() else 1.0

		self.travDialog = TraversalDialog(self)
		self.falloffDialog = FalloffDialog(self)
		#self.showTraversalDialog()
		type(self).openedDialogs.append(weakref.ref(self))

	@classmethod
	def lastOpenedDialog(cls):
		''' Returns the last currently opened dialog that still exists '''
		for dlgRef in reversed(cls.openedDialogs):
			dlg = dlgRef()
			if dlg is not None:
				return dlg
		return None

	def showTraversalDialog(self):
		''' Display the traversal dialog '''
		self.travDialog.show()
		self.travDialog.setGeometry(30, 30, 400, 400)

	def showFalloffDialog(self):
		''' Display the Falloff Dialog '''
		self.falloffDialog.show()
		pp = self.falloffDialog.pos()
		x, y = pp.x(), pp.y()
		if x < 0 or y < 0:
			self.falloffDialog.move(max(x, 0), max(y, 0))

	def dragStart(self):
		''' Slot for handling the start of a MMB Drag event '''
		if self.simplex is not None:
			self.simplex.DCC.undoOpen()

	def dragStop(self):
		''' Slot for handling the end of a MMB Drag event '''
		if self.simplex is not None:
			self.simplex.DCC.undoClose()

	def storeSettings(self):
		''' Store the state of the UI for the next run '''
		if blurdev is None:
			pref = QSettings("Blur", "Simplex3")
			pref.setValue("geometry", self.saveGeometry())
			pref.sync()
		else:
			pref = blurdev.prefs.find("tools/simplex3")
			pref.recordProperty("geometry", self.saveGeometry())
			pref.save()

	def loadSettings(self):
		''' Load the state of the UI from a previous run '''
		if blurdev is None:
			pref = QSettings("Blur", "Simplex3")
			self.restoreGeometry(toPyObject(pref.value("geometry")))
		else:
			pref = blurdev.prefs.find("tools/simplex3")
			geo = pref.restoreProperty('geometry', None)
			if geo is not None:
				self.restoreGeometry(geo)

	def closeEvent(self, event):
		''' Handle the close event '''
		self.storeSettings()
		self.deleteLater()

	# Undo/Redo
	def newScene(self):
		''' Call this before a new scene is created. Usually called from the stack '''
		self.clearSelectedObject()

	def handleUndo(self):
		''' Call this after an undo/redo action. Usually called from the stack '''
		rev = self.simplex.DCC.getRevision()
		data = self.simplex.stack.getRevision(rev)
		if data is not None:
			self.setSystem(data)
			self.uiSliderTREE.setItemExpansion()
			self.uiComboTREE.setItemExpansion()

	def currentSystemChanged(self, idx):
		''' Slot called when the current system changes '''
		if idx == -1:
			self.setSystem(None)
			return
		name = str(self.uiCurrentSystemCBOX.currentText())
		if not name:
			self.setSystem(None)
			return
		if self.simplex is not None:
			if self.simplex.name == name:
				return # Do nothing

		pBar = QProgressDialog("Loading from Mesh", "Cancel", 0, 100, self)
		system = Simplex.buildSystemFromMesh(self._currentObject, name, sliderMul=self._sliderMul, pBar=pBar)
		self.setSystem(system)
		pBar.close()

	def setSystem(self, system):
		''' Set the system on this UI

		Parameters
		----------
		system : Simplex
			The Simplex system to load into this UI
		'''
		if system == self.simplex:
			return

		if self.simplex is not None:
			# disconnect the previous stuff
			sliderSelModel = self.uiSliderTREE.selectionModel()
			sliderSelModel.selectionChanged.disconnect(self.unifySliderSelection)
			sliderSelModel.selectionChanged.disconnect(self.populateComboRequirements)
			sliderSelModel.selectionChanged.disconnect(self.autoSetSliders)

			comboSelModel = self.uiComboTREE.selectionModel()
			comboSelModel.selectionChanged.disconnect(self.unifyComboSelection)
			comboSelModel.selectionChanged.disconnect(self.autoSetComboSliders)

			oldStack = self.simplex.stack
		else:
			oldStack = Stack()

		if system is None:
			#self.toolActions.simplex = None
			self.uiSliderTREE.setModel(QStandardItemModel())
			self.uiComboTREE.setModel(QStandardItemModel())
			self.simplex = system
			self.uiMainShapesGRP.setEnabled(False)
			self.uiComboShapesGRP.setEnabled(False)
			self.uiConnectionGroupWID.setEnabled(False)
			self.falloffDialog.loadSimplex()
			self.simplexLoaded.emit()
			return

		# set and connect the new stuff
		self.simplex = system
		self.simplex.models = []
		self.simplex.falloffModels = []
		self.simplex.stack = oldStack

		#self.toolActions.simplex = self.simplex

		simplexModel = SimplexModel(self.simplex, None)

		sliderModel = SliderModel(simplexModel, None)
		sliderProxModel = SliderFilterModel(sliderModel)
		self.uiSliderTREE.setModel(sliderProxModel)
		sliderSelModel = self.uiSliderTREE.selectionModel()
		sliderSelModel.selectionChanged.connect(self.unifySliderSelection)
		sliderSelModel.selectionChanged.connect(self.populateComboRequirements)
		sliderSelModel.selectionChanged.connect(self.autoSetSliders)

		comboModel = ComboModel(simplexModel, None)
		comboProxModel = ComboFilterModel(comboModel)
		self.uiComboTREE.setModel(comboProxModel)
		comboSelModel = self.uiComboTREE.selectionModel()
		comboSelModel.selectionChanged.connect(self.unifyComboSelection)
		comboSelModel.selectionChanged.connect(self.autoSetComboSliders)

		self.falloffDialog.loadSimplex()

		# Make sure the UI is up and running
		self.enableComboRequirements()
		self.uiMainShapesGRP.setEnabled(True)
		self.uiComboShapesGRP.setEnabled(True)
		self.uiConnectionGroupWID.setEnabled(True)

		self.setSimplexLegacy()
		self.simplexLoaded.emit()

	# Helpers
	def getSelectedItems(self, tree, typ=None):
		''' Convenience function to get the selected system items

		Parameters
		----------
		tree : QTreeView
			The tree to get selected items from
		typ : Type
			The type of objects to return

		Returns
		-------
		[object, ...]
			A list of selected items
		'''
		sel = tree.selectedIndexes()
		sel = [i for i in sel if i.column() == 0]
		model = tree.model()
		items = [model.itemFromIndex(i) for i in sel]
		if typ is not None:
			items = [i for i in items if isinstance(i, typ)]
		return items

	def getCurrentObject(self):
		''' Convenience function to get the current object loaded into the UI '''
		return self._currentObject

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
		an item on the slider tree is selected
		'''
		mods = QApplication.keyboardModifiers()
		if not mods & (Qt.ControlModifier | Qt.ShiftModifier):
			comboSelModel = self.uiComboTREE.selectionModel()
			if not comboSelModel:
				return

			with signalsBlocked(comboSelModel):
				comboSelModel.clearSelection()
			self.uiComboTREE.viewport().update()

	def unifyComboSelection(self):
		''' Clear the selection of the slider tree when
		an item on the combo tree is selected
		'''
		mods = QApplication.keyboardModifiers()
		if not mods & (Qt.ControlModifier | Qt.ShiftModifier):
			sliderSelModel = self.uiSliderTREE.selectionModel()
			if not sliderSelModel:
				return
			with signalsBlocked(sliderSelModel):
				sliderSelModel.clearSelection()
			self.uiSliderTREE.viewport().update()

	# dependency setup
	def setLockComboRequirement(self):
		''' Refresh the combo selection filter with the new filterLock state '''
		comboModel = self.uiComboTREE.model()
		if not comboModel:
			return
		self.populateComboRequirements()

	def populateComboRequirements(self):
		''' Let the combo tree know the requirements from the slider tree '''
		items = self.uiSliderTREE.getSelectedItems(Slider)
		comboModel = self.uiComboTREE.model()
		locked = self.uiComboDependLockCHK.isChecked()
		if not locked:
			comboModel.requires = items
		if comboModel.filterRequiresAll or comboModel.filterRequiresAny or comboModel.filterRequiresOnly:
			comboModel.invalidateFilter()

	def enableComboRequirements(self):
		''' Set the requirements for the combo filter model '''
		comboModel = self.uiComboTREE.model()
		if not comboModel:
			return
		comboModel.filterRequiresAll = self.uiComboDependAllRDO.isChecked() and self.uiShowDependentGRP.isChecked()
		comboModel.filterRequiresAny = self.uiComboDependAnyRDO.isChecked() and self.uiShowDependentGRP.isChecked()
		comboModel.filterRequiresOnly = self.uiComboDependOnlyRDO.isChecked() and self.uiShowDependentGRP.isChecked()
		comboModel.invalidateFilter()

	# Bottom Left Corner Buttons
	def zeroAllSliders(self):
		''' Slot to Zero all Sliders in Slider UI panel '''
		if self.simplex is None:
			return
		sliders = self.simplex.sliders
		weights = [0.0] * len(sliders)
		self.simplex.setSlidersWeights(sliders, weights)
		self.uiSliderTREE.repaint()

	def zeroSelectedSliders(self):
		''' Slot to Zero the selected sliders in the UI panel '''
		if self.simplex is None:
			return
		items = self.uiSliderTREE.getSelectedItems(Slider)
		values = [0.0] * len(items)
		self.simplex.setSlidersWeights(items, values)
		self.uiSliderTREE.repaint()

	def selectCtrl(self):
		''' Select the Control object in the DCC '''
		if self.simplex is None:
			return
		self.simplex.DCC.selectCtrl()

	def autoSetSliders(self):
		''' Automatically set any selected sliders to 1.0 '''
		if self.simplex is None:
			return
		if not self.uiAutoSetSlidersCHK.isChecked():
			return
		sel = set(self.uiSliderTREE.getSelectedItems(Slider))
		sliders = self.simplex.sliders

		weights = [0.0] * len(sliders)
		for i, slider in enumerate(sliders):
			if slider in sel:
				weights[i] = 1.0
		self.simplex.setSlidersWeights(sliders, weights)
		self.uiSliderTREE.repaint()

	def _getAName(self, tpe, default=None, taken=tuple(), uniqueAccept=False):
		''' uniqueAccept forces the user to provide and accept a unique name
			If the user enters a non-unique name, the name is uniquified, and the
			dialog is re-shown with the unique name as the default suggestion
		'''
		tpe = tpe.lower()
		uTpe = tpe[0].upper() + tpe[1:]

		unique = False
		default = getNextName(default, taken)
		while not unique:
			eMsg = "Enter a name for the new {0}".format(tpe)
			newName, good = QInputDialog.getText(self, "New {0}".format(uTpe), eMsg, text=default)
			if not good:
				return None
			if len(newName) < 3:
				message = 'Please use names longer than 2 letters'
				QMessageBox.warning(self, 'Warning', message)
				return None
			if not NAME_CHECK.match(newName):
				message = '{0} name can only contain letters and numbers, and cannot start with a number'
				message = message.format(uTpe)
				QMessageBox.warning(self, 'Warning', message)
				return None

			unqName = getNextName(newName, taken)
			unique = (unqName == newName) or uniqueAccept
			default = unqName

		return default

	# Top Left Corner Buttons
	def newSliderGroup(self):
		''' Slot to Create a new slider group '''
		if self.simplex is None:
			return

		newName = self._getAName('group', default='Group')
		if newName is None:
			return

		Group.createGroup(str(newName), self.simplex, groupType=Slider)
		#self.uiSliderTREE.model().invalidateFilter()
		#self.uiComboTREE.model().invalidateFilter()

	def newSlider(self):
		''' Slot to create a new slider '''
		if self.simplex is None:
			return

		newName = self._getAName('slider')
		if newName is None:
			return

		idxs = self.uiSliderTREE.getSelectedIndexes()
		groups = coerceIndexToParentType(idxs, Group)
		group = groups[0].model().itemFromIndex(groups[0]) if groups else None

		Slider.createSlider(str(newName), self.simplex, group=group)

	def newSliderShape(self):
		''' Slot to create a new Shape in a Slider's progression '''
		pars = self.uiSliderTREE.getSelectedItems(Slider)
		if not pars:
			return
		parItem = pars[0]
		parItem.createShape()
		self.uiSliderTREE.model().invalidateFilter()

	def sliderTreeDelete(self):
		''' Delete some objects in the slider tree '''
		idxs = self.uiSliderTREE.getSelectedIndexes()
		roots = coerceIndexToRoots(idxs)
		if not roots:
			QMessageBox.warning(self, 'Warning', 'Nothing Selected')
			return
		roots = makeUnique([i.model().itemFromIndex(i) for i in roots])
		for r in roots:
			if isinstance(r, Simplex):
				QMessageBox.warning(self, 'Warning', 'Cannot delete a simplex system this way (for now)')
				return

		for r in roots:
			r.delete()
		self.uiSliderTREE.model().invalidateFilter()

	# Top Right Corner Buttons
	def comboTreeDelete(self):
		''' Delete some objects in the Combo tree '''
		idxs = self.uiComboTREE.getSelectedIndexes()
		roots = coerceIndexToRoots(idxs)
		roots = makeUnique([i.model().itemFromIndex(i) for i in roots])
		for r in roots:
			r.delete()
		self.uiComboTREE.model().invalidateFilter()

	def _newCombo(self, sliders, values):
		if len(sliders) < 2:
			message = 'A combo must use at least 2 sliders'
			QMessageBox.warning(self, 'Warning', message)
			return

		ccd = ComboCheckDialog(sliders, values=values, mode='create', parent=self)
		ccd.move(self.pos())
		ccd.exec_()

	def newActiveCombo(self):
		''' Create a combo based on the UI Sliders that are currently nonzero '''
		if self.simplex is None:
			return
		sliders = []
		values = {}
		for s in self.simplex.sliders:
			if s.value != 0.0:
				sliders.append(s)
				values[s] = [s.value]
		self._newCombo(sliders, values)

	def newSelectedCombo(self):
		''' Create a combo based on the currently selected UI sliders '''
		if self.simplex is None:
			return
		sliders = self.uiSliderTREE.getSelectedItems(Slider)
		values = {s: [1.0] for s in sliders}
		self._newCombo(sliders, values)

	def newComboShape(self):
		''' Create a new shape in the Combo's progression '''
		parIdxs = self.uiComboTREE.getSelectedIndexes()
		pars = coerceIndexToParentType(parIdxs, Combo)
		if not pars:
			return

		parItem = pars[0].model().itemFromIndex(pars[0]) if pars else None
		parItem.createShape()
		self.uiComboTREE.model().invalidateFilter()

	def newComboGroup(self):
		''' Create a new group for organizing combos '''
		if self.simplex is None:
			return

		newName = self._getAName('group', default='Group')
		if newName is None:
			return

		Group.createGroup(str(newName), self.simplex, groupType=Combo)
		#self.uiComboTREE.model().invalidateFilter()
		#self.uiSliderTREE.model().invalidateFilter()

	# Bottom right corner buttons
	def setSliderVals(self):
		''' Set all slider values to those stored in the currently selected Combos '''
		if self.simplex is None:
			return
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
		self.uiSliderTREE.repaint()

	def selectSliders(self):
		''' Select the sliders that are contained in the currently selected Combos '''
		combos = self.uiComboTREE.getSelectedItems(Combo)
		sliders = []
		for combo in combos:
			for pair in combo.pairs:
				sliders.append(pair.slider)
		self.uiSliderTREE.setItemSelection(sliders)

	def autoSetComboSliders(self):
		''' Automatically set the DCC Slider values to activate the currently selected Combos '''
		if self.simplex is None:
			return
		if not self.uiAutoSetCombosCHK.isChecked():
			return
		sel = set(self.uiComboTREE.getSelectedItems(Combo))
		sv = {}
		for combo in self.simplex.combos:
			isSel = combo in sel
			for pair in combo.pairs:
				curVal = sv.get(pair.slider, 0.0)
				newVal = pair.value if isSel else 0.0
				if abs(newVal) >= abs(curVal):
					sv[pair.slider] = newVal

		sliders, weights = zip(*sv.items())
		self.simplex.setSlidersWeights(sliders, weights)
		self.uiSliderTREE.repaint()

	# Extraction/connection
	def shapeConnectScene(self):
		''' Connect any selected meshes into the system based on the name '''
		if self.simplex is None:
			return
		# make a dict of name:object
		sel = DCC.getSelectedObjects()
		selDict = {}
		for s in sel:
			name = DCC.getObjectName(s)
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

	def sliderShapeExtract(self):
		''' Create meshes that are possibly live-connected to the shapes '''
		sliderIdxs = self.uiSliderTREE.getSelectedIndexes()
		return self.shapeIndexExtract(sliderIdxs)

	def comboShapeExtract(self):
		''' Create meshes that are possibly live-connected to the shapes '''
		comboIdxs = self.uiComboTREE.getSelectedIndexes()
		return self.shapeIndexExtract(comboIdxs)

	def shapeExtract(self):
		''' Create meshes that are possibly live-connected to the shapes '''
		sliderIdxs = self.uiSliderTREE.getSelectedIndexes()
		comboIdxs = self.uiComboTREE.getSelectedIndexes()
		return self.shapeIndexExtract(sliderIdxs + comboIdxs)

	def shapeIndexExtract(self, indexes, live=None):
		''' Create meshes that are possibly live-connected to the shapes

		Parameters
		----------
		indexes : [QModelIndex, ...]
			A list of indexes to extract
		live : bool or None
			Whether the connection is live. If None, check the UI properties
		'''
		if live is None:
			live = self.uiLiveShapeConnectionACT.isChecked()

		pairs = coerceIndexToChildType(indexes, ProgPair)
		pairs = [i.model().itemFromIndex(i) for i in pairs]
		pairs = makeUnique([i for i in pairs if not i.shape.isRest])
		pairs.sort(key=lambda x: naturalSortKey(x.shape.name))

		# Set up the progress bar
		pBar = QProgressDialog("Extracting Shapes", "Cancel", 0, 100, self)
		pBar.setMaximum(len(pairs))

		# Do the extractions
		offset = 10
		extracted = []
		for pair in pairs:
			c = pair.prog.controller
			ext = c.extractShape(pair.shape, live=live, offset=offset)
			extracted.append(ext)
			offset += 5

			# ProgressBar
			pBar.setValue(pBar.value() + 1)
			pBar.setLabelText("Extracting:\n{0}".format(pair.shape.name))
			QApplication.processEvents()
			if pBar.wasCanceled():
				return extracted

		pBar.close()
		return extracted

	def shapeConnect(self):
		''' Match any selected Shapes to DCC meshes based on their names, then delete the Meshes '''
		sliderIdxs = self.uiSliderTREE.getSelectedIndexes()
		comboIdxs = self.uiComboTREE.getSelectedIndexes()
		self.shapeConnectIndexes(sliderIdxs + comboIdxs)

	def shapeConnectIndexes(self, indexes):
		''' Match the provided shapes to DCC meshes based on their names, then delete the Meshes

		Parameters
		----------
		indexes : list of QModelIndex
			A list of selected model indexes
		'''
		pairs = coerceIndexToChildType(indexes, ProgPair)
		pairs = [i.model().itemFromIndex(i) for i in pairs]
		pairs = makeUnique([i for i in pairs if not i.shape.isRest])

		# Set up the progress bar
		pBar = QProgressDialog("Connecting Shapes", "Cancel", 0, 100, self)
		pBar.setMaximum(len(pairs))

		# Do the extractions
		for pair in pairs:
			c = pair.prog.controller
			c.connectShape(pair.shape, delete=True)

			# ProgressBar
			pBar.setValue(pBar.value() + 1)
			pBar.setLabelText("Extracting:\n{0}".format(pair.shape.name))
			QApplication.processEvents()
			if pBar.wasCanceled():
				return

		pBar.close()

	def shapeMatch(self):
		''' Match any selected Shapes to A selected DCC mesh '''
		sliderIdxs = self.uiSliderTREE.getSelectedIndexes()
		comboIdxs = self.uiComboTREE.getSelectedIndexes()
		self.shapeMatchIndexes(sliderIdxs + comboIdxs)

	def shapeMatchIndexes(self, indexes):
		''' Match any provided shapes to A selected DCC mesh

		Parameters
		----------
		indexes : list of QModelIndex
			A list of selected model indexes
		'''
		# make a dict of name:object
		sel = DCC.getSelectedObjects()
		if not sel:
			return
		mesh = sel[0]

		pairs = coerceIndexToChildType(indexes, ProgPair)
		pairs = [i.model().itemFromIndex(i) for i in pairs]
		pairs = makeUnique([i for i in pairs if not i.shape.isRest])

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
		''' Match all selected shapes to the rest '''
		sliderIdxs = self.uiSliderTREE.getSelectedIndexes()
		comboIdxs = self.uiComboTREE.getSelectedIndexes()
		self.shapeClearIndexes(sliderIdxs + comboIdxs)

	def shapeClearIndexes(self, indexes):
		''' Match all provided shapes to the rest

		Parameters
		----------
		indexes : list of QModelIndex
			A list of selected model indexes
		'''
		pairs = coerceIndexToChildType(indexes, ProgPair)
		pairs = [i.model().itemFromIndex(i) for i in pairs]
		pairs = makeUnique([i for i in pairs if not i.shape.isRest])

		for pair in pairs:
			pair.shape.zeroShape()

	# System level
	def loadObject(self, thing):
		''' Load a DCC mesh into the UI

		Parameters
		----------
		thing : object
			The DCC mesh to load into the UI
		'''
		if thing is None:
			return

		self.uiClearSelectedObjectBTN.show()
		self.uiCurrentSystemCBOX.clear()
		objName = DCC.getObjectName(thing)
		self._currentObject = thing
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
		''' Slot called when the current DCC object is changed '''
		name = str(self.uiCurrentObjectTXT.text())
		if self._currentObjectName == name:
			return
		if not name:
			return

		newObject = DCC.getObjectByName(name)
		if not newObject:
			return

		self.loadObject(newObject)

	def getSelectedObject(self):
		''' Load the first selected DCC object into the UI '''
		sel = DCC.getSelectedObjects()
		if not sel:
			return
		newObj = sel[0]
		if not newObj:
			return
		self.loadObject(newObj)

	def clearSelectedObject(self):
		''' Unload the current DCC object from the UI '''
		self.uiClearSelectedObjectBTN.hide()
		self.uiCurrentSystemCBOX.clear()
		self._currentObject = None
		self._currentObjectName = None
		self.uiCurrentObjectTXT.setText('')
		self.setSystem(None)
		# Clear the current system

	def newSystem(self):
		''' Create a new system on the current DCC Object '''
		if self._currentObject is None:
			QMessageBox.warning(self, 'Warning', 'Must have a current object selection')
			return

		newName = self._getAName('system')
		if newName is None:
			return

		newSystem = Simplex.buildEmptySystem(self._currentObject, newName, sliderMul=self._sliderMul)
		with signalsBlocked(self.uiCurrentSystemCBOX):
			self.uiCurrentSystemCBOX.addItem(newName)
			self.uiCurrentSystemCBOX.setCurrentIndex(self.uiCurrentSystemCBOX.count()-1)
			self.setSystem(newSystem)

	def renameSystem(self):
		''' Rename the current Simplex system '''
		if self.simplex is None:
			return

		sysNames = [str(self.uiCurrentSystemCBOX.itemText(i)) for i in range(self.uiCurrentSystemCBOX.count())]
		newName = self._getAName('system', taken=sysNames)
		if newName is None:
			return

		self.simplex.name = newName
		idx = self.uiCurrentSystemCBOX.currentIndex()
		self.uiCurrentSystemCBOX.setItemText(idx, newName)

		self.currentSystemChanged(idx)

	def setSimplexLegacy(self):
		''' Slot to toggle the legacy behavior of the current Simplex system '''
		if self.simplex is not None:
			self.simplex.setLegacy(self.uiLegacyJsonACT.isChecked())
			self.simplex.DCC.incrementRevision()

	# File Menu
	def importSystemFromFile(self):
		''' Open a File Dialog to load a simplex system from a file.
		Systems can be in either .smpx, or .json formats
		'''
		if self._currentObject is None:
			impTypes = ['smpx']
		else:
			impTypes = ['smpx', 'json']

		if blurdev is None:
			pref = QSettings("Blur", "Simplex3")
			defaultPath = str(toPyObject(pref.value('systemImport', os.path.join(os.path.expanduser('~')))))
			path = self._fileDialog("Import Template", defaultPath, impTypes, save=False)
			if not path:
				return
			pref.setValue('systemImport', os.path.dirname(path))
			pref.sync()
		else:
			# Blur Prefs
			pref = blurdev.prefs.find('tools/simplex3')
			defaultPath = pref.restoreProperty('systemImport', os.path.join(os.path.expanduser('~')))
			path = self._fileDialog("Import Template", defaultPath, impTypes, save=False)
			if not path:
				return
			pref.recordProperty('systemImport', os.path.dirname(path))
			pref.save()
		self.loadFile(path)

	def loadFile(self, path):
		pBar = QProgressDialog("Loading Shapes", "Cancel", 0, 100, self)
		pBar.show()
		QApplication.processEvents()

		# TODO: Come up with a better list of possibilites for loading
		# simplex files, and make the appropriate methods on the Simplex
		if path.endswith('.smpx'):
			newSystem = Simplex.buildSystemFromSmpx(path, self._currentObject, sliderMul=self._sliderMul, pBar=pBar)
			if newSystem is None:
				QMessageBox.warning(self, 'Point Count Mismatch', 'The .smpx file point count does not match the current object')
				pBar.close()
				return

		elif path.endswith('.json'):
			newSystem = Simplex.buildSystemFromJson(path, self._currentObject, sliderMul=self._sliderMul, pBar=pBar)

		with signalsBlocked(self.uiCurrentSystemCBOX):
			self.loadObject(newSystem.DCC.mesh)
			idx = self.uiCurrentSystemCBOX.findText(self._currentObjectName)
			if idx >= 0:
				self.uiCurrentSystemCBOX.setCurrentIndex(idx)
			else:
				self.uiCurrentSystemCBOX.addItem(newSystem.name)
				self.uiCurrentSystemCBOX.setCurrentIndex(self.uiCurrentSystemCBOX.count()-1)

		self.setSystem(newSystem)
		pBar.close()

	def _fileDialog(self, title, initPath, filters, save=True):
		''' Convenience function for displaying File Dialogs '''
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
		''' Open a file dialog and export a system to the chosen path '''
		if self._currentObject is None:
			QMessageBox.warning(self, 'Warning', 'Must have a current object selection')
			return

		if blurdev is None:
			pref = QSettings("Blur", "Simplex3")
			defaultPath = str(toPyObject(pref.value('systemExport', os.path.join(os.path.expanduser('~')))))
			path = self._fileDialog("Export Template", defaultPath, ["smpx", "json"], save=True)
			if not path:
				return
			pref.setValue('systemExport', os.path.dirname(path))
			pref.sync()
		else:
			# Blur Prefs
			pref = blurdev.prefs.find('tools/simplex3')
			defaultPath = pref.restoreProperty('systemExport', os.path.join(os.path.expanduser('~')))
			path = self._fileDialog("Export Template", defaultPath, ["smpx", "json"], save=True)
			if not path:
				return
			pref.recordProperty('systemExport', os.path.dirname(path))
			pref.save()

		if path.endswith('.smpx'):
			pBar = QProgressDialog("Exporting smpx File", "Cancel", 0, 100, self)
			pBar.show()
			self.simplex.exportAbc(path, pBar)
			pBar.close()
		elif path.endswith('.json'):
			dump = self.simplex.dump()
			with open(path, 'w') as f:
				f.write(dump)

	# Slider Settings
	def setSelectedSliderGroups(self, group):
		''' Set the group for the selected Sliders

		Parameters
		----------
		group : Group
			The group that will take the selected Sliders
		'''
		if not group:
			return
		sliders = self.uiSliderTREE.getSelectedItems(Slider)
		group.take(sliders)
		self.uiSliderTREE.viewport().update()

	def setSelectedSliderFalloff(self, falloff, state):
		''' Set the Falloffs for the selected Sliders

		Parameters
		----------
		falloff : Falloff
			The falloff to set on the selected sliders
		state : bool
			Whether to add or remove this falloff from the selection
		'''
		if not falloff:
			return
		sliders = self.uiSliderTREE.getSelectedItems(Slider)
		for s in sliders:
			if state == Qt.Checked:
				s.prog.addFalloff(falloff)
			else:
				s.prog.removeFalloff(falloff)
		self.uiSliderTREE.viewport().update()

	def setSelectedSliderInterp(self, interp):
		''' Set the interpolation for the selected sliders

		Parameters
		----------
		interp : str
			The interpolation to set on the selection.
			Could be 'linear', 'spline', or 'splitSpline'
		'''
		sliders = self.uiSliderTREE.getSelectedItems(Slider)
		for s in sliders:
			s.prog.interp = interp

	# Combo Settings
	def setSelectedComboSolveType(self, stVal):
		''' Set the solve type for the selected combos

		Parameters
		----------
		stVal : str
			The solve type to set for the combos.
			See Combo.solveTypes for a list
		'''
		combos = self.uiComboTREE.getSelectedItems(Combo)
		for c in combos:
			c.solveType = stVal

	# Edit Menu
	def hideRedundant(self):
		''' Hide redundant items from the Slider and Combo trees based on a user preference '''
		check = self.uiHideRedundantACT.isChecked()
		comboModel = self.uiComboTREE.model()
		comboModel.filterShapes = check
		comboModel.invalidateFilter()
		sliderModel = self.uiSliderTREE.model()
		sliderModel.doFilter = check
		sliderModel.invalidateFilter()

	def setSliderRange(self):
		''' Double the range for the sliders *IN THE DCC ONLY* based on a user preference '''
		self._sliderMul = 2.0 if self.uiDoubleSliderRangeACT.isChecked() else 1.0
		if self.simplex is None:
			return
		self.simplex.DCC.sliderMul = self._sliderMul
		self.simplex.DCC.setSlidersRange(self.simplex.sliders)

	# Isolation
	def isSliderIsolate(self):
		''' Check if the slider tree is currently isolated '''
		model = self.uiSliderTREE.model()
		if model:
			return bool(model.isolateList)
		return False

	def sliderIsolateSelected(self):
		''' Isolate the selected Sliders in the Slider Tree '''
		self.uiSliderTREE.isolateSelected()
		self.uiSliderExitIsolateBTN.show()

	def sliderTreeExitIsolate(self):
		''' Disable isolation mode in the Slider Tree '''
		self.uiSliderTREE.exitIsolate()
		self.uiSliderExitIsolateBTN.hide()

	def isComboIsolate(self):
		''' Check if the combo tree is currently isolated '''
		model = self.uiComboTREE.model()
		if model:
			return bool(model.isolateList)
		return False

	def comboIsolateSelected(self):
		''' Isolate the selected Combos in the Combo Tree '''
		self.uiComboTREE.isolateSelected()
		self.uiComboExitIsolateBTN.show()

	def comboTreeExitIsolate(self):
		''' Disable isolation mode in the Combo Tree '''
		self.uiComboTREE.exitIsolate()
		self.uiComboExitIsolateBTN.hide()


