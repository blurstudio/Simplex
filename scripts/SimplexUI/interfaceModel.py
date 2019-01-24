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

#pylint:disable=missing-docstring,unused-argument,no-self-use,too-many-return-statements
from SimplexUI.Qt.QtCore import QAbstractItemModel, QModelIndex, Qt, QSortFilterProxyModel #pylint:disable=E0611,E0401
import re
from contextlib import contextmanager
from interfaceItems import (ProgPair, Progression, Slider, ComboPair,
							Combo, Group, Simplex, Traversal, TravPair)

# Hierarchy Helpers
def coerceIndexToType(indexes, typ):
	''' Get a list of indices of a specific type based on a given index list
	Items containing parents of the type fall down to their children
	Items containing children of the type climb up to their parents
	'''
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
	''' Get a list of indices of a specific type based on a given index list
	Lists containing parents of the type fall down to their children
	'''
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
	''' Get a list of indices of a specific type based on a given index list
	Lists containing children of the type climb up to their parents
	'''
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
	''' Get the topmost indexes for each brach in the hierarchy '''
	indexes = [i for i in indexes if i.column() == 0]
	indexes = sorted(indexes, key=lambda x: x.model().itemFromIndex(x), reverse=True)
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
class ContextModel(QAbstractItemModel):
	@contextmanager
	def insertItemManager(self, parent, row=-1):
		parIdx = self.indexFromItem(parent)
		if row == -1:
			row = self.getItemAppendRow(parent)
		self.beginInsertRows(parIdx, row, row)
		try:
			yield
		finally:
			self.endInsertRows()

	@contextmanager
	def removeItemManager(self, item):
		idx = self.indexFromItem(item)
		if idx.isValid():
			parIdx = idx.parent()
			self.beginRemoveRows(parIdx, idx.row(), idx.row())
		try:
			yield
		finally:
			if idx.isValid():
				self.endRemoveRows()

	@contextmanager
	def moveItemManager(self, item, destPar, destRow=-1):
		itemIdx = self.indexFromItem(item)
		destParIdx = self.indexFromItem(destPar)
		handled = False
		if itemIdx.isValid() and destParIdx.isValid():
			handled = True
			srcParIdx = itemIdx.parent()
			row = itemIdx.row()
			if destRow == -1:
				destRow = self.getItemAppendRow(destPar)
			self.beginMoveRows(srcParIdx, row, row, destParIdx, destRow)
		try:
			yield
		finally:
			if handled:
				self.endMoveRows()

	@contextmanager
	def resetModelManager(self):
		self.beginResetModel()
		try:
			yield
		finally:
			self.endResetModel()

	def indexFromItem(self, item, column=0):
		row = self.getItemRow(item)
		if row is None:
			return QModelIndex()
		return self.createIndex(row, column, item)

	def itemFromIndex(self, index):
		return index.internalPointer()


