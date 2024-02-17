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

# pylint:disable=unused-variable
from __future__ import absolute_import

from functools import partial

from ...items import Combo, ComboPair, ProgPair, Progression, Slider
from ...Qt.QtCore import Qt
from ...Qt.QtWidgets import QCheckBox, QWidgetAction


def registerContext(tree, clickIdx, indexes, menu):
    self = tree.window()
    if tree == self.uiComboTREE:
        registerComboTree(self, clickIdx, indexes, menu)
    if tree == self.uiSliderTREE:
        registerSliderTree(self, clickIdx, indexes, menu)


def registerSliderTree(window, clickIdx, indexes, menu):
    self = window
    # live = self.uiLiveShapeConnectionACT.isChecked()
    items = [i.model().itemFromIndex(i) for i in indexes]
    types = {}
    for i in items:
        types.setdefault(type(i), []).append(i)

    activeCount = 0
    for s in self.simplex.sliders:
        if s.value != 0.0:
            activeCount += 1

    sel = self.simplex.DCC.getSelectedObjects()

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

    if Slider in types:
        menu.addSeparator()
        setGroupMenu = menu.addMenu("Set Group")
        for group in window.simplex.sliderGroups:
            gAct = setGroupMenu.addAction(group.name)
            gAct.triggered.connect(partial(self.setSelectedSliderGroups, group))

        setFalloffMenu = menu.addMenu("Set Falloffs")
        sliders = list(set([i for i in items if isinstance(i, Slider)]))

        foChecks = {}
        interps = set()
        for slider in sliders:
            for fo in slider.prog.falloffs:
                foChecks.setdefault(fo, []).append(slider)
            interps.add(slider.prog.interp.lower())

        for falloff in window.simplex.falloffs:
            cb = QCheckBox(falloff.name, setFalloffMenu)
            chk = foChecks.get(falloff)
            if not chk:
                cb.setCheckState(Qt.Unchecked)
            elif len(chk) != len(sliders):
                cb.setCheckState(Qt.PartiallyChecked)
            else:
                cb.setCheckState(Qt.Checked)

            cb.stateChanged.connect(partial(self.setSelectedSliderFalloff, falloff))

            fAct = QWidgetAction(setFalloffMenu)
            fAct.setDefaultWidget(cb)
            setFalloffMenu.addAction(fAct)

        setFalloffMenu.addSeparator()
        editFalloffsACT = setFalloffMenu.addAction("Edit Falloffs ...")
        editFalloffsACT.triggered.connect(window.showFalloffDialog)

        setInterpMenu = menu.addMenu("Set Interpolation")
        for interpName, interpType in Progression.interpTypes:
            act = setInterpMenu.addAction(interpName)
            act.triggered.connect(partial(self.setSelectedSliderInterp, interpType))
            act.setCheckable(True)
            if interpType in interps:
                act.setChecked(True)

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


def registerComboTree(window, clickIdx, indexes, menu):
    self = window
    # live = self.uiLiveShapeConnectionACT.isChecked()
    items = [i.model().itemFromIndex(i) for i in indexes]
    types = {}
    for i in items:
        types.setdefault(type(i), []).append(i)
    sel = self.simplex.DCC.getSelectedObjects()

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

        setGroupMenu = menu.addMenu("Set Group")
        for group in window.simplex.comboGroups:
            gAct = setGroupMenu.addAction(group.name)
            gAct.triggered.connect(partial(self.setSelectedComboGroups, group))

        menu.addSeparator()

        setSolveMenu = menu.addMenu("Set Solve Type")
        solves = set()
        combos = list(set([i for i in items if isinstance(i, Combo)]))
        for combo in combos:
            solves.add(str(combo.solveType))

        if "None" in solves:
            solves.discard("None")
            solves.add("min")

        for stName, stVal in Combo.solveTypes:
            if stName != "None":
                act = setSolveMenu.addAction(stName)
                act.setCheckable(True)
                if stVal in solves:
                    act.setChecked(True)
                act.triggered.connect(partial(self.setSelectedComboSolveType, stVal))

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
