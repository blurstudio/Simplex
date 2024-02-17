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

from __future__ import absolute_import, print_function

import os
import sys

from six.moves import range

# Add the parent folder to the path so I can import SimplexUI
# Means I can run this test code from inside the module and
# keep everything together
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base)

from .interfaceModel import (
    ComboFilterModel,
    ComboModel,
    Simplex,
    SimplexModel,
    Slider,
    SliderFilterModel,
    SliderModel,
    TraversalFilterModel,
    TraversalModel,
)
from .Qt.QtCore import QModelIndex
from .Qt.QtWidgets import QApplication, QPushButton, QTreeView, QVBoxLayout, QWidget


# HELPERS
def expandRecursive(view, model, index=QModelIndex(), depth=0, debug=False):
    """helper to expand the whole tree"""
    view.setExpanded(index, True)
    rows = model.rowCount(index)

    if debug:
        item = model.itemFromIndex(index)
        print(
            "   " * depth
            + "Name {0}, children {1}".format(item.name if item else None, rows)
        )
        print(
            "   " * depth
            + "Depth {0}, Row {1}, Col {2}".format(depth, index.row(), index.column())
        )

    for row in range(rows):
        child = model.index(row, 0, index)
        if not child.isValid():
            continue
        expandRecursive(view, model, child, depth + 1)


def showTree(model):
    app = QApplication(sys.argv)
    tv = QTreeView()
    tv.setModel(model)
    expandRecursive(tv, model)
    tv.resizeColumnToContents(0)
    tv.show()
    sys.exit(app.exec_())


def buildDummySystem(path, name="Face"):
    if path.endswith(".json"):
        simp = Simplex.buildSystemFromFile(path)
    elif path.endswith(".smpx"):
        simp = Simplex.buildSystemFromFile(path)
    else:
        raise IOError("Filepath is not .smpx or .json")
    return simp


# DISPLAY TESTS
def testSliderDisplay(smpxPath, applyFilter=True):
    simp = Simplex.buildSystemFromFile(smpxPath)
    model = SimplexModel(simp, None)
    model = SliderModel(model)
    if applyFilter:
        model = SliderFilterModel(model)
    showTree(model)


def testComboDisplay(smpxPath, applyFilter=True):
    simp = Simplex.buildSystemFromFile(smpxPath)
    model = SimplexModel(simp, None)
    model = ComboModel(model)
    if applyFilter:
        model = ComboFilterModel(model)
    showTree(model)


def testTraversalDisplay(path, applyFilter=True):
    simp = buildDummySystem(path)

    model = SimplexModel(simp, None)
    model = TraversalModel(model)
    if applyFilter:
        model = TraversalFilterModel(model)
    showTree(model)


def testBaseDisplay(path):
    simp = buildDummySystem(path)

    model = SimplexModel(simp, None)
    showTree(model)


def testEmptySimplex():
    simp = Simplex.buildEmptySystem(None, "Face")
    model = SimplexModel(simp, None)
    model = SliderModel(model)
    showTree(model)


# RowAdd Tests
def testNewSlider():
    simp = Simplex.buildEmptySystem(None, "Face")
    model = SimplexModel(simp, None)
    smodel = SliderModel(model)
    fmodel = SliderFilterModel(smodel)
    fmodel.doFilter = True

    app = QApplication(sys.argv)

    topWid = QWidget()
    lay = QVBoxLayout(topWid)

    tv = QTreeView(topWid)
    btn = QPushButton("NEW", topWid)
    lay.addWidget(tv)
    lay.addWidget(btn)

    tv.setModel(fmodel)
    expandRecursive(tv, fmodel)
    topWid.show()

    def newSlider():
        return Slider.createSlider("NewSlider", simp)

    btn.clicked.connect(newSlider)

    sys.exit(app.exec_())


def testDeleteBase(path):
    simp = buildDummySystem(path)
    model = SimplexModel(simp, None)

    # model = SliderModel(model)
    # model = SliderFilterModel(model)

    model = ComboModel(model)
    # model = ComboFilterModel(model)

    app = QApplication(sys.argv)

    topWid = QWidget()
    lay = QVBoxLayout(topWid)

    tv = QTreeView(topWid)

    btn = QPushButton("DELETE", topWid)
    lay.addWidget(tv)
    lay.addWidget(btn)

    tv.setModel(model)
    topWid.show()

    expandRecursive(tv, model)
    tv.resizeColumnToContents(0)

    def delCallback():
        sel = tv.selectedIndexes()
        sel = [i for i in sel if i.column() == 0]
        items = [s.model().itemFromIndex(s) for s in sel]
        item = items[0]
        print("Deleting", type(item), item.name)
        item.delete()
        tv.model().invalidateFilter()

    btn.clicked.connect(delCallback)

    sys.exit(app.exec_())


def testNewChild(path):
    simp = buildDummySystem(path)
    model = SimplexModel(simp, None)
    model = SliderModel(model)
    model = SliderFilterModel(model)

    app = QApplication(sys.argv)

    topWid = QWidget()
    lay = QVBoxLayout(topWid)

    tv = QTreeView(topWid)

    btn = QPushButton("NEW", topWid)
    lay.addWidget(tv)
    lay.addWidget(btn)

    tv.setModel(model)
    topWid.show()

    expandRecursive(tv, model)
    tv.resizeColumnToContents(0)

    def newCallback():
        sel = tv.selectedIndexes()
        sel = [i for i in sel if i.column() == 0]
        items = [s.model().itemFromIndex(s) for s in sel]
        # item = items[0]

        # TODO
        # find the child type of item
        # make a new one of those

        # tv.model().invalidateFilter()

    btn.clicked.connect(newCallback)

    sys.exit(app.exec_())


if __name__ == "__main__":
    # basePath = r'D:\Users\tyler\Documents\GitHub\Simplex\scripts\SimplexUI\build'
    basePath = r"D:\Users\tyler\Documents\GitHub\Simplex\Useful"
    # path = os.path.join(basePath, 'male_Simplex_v005_Split.smpx')
    # path = os.path.join(basePath, 'sphere_abcd_50.smpx')
    # path = os.path.join(basePath, 'male_traversal3.json')
    path = os.path.join(basePath, "SquareTest_Floater.json")

    # Only works for one at a time
    # testEmptySimplex()
    # testBaseDisplay(path)
    # testSliderDisplay(path, applyFilter=True)
    # testComboDisplay(path, applyFilter=True)
    # testTraversalDisplay(path, applyFilter=True)
    # testNewSlider()
    testDeleteBase(path)