class SimplexModel(ContextModel):
	''' The base model for all interaction with a simplex system.
	All ui interactions with a simplex system must go through this model
	Any special requirements, or reorganizations of the trees will only
	be implemented as proxy models.
	'''
	def __init__(self, simplex, parent):
		super(SimplexModel, self).__init__(parent)
		self.simplex = simplex
		self.simplex.models.append(self)

	def index(self, row, column, parIndex):
		par = parIndex.internalPointer()
		child = self.getChildItem(par, row)
		if child is None:
			return QModelIndex()
		return self.createIndex(row, column, child)

	def parent(self, index):
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

	def rowCount(self, parIndex):
		parent = parIndex.internalPointer()
		ret = self.getItemRowCount(parent)
		return ret

	def columnCount(self, parIndex):
		return 3

	def data(self, index, role):
		if not index.isValid():
			return None
		item = index.internalPointer()
		return self.getItemData(item, index.column(), role)

	def flags(self, index):
		if not index.isValid():
			return Qt.ItemIsEnabled
		if index.column() == 0:
			item = index.internalPointer()
			if isinstance(item, (Slider, Combo, Traversal)):
				return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsUserCheckable
		# TODO: make the SHAPES object under a combo or traversal not-editable
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

	def setData(self, index, value, role=Qt.EditRole):
		if not index.isValid():
			return False
		if role == Qt.CheckStateRole:
			item = index.internalPointer()
			if index.column() == 0:
				if isinstance(item, (Slider, Combo, Traversal)):
					item.enabled = value == Qt.Checked
					return True
		elif role == Qt.EditRole:
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

	def headerData(self, section, orientation, role):
		if orientation == Qt.Horizontal:
			if role == Qt.DisplayRole:
				sects = ("Items", "Slide", "Value")
				return sects[section]
		return None

	# Methods for dealing with items only
	# These will be used to build the indexes
	# and will be public for utility needs
	def getChildItem(self, parent, row):
		if parent is None:
			if row == 0:
				return self.simplex
			else:
				return None
		return parent.treeChild(row)

	def getItemRow(self, item):
		return item.treeRow()

	def getParentItem(self, item):
		return item.treeParent()

	def getItemRowCount(self, item):
		# Null parent means 1 row that is the simplex object
		if item is None:
			ret = 1
		else:
			ret = item.treeChildCount()
		return ret

	def getItemData(self, item, column, role):
		if role in (Qt.DisplayRole, Qt.EditRole):
			return item.treeData(column)

		elif role == Qt.CheckStateRole:
			chk = None
			if column == 0:
				chk = item.treeChecked()
			if chk is not None:
				chk = Qt.Checked if chk else Qt.Unchecked
			return chk
		return None

	def updateTickValues(self, updatePairs):
		''' Update all the drag-tick values at once. This should be called
		by a single-shot timer or some other once-per-refresh mechanism
		'''
		# Don't make this mouse-tick be stackable. That way
		# we don't update the whole System for a slider value changes
		sliderList = []
		progs = []
		comboList = []
		for i in updatePairs:
			if isinstance(i[0], Slider):
				sliderList.append(i)
			elif isinstance(i[0], ProgPair):
				progs.append(i)
			elif isinstance(i[0], ComboPair):
				comboList.append(i)

		if progs:
			progPairs, values = zip(*progs)
			self.simplex.setShapesValues(progPairs, values)

		if sliderList:
			sliders, values = zip(*sliderList)
			self.simplex.setSlidersWeights(sliders, values)

		if comboList:
			comboPairs, values = zip(*comboList)
			self.simplex.setCombosValues(comboPairs, values)

	def getItemAppendRow(self, item):
		if isinstance(item, Combo):
			# insert before the special "SHAPES" item
			# getItemRowCount returns len(item.pairs) + 1
			return len(item.pairs)
		return self.getItemRowCount(item)

	def itemDataChanged(self, item):
		idx = self.indexFromItem(item)
		if idx.isValid():
			self.dataChanged.emit(idx, idx)


# VIEW MODELS
class BaseProxyModel(QSortFilterProxyModel):
	''' Holds the common item/index translation code '''
	def __init__(self, model, parent=None):
		super(BaseProxyModel, self).__init__(parent)
		self.setSourceModel(model)

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
		super(BaseProxyModel, self).invalidate()

	def invalidateFilter(self):
		source = self.sourceModel()
		if isinstance(source, QSortFilterProxyModel):
			source.invalidateFilter()
		super(BaseProxyModel, self).invalidateFilter()

	def filterAcceptsRow(self, sourceRow, sourceParent):
		return True


class SliderModel(BaseProxyModel):
	def filterAcceptsRow(self, sourceRow, sourceParent):
		sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
		if sourceIndex.isValid():
			item = self.sourceModel().itemFromIndex(sourceIndex)
			if isinstance(item, Group):
				if item.groupType is not Slider:
					return False
		return super(SliderModel, self).filterAcceptsRow(sourceRow, sourceParent)


