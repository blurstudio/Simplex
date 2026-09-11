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

from __future__ import annotations

import re
from typing import Any, TypeVar, cast

from Qt.QtCore import QModelIndex, QSortFilterProxyModel, Qt
from Qt.QtWidgets import QWidget

from .items import (
    Combo,
    ComboPair,
    Falloff,
    Group,
    ProgPair,
    Progression,
    Simplex,
    Slider,
    Traversal,
    TravPair,
)
from .items.treeItem import AdapterModel, TreeItem, TreeRootItem

T = TypeVar('T', bound=TreeItem)


# Hierarchy Helpers
def coerceIndexToType(indexes: list[QModelIndex], typ: type[T]) -> list[QModelIndex]:
    """Get a list of indices of a specific type based on a given index list
    Items containing parents of the type fall down to their children
    Items containing children of the type climb up to their parents

    Parameters
    ----------
    indexes : [QModelIndex, ...]
        A list of indexes to coerce
    typ : Type
        The type to coerce to

    Returns
    -------
    [QModelIndex, ...]
        The coerced list
    """
    targetDepth = typ.classDepth

    children = []
    parents = []
    out = []
    for idx in indexes:
        item = idx.model().itemFromIndex(idx)
        depth = item.classDepth
        if depth < targetDepth:
            parents.append(idx)
        elif depth > targetDepth:
            children.append(idx)
        else:
            out.append(idx)

    out.extend(coerceIndexToChildType(parents, typ))
    out.extend(coerceIndexToParentType(children, typ))
    out = list(set(out))
    return out


def coerceIndexToChildType(
    indexes: list[QModelIndex], typ: type[T]
) -> list[QModelIndex]:
    """Get a list of indices of a specific type based on a given index list
        Lists containing parents of the type fall down to their children

    Parameters
    ----------
    indexes : [QModelIndex, ...]
        A list of indexes to coerce
    typ : Type
        The type to coerce to

    Returns
    -------
    [QModelIndex, ...]
        The coerced list
    """
    targetDepth = typ.classDepth
    out = []

    for idx in indexes:
        model = idx.model()
        item = idx.model().itemFromIndex(idx)
        if item.classDepth < targetDepth:
            # Too high up, grab children
            queue = [idx]
            depthIdxs = []
            while queue:
                checkIdx = queue.pop()
                checkItem = checkIdx.model().itemFromIndex(checkIdx)
                if checkItem.classDepth < targetDepth:
                    for row in range(model.rowCount(checkIdx)):
                        queue.append(model.index(row, 0, checkIdx))
                elif checkItem.classDepth == targetDepth:
                    depthIdxs.append(checkIdx)
            out.extend(depthIdxs)
        elif item.classDepth == targetDepth:
            out.append(idx)

    out = list(set(out))
    return out


def coerceIndexToParentType(
    indexes: list[QModelIndex], typ: type[T]
) -> list[QModelIndex]:
    """Get a list of indices of a specific type based on a given index list
        Lists containing children of the type climb up to their parents

    Parameters
    ----------
    indexes : [QModelIndex, ...]
        A list of indexes to coerce
    typ : Type
        The type to coerce to

    Returns
    -------
    [QModelIndex, ...]
        The coerced list
    """
    targetDepth = typ.classDepth
    out = []
    for idx in indexes:
        item = idx.model().itemFromIndex(idx)
        depth = item.classDepth
        if depth > targetDepth:
            parIdx = idx
            parItem = parIdx.model().itemFromIndex(parIdx)
            while parItem.classDepth > targetDepth:
                parIdx = parIdx.parent()
                parItem = parIdx.model().itemFromIndex(parIdx)
            if parItem.classDepth == targetDepth:
                out.append(parIdx)
        elif depth == targetDepth:
            out.append(idx)

    out = list(set(out))
    return out


def coerceIndexToRoots(indexes: list[QModelIndex]) -> list[QModelIndex]:
    """Get the topmost indexes for each brach in the hierarchy

    Parameters
    ----------
    indexes : [QModelIndex, ...]
        A list of indexes to coerce

    Returns
    -------
    [QModelIndex, ...]
        The coerced list
    """
    indexes = [i for i in indexes if i.column() == 0]
    indexes = sorted(
        indexes, key=lambda x: x.model().itemFromIndex(x).classDepth, reverse=True
    )
    # Check each item to see if any of it's ancestors
    # are in the selection list.  If not, it's a root
    roots = []
    for idx in indexes:
        par = idx.parent()
        while par.isValid():
            if par in indexes:
                break
            par = par.parent()
        else:
            roots.append(idx)

    return roots


