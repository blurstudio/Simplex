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
"""A Qt model that stays out of the way of the hierarchy you want to make
Your objects don't need to know anything about Qt. They just expose the few methods
that are required for the rest of the model to work.

Why do this?
For some cases it makes sense to have a hierarchy built into your objects, but if you
don't want to tightly couple your hierarchy to Qt, you have limited choices on how to
proceed:

One way would be to write a translation system that can map between your objects and the
Qt standard item hierarchy. This can be done in a non-intrusive way, but it requires
building and maintaining maps between the two separate hierarchies, or discovering the
relationship dynamically. It's totally doable, but the mapping feels fragile and it's
duplicating data (which I don't like)

Another possible way is to create a custom model from your objects, which is extra work.
So I did that work and packaged it into this setup.

Just inherit from TreeItem and override the methods that expose the tree structure.
Then you can attach the root of your hierarchy to the Adapter model, which translates
between your hierarchy and Qt. The TreeItem itself has nothing to do with QT. It
communicates to Qt via the OverserverServer.

---
I tried to plug as many leaks in this abstraction as I could, but there's still a couple
things that are required. You have to call self.notifyChanged() when a
value visible in the tree changes. And you have to use the managers when changing
the hierarchy. But I think that's it.

This model doesn't handle the full "each cell can have its own separate table of
children" thing that the full QAbstractItemModel allows for. It's closer to the
QTreeWidget's model where each item is its own row.
"""

from __future__ import annotations
from typing import Any, Generator, Callable, Iterator, Literal, overload
from Qt.QtGui import QIcon
from Qt.QtCore import QAbstractItemModel, QModelIndex, Qt, QObject
from Qt.QtWidgets import QTreeView
from contextlib import contextmanager, ExitStack
import uuid
import enum


class CustomRoles(enum.IntEnum):
    UID_ROLE = Qt.ItemDataRole.UserRole + 1


SimpleGenerator = Generator[None, None, None]


class ObserverServer:  # it's just fun to say!
    def __init__(self, model: AdapterModel):
        self.model: AdapterModel = model

    def valueObserver(self, item: TreeItem) -> None:
        self.model.itemDataChanged(item)

    @contextmanager
    def insertManager(self, parent: TreeItem, row=-1) -> SimpleGenerator:
        parIdx = self.model.indexFromItem(parent)
        if row == -1:
            row = parent.getItemAppendRow()
        self.model.beginInsertRows(parIdx, row, row)
        try:
            yield
        finally:
            self.model.endInsertRows()

    @contextmanager
    def removeManager(self, item: TreeItem) -> SimpleGenerator:
        idx = self.model.indexFromItem(item)
        valid = idx.isValid()
        if valid:
            parIdx = idx.parent()
            self.model.beginRemoveRows(parIdx, idx.row(), idx.row())
        try:
            yield
        finally:
            if valid:
                self.model.endRemoveRows()

    @contextmanager
    def moveManager(
        self, item: TreeItem, destPar: TreeItem, destRow: int = -1
    ) -> SimpleGenerator:
        itemIdx = self.model.indexFromItem(item)
        destParIdx = self.model.indexFromItem(destPar)
        handled = False
        if itemIdx.isValid() and destParIdx.isValid():
            handled = True
            srcParIdx = itemIdx.parent()
            row = itemIdx.row()
            if destRow == -1:
                destRow = destPar.getItemAppendRow()
            self.model.beginMoveRows(srcParIdx, row, row, destParIdx, destRow)
        try:
            yield
        finally:
            if handled:
                self.model.endMoveRows()

    @contextmanager
    def resetManager(self) -> SimpleGenerator:
        self.model.beginResetModel()
        try:
            yield
        finally:
            self.model.endResetModel()


