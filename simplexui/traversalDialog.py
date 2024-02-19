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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.


# Ignore a bunch of linter warnings that show up because of my choice of abstraction
# pylint: disable=unused-argument,too-many-public-methods,relative-import
# pylint: disable=too-many-statements,no-self-use,missing-docstring
from __future__ import absolute_import

import re

import six

from .interface import DCC
from .interfaceModel import (
    TraversalFilterModel,
    TraversalModel,
    coerceIndexToRoots,
    coerceIndexToType,
)
from .interfaceModelTrees import TraversalTree
from .items import Group, Simplex, Slider, Traversal, TravPair

# This module imports QT from PyQt4, PySide or PySide2
# Depending on what's available
from .Qt import QtCompat
from .Qt.QtGui import QStandardItemModel
from .Qt.QtWidgets import (
    QApplication,
    QDialog,
    QInputDialog,
    QMessageBox,
    QProgressDialog,
)
from .travCheckDialog import TraversalCheckDialog
from .utils import getUiFile, makeUnique

NAME_CHECK = re.compile(r"[A-Za-z][\w.]*")


class TraversalDialog(QDialog):
    """The dialog for dealing with Traversals

    Parameters
    ----------
    parent : SimplexDialog
        The parent simplex dialog
    """

    def __init__(self, parent):
        super(TraversalDialog, self).__init__(parent)

        uiPath = getUiFile(__file__)
        QtCompat.loadUi(uiPath, self)
        self.parUI = parent

        # Load the custom tree manually
        self.uiTraversalTREE = TraversalTree(self)
        self.uiTraversalTREE.setDragEnabled(False)
        self.uiTraversalTREE.setDragDropMode(TraversalTree.NoDragDrop)
        self.uiTraversalTREE.setSelectionMode(TraversalTree.ExtendedSelection)
        self.uiTraversalTREE.dragFilter.dragPressed.connect(self.dragStart)
        self.uiTraversalTREE.dragFilter.dragReleased.connect(self.dragStop)

        self.uiTraversalLAY.addWidget(self.uiTraversalTREE)
        self.simplex = None
        self.parUI.simplexLoaded.connect(self.loadSimplex)

        self.uiTravDeleteBTN.clicked.connect(self.deleteTrav)
        self.uiTravNewBTN.clicked.connect(self.newTrav)
        self.uiTravNewGroupBTN.clicked.connect(self.newGroup)
        self.uiTravNewShapeBTN.clicked.connect(self.newShape)
        self.uiTravAddSliderBTN.clicked.connect(self.addSlider)
        self.uiShapeExtractBTN.clicked.connect(self.shapeExtract)
        self.uiShapeConnectBTN.clicked.connect(self.shapeConnectFromSelection)

        self.parUI.uiHideRedundantACT.toggled.connect(self.hideRedundant)

        self.loadSimplex()

    def hideRedundant(self):
        """Hide Redundant items in the ui based on the checkbox"""
        check = self.uiHideRedundantACT.isChecked()
        travModel = self.uiTraversalTREE.model()
        travModel.doFilter = check
        travModel.invalidateFilter()

    def dragStart(self):
        """Slot for handling the start of a MMB Drag event"""
        if self.simplex is not None:
            self.simplex.DCC.undoOpen()

    def dragStop(self):
        """Slot for handling the end of a MMB Drag event"""
        if self.simplex is not None:
            self.simplex.DCC.undoClose()

    def loadSimplex(self):
        """Load the simplex system from the parent dialog"""
        system = self.parUI.simplex
        if system is None:
            self.simplex = system
            self.uiTraversalTREE.setModel(QStandardItemModel())

            self.uiTravDeleteBTN.setEnabled(False)
            self.uiTravNewBTN.setEnabled(False)
            self.uiTravNewGroupBTN.setEnabled(False)
            self.uiTravNewShapeBTN.setEnabled(False)
            self.uiTravAddSliderBTN.setEnabled(False)
            self.uiShapeExtractBTN.setEnabled(False)
            self.uiShapeConnectBTN.setEnabled(False)
            return
        else:
            self.uiTravDeleteBTN.setEnabled(True)
            self.uiTravNewBTN.setEnabled(True)
            self.uiTravNewGroupBTN.setEnabled(True)
            self.uiTravNewShapeBTN.setEnabled(True)
            self.uiTravAddSliderBTN.setEnabled(True)
            self.uiShapeExtractBTN.setEnabled(True)
            self.uiShapeConnectBTN.setEnabled(True)

        if system == self.simplex:
            return

        self.simplex = system

        sliderProxyModel = self.parUI.uiSliderTREE.model()
        if not sliderProxyModel:
            self.uiTraversalTREE.setModel(None)
            return
        sliderModel = sliderProxyModel.sourceModel()
        simplexModel = sliderModel.sourceModel()

        travModel = TraversalModel(simplexModel)
        travProxModel = TraversalFilterModel(travModel)
        self.uiTraversalTREE.setModel(travProxModel)

    def deleteTrav(self):
        """Delete the selected traversals"""
        idxs = self.uiTraversalTREE.getSelectedIndexes()
        roots = coerceIndexToRoots(idxs)
        if not roots:
            QMessageBox.warning(self, "Warning", "Nothing Selected")
            return
        roots = makeUnique([i.model().itemFromIndex(i) for i in roots])
        for r in roots:
            if isinstance(r, Simplex):
                QMessageBox.warning(
                    self, "Warning", "Cannot delete a simplex system this way (for now)"
                )
                return

        pairs = [r for r in roots if isinstance(r, TravPair)]
        roots = [r for r in roots if not isinstance(r, TravPair)]

        for r in roots:
            r.delete()

        TravPair.removeAll(pairs)

        self.uiTraversalTREE.model().invalidateFilter()

    def newGroup(self):
        """Create a new group for organizing the traversals"""
        if self.simplex is None:
            return
        newName, good = QInputDialog.getText(
            self, "New Group", "Enter a name for the new group", text="Group"
        )
        if not good:
            return
        if not NAME_CHECK.match(newName):
            message = "Group name can only contain letters and numbers, and cannot start with a number"
            QMessageBox.warning(self, "Warning", message)
            return

        items = self.uiTraversalTREE.getSelectedItems(Slider)
        Group.createGroup(str(newName), self.simplex, items)

    def newShape(self):
        """Add a new shape to the traversal's Progression"""
        pars = self.uiTraversalTREE.getSelectedIndexes()
        if not pars:
            return
        travs = coerceIndexToType(pars, Traversal)
        for travIdx in travs:
            trav = travIdx.model().itemFromIndex(travIdx)
            trav.prog.createShape()

    def shapeExtract(self):
        """Extract a shape from the traversal's progression"""
        indexes = self.uiTraversalTREE.getSelectedIndexes()
        return self.parUI.shapeIndexExtract(indexes)

    def newTrav(self):
        """Create a new traversal based on the selection in the main UI"""
        sliders = self.parUI.uiSliderTREE.getSelectedItems(Slider)
        if len(sliders) < 2:
            message = "Must have at least 2 sliders selected"
            QMessageBox.warning(self, "Warning", message)
            return None

        tcd = TraversalCheckDialog(
            sliders, mode="create", parent=self, grandparent=self.parUI
        )
        tcd.move(self.pos())
        tcd.exec_()

    def addSlider(self):
        """Add a slider to the traversal's definition"""
        # add the slider to both the start and end
        travs = self.uiTraversalTREE.getSelectedItems(Traversal)
        sliders = self.parUI.uiSliderTREE.getSelectedItems(Slider)
        if not travs:
            return
        if not sliders:
            return
        for slider in sliders:
            travs[-1].addSlider(slider)

    def shapeConnectFromSelection(self):
        """Connect a shape into the traversal based on the DCC scene selection"""
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
        selKeys = set(six.iterkeys(selDict))
        pairKeys = set(six.iterkeys(pairDict))
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