# BASE MODEL
class SimplexModel(AdapterModel):
    """The base model for all interaction with a simplex system.
    All ui interactions with a simplex system must go through this model
    Any special requirements, or reorganizations of the trees will only
    be implemented as proxy models.

    There will be little documentation for this class, as all methods
    are virtual overrides of the underlying Qt class

    Parameters
    ----------
    simplex : Simplex
        The Simplex system for this model
    parent : QObject
        The parent for this model

    """

    @property
    def simplex(self) -> TreeRootItem | None:
        return self._rootItem

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int
    ) -> str | None:
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                sects = ("Items", "Slide", "Value")
                return sects[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        if index.column() == 0:
            item = index.internalPointer()
            if isinstance(item, (Slider, Combo, Traversal)):
                return (
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEditable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
            elif isinstance(item, Progression):
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if not index.isValid():
            return False
        if role == Qt.ItemDataRole.CheckStateRole:
            item = index.internalPointer()
            if index.column() == 0:
                if isinstance(item, (Slider, Combo, Traversal)):
                    item.enabled = value == Qt.CheckState.Checked.value
                    return True
        elif role == Qt.ItemDataRole.EditRole:
            item = index.internalPointer()
            if index.column() == 0:
                if isinstance(item, (Group, Slider, Combo, Traversal, ProgPair)):
                    item.name = value
                    return True

            elif index.column() == 1:
                if isinstance(item, Slider):
                    item.value = value
                elif isinstance(item, ComboPair):
                    item.value = value
                elif isinstance(item, TravPair):
                    item.value = value

            elif index.column() == 2:
                if isinstance(item, ProgPair):
                    item.value = value
        return False


# VIEW MODELS
class BaseProxyModel(QSortFilterProxyModel):
    """Holds the common item/index translation code for my filter models
    Again, This is just a concrete implementation of a Qt base class, so
    documentation will be lacking
    """

    def __init__(self, model: SimplexModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSourceModel(model)

    def sourceModel(self) -> SimplexModel:
        return cast(SimplexModel, super().sourceModel())

    def indexFromItem(self, item: TreeItem, column: int = 0) -> QModelIndex:
        sourceModel = self.sourceModel()
        sourceIndex = sourceModel.indexFromItem(item, column)
        return self.mapFromSource(sourceIndex)

    def itemFromIndex(self, index: QModelIndex) -> TreeItem | None:
        sourceModel = self.sourceModel()
        sIndex = self.mapToSource(index)
        return sourceModel.itemFromIndex(sIndex)

    def invalidate(self):
        source = self.sourceModel()
        if isinstance(source, QSortFilterProxyModel):
            source.invalidate()
        super().invalidate()

    def invalidateFilter(self):
        source = self.sourceModel()
        if isinstance(source, QSortFilterProxyModel):
            source.invalidateFilter()
        super().invalidateFilter()

    def filterAcceptsRow(self, sourceRow: int, sourceParent: QModelIndex) -> bool:
        return True


class SliderModel(BaseProxyModel):
    def filterAcceptsRow(self, sourceRow: int, sourceParent: QModelIndex) -> bool:
        sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
        if sourceIndex.isValid():
            item = self.sourceModel().itemFromIndex(sourceIndex)
            if isinstance(item, Group):
                if item.groupType is not Slider:
                    return False
        return super().filterAcceptsRow(sourceRow, sourceParent)


class ComboModel(BaseProxyModel):
    def filterAcceptsRow(self, sourceRow: int, sourceParent: QModelIndex) -> bool:
        sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
        if sourceIndex.isValid():
            item = self.sourceModel().itemFromIndex(sourceIndex)
            if isinstance(item, Group):
                if item.groupType is not Combo:
                    return False
        return super().filterAcceptsRow(sourceRow, sourceParent)


class TraversalModel(BaseProxyModel):
    def filterAcceptsRow(self, sourceRow: int, sourceParent: QModelIndex) -> bool:
        sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
        if sourceIndex.isValid():
            item = self.sourceModel().itemFromIndex(sourceIndex)
            if isinstance(item, Group):
                if item.groupType is not Traversal:
                    return False
        return super().filterAcceptsRow(sourceRow, sourceParent)


# FILTER MODELS
class SimplexFilterModel(BaseProxyModel):
    """Filter a model based off of a given string
    Set the `filterString` object property to filter the model
    """

    def __init__(self, model: SimplexModel, parent: QWidget | None = None):
        super().__init__(model, parent)
        self.setSourceModel(model)
        self.filterShapes: bool = True
        self._filterString: list[str] = []
        self._filterReg: list[re.Pattern[str]] = []
        self.isolateList: list[str] = []

    @property
    def filterString(self) -> str:
        return " ".join(self._filterString)

    @filterString.setter
    def filterString(self, val: str):
        self._filterString = val.split()

        self._filterReg = []
        for sp in self._filterString:
            if sp[0] == "*":
                rex = re.compile(sp, flags=re.I)
                self._filterReg.append(rex)
            else:
                rex = re.compile(".*?".join(sp), flags=re.I)
                self._filterReg.append(rex)

    def filterAcceptsRow(self, sourceRow: int, sourceParent: QModelIndex) -> bool:
        column = 0  # always sort by the first column #column = self.filterKeyColumn()
        sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
        if sourceIndex.isValid():
            if self.filterString or self.isolateList:
                sourceItem = self.sourceModel().itemFromIndex(sourceIndex)
                if isinstance(
                    sourceItem, (ProgPair, Slider, Combo, ComboPair, Progression)
                ):
                    if not self.checkChildren(sourceItem):
                        return False

        return super().filterAcceptsRow(sourceRow, sourceParent)

    def matchFilterString(self, itemString: str) -> bool:
        if not self._filterString:
            return True
        for reg in self._filterReg:
            if reg.search(itemString):
                return True
        return False

    def matchIsolation(self, itemString: str) -> bool:
        if self.isolateList:
            return itemString in self.isolateList
        return True

    def checkChildren(self, sourceItem: TreeItem) -> bool:
        if hasattr(sourceItem, 'name'):
            itemString = sourceItem.name  # type: ignore
            if self.matchFilterString(itemString) and self.matchIsolation(itemString):
                return True

        sourceModel = self.sourceModel().sourceModel()
        for row in range(sourceModel.getItemRowCount(sourceItem)):
            childItem = sourceModel.getChildItem(sourceItem, row)
            if childItem is not None:
                return self.checkChildren(childItem)

        return False


class SliderFilterModel(SimplexFilterModel):
    """Hide single shapes under a slider"""

    def __init__(self, model: SimplexModel, parent: QWidget | None = None):
        super().__init__(model, parent)
        self.requires: list[Combo] = []
        self.filterRequiresAny: bool = False
        self.filterRequiresAll: bool = False
        self.doFilter: bool = True

    def filterAcceptsRow(self, sourceRow: int, sourceParent: QModelIndex) -> bool:
        # always sort by the first column #column = self.filterKeyColumn()
        column = 0
        sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
        if sourceIndex.isValid():
            data = self.sourceModel().itemFromIndex(sourceIndex)
            if self.doFilter:
                if isinstance(data, ProgPair):
                    if data.prog is None:
                        return False
                    elif len(data.prog.pairs) <= 2:
                        return False
                    elif data.shape.isRest:
                        return False

            if (self.filterRequiresAny or self.filterRequiresAll) and self.requires:
                # Ignore items that aren't part of the required combos, if requested
                if isinstance(data, Slider):
                    sliGroups = [[i.slider for i in c.pairs] for c in self.requires]
                    if self.filterRequiresAny:
                        if not any(data in s for s in sliGroups):
                            return False
                    elif self.filterRequiresAll:
                        if not all(data in s for s in sliGroups):
                            return False

        return super().filterAcceptsRow(sourceRow, sourceParent)


class ComboFilterModel(SimplexFilterModel):
    """Filter by slider when Show Dependent Combos is checked"""

    def __init__(self, model: SimplexModel, parent: QWidget | None = None):
        super().__init__(model, parent)
        self.requires: list[Slider] = []
        self.filterRequiresAll: bool = False
        self.filterRequiresAny: bool = False
        self.filterRequiresOnly: bool = False

    def filterAcceptsRow(self, sourceRow: int, sourceParent: QModelIndex) -> bool:
        # always sort by the first column #column = self.filterKeyColumn()
        column = 0
        sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
        if sourceIndex.isValid():
            data = self.sourceModel().itemFromIndex(sourceIndex)
            if self.filterShapes:
                # ignore the SHAPE par if there's nothing under there
                if isinstance(data, Progression):
                    if len(data.pairs) <= 2:
                        return False
                # Ignore shape things if requested
                if isinstance(data, ProgPair):
                    if data.prog is None:
                        return False
                    elif len(data.prog.pairs) <= 2:
                        return False
                    elif data.shape.isRest:
                        return False
            if (
                self.filterRequiresAny
                or self.filterRequiresAll
                or self.filterRequiresOnly
            ) and self.requires:
                # Ignore items that don't use the required sliders if requested
                if isinstance(data, Combo):
                    sliders = [i.slider for i in data.pairs]
                    if self.filterRequiresAll:
                        if not all(r in sliders for r in self.requires):
                            return False
                    elif self.filterRequiresAny:
                        if not any(r in sliders for r in self.requires):
                            return False
                    elif self.filterRequiresOnly:
                        if not all(r in self.requires for r in sliders):
                            return False

        return super().filterAcceptsRow(sourceRow, sourceParent)


class TraversalFilterModel(SimplexFilterModel):
    """Hide single shapes under a slider"""

    def __init__(self, model: SimplexModel, parent: QWidget | None = None):
        super().__init__(model, parent)
        self.doFilter = True

    def filterAcceptsRow(self, sourceRow: int, sourceParent: QModelIndex) -> bool:
        column = 0  # always sort by the first column #column = self.filterKeyColumn()
        sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
        if sourceIndex.isValid():
            if self.doFilter:
                data = self.sourceModel().itemFromIndex(sourceIndex)
                if isinstance(data, ProgPair):
                    if data.prog is None:
                        return False
                    elif len(data.prog.pairs) <= 2:
                        return False
                    elif data.shape.isRest:
                        return False

        return super().filterAcceptsRow(sourceRow, sourceParent)


class FalloffDataModel(AdapterModel):
    """A model for displaying the data of Falloff objects"""

    def __init__(self, simplex: Simplex, parent: QWidget | None):
        super().__init__(simplex, parent)
        self.simplex = simplex

    def getItemAppendRow(self, item: TreeItem) -> int:
        try:
            return len(self.simplex.falloffs)
        except AttributeError:
            return 0

    def index(
        self, row: int, column: int = 0, parIndex: QModelIndex | None = None
    ) -> QModelIndex:
        parIndex = QModelIndex() if parIndex is None else parIndex
        if row < 0:
            return QModelIndex()
        try:
            falloff = self.simplex.falloffs[row]
        except IndexError:
            return QModelIndex()
        except AttributeError:
            return QModelIndex()
        return self.createIndex(row, column, falloff)

    def parent(self, index: QModelIndex) -> QModelIndex:
        return QModelIndex()

    def rowCount(self, parent):
        try:
            return len(self.simplex.falloffs)
        except AttributeError:
            return 0

    def columnCount(self, parent: QModelIndex) -> int:
        return 8

    def data(self, index: QModelIndex, role: int) -> Any:
        if not index.isValid():
            return None
        falloff = index.internalPointer()
        if not falloff:
            return None

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if index.column() == 0:
                return falloff.name
            elif index.column() == 1:
                st = falloff.splitType
                sti = ("planar", "map").index(st.lower())
                return sti
            elif index.column() == 2:
                ax = falloff.axis
                axi = "xyz".index(ax.lower())
                return axi
            elif index.column() == 3:
                return falloff.maxVal
            elif index.column() == 4:
                return falloff.maxHandle
            elif index.column() == 5:
                return falloff.minHandle
            elif index.column() == 6:
                return falloff.minVal
            elif index.column() == 7:
                return falloff.mapName
        return None

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        if not index.isValid():
            return False
        falloff = index.internalPointer()
        if not falloff:
            return False
        if role == Qt.ItemDataRole.EditRole:
            if index.column() == 0:
                falloff.name = value
            elif index.column() == 1:
                if value in [0, 1]:
                    value = ("planar", "map")[value]
                falloff.splitType = value
            elif index.column() == 2:
                if value in [0, 1, 2]:
                    value = "XYZ"[value]
                falloff.axis = value
            elif index.column() == 3:
                falloff.maxVal = value
            elif index.column() == 4:
                falloff.maxHandle = value
            elif index.column() == 5:
                falloff.minHandle = value
            elif index.column() == 6:
                falloff.minVal = value
            elif index.column() == 7:
                falloff.mapName = value
            return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsSelectable
        )

    def itemFromIndex(self, index: QModelIndex) -> TreeItem:
        return index.internalPointer()

    def getItemRow(self, item: Falloff) -> int | None:
        try:
            idx = self.simplex.falloffs.index(item)
        except ValueError:
            return None
        except AttributeError:
            return None
        return idx