class TreeItem:
    classDepth = -1

    def __init__(self, root: TreeRootItem):
        self.root: TreeRootItem = root
        self.uid: str = uuid.uuid4().hex  # Unique identifier for tree expansion

    @property
    def observers(self) -> list[ObserverServer]:
        return self.root.observerServers()

    def notifyChanged(self):
        """Let the observers know that this item has changed"""
        for ob in self.observers:
            if ob.valueObserver is not None:
                ob.valueObserver(self)

    @contextmanager
    def insertItemManager(self, item: TreeItem, row: int = -1):
        with ExitStack() as stack:
            for ob in self.observers:
                stack.enter_context(ob.insertManager(item, row=row))
            yield

    @contextmanager
    def removeItemManager(self, item: TreeItem):
        with ExitStack() as stack:
            for ob in self.observers:
                stack.enter_context(ob.removeManager(item))
            yield

    @contextmanager
    def moveItemManager(self, item: TreeItem, destPar: TreeItem, destRow: int = -1):
        with ExitStack() as stack:
            for ob in self.observers:
                stack.enter_context(ob.moveManager(item, destPar, destRow=destRow))
            yield

    @contextmanager
    def resetManager(self):
        with ExitStack() as stack:
            for ob in self.observers:
                stack.enter_context(ob.resetManager())
            yield

    ################
    # Default implementations of the methods that are available to override
    ################

    def getItemAppendRow(self) -> int:
        """Get the row to insert at to append a new item"""
        return 0

    def treeChild(self, row: int) -> TreeItem | None:
        """Return the child tree item at the given row if it exists"""
        return None

    def treeRow(self) -> int:
        """Return the row of the current item in the tree"""
        return 0

    def treeParent(self) -> TreeItem | None:
        """Return the parent of this TreeItem if it has one"""
        return None

    def treeChildCount(self) -> int:
        """Return the number of children this item has"""
        return 0

    def treeChecked(self) -> bool | None:
        """Return whether this item is checked"""
        return None

    def treeData(self, column: int) -> Any | None:
        """Return the data for the given column"""
        return None

    def icon(self) -> QIcon | None:
        """Return the icon of this item, if it has one"""
        return None


class TreeRootItem(TreeItem):
    def __init__(self, observerServers: list[ObserverServer] | None = None):
        super().__init__(self)
        # The root just keeps track of everybody's observers
        if observerServers is None:
            observerServers = []
        self._observerServers: list[ObserverServer] = observerServers

    def addObserver(self, observerServer: ObserverServer):
        self._observerServers.append(observerServer)

    def removeObserver(self, observerServer: ObserverServer):
        self._observerServers.remove(observerServer)

    def observerServers(self) -> list[ObserverServer]:
        return self._observerServers[:]  # Return a copy

    # Override this
    def columnCount(self) -> int:
        return 1


