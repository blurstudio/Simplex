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

# pylint:disable=missing-docstring,unused-argument,no-self-use,too-many-return-statements
import re

from .items import (
    Combo,
    ComboPair,
    Group,
    ProgPair,
    Progression,
    Slider,
    Traversal,
)

from .items.treeItem import AdapterModel

from Qt.QtCore import QModelIndex, QSortFilterProxyModel, Qt
from typing import cast


# Hierarchy Helpers
def coerceIndexToType(indexes, typ):
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


def coerceIndexToChildType(indexes, typ):
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


def coerceIndexToParentType(indexes, typ):
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


def coerceIndexToRoots(indexes):
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
    def simplex(self):
        return self._rootItem


# VIEW MODELS
class BaseProxyModel(QSortFilterProxyModel):
    """Holds the common item/index translation code for my filter models
    Again, This is just a concrete implementation of a Qt base class, so
    documentation will be lacking
    """

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setSourceModel(model)

    def sourceModel(self) -> SimplexModel:
        return cast(SimplexModel, super().sourceModel())

    def indexFromItem(self, item, column=0):
        sourceModel = self.sourceModel()
        sourceIndex = sourceModel.indexFromItem(item, column)
        return self.mapFromSource(sourceIndex)

    def itemFromIndex(self, index):
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

    def filterAcceptsRow(self, sourceRow, sourceParent) -> bool:
        return True


class SliderModel(BaseProxyModel):
    def filterAcceptsRow(self, sourceRow, sourceParent):
        sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
        if sourceIndex.isValid():
            item = self.sourceModel().itemFromIndex(sourceIndex)
            if isinstance(item, Group):
                if item.groupType is not Slider:
                    return False
        return super().filterAcceptsRow(sourceRow, sourceParent)


class ComboModel(BaseProxyModel):
    def filterAcceptsRow(self, sourceRow, sourceParent):
        sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
        if sourceIndex.isValid():
            item = self.sourceModel().itemFromIndex(sourceIndex)
            if isinstance(item, Group):
                if item.groupType is not Combo:
                    return False
        return super().filterAcceptsRow(sourceRow, sourceParent)


class TraversalModel(BaseProxyModel):
    def filterAcceptsRow(self, sourceRow, sourceParent):
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

    def __init__(self, model, parent=None):
        super().__init__(model, parent)
        self.setSourceModel(model)
        self._filterString = []
        self._filterReg = []
        self.isolateList = []

    @property
    def filterString(self):
        return " ".join(self._filterString)

    @filterString.setter
    def filterString(self, val):
        self._filterString = val.split()

        self._filterReg = []
        for sp in self._filterString:
            if sp[0] == "*":
                self._filterReg.append(re.compile(sp, flags=re.I))
            else:
                self._filterReg.append(re.compile(".*?".join(sp), flags=re.I))

    def filterAcceptsRow(self, sourceRow, sourceParent):
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

    def matchFilterString(self, itemString):
        if not self._filterString:
            return True
        for reg in self._filterReg:
            if reg.search(itemString):
                return True
        return False

    def matchIsolation(self, itemString):
        if self.isolateList:
            return itemString in self.isolateList
        return True

    def checkChildren(self, sourceItem):
        itemString = sourceItem.name
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

    def __init__(self, model, parent=None):
        super().__init__(model, parent)
        self.requires = []
        self.filterRequiresAny = False
        self.filterRequiresAll = False

        self.doFilter = True

    def filterAcceptsRow(self, sourceRow, sourceParent):
        # always sort by the first column #column = self.filterKeyColumn()
        column = 0
        sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
        if sourceIndex.isValid():
            data = self.sourceModel().itemFromIndex(sourceIndex)
            if self.doFilter:
                if isinstance(data, ProgPair):
                    if len(data.prog.pairs) <= 2:
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

    def __init__(self, model, parent=None):
        super().__init__(model, parent)
        self.requires = []
        self.filterRequiresAll = False
        self.filterRequiresAny = False
        self.filterRequiresOnly = False

        self.filterShapes = True

    def filterAcceptsRow(self, sourceRow, sourceParent):
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
                    if len(data.prog.pairs) <= 2:
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

    def __init__(self, model, parent=None):
        super().__init__(model, parent)
        self.doFilter = True

    def filterAcceptsRow(self, sourceRow, sourceParent):
        column = 0  # always sort by the first column #column = self.filterKeyColumn()
        sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
        if sourceIndex.isValid():
            if self.doFilter:
                data = self.sourceModel().itemFromIndex(sourceIndex)
                if isinstance(data, ProgPair):
                    if len(data.prog.pairs) <= 2:
                        return False
                    elif data.shape.isRest:
                        return False

        return super().filterAcceptsRow(
            sourceRow, sourceParent
        )