class ComboModel(BaseProxyModel):
	def filterAcceptsRow(self, sourceRow, sourceParent):
		sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
		if sourceIndex.isValid():
			item = self.sourceModel().itemFromIndex(sourceIndex)
			if isinstance(item, Group):
				if item.groupType is not Combo:
					return False
		return super(ComboModel, self).filterAcceptsRow(sourceRow, sourceParent)


class TraversalModel(BaseProxyModel):
	def filterAcceptsRow(self, sourceRow, sourceParent):
		sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
		if sourceIndex.isValid():
			item = self.sourceModel().itemFromIndex(sourceIndex)
			if isinstance(item, Group):
				if item.groupType is not Traversal:
					return False
		return super(TraversalModel, self).filterAcceptsRow(sourceRow, sourceParent)


# FILTER MODELS
class SimplexFilterModel(BaseProxyModel):
	def __init__(self, model, parent=None):
		super(SimplexFilterModel, self).__init__(model, parent)
		self.setSourceModel(model)
		self._filterString = []
		self._filterReg = []
		self.isolateList = []

	@property
	def filterString(self):
		return ' '.join(self._filterString)

	@filterString.setter
	def filterString(self, val):
		self._filterString = val.split()

		self._filterReg = []
		for sp in self._filterString:
			if sp[0] == '*':
				self._filterReg.append(re.compile(sp, flags=re.I))
			else:
				self._filterReg.append(re.compile('.*?'.join(sp), flags=re.I))

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			if self.filterString or self.isolateList:
				sourceItem = self.sourceModel().itemFromIndex(sourceIndex)
				if isinstance(sourceItem, (ProgPair, Slider, Combo, ComboPair, Progression)):
					if not self.checkChildren(sourceItem):
						return False

		return super(SimplexFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)

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
		global ccDepth
		itemString = sourceItem.name
		print " "*ccDepth, "Check Children", itemString
		if self.matchFilterString(itemString) and self.matchIsolation(itemString):
			return True

		sourceModel = self.sourceModel().sourceModel()
		for row in xrange(sourceModel.getItemRowCount(sourceItem)):
			childItem = sourceModel.getChildItem(sourceItem, row)
			if childItem is not None:
				ccDepth += 1
				ret = self.checkChildren(childItem)
				ccDepth -= 1
				return ret

		return False

ccDepth = 0

class SliderFilterModel(SimplexFilterModel):
	""" Hide single shapes under a slider """
	def __init__(self, model, parent=None):
		super(SliderFilterModel, self).__init__(model, parent)
		self.doFilter = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			if self.doFilter:
				data = self.sourceModel().itemFromIndex(sourceIndex)
				if isinstance(data, ProgPair):
					if len(data.prog.pairs) <= 2:
						return False
					elif data.shape.isRest:
						return False

		return super(SliderFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)


class ComboFilterModel(SimplexFilterModel):
	""" Filter by slider when Show Dependent Combos is checked """
	def __init__(self, model, parent=None):
		super(ComboFilterModel, self).__init__(model, parent)
		self.requires = []
		self.filterRequiresAll = False
		self.filterRequiresAny = False
		self.filterRequiresOnly = False

		self.filterShapes = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
		#always sort by the first column #column = self.filterKeyColumn()
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
			if (self.filterRequiresAny or self.filterRequiresAll or self.filterRequiresOnly) and self.requires:
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

		return super(ComboFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)


class TraversalFilterModel(SimplexFilterModel):
	""" Hide single shapes under a slider """
	def __init__(self, model, parent=None):
		super(TraversalFilterModel, self).__init__(model, parent)
		self.doFilter = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			if self.doFilter:
				data = self.sourceModel().itemFromIndex(sourceIndex)
				if isinstance(data, ProgPair):
					if len(data.prog.pairs) <= 2:
						return False
					elif data.shape.isRest:
						return False

		return super(TraversalFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)


