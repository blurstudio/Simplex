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
#pylint: disable=unused-argument,too-many-public-methods,relative-import
#pylint: disable=too-many-statements,no-self-use,missing-docstring
import os, sys, re, json, copy, weakref
from functools import wraps
from contextlib import contextmanager

# This module imports QT from PyQt4, PySide or PySide2
# Depending on what's available
from Qt import QtCompat
#from Qt.QtCore import Slot
from Qt.QtCore import Qt, QSettings
from Qt.QtGui import QStandardItemModel
from Qt.QtWidgets import QMessageBox, QInputDialog, QMenu, QApplication, QTreeView, QDataWidgetMapper
from Qt.QtWidgets import QDialog, QProgressDialog, QPushButton, QComboBox, QCheckBox

from utils import toPyObject, getUiFile, getNextName, makeUnique

from interfaceItems import (ProgPair, Slider, Combo, Traversal, Group, Simplex, Shape, Stack, Falloff)

from interfaceModel import (SliderModel, ComboModel, ComboFilterModel, SliderFilterModel,
							TraversalModel, TraversalFilterModel,
							coerceIndexToChildType, coerceIndexToParentType, coerceIndexToRoots,
							SliderGroupModel, FalloffModel, FalloffDataModel, SimplexModel)

from interface import undoContext, rootWindow, DCC, DISPATCH
from plugInterface import loadPlugins, buildToolMenu, buildRightClickMenu
from interfaceModelTrees import TraversalTree

try:
	# This module is unique to Blur Studio
	import blurdev
except ImportError:
	blurdev = None

NAME_CHECK = re.compile(r'[A-Za-z][\w.]*')

class TraversalDialog(QDialog):
	''' The main ui for simplex '''
	def __init__(self, parent):
		super(TraversalDialog, self).__init__(parent)

		uiPath = getUiFile(__file__)
		QtCompat.loadUi(uiPath, self)

		# Load the custom tree manually
		self.uiTraversalTREE = TraversalTree(self)
		self.uiTraversalTREE.setDragEnabled(False)
		self.uiTraversalTREE.setDragDropMode(TraversalTree.NoDragDrop)
		#self.uiTraversalTREE.setSelectionMode(TraversalTree.ExtendedSelection)
		self.uiTraversalTREE.setSelectionMode(TraversalTree.SingleSelection) # For now
		self.uiTraversalTREE.dragFilter.dragPressed.connect(self.dragStart)
		self.uiTraversalTREE.dragFilter.dragReleased.connect(self.dragStop)
		self.uiTraversalLAY.addWidget(self.uiTraversalTREE)
		self.simplex = None
		self.parent().simplexLoaded.connect(self.loadSimplex)

		self.uiTravDeleteBTN.clicked.connect(self.deleteTrav)
		self.uiTravNewBTN.clicked.connect(self.newTrav)
		self.uiTravNewGroupBTN.clicked.connect(self.newGroup)
		self.uiTravNewShapeBTN.clicked.connect(self.newShape)
		self.uiTravSetMultiplierBTN.clicked.connect(self.setMultiplier)
		self.uiTravSetProgressorBTN.clicked.connect(self.setProgressor)
		self.uiShapeExtractBTN.clicked.connect(self.shapeExtract)
		self.uiShapeConnectBTN.clicked.connect(self.shapeConnectFromSelection)

		self.loadSimplex()

	def dragStart(self):
		if self.simplex is not None:
			self.simplex.DCC.undoOpen()

	def dragStop(self):
		if self.simplex is not None:
			self.simplex.DCC.undoClose()

	def loadSimplex(self):
		parent = self.parent()
		system = parent.simplex
		if system is None:
			self.simplex = system
			self.uiTraversalTREE.setModel(QStandardItemModel())

			self.uiTravDeleteBTN.setEnabled(False)
			self.uiTravNewBTN.setEnabled(False)
			self.uiTravNewGroupBTN.setEnabled(False)
			self.uiTravNewShapeBTN.setEnabled(False)
			self.uiTravSetMultiplierBTN.setEnabled(False)
			self.uiTravSetProgressorBTN.setEnabled(False)
			self.uiShapeExtractBTN.setEnabled(False)
			self.uiShapeConnectBTN.setEnabled(False)
			return
		else:
			self.uiTravDeleteBTN.setEnabled(True)
			self.uiTravNewBTN.setEnabled(True)
			self.uiTravNewGroupBTN.setEnabled(True)
			self.uiTravNewShapeBTN.setEnabled(True)
			self.uiTravSetMultiplierBTN.setEnabled(True)
			self.uiTravSetProgressorBTN.setEnabled(True)
			self.uiShapeExtractBTN.setEnabled(True)
			self.uiShapeConnectBTN.setEnabled(True)

		if system == self.simplex:
			return

		self.simplex = system

		sliderProxyModel = self.parent().uiSliderTREE.model()
		if not sliderProxyModel:
			self.uiTraversalTREE.setModel(None)
			return
		sliderModel = sliderProxyModel.sourceModel()
		simplexModel = sliderModel.sourceModel()

		travModel = TraversalModel(simplexModel)
		travProxModel = TraversalFilterModel(travModel)
		self.uiTraversalTREE.setModel(travProxModel)

	def deleteTrav(self):
		idxs = self.uiTraversalTREE.getSelectedIndexes()
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

		self.uiTraversalTREE.model().invalidateFilter()

	def newTrav(self):
		# Reads selected items in the main window
		# There's no "good" way to do this that I can think of
		# I may need to add a "swap roles" right-click or button

		# It may be smart to figure out if one of the things
		# has a progression, and set that to the progress object
		pass

	def newGroup(self):
		if self.simplex is None:
			return
		newName, good = QInputDialog.getText(self, "New Group", "Enter a name for the new group", text="Group")
		if not good:
			return
		if not NAME_CHECK.match(newName):
			message = 'Group name can only contain letters and numbers, and cannot start with a number'
			QMessageBox.warning(self, 'Warning', message)
			return

		items = self.uiTraversalTREE.getSelectedItems(Slider)
		Group.createGroup(str(newName), self.simplex, items)

	def newShape(self):
		pars = self.uiTraversalTREE.getSelectedItems(Traversal)
		if not pars:
			return
		parItem = pars[0]
		parItem.prog.createShape()

	def setMultiplier(self):
		# Reads last selected item from the main window
		pass

	def setProgressor(self):
		# Reads last selected item from the main window
		pass

	def shapeConnectFromSelection(self):
		# Probably very close to combo connection
		pass

	def shapeExtract(self):
		indexes = self.uiTraversalTREE.getSelectedIndexes()
		self.parent().shapeIndexExtract(indexes)

