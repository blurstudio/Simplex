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

from six.moves import range

from .dragFilter import DragFilter
from .items import Group
from .Qt.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, QRegExp, Qt
from .Qt.QtGui import QRegExpValidator
from .Qt.QtWidgets import QApplication, QLineEdit, QMenu, QStyledItemDelegate, QTreeView


class SimplexNameDelegate(QStyledItemDelegate):
    """An QStyledItemDelegate subclass that implements a Regex validator"""

    def __init__(self, parent=None):
        super(SimplexNameDelegate, self).__init__(parent)
        self._rx = QRegExp(r"[A-Za-z][A-Za-z0-9_]*")

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        rxv = QRegExpValidator(self._rx, editor)
        editor.setValidator(rxv)
        return editor


class SimplexTree(QTreeView):
    """Abstract base tree displaying Simplex objects"""

    def __init__(self, parent):
        super(SimplexTree, self).__init__(parent)

        self.expandModifier = Qt.ControlModifier
        self.depthModifier = Qt.ShiftModifier

        self._menu = None
        self._plugins = []

        self.expanded.connect(self.expandTree)
        self.collapsed.connect(self.collapseTree)
        self.connectMenus()

        self.dragFilter = DragFilter(self.viewport())
        self.viewport().installEventFilter(self.dragFilter)

        self.dragFilter.dragTick.connect(self.dragTick)

        self.delegate = SimplexNameDelegate(self)
        self.setItemDelegateForColumn(0, self.delegate)

        self.setColumnWidth(1, 50)
        self.setColumnWidth(2, 20)

    def setPlugins(self, plugins):
        """Set the right-click menu plugins for the tree

        Parameters
        ----------
        plugins : list
            The list of plugins for the tree
        """
        self._plugins = plugins

    def unifySelection(self):
        """Handle selection across multiple Trees.
        The other tree's selectionChanged signal will be connected to this
        And it will clear the selection on this tree if no modifiers are being held
        """
        mods = QApplication.keyboardModifiers()
        if not mods & (Qt.ControlModifier | Qt.ShiftModifier):
            selModel = self.selectionModel()
            selModel.blockSignals(True)
            try:
                selModel.clearSelection()
            finally:
                selModel.blockSignals(False)
            self.viewport().update()

    def hideRedundant(self, check):
        """Update the filter model to show/hide single shapes

        Parameters
        ----------
        check : bool
            Whether to hid redundant
        """
        model = self.model()
        model.filterShapes = check
        model.invalidateFilter()

    def stringFilter(self, filterString):
        """Update the filter model with a filter string

        Parameters
        ----------
        filterString : str
            The string to filter on
        """
        model = self.model()
        model.filterString = str(filterString)
        model.invalidateFilter()

    def isolate(self, sliderNames):
        """Update the filter model with a whitelist of names

        Parameters
        ----------
        sliderNames : [str, ...]
            The names items to show
        """
        model = self.model()
        model.isolateList = sliderNames
        model.invalidateFilter()

    def isolateSelected(self):
        """Isolate the selected items"""
        items = self.getSelectedItems()
        isoList = [i.name for i in items]
        self.isolate(isoList)

    def exitIsolate(self):
        """Remove all items from isolation"""
        self.isolate([])

    # Tree expansion/collapse code
    def expandTree(self, index):
        """Expand all items under index

        Parameters
        ----------
        index : QModelIndex
            The index to recursively expand
        """
        self.toggleTree(index, True)

    def collapseTree(self, index):
        """Collapse all items under index

        Parameters
        ----------
        index : QModelIndex
            The index to recursively collapse
        """
        self.toggleTree(index, False)

    def resizeColumns(self):
        '''Resize all columns to their contents "smartly"'''
        model = self.model()
        for i in range(model.columnCount() - 1):
            oldcw = self.columnWidth(i)
            self.resizeColumnToContents(i)
            newcw = self.columnWidth(i) + 10
            self.setColumnWidth(i, max(oldcw, newcw, 30))
        self.setColumnWidth(model.columnCount() - 1, 5)

    def toggleTree(self, index, expand):
        """Recursively expand or collapse an entire sub-tree of an
        index.  If certain modifiers are held, then only a partial
        sub-tree will be expanded

        Parameters
        ----------
        index : QModelIndex
            The index to change expansion
        expand : bool
            Whether to expand or collapse the item
        """
        # Separate function to deal with filtering capability
        if not index.isValid():
            return

        model = self.model()
        mods = QApplication.keyboardModifiers()
        thing = model.itemFromIndex(index)
        thing.expanded[id(self)] = expand

        if mods & (self.expandModifier | self.depthModifier):
            queue = [index]
            self.blockSignals(True)
            try:
                while queue:
                    idx = queue.pop()
                    thing = model.itemFromIndex(idx)
                    thing.expanded[id(self)] = expand
                    self.setExpanded(idx, expand)
                    if mods & self.depthModifier:
                        if isinstance(thing, Group):
                            continue
                    for i in range(model.rowCount(idx)):
                        child = model.index(i, 0, idx)
                        if child and child.isValid():
                            queue.append(child)
            finally:
                self.blockSignals(False)

        if expand:
            self.resizeColumns()

    def expandToItem(self, item):
        """Make sure that all parents leading to `item` are expanded

        Parameters
        ----------
        item : object
            The item to expand to
        """
        model = self.model()
        index = model.indexFromItem(item)
        self.expandToIndex(index)

    def expandToIndex(self, index):
        """Make sure that all parents leading to `index` are expanded

        Parameters
        ----------
        index : QModelIndex
            The index to expand to
        """
        model = self.model()
        while index and index.isValid():
            self.setExpanded(index, True)
            thing = model.itemFromIndex(index)
            thing.expanded[id(self)] = True
            index = index.parent()
        self.resizeColumns()

    def scrollToItem(self, item):
        """Ensure that the item is scrolled to in the tree

        Parameters
        ----------
        item : object
            The Item to expand to
        """
        model = self.model()
        index = model.indexFromItem(item)
        self.scrollToIndex(index)

    def scrollToIndex(self, index):
        """Ensure that the index is scrolled to in the tree

        Parameters
        ----------
        index : QModelIndex
            The Index to expand to

        """
        self.expandToIndex(index)
        self.scrollTo(index)

    def storeExpansion(self):
        """Store the expansion state of the tree for the undo stack"""
        model = self.model()
        queue = [model.index(0, 0, QModelIndex())]
        while queue:
            index = queue.pop()
            item = model.itemFromIndex(index)
            item.expanded[id(self)] = self.isExpanded(index)
            for row in range(model.rowCount(index)):
                queue.append(model.index(row, 0, index))

    def setItemExpansion(self):
        """Load the stored expansions onto the tree"""
        model = self.model()
        queue = [model.index(0, 0, QModelIndex())]
        self.blockSignals(True)
        try:
            while queue:
                index = queue.pop()
                item = model.itemFromIndex(index)
                exp = item.expanded.get(id(self), False)
                self.setExpanded(index, exp)
                for row in range(model.rowCount(index)):
                    queue.append(model.index(row, 0, index))
        finally:
            self.blockSignals(False)

    def dragTick(self, ticks, mul):
        """Deal with the ticks coming from the drag handler

        Parameters
        ----------
        ticks : int
            The number and direction of update ticks coming from the drag handler
        mul : float
            The multiplier based on user hotkeys
        """
        selModel = self.selectionModel()
        if not selModel:
            return
        items = self.getSelectedItems()
        for item in items:
            if hasattr(item, "valueTick"):
                item.valueTick(ticks, mul)
        self.viewport().update()

    # Menus and Actions
    def connectMenus(self):
        """Setup the QT signal/slot connections to the context menus"""
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.openMenu)

    def openMenu(self, pos):
        """Handle getting the data to show the context menu

        Parameters
        ----------
        pos : QPoint
            The position of the click
        """
        clickIdx = self.indexAt(pos)
        selIdxs = self.getSelectedIndexes()
        if self.window().simplex is None:
            return
        self.showContextMenu(clickIdx, selIdxs, self.viewport().mapToGlobal(pos))

    def showContextMenu(self, clickIdx, indexes, pos):
        """Handle showing the context menu items from the plugins

        Parameters
        ----------
        clickIdx : QModelIndex
            The model index that was clicked
        indexes : [QModelIndex, ...]
            The indexes that were selected
        pos : QPoint
            The position of the click
        """
        menu = QMenu()
        for plug in self._plugins:
            plug.registerContext(self, clickIdx, indexes, menu)
        menu.exec_(pos)

    # Selection
    def getSelectedItems(self, typ=None):
        """Get the selected tree items

        Parameters
        ----------
        typ : Type
            Only return selected items of this type. Optional

        Returns
        -------
        [object, ...]
            A list of selected tree items
        """
        selModel = self.selectionModel()
        if not selModel:
            return []
        selIdxs = selModel.selectedIndexes()
        selIdxs = [i for i in selIdxs if i.column() == 0]
        model = self.model()
        items = [model.itemFromIndex(i) for i in selIdxs]
        if typ is not None:
            items = [i for i in items if isinstance(i, typ)]
        return items

    def getSelectedIndexes(self, filtered=False):
        """Get selected indexes for either the filtered or unfiltered models

        Parameters
        ----------
        filtered : bool
            Whether the model is filtered or not. Defaults to False

        Returns
        -------
        [QModelIndex, ...]
            A list of selected indexes
        """
        selModel = self.selectionModel()
        if not selModel:
            return []
        selIdxs = selModel.selectedIndexes()
        if filtered:
            return selIdxs

        model = self.model()
        indexes = [model.mapToSource(i) for i in selIdxs]
        return indexes

    def setItemSelection(self, items):
        """Set the selection based on a list of items

        Parameters
        ----------
        items : [object, ...]
            List of items to select
        """
        model = self.model()
        idxs = [model.indexFromItem(i) for i in items]
        idxs = [i for i in idxs if i and i.isValid()]

        toSel = QItemSelection()
        for idx in idxs:
            toSel.merge(QItemSelection(idx, idx), QItemSelectionModel.Select)

        for idx in idxs:
            par = idx.parent()
            if par.isValid():
                self.scrollToIndex(par)

        selModel = self.selectionModel()
        selModel.select(toSel, QItemSelectionModel.ClearAndSelect)


# Currently, there's no difference between these
# Later on, though, they may be different
class SliderTree(SimplexTree):
    """A SimplexTree sub-class for sliders"""

    pass


class ComboTree(SimplexTree):
    """A SimplexTree sub-class for combos"""

    pass


class TraversalTree(SimplexTree):
    """A SimplexTree sub-class for traversals"""

    pass