class AdapterModel(QAbstractItemModel):
    """Model that adapts the values from the TreeItem to the AbstractItemModel interface"""

    def __init__(
        self, rootItem: TreeRootItem | None = None, parent: QObject | None = None
    ):
        super().__init__(parent=parent)
        self._rootItem: TreeRootItem | None = None
        self.observer = ObserverServer(self)
        if rootItem is not None:
            self.setRootItem(rootItem)

    def setRootItem(self, rootItem: TreeRootItem):
        self.beginResetModel()
        try:
            if self._rootItem is not None:
                self._rootItem.removeObserver(self.observer)
            self._rootItem = rootItem
            self._rootItem.addObserver(self.observer)
        finally:
            self.endResetModel()

    def getItemRow(self, item: TreeItem | None) -> int | None:
        if item is None:
            return None
        return item.treeRow()

    def indexFromItem(self, item: TreeItem, column: int = 0) -> QModelIndex:
        row = self.getItemRow(item)
        if row is None:
            return QModelIndex()
        return self.createIndex(row, column, item)

    def itemFromIndex(self, index: QModelIndex) -> TreeItem | None:
        return index.internalPointer()

    def itemDataChanged(self, item: TreeItem):
        idx = self.indexFromItem(item)
        self.emitDataChanged(idx)

    def emitDataChanged(self, index: QModelIndex):
        if index.isValid():
            self.dataChanged.emit(index, index, [])

    def getChildItem(self, parent: TreeItem | None, row: int) -> TreeItem | None:
        if parent is None:
            if row == 0:
                return self._rootItem
            else:
                return None
        return parent.treeChild(row)

    def getParentItem(self, item: TreeItem | None) -> TreeItem | None:
        if item is None:
            return None
        return item.treeParent()

    def getItemRowCount(self, item: TreeItem | None) -> int:
        if item is None:
            # Null parent means return the only root item
            ret = 1
        else:
            ret = item.treeChildCount()
        return ret

    def index(self, row: int, column: int, parIndex: QModelIndex) -> QModelIndex:
        par = parIndex.internalPointer()
        child = self.getChildItem(par, row)
        if child is None:
            return QModelIndex()
        return self.createIndex(row, column, child)

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        item = index.internalPointer()
        if item is None:
            return QModelIndex()
        par = self.getParentItem(item)
        if par is None:
            return QModelIndex()
        row = self.getItemRow(par)
        if row is None:
            return QModelIndex()
        return self.createIndex(row, 0, par)

    def rowCount(self, parIndex: QModelIndex) -> int:
        parent = parIndex.internalPointer()
        ret = self.getItemRowCount(parent)
        return ret

    def data(self, index: QModelIndex, role: int) -> Any:
        if not index.isValid():
            return None
        item = index.internalPointer()
        return self.getItemData(item, index.column(), role)

    def columnCount(self, parIndex: QModelIndex) -> int:
        if self._rootItem is None:
            return 1
        return self._rootItem.columnCount()

    @overload
    def getItemData(self, item: None, column: int, role: int) -> None: ...

    @overload
    def getItemData(
        self,
        item: TreeItem,
        column: int,
        role: Literal[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
    ) -> str | None: ...

    @overload
    def getItemData(
        self,
        item: TreeItem,
        column: int,
        role: Literal[Qt.ItemDataRole.CheckStateRole],
    ) -> Qt.CheckState | None: ...

    @overload
    def getItemData(
        self,
        item: TreeItem,
        column: int,
        role: Literal[Qt.ItemDataRole.DecorationRole],
    ) -> QIcon | None: ...

    @overload
    def getItemData(
        self,
        item: TreeItem,
        column: int,
        role: Literal[CustomRoles.UID_ROLE],
    ) -> str | None: ...

    def getItemData(self, item: TreeItem | None, column: int, role: int) -> Any | None:
        if item is None:
            return None

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return item.treeData(column)

        elif role == Qt.ItemDataRole.CheckStateRole:
            chk = None
            if column == 0:
                chk = item.treeChecked()
            if chk is not None:
                chk = Qt.CheckState.Checked if chk else Qt.CheckState.Unchecked
            return chk
        elif role == Qt.ItemDataRole.DecorationRole:
            if column == 0:
                return item.icon()
        elif role == CustomRoles.UID_ROLE:
            return item.uid
        return None

    def iterindices(
        self, pred: Callable[[QModelIndex], bool] | None = None
    ) -> Iterator[QModelIndex]:
        """Iterate all indices of this model breadth-first"""
        queue = [QModelIndex()]
        while queue:
            index = queue.pop()
            if pred is None or pred(index):
                yield index
                for row in range(self.rowCount(index)):
                    queue.append(self.index(row, 0, index))

    def iteritems(
        self, pred: Callable[[TreeItem], bool] | None = None
    ) -> Iterator[TreeItem | None]:
        """Iterate all items of this model breadth-first"""
        # The only way I could make the typechecker happy was by
        # having 2 separate loops over self.iterindices
        if pred is None:
            for index in self.iterindices(pred=pred):
                yield self.itemFromIndex(index)
            return

        def itempred(x):
            item = self.itemFromIndex(x)
            return False if item is None else pred(item)

        for index in self.iterindices(pred=itempred):
            yield self.itemFromIndex(index)


def save_view_expansion_state(tree_view: QTreeView) -> set[str]:
    expanded_uids = set()
    model = tree_view.model()
    assert isinstance(model, AdapterModel)

    for index in model.iterindices(pred=lambda x: tree_view.isExpanded(x)):
        uid = model.data(index, CustomRoles.UID_ROLE)
        if uid:
            expanded_uids.add(uid)
    return expanded_uids


def restore_view_expansion_state(tree_view: QTreeView, expanded_uids: set[str]):
    model = tree_view.model()
    assert isinstance(model, AdapterModel)
    for index in model.iterindices(
        pred=lambda x: model.data(x, CustomRoles.UID_ROLE) in expanded_uids
    ):
        tree_view.setExpanded(index, True)
