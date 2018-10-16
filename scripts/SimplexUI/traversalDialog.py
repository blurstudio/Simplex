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
from Qt.QtWidgets import QMessageBox, QInputDialog, QMenu, QApplication, QTreeView, QDataWidgetMapper
from Qt.QtWidgets import QDialog, QProgressDialog, QPushButton, QComboBox, QCheckBox

from utils import toPyObject, getUiFile, getNextName, makeUnique

from interfaceItems import (ProgPair, Slider, Combo, Group, Simplex, Shape, Stack, Falloff)

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
		self.uiTraversalTREE.setSelectionMode(TraversalTree.ExtendedSelection)
		#self.uiTraversalTREE.dragFilter.dragPressed.connect(self.dragStart)
		#self.uiTraversalTREE.dragFilter.dragReleased.connect(self.dragStop)
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


	def loadSimplex(self):
		parent = self.parent()
		system = parent.simplex
		if system is None:
			self.simplex = system
			self.uiTraversalTREE.setModel(self.simplex)

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
		pass

	def newTrav(self):
		pass

	def newGroup(self):
		pass

	def newShape(self):
		pass

	def setMultiplier(self):
		pass

	def setProgressor(self):
		pass

	def shapeExtract(self):
		pass

	def shapeConnectFromSelection(self):
		pass

