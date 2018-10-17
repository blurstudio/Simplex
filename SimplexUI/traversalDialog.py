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
from Qt.QtGui import QStandardItemModel, QColor
from Qt.QtWidgets import QMessageBox, QInputDialog, QMenu, QApplication, QTreeView, QDataWidgetMapper
from Qt.QtWidgets import QDialog, QProgressDialog, QPushButton, QComboBox, QCheckBox

from utils import toPyObject, getUiFile, getNextName, makeUnique

from interfaceItems import (ProgPair, Slider, Combo, Traversal, TravPair, Group, Simplex, Shape, Stack, Falloff)

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

	def shapeExtract(self):
		indexes = self.uiTraversalTREE.getSelectedIndexes()
		self.parent().shapeIndexExtract(indexes)

	def newTrav(self):
		sliders = self.parent().uiSliderTREE.getSelectedItems(Slider)
		combos = self.parent().uiComboTREE.getSelectedItems(Combo)
		items = sliders + combos

		if len(items) != 2:
			message = 'Must have exactly 2 other controller selected'
			QMessageBox.warning(self, 'Warning', message)
			return None

		# the progressor will have more shapes in the prog
		val0 = items[0].prog.getValues()
		val1 = items[1].prog.getValues()
		pos0count = len([i for i in val0 if i > 0])
		neg0count = len([i for i in val0 if i < 0])
		pos1count = len([i for i in val1 if i > 0])
		neg1count = len([i for i in val1 if i < 0])

		# Find the prog item
		vals = [pos0count, neg0count, pos1count, neg1count]
		mIdx = vals.index(max(vals))
		iidx = 0 if mIdx < 2 else 1
		progItem = items[iidx]
		multItem = items[iidx-1]

		progFlip = (mIdx % 2) == 1
		multFlip = False

		name = "{0}_T_{1}".format(progItem.name, multItem.name)

		return Traversal.createTraversal(name, self.simplex, multItem, progItem, multFlip, progFlip, count=vals[mIdx])

	def setMultiplier(self):
		travs = self.uiTraversalTREE.getSelectedItems(Traversal)
		sliders = self.parent().uiSliderTREE.getSelectedItems(Slider)
		combos = self.parent().uiComboTREE.getSelectedItems(Combo)
		items = sliders+combos

		if not travs: return
		if not items: return

		trav = travs[0]
		item = items[0]

		trav.setMultiplier(item)

	def setProgressor(self):
		travs = self.uiTraversalTREE.getSelectedItems(Traversal)
		sliders = self.parent().uiSliderTREE.getSelectedItems(Slider)
		combos = self.parent().uiComboTREE.getSelectedItems(Combo)
		items = sliders+combos

		if not travs: return
		if not items: return

		trav = travs[0]
		item = items[0]

		trav.setProgressor(item)

	def shapeConnectFromSelection(self):
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