# SETTINGS MODELS
class SliderGroupModel(AdapterModel):
    """A model for displaying Group objects that contain Sliders"""

    def __init__(self, simplex, parent):
        super().__init__(simplex, parent)
        self.simplex = simplex
        self.simplex.models.append(self)

    def getItemRow(self, item):
        try:
            idx = self.simplex.sliderGroups.index(item)
        except ValueError:
            return None
        return idx + 1

    def getItemAppendRow(self, item):
        return len(self.simplex.sliderGroups) + 1

    def index(self, row, column=0, parIndex=None):
        parIndex = QModelIndex() if parIndex is None else parIndex
        if row <= 0:
            return self.createIndex(row, column, None)
        try:
            falloff = self.simplex.sliderGroups[row - 1]
        except IndexError:
            return QModelIndex()
        return self.createIndex(row, column, falloff)

    def parent(self, index):
        return QModelIndex()

    def rowCount(self, parent):
        return len(self.simplex.sliderGroups) + 1

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if not index.isValid():
            return None
        group = index.internalPointer()
        if group and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return group.name
        return None

    def flags(self, index):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def itemFromIndex(self, index):
        return index.internalPointer()


class FalloffModel(AdapterModel):
    """A model for displaying Falloff objects connected to Sliders"""

    def __init__(self, simplex, parent):
        super().__init__(simplex, parent)
        self.simplex = simplex
        if self.simplex is not None:
            self.simplex.falloffModels.append(self)
        self.sliders = []
        self._checks = {}
        self.line = ""

    def setSliders(self, sliders):
        self.beginResetModel()
        self.sliders = sliders
        self._checks = {}
        for slider in self.sliders:
            for fo in slider.prog.falloffs:
                self._checks.setdefault(fo, []).append(slider)
        self.endResetModel()
        self.buildLine()

    def buildLine(self):
        if not self.sliders:
            self.line = ""
            return
        fulls = []
        partials = []
        for fo in self.simplex.falloffs:
            cs = self._getCheckState(fo)
            if cs == Qt.CheckState.Checked:
                fulls.append(fo.name)
            elif cs == Qt.CheckState.PartiallyChecked:
                partials.append(fo.name)
        if partials:
            title = "{0} <<{1}>>".format(",".join(fulls), ",".join(partials))
        else:
            title = ",".join(fulls)
        self.line = title

    def getItemRow(self, item):
        try:
            idx = self.simplex.falloffs.index(item)
        except ValueError:
            return None
        except AttributeError:
            return None
        return idx + 1

    def getItemAppendRow(self, item):
        try:
            return len(self.simplex.falloffs)
        except AttributeError:
            return 0

    def index(self, row, column=0, parIndex=None):
        parIndex = QModelIndex() if parIndex is None else parIndex
        if row <= 0:
            return self.createIndex(row, column, None)
        try:
            falloff = self.simplex.falloffs[row - 1]
        except IndexError:
            return QModelIndex()
        except AttributeError:
            return QModelIndex()
        return self.createIndex(row, column, falloff)

    def parent(self, index):
        return QModelIndex()

    def rowCount(self, parent):
        try:
            return len(self.simplex.falloffs) + 1
        except AttributeError:
            return 0

    def columnCount(self, parent):
        return 1

    def _getCheckState(self, fo):
        sli = self._checks.get(fo, [])
        if len(sli) == len(self.sliders):
            return Qt.CheckState.Checked
        elif len(sli) == 0:
            return Qt.CheckState.Unchecked
        return Qt.CheckState.PartiallyChecked

    def data(self, index, role):
        if not index.isValid():
            return None
        falloff = index.internalPointer()
        if not falloff:
            return None

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return falloff.name
        elif role == Qt.ItemDataRole.CheckStateRole:
            return self._getCheckState(falloff)
        return None

    def setData(self, index, value, role):
        if role == Qt.ItemDataRole.CheckStateRole:
            fo = index.internalPointer()
            if not fo:
                return
            if value == Qt.CheckState.Checked:
                for s in self.sliders:
                    if fo not in s.prog.falloffs:
                        s.prog.addFalloff(fo)
                        self._checks.setdefault(fo, []).append(s)
            elif value == Qt.CheckState.Unchecked:
                for s in self.sliders:
                    if fo in s.prog.falloffs:
                        s.prog.removeFalloff(fo)
                        if s in self._checks[fo]:
                            self._checks[fo].remove(s)
            self.buildLine()
            self.emitDataChanged(index)
            return True
        return False

    def flags(self, index):
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsUserCheckable
        )

    def itemFromIndex(self, index):
        return index.internalPointer()


class FalloffDataModel(AdapterModel):
    """A model for displaying the data of Falloff objects"""

    def __init__(self, simplex, parent):
        super().__init__(simplex, parent)
        self.simplex = simplex
        if self.simplex is not None:
            self.simplex.falloffModels.append(self)

    def getItemAppendRow(self, item):
        try:
            return len(self.simplex.falloffs)
        except AttributeError:
            return 0

    def index(self, row, column=0, parIndex=None):
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

    def parent(self, index):
        return QModelIndex()

    def rowCount(self, parent):
        try:
            return len(self.simplex.falloffs)
        except AttributeError:
            return 0

    def columnCount(self, parent):
        return 8

    def data(self, index, role):
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

    def setData(self, index, value, role):
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

    def flags(self, index):
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsSelectable
        )

    def itemFromIndex(self, index):
        return index.internalPointer()

    def getItemRow(self, item):
        try:
            idx = self.simplex.falloffs.index(item)
        except ValueError:
            return None
        except AttributeError:
            return None
        return idx