# SETTINGS MODELS
class SliderGroupModel(ContextModel):
	def __init__(self, simplex, parent):
		super(SliderGroupModel, self).__init__(parent)
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

	def index(self, row, column=0, parIndex=QModelIndex()):
		if row <= 0:
			return self.createIndex(row, column, None)
		try:
			falloff = self.simplex.sliderGroups[row-1]
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
		if group and role in (Qt.DisplayRole, Qt.EditRole):
			return group.name
		return None

	def flags(self, index):
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable

	def itemFromIndex(self, index):
		return index.internalPointer()

	def itemDataChanged(self, item):
		idx = self.indexFromItem(item)
		if idx.isValid():
			self.dataChanged.emit(idx, idx)


class FalloffModel(ContextModel):
	def __init__(self, simplex, parent):
		super(FalloffModel, self).__init__(parent)
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
			self.line = ''
			return
		fulls = []
		partials = []
		for fo in self.simplex.falloffs:
			cs = self._getCheckState(fo)
			if cs == Qt.Checked:
				fulls.append(fo.name)
			elif cs == Qt.PartiallyChecked:
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

	def index(self, row, column=0, parIndex=QModelIndex()):
		if row <= 0:
			return self.createIndex(row, column, None)
		try:
			falloff = self.simplex.falloffs[row-1]
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
			return Qt.Checked
		elif len(sli) == 0:
			return Qt.Unchecked
		return Qt.PartiallyChecked

	def data(self, index, role):
		if not index.isValid():
			return None
		falloff = index.internalPointer()
		if not falloff:
			return None

		if role in (Qt.DisplayRole, Qt.EditRole):
			return falloff.name
		elif role == Qt.CheckStateRole:
			return self._getCheckState(falloff)
		return None

	def setData(self, index, value, role):
		if role == Qt.CheckStateRole:
			fo = index.internalPointer()
			if not fo:
				return
			if value == Qt.Checked:
				for s in self.sliders:
					if fo not in s.prog.falloffs:
						s.prog.addFalloff(fo)
						self._checks.setdefault(fo, []).append(s)
			elif value == Qt.Unchecked:
				for s in self.sliders:
					if fo in s.prog.falloffs:
						s.prog.removeFalloff(fo)
						if s in self._checks[fo]:
							self._checks[fo].remove(s) 
			self.buildLine()
			self.dataChanged.emit(index, index)
			return True
		return False

	def flags(self, index):
		return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsUserCheckable

	def itemFromIndex(self, index):
		return index.internalPointer()

	def itemDataChanged(self, item):
		idx = self.indexFromItem(item)
		if idx.isValid():
			self.dataChanged.emit(idx, idx)


class FalloffDataModel(ContextModel):
	def __init__(self, simplex, parent):
		super(FalloffDataModel, self).__init__(parent)
		self.simplex = simplex
		if self.simplex is not None:
			self.simplex.falloffModels.append(self)

	def getItemAppendRow(self, item):
		try:
			return len(self.simplex.falloffs)
		except AttributeError:
			return 0

	def index(self, row, column=0, parIndex=QModelIndex()):
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

		if role in (Qt.DisplayRole, Qt.EditRole):
			if index.column() == 0:
				return falloff.name
			elif index.column() == 1:
				st = falloff.splitType
				sti = ('planar', 'map').index(st.lower())
				return sti
			elif index.column() == 2:
				ax = falloff.axis
				axi = 'xyz'.index(ax.lower())
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
		if role == Qt.EditRole:
			if index.column() == 0:
				falloff.name = value
			elif index.column() == 1:
				if value in [0, 1]:
					value = ('Planar', 'Map')[value]
				falloff.splitType = value
			elif index.column() == 2:
				if value in [0, 1, 2]:
					value = 'XYZ'[value]
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
		return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable

	def itemFromIndex(self, index):
		return index.internalPointer()

	def itemDataChanged(self, item):
		idx = self.indexFromItem(item)
		if idx.isValid():
			self.dataChanged.emit(idx, idx)

	def getItemRow(self, item):
		try:
			idx = self.simplex.falloffs.index(item)
		except ValueError:
			return None
		except AttributeError:
			return None
		return idx

