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

from __future__ import absolute_import

from itertools import combinations, product

import six
from six.moves import range, zip

from .dragFilter import DragFilter
from .items import Slider, Traversal
from .Qt import QtCompat
from .Qt.QtCore import Qt
from .Qt.QtGui import QBrush, QColor
from .Qt.QtWidgets import QDialog, QTreeWidgetItem
from .utils import getUiFile


class TooManyPossibilitiesError(Exception):
    """Error raised when there are too many possibilities
    Basically used as a stop-iteration
    """

    pass


def buildPossibleTraversals(
    simplex, sliders, minDepth, maxDepth, lockDict=None, maxPoss=100
):
    """Build a list of possible traversals

    Parameters
    ----------
    simplex : Simplex
        The simplex system to check
    sliders : Slider
        The sliders to check
    minDepth : int
        The minimum number of sliders that will go into any traversals
    maxDepth : int
        The maximum number of sliders that will go into any traversals
    lockDict : {Slider: ((float, ...), bool), ...}
        An optional per-slider dict of possible values
    maxPoss : float
        The Maximum number of possibilities to return.(Default value = 100)

    Returns
    -------
    : bool
        True if the maximum number of possibilities was exceeded
    : [([(Slider, (float, float)), ...], Traversal), ...]
        Grouped slider/range pairs to existing (or None) Traversals
    """
    allRanges = {}
    allDyn = {}
    sliderDict = {}
    lockDict = lockDict or {}

    # Get the range values for each slider
    for slider in sliders:
        rng, dyn = lockDict.get(slider, (slider.prog.getRange(), True))
        rng = set(rng)
        rng.discard(0)  # ignore the zeros
        allRanges[slider] = sorted(rng)
        allDyn[slider] = dyn
        sliderDict[slider.name] = slider

    poss = []
    tooMany = False
    try:
        for size in range(minDepth, maxDepth + 1):
            for grp in combinations(sliders, size):
                names = [i.name for i in grp]
                ranges = [allRanges[s] for s in grp]
                for vals in product(*ranges):
                    for dynIdx in range(len(grp)):
                        if not allDyn[grp[dynIdx]]:
                            continue
                        trng = list(zip(vals, vals))
                        trng[dynIdx] = (0, trng[dynIdx][0])

                        count = Traversal.getCount(grp, trng)
                        if count == 0:
                            continue

                        poss.append(frozenset(list(zip(names, trng))))
                        if len(poss) > maxPoss:
                            raise TooManyPossibilitiesError("Don't melt your computer")
    except TooManyPossibilitiesError:
        tooMany = True

    # Build a dict of traversals that already exist
    # but only if their sliders are in the list of sliders to check
    onlys = {}
    for trav in simplex.traversals:
        sls = trav.allSliders()
        if all(r in sliders for r in sls):
            rngs = trav.ranges()
            key = frozenset([(k.name, v) for k, v in six.iteritems(rngs)])
            onlys[key] = trav

    toAdd = []
    for p in poss:
        truePairs = [(sliderDict[n], r) for n, r in p]
        toAdd.append((truePairs, onlys.get(p)))
    return tooMany, toAdd


class TravCheckItem(QTreeWidgetItem):
    def __init__(self, pairs, trav, *args, **kwargs):
        super(TravCheckItem, self).__init__(*args, **kwargs)
        self.pairs = pairs
        self.trav = trav

        exists = False
        grayBrush = QBrush(QColor(128, 128, 128))
        if self.trav is None:
            ranges = dict(self.pairs)
            newName = Traversal.buildTraversalName(ranges)
            self.setText(0, newName)
        else:
            exists = True
            self.setText(0, self.trav.name)
            self.setForeground(0, grayBrush)
            self.setForeground(1, grayBrush)
            self.setForeground(2, grayBrush)

        # create the slider sub-rows
        for slider, rng in pairs:
            item = QTreeWidgetItem(self)

            item.setData(0, Qt.EditRole, slider.name)
            item.setData(1, Qt.EditRole, rng[0])
            item.setData(2, Qt.EditRole, rng[1])
            if exists:
                item.setForeground(0, grayBrush)
                item.setForeground(1, grayBrush)
                item.setForeground(2, grayBrush)

        self.setExpanded(True)


class TraversalCheckDialog(QDialog):
    """Dialog for checking what possible traversals exist, and picking new traversals
    In 'Create' mode, it provides a quick way of choosing the one specific traversal
    that the user is looking for

    In 'Check' mode, it provides a convenient way to explore the possibilites
    and create any missing traversals directly

    Parameters
    ----------
    sliders : [Slider, ...]
        A list of sliders to check
    values : {Slider: (float, ...), ...}
        A dictionary of values to use per slider
    mode : str
        The mode to display the dialog. Defaults to 'create'
    parent : QObject
        The Parent of the dialog. Must be a SimplexDialog

    Returns
    -------
    """

    def __init__(
        self,
        sliders,
        values=None,
        dynamics=None,
        mode="create",
        parent=None,
        grandparent=None,
    ):
        super(TraversalCheckDialog, self).__init__(parent)

        uiPath = getUiFile(__file__)
        QtCompat.loadUi(uiPath, self)
        self.mode = mode.lower()

        # Store the Parent UI rather than relying on Qt's .parent()
        # Could cause crashes otherwise
        self.parUI = parent
        self.gparUI = grandparent
        self.maxPoss = 100
        self.colCheckRoles = [Qt.UserRole, Qt.UserRole, Qt.UserRole, Qt.EditRole]

        self.uiCreateSelectedBTN.clicked.connect(self.createMissing)
        self.uiMinLimitSPIN.valueChanged.connect(self.populateWithoutUpdate)
        self.uiMaxLimitSPIN.valueChanged.connect(self.populateWithoutUpdate)
        self.uiCancelBTN.clicked.connect(self.close)
        self.uiManualUpdateBTN.clicked.connect(self.populateWithUpdate)
        self.uiEditTREE.itemChanged.connect(self.populateWithoutUpdate)

        self.dragFilter = DragFilter(self)
        self.uiEditTREE.viewport().installEventFilter(self.dragFilter)
        self.dragFilter.dragTick.connect(self.dragTick)

        self.gparUI.uiSliderTREE.selectionModel().selectionChanged.connect(
            self.populateWithCheck
        )

        self.valueDict = values or {}
        self.dynDict = dynamics or {}
        self.setSliders(sliders)
        if self.mode == "create":
            self.uiAutoUpdateCHK.setCheckState(Qt.Unchecked)
            self.uiAutoUpdateCHK.hide()
            self.uiManualUpdateBTN.hide()

        self.uiMaxLimitSPIN.setValue(max(len(sliders), 2))
        self.uiMinLimitSPIN.setValue(max(len(sliders) - 2, 2))

        if sliders is None:
            self.populateWithUpdate()
        else:
            self._populate()

    def dragTick(self, ticks, mul):
        """Deal with the ticks coming from the drag handler

        Parameters
        ----------
        ticks : int
            The number of ticks since the last update
        mul : float
            The multiplier value from the drag handler

        Returns
        -------

        """
        items = self.uiEditTREE.selectedItems()
        for item in items:
            val = item.data(3, Qt.EditRole)
            val += (0.05) * ticks * mul
            if abs(val) < 1.0e-5:
                val = 0.0
            val = max(min(val, 1.0), -1.0)
            item.setData(3, Qt.EditRole, val)
        self.uiEditTREE.viewport().update()

    def setSliders(self, val):
        """Set the sliders displayed in this UI

        Parameters
        ----------
        val : [Slider, ...]
            The sliders to be displayed

        Returns
        -------

        """
        self.uiEditTREE.clear()
        dvs = [None, -1.0, 1.0, 0.5]
        val = val or []
        for slider in val:
            item = QTreeWidgetItem(self.uiEditTREE, [slider.name])
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            rangeVals = self.valueDict.get(slider, [-1.0, 1.0])

            item.setData(0, Qt.UserRole, slider)
            for col in range(1, 3):
                val = dvs[col]
                item.setData(col, self.colCheckRoles[col], val)
                rng = slider.prog.getRange()
                if val in rng:
                    chk = Qt.Checked if val in rangeVals else Qt.Unchecked
                    item.setCheckState(col, chk)
            item.setCheckState(3, self.dynDict.get(slider, Qt.Checked))

        for col in reversed(list(range(4))):
            self.uiEditTREE.resizeColumnToContents(col)

    def closeEvent(self, event):
        """Override the Qt close event"""
        self.gparUI.uiSliderTREE.selectionModel().selectionChanged.disconnect(
            self.populateWithCheck
        )
        super(TraversalCheckDialog, self).closeEvent(event)

    def populateWithUpdate(self):
        """Populate the list from the main dialog selection"""
        self.setSliders(self.gparUI.uiSliderTREE.getSelectedItems(typ=Slider))
        self._populate()

    def populateWithoutUpdate(self):
        """Populate the list and but don't look at the main dialog"""
        self._populate()

    def populateWithCheck(self):
        """Populate the list from the main dialog selection, only if the AutoUpdate checkbox is checked"""
        if self.uiAutoUpdateCHK.isChecked():
            self.setSliders(self.gparUI.uiSliderTREE.getSelectedItems(typ=Slider))
        self._populate()

    def _populate(self):
        """Populate the list widgets in the UI"""
        minDepth = self.uiMinLimitSPIN.value()
        maxDepth = self.uiMaxLimitSPIN.value()

        root = self.uiEditTREE.invisibleRootItem()
        lockDict = {}
        sliderList = []

        for row in range(root.childCount()):
            item = root.child(row)
            slider = item.data(0, Qt.UserRole)
            if slider is not None:
                sliderList.append(slider)
                lv = [
                    item.data(col, self.colCheckRoles[col])
                    for col in range(1, 3)
                    if item.checkState(col) == Qt.Checked
                ]
                dyn = item.checkState(3) == Qt.Checked
                lockDict[slider] = (lv, dyn)

        tooMany, toAdd = buildPossibleTraversals(
            self.parUI.simplex,
            sliderList,
            minDepth,
            maxDepth,
            lockDict=lockDict,
            maxPoss=self.maxPoss,
        )

        lbl = (
            "Too many possibilities. Limiting to {0}".format(self.maxPoss)
            if tooMany
            else ""
        )
        self.uiWarningLBL.setText(lbl)

        self.uiTravCheckTREE.clear()
        for pairs, trav in reversed(toAdd):
            TravCheckItem(pairs, trav, self.uiTravCheckTREE)

        for i in reversed(list(range(self.uiTravCheckTREE.columnCount()))):
            self.uiTravCheckTREE.resizeColumnToContents(i)

        if self.mode == "create":
            if self.uiTravCheckTREE.topLevelItemCount() > 0:
                self.uiTravCheckTREE.topLevelItem(0).setSelected(True)

    def createMissing(self):
        """Create selected traversals if they don't already exist"""
        simplex = self.parUI.simplex
        created = []

        tops = []
        for item in self.uiTravCheckTREE.selectedItems():
            par = item.parent()
            if par is not None:
                item = par
            if item not in tops:
                tops.append(item)

        for item in tops:
            name = item.text(0)
            sliders, ranges = list(zip(*item.pairs))
            # Double check that the user didn't create any extra sliders
            if Traversal.traversalAlreadyExists(simplex, sliders, ranges) is None:
                count = Traversal.getCount(sliders, ranges)
                startPairs, endPairs = list(
                    zip(*[((s, a), (s, b)) for s, (a, b) in item.pairs])
                )
                t = Traversal.createTraversal(
                    name, simplex, startPairs, endPairs, count=count
                )
                created.append(t)

        self.parUI.uiTraversalTREE.setItemSelection(created)
        if self.mode == "create":
            self.close()
        else:
            self.populateWithoutUpdate()
