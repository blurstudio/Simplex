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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.

#pylint:disable=missing-docstring,unused-argument,no-self-use,too-many-return-statements
from .Qt.QtCore import QAbstractItemModel, QModelIndex, Qt, QSortFilterProxyModel #pylint:disable=E0611,E0401
from .Qt import IsPySide2, IsPyQt5

import re
from contextlib import contextmanager
from items import (ProgPair, Progression, Slider, ComboPair, Combo, Group, Simplex, Traversal, TravPair)

# Hierarchy Helpers
def coerceIndexToType(indexes, typ):
	''' Get a list of indices of a specific type based on a given index list
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
	''' Get the topmost indexes for each brach in the hierarchy

	Parameters
	----------
	indexes : [QModelIndex, ...]
		A list of indexes to coerce

	Returns
	-------
	[QModelIndex, ...]
		The coerced list
	'''
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
	''' A sub-class of QAbstractItemModel with built-in contextmanagers
		that handle calling the begin/end signals for adding/removing/moving/resettting
	'''
	@contextmanager
	def insertItemManager(self, parent, row=-1):
		''' ContextManager for inserting items into the model

		Parameters
		----------
		parent : object
			The item in the tree that will be the parent
		row : int
			The row to insert into. Pass -1 to append to the list (Default value = -1)
		'''
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
		''' ContextManager for removing items from the model

		Parameters
		----------
		item : object
			The item to remove from the model
		'''
		idx = self.indexFromItem(item)
		valid = idx.isValid()
		if valid:
			parIdx = idx.parent()
			self.beginRemoveRows(parIdx, idx.row(), idx.row())
		try:
			yield
		finally:
			if valid:
				self.endRemoveRows()

	@contextmanager
	def moveItemManager(self, item, destPar, destRow=-1):
		''' ContextManager for moving items within the model

		Parameters
		----------
		item : object
			The item to move in the model
		destPar : object
			The object that will be the new parent
		destRow : int
			The row to move to. Pass -1 to move to the end (Default value = -1)
		'''
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
		''' ContextManager for resetting the entire model '''
		self.beginResetModel()
		try:
			yield
		finally:
			self.endResetModel()

	def indexFromItem(self, item, column=0):
		''' Return the index for the given item

		Parameters
		----------
		item : object
			The item to move in the model
		column : int
			The column to get the index for. Defaults to 0

		Returns
		-------
		QModelIndex
			The index of the item
		'''
		row = self.getItemRow(item)
		if row is None:
			return QModelIndex()
		return self.createIndex(row, column, item)

	def itemFromIndex(self, index):
		''' Return the item for the given index

		Parameters
		----------
		index : QModelIndex
			The index to get the item of

		Returns
		-------
		object
			The item in the tree
		'''
		return index.internalPointer()

	def itemDataChanged(self, item):
		''' Emit the itemDataChanged signal.
		
		This must be done through this interface because, unfortunately, I can't quite figure out how
		to make the empty `roles` list pass properly for Qt5. So I have to change behavior based
		on the Qt backend

		Parameters
		----------
		item : object
			The object whose data has changed
		'''
		idx = self.indexFromItem(item)
		self.emitDataChanged(idx)

	def _emitDataChangedQt5(self, index):
     """
     Reimplemented signal signal

     Args:
         self: (todo): write your description
         index: (int): write your description
     """
		if index.isValid():
			self.dataChanged.emit(index, index, [])

	def _emitDataChangedQt4(self, index):
     """
     Reimplemented from the editor.

     Args:
         self: (todo): write your description
         index: (int): write your description
     """
		if index.isValid():
			self.dataChanged.emit(index, index)

	emitDataChanged = _emitDataChangedQt5 if IsPySide2 or IsPyQt5 else _emitDataChangedQt4


class SimplexModel(ContextModel):
	''' The base model for all interaction with a simplex system.
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

	'''
	def __init__(self, simplex, parent):
     """
     Initialize simulation.

     Args:
         self: (todo): write your description
         simplex: (todo): write your description
         parent: (todo): write your description
     """
		super(SimplexModel, self).__init__(parent)
		self.simplex = simplex
		self.simplex.models.append(self)

	def index(self, row, column, parIndex):
     """
     Return the index of the item at the given index.

     Args:
         self: (todo): write your description
         row: (int): write your description
         column: (str): write your description
         parIndex: (todo): write your description
     """
		par = parIndex.internalPointer()
		child = self.getChildItem(par, row)
		if child is None:
			return QModelIndex()
		return self.createIndex(row, column, child)

	def parent(self, index):
     """
     Return the parent of the item

     Args:
         self: (todo): write your description
         index: (todo): write your description
     """
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
     """
     Return the number of rows in the item.

     Args:
         self: (todo): write your description
         parIndex: (todo): write your description
     """
		parent = parIndex.internalPointer()
		ret = self.getItemRowCount(parent)
		return ret

	def columnCount(self, parIndex):
     """
     Return the number of rows in a column.

     Args:
         self: (todo): write your description
         parIndex: (int): write your description
     """
		return 3

	def data(self, index, role):
     """
     Return the data for the item at the given index.

     Args:
         self: (todo): write your description
         index: (todo): write your description
         role: (str): write your description
     """
		if not index.isValid():
			return None
		item = index.internalPointer()
		return self.getItemData(item, index.column(), role)

	def flags(self, index):
     """
     Returns the item flags

     Args:
         self: (todo): write your description
         index: (todo): write your description
     """
		if not index.isValid():
			return Qt.ItemIsEnabled
		if index.column() == 0:
			item = index.internalPointer()
			if isinstance(item, (Slider, Combo, Traversal)):
				return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsUserCheckable
		# TODO: make the SHAPES object under a combo or traversal not-editable
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

	def setData(self, index, value, role=Qt.EditRole):
     """
     Sets the data for : meth : qabstractitemmodel | <int >

     Args:
         self: (todo): write your description
         index: (todo): write your description
         value: (todo): write your description
         role: (str): write your description
         Qt: (todo): write your description
         EditRole: (todo): write your description
     """
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
     """
     Return the header

     Args:
         self: (todo): write your description
         section: (todo): write your description
         orientation: (todo): write your description
         role: (str): write your description
     """
		if orientation == Qt.Horizontal:
			if role == Qt.DisplayRole:
				sects = ("Items", "Slide", "Value")
				return sects[section]
		return None

	# Methods for dealing with items only
	# These will be used to build the indexes
	# and will be public for utility needs
	def getChildItem(self, parent, row):
     """
     Return the child of the given parent.

     Args:
         self: (todo): write your description
         parent: (todo): write your description
         row: (str): write your description
     """
		if parent is None:
			if row == 0:
				return self.simplex
			else:
				return None
		return parent.treeChild(row)

	def getItemRow(self, item):
     """
     Returns the item at the item.

     Args:
         self: (todo): write your description
         item: (str): write your description
     """
		if item is None:
			return None
		return item.treeRow()

	def getParentItem(self, item):
     """
     Get the parent item in the given item.

     Args:
         self: (todo): write your description
         item: (todo): write your description
     """
		if item is None:
			return None
		return item.treeParent()

	def getItemRowCount(self, item):
     """
     Returns the number of rows in the tree.

     Args:
         self: (todo): write your description
         item: (todo): write your description
     """
		# Null parent means 1 row that is the simplex object
		if item is None:
			ret = 1
		else:
			ret = item.treeChildCount()
		return ret

	def getItemData(self, item, column, role):
     """
     Return the data for the item

     Args:
         self: (todo): write your description
         item: (todo): write your description
         column: (todo): write your description
         role: (str): write your description
     """
		if item is None:
			return None

		if role in (Qt.DisplayRole, Qt.EditRole):
			return item.treeData(column)

		elif role == Qt.CheckStateRole:
			chk = None
			if column == 0:
				chk = item.treeChecked()
			if chk is not None:
				chk = Qt.Checked if chk else Qt.Unchecked
			return chk
		elif role == Qt.DecorationRole:
			if column == 0:
				return item.icon()
		return None

	def getItemAppendRow(self, item):
     """
     Returns the number of rows of the item.

     Args:
         self: (todo): write your description
         item: (str): write your description
     """
		if isinstance(item, Combo):
			# insert before the special "SHAPES" item
			# getItemRowCount returns len(item.pairs) + 1
			return len(item.pairs)
		return self.getItemRowCount(item)


# VIEW MODELS
class BaseProxyModel(QSortFilterProxyModel):
	''' Holds the common item/index translation code for my filter models
	Again, This is just a concrete implementation of a Qt base class, so
	documentation will be lacking
	'''
	def __init__(self, model, parent=None):
     """
     Initialize the parent model.

     Args:
         self: (todo): write your description
         model: (todo): write your description
         parent: (todo): write your description
     """
		super(BaseProxyModel, self).__init__(parent)
		self.setSourceModel(model)

	def indexFromItem(self, item, column=0):
     """
     Returns the index of the given item.

     Args:
         self: (todo): write your description
         item: (todo): write your description
         column: (str): write your description
     """
		sourceModel = self.sourceModel()
		sourceIndex = sourceModel.indexFromItem(item, column)
		return self.mapFromSource(sourceIndex)

	def itemFromIndex(self, index):
     """
     Return the index for the given index.

     Args:
         self: (todo): write your description
         index: (int): write your description
     """
		sourceModel = self.sourceModel()
		sIndex = self.mapToSource(index)
		return sourceModel.itemFromIndex(sIndex)

	def invalidate(self):
     """
     Reimplemented from the qgraphicswidget method.

     Args:
         self: (todo): write your description
     """
		source = self.sourceModel()
		if isinstance(source, QSortFilterProxyModel):
			source.invalidate()
		super(BaseProxyModel, self).invalidate()

	def invalidateFilter(self):
     """
     Filters the filter for the filter.

     Args:
         self: (todo): write your description
     """
		source = self.sourceModel()
		if isinstance(source, QSortFilterProxyModel):
			source.invalidateFilter()
		super(BaseProxyModel, self).invalidateFilter()

	def filterAcceptsRow(self, sourceRow, sourceParent):
     """
     Todo - filter.

     Args:
         self: (todo): write your description
         sourceRow: (str): write your description
         sourceParent: (todo): write your description
     """
		return True


class SliderModel(BaseProxyModel):
	def filterAcceptsRow(self, sourceRow, sourceParent):
     """
     Filters out - of the inputed row.

     Args:
         self: (todo): write your description
         sourceRow: (str): write your description
         sourceParent: (todo): write your description
     """
		sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
		if sourceIndex.isValid():
			item = self.sourceModel().itemFromIndex(sourceIndex)
			if isinstance(item, Group):
				if item.groupType is not Slider:
					return False
		return super(SliderModel, self).filterAcceptsRow(sourceRow, sourceParent)


class ComboModel(BaseProxyModel):
	def filterAcceptsRow(self, sourceRow, sourceParent):
     """
     Filters out - combobox for this item.

     Args:
         self: (todo): write your description
         sourceRow: (str): write your description
         sourceParent: (todo): write your description
     """
		sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
		if sourceIndex.isValid():
			item = self.sourceModel().itemFromIndex(sourceIndex)
			if isinstance(item, Group):
				if item.groupType is not Combo:
					return False
		return super(ComboModel, self).filterAcceptsRow(sourceRow, sourceParent)


class TraversalModel(BaseProxyModel):
	def filterAcceptsRow(self, sourceRow, sourceParent):
     """
     Filters the given row.

     Args:
         self: (todo): write your description
         sourceRow: (str): write your description
         sourceParent: (todo): write your description
     """
		sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
		if sourceIndex.isValid():
			item = self.sourceModel().itemFromIndex(sourceIndex)
			if isinstance(item, Group):
				if item.groupType is not Traversal:
					return False
		return super(TraversalModel, self).filterAcceptsRow(sourceRow, sourceParent)


# FILTER MODELS
class SimplexFilterModel(BaseProxyModel):
	''' Filter a model based off of a given string
	Set the `filterString` object property to filter the model
	'''
	def __init__(self, model, parent=None):
     """
     Init the parent filter.

     Args:
         self: (todo): write your description
         model: (todo): write your description
         parent: (todo): write your description
     """
		super(SimplexFilterModel, self).__init__(model, parent)
		self.setSourceModel(model)
		self._filterString = []
		self._filterReg = []
		self.isolateList = []

	@property
	def filterString(self):
     """
     Returns a string representation.

     Args:
         self: (todo): write your description
     """
		return ' '.join(self._filterString)

	@filterString.setter
	def filterString(self, val):
     """
     Add a filter.

     Args:
         self: (todo): write your description
         val: (str): write your description
     """
		self._filterString = val.split()

		self._filterReg = []
		for sp in self._filterString:
			if sp[0] == '*':
				self._filterReg.append(re.compile(sp, flags=re.I))
			else:
				self._filterReg.append(re.compile('.*?'.join(sp), flags=re.I))

	def filterAcceptsRow(self, sourceRow, sourceParent):
     """
     Filters out the row for this item.

     Args:
         self: (todo): write your description
         sourceRow: (str): write your description
         sourceParent: (todo): write your description
     """
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
     """
     Returns true if the filter matches the filter.

     Args:
         self: (todo): write your description
         itemString: (str): write your description
     """
		if not self._filterString:
			return True
		for reg in self._filterReg:
			if reg.search(itemString):
				return True
		return False

	def matchIsolation(self, itemString):
     """
     Determine if a list matches the given string.

     Args:
         self: (todo): write your description
         itemString: (str): write your description
     """
		if self.isolateList:
			return itemString in self.isolateList
		return True

	def checkChildren(self, sourceItem):
     """
     Checks if the inputed children are valid

     Args:
         self: (todo): write your description
         sourceItem: (str): write your description
     """
		itemString = sourceItem.name
		if self.matchFilterString(itemString) and self.matchIsolation(itemString):
			return True

		sourceModel = self.sourceModel().sourceModel()
		for row in xrange(sourceModel.getItemRowCount(sourceItem)):
			childItem = sourceModel.getChildItem(sourceItem, row)
			if childItem is not None:
				return self.checkChildren(childItem)

		return False


class SliderFilterModel(SimplexFilterModel):
	''' Hide single shapes under a slider '''
	def __init__(self, model, parent=None):
     """
     Initialize filter

     Args:
         self: (todo): write your description
         model: (todo): write your description
         parent: (todo): write your description
     """
		super(SliderFilterModel, self).__init__(model, parent)
		self.doFilter = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
     """
     Filters out the rows for the given row.

     Args:
         self: (todo): write your description
         sourceRow: (str): write your description
         sourceParent: (todo): write your description
     """
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
	''' Filter by slider when Show Dependent Combos is checked '''
	def __init__(self, model, parent=None):
     """
     Init filter

     Args:
         self: (todo): write your description
         model: (todo): write your description
         parent: (todo): write your description
     """
		super(ComboFilterModel, self).__init__(model, parent)
		self.requires = []
		self.filterRequiresAll = False
		self.filterRequiresAny = False
		self.filterRequiresOnly = False

		self.filterShapes = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
     """
     Filters out the row.

     Args:
         self: (todo): write your description
         sourceRow: (str): write your description
         sourceParent: (todo): write your description
     """
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
	''' Hide single shapes under a slider '''
	def __init__(self, model, parent=None):
     """
     Initialize the filter.

     Args:
         self: (todo): write your description
         model: (todo): write your description
         parent: (todo): write your description
     """
		super(TraversalFilterModel, self).__init__(model, parent)
		self.doFilter = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
     """
     Filters the given row.

     Args:
         self: (todo): write your description
         sourceRow: (str): write your description
         sourceParent: (todo): write your description
     """
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
	''' A model for displaying Group objects that contain Sliders '''
	def __init__(self, simplex, parent):
     """
     Initialize simulation.

     Args:
         self: (todo): write your description
         simplex: (todo): write your description
         parent: (todo): write your description
     """
		super(SliderGroupModel, self).__init__(parent)
		self.simplex = simplex
		self.simplex.models.append(self)

	def getItemRow(self, item):
     """
     Returns the item at the item.

     Args:
         self: (todo): write your description
         item: (str): write your description
     """
		try:
			idx = self.simplex.sliderGroups.index(item)
		except ValueError:
			return None
		return idx + 1

	def getItemAppendRow(self, item):
     """
     Returns the number of rows in item.

     Args:
         self: (todo): write your description
         item: (str): write your description
     """
		return len(self.simplex.sliderGroups) + 1

	def index(self, row, column=0, parIndex=QModelIndex()):
     """
     Return the index at the given column.

     Args:
         self: (todo): write your description
         row: (int): write your description
         column: (str): write your description
         parIndex: (int): write your description
         QModelIndex: (todo): write your description
     """
		if row <= 0:
			return self.createIndex(row, column, None)
		try:
			falloff = self.simplex.sliderGroups[row-1]
		except IndexError:
			return QModelIndex()
		return self.createIndex(row, column, falloff)

	def parent(self, index):
     """
     Returns the parent of the given index.

     Args:
         self: (todo): write your description
         index: (int): write your description
     """
		return QModelIndex()

	def rowCount(self, parent):
     """
     Return the number of rows in the given parent.

     Args:
         self: (todo): write your description
         parent: (todo): write your description
     """
		return len(self.simplex.sliderGroups) + 1

	def columnCount(self, parent):
     """
     Return the number of columns under parent.

     Args:
         self: (todo): write your description
         parent: (todo): write your description
     """
		return 1

	def data(self, index, role):
     """
     Return the data for the item at index

     Args:
         self: (todo): write your description
         index: (todo): write your description
         role: (str): write your description
     """
		if not index.isValid():
			return None
		group = index.internalPointer()
		if group and role in (Qt.DisplayRole, Qt.EditRole):
			return group.name
		return None

	def flags(self, index):
     """
     Returns the item flags for the given index.

     Args:
         self: (todo): write your description
         index: (todo): write your description
     """
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable

	def itemFromIndex(self, index):
     """
     Return the item at the given index.

     Args:
         self: (todo): write your description
         index: (todo): write your description
     """
		return index.internalPointer()


class FalloffModel(ContextModel):
	''' A model for displaying Falloff objects connected to Sliders '''
	def __init__(self, simplex, parent):
     """
     Initialize simulation.

     Args:
         self: (todo): write your description
         simplex: (todo): write your description
         parent: (todo): write your description
     """
		super(FalloffModel, self).__init__(parent)
		self.simplex = simplex
		if self.simplex is not None:
			self.simplex.falloffModels.append(self)
		self.sliders = []
		self._checks = {}
		self.line = ""

	def setSliders(self, sliders):
     """
     Set the providers.

     Args:
         self: (todo): write your description
         sliders: (str): write your description
     """
		self.beginResetModel()
		self.sliders = sliders
		self._checks = {}
		for slider in self.sliders:
			for fo in slider.prog.falloffs:
				self._checks.setdefault(fo, []).append(slider)
		self.endResetModel()
		self.buildLine()

	def buildLine(self):
     """
     Builds the line for this function.

     Args:
         self: (todo): write your description
     """
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
     """
     Return the first row of item.

     Args:
         self: (todo): write your description
         item: (str): write your description
     """
		try:
			idx = self.simplex.falloffs.index(item)
		except ValueError:
			return None
		except AttributeError:
			return None
		return idx + 1

	def getItemAppendRow(self, item):
     """
     Return the first row of the item.

     Args:
         self: (todo): write your description
         item: (str): write your description
     """
		try:
			return len(self.simplex.falloffs)
		except AttributeError:
			return 0

	def index(self, row, column=0, parIndex=QModelIndex()):
     """
     Return the index of the given row.

     Args:
         self: (todo): write your description
         row: (int): write your description
         column: (str): write your description
         parIndex: (int): write your description
         QModelIndex: (todo): write your description
     """
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
     """
     Returns the parent of the given index.

     Args:
         self: (todo): write your description
         index: (int): write your description
     """
		return QModelIndex()

	def rowCount(self, parent):
     """
     Return the number of rows in the parent.

     Args:
         self: (todo): write your description
         parent: (todo): write your description
     """
		try:
			return len(self.simplex.falloffs) + 1
		except AttributeError:
			return 0

	def columnCount(self, parent):
     """
     Return the number of columns under parent.

     Args:
         self: (todo): write your description
         parent: (todo): write your description
     """
		return 1

	def _getCheckState(self, fo):
     """
     Returns the checked checked state

     Args:
         self: (todo): write your description
         fo: (todo): write your description
     """
		sli = self._checks.get(fo, [])
		if len(sli) == len(self.sliders):
			return Qt.Checked
		elif len(sli) == 0:
			return Qt.Unchecked
		return Qt.PartiallyChecked

	def data(self, index, role):
     """
     Return the data for the item at index

     Args:
         self: (todo): write your description
         index: (todo): write your description
         role: (str): write your description
     """
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
     """
     Set the data for the : meth.

     Args:
         self: (todo): write your description
         index: (todo): write your description
         value: (todo): write your description
         role: (str): write your description
     """
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
			self.emitDataChanged(index)
			return True
		return False

	def flags(self, index):
     """
     Return the item flags for the given index

     Args:
         self: (todo): write your description
         index: (todo): write your description
     """
		return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsUserCheckable

	def itemFromIndex(self, index):
     """
     Return the item at the given index.

     Args:
         self: (todo): write your description
         index: (todo): write your description
     """
		return index.internalPointer()


class FalloffDataModel(ContextModel):
	''' A model for displaying the data of Falloff objects '''
	def __init__(self, simplex, parent):
     """
     Initialize a simulation.

     Args:
         self: (todo): write your description
         simplex: (todo): write your description
         parent: (todo): write your description
     """
		super(FalloffDataModel, self).__init__(parent)
		self.simplex = simplex
		if self.simplex is not None:
			self.simplex.falloffModels.append(self)

	def getItemAppendRow(self, item):
     """
     Return the first row of the item.

     Args:
         self: (todo): write your description
         item: (str): write your description
     """
		try:
			return len(self.simplex.falloffs)
		except AttributeError:
			return 0

	def index(self, row, column=0, parIndex=QModelIndex()):
     """
     Return the index of the given row

     Args:
         self: (todo): write your description
         row: (int): write your description
         column: (str): write your description
         parIndex: (int): write your description
         QModelIndex: (todo): write your description
     """
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
     """
     Returns the parent of the given index.

     Args:
         self: (todo): write your description
         index: (int): write your description
     """
		return QModelIndex()

	def rowCount(self, parent):
     """
     Return the number of rows under parent.

     Args:
         self: (todo): write your description
         parent: (todo): write your description
     """
		try:
			return len(self.simplex.falloffs)
		except AttributeError:
			return 0

	def columnCount(self, parent):
     """
     Return the number of columns in parent.

     Args:
         self: (todo): write your description
         parent: (todo): write your description
     """
		return 8

	def data(self, index, role):
     """
     Return the data for the item at index

     Args:
         self: (todo): write your description
         index: (todo): write your description
         role: (str): write your description
     """
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
     """
     Sets the data for the item at index to value

     Args:
         self: (todo): write your description
         index: (todo): write your description
         value: (todo): write your description
         role: (str): write your description
     """
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
					value = ('planar', 'map')[value]
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
     """
     Gets the item flags

     Args:
         self: (todo): write your description
         index: (todo): write your description
     """
		return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable

	def itemFromIndex(self, index):
     """
     Return the item at the given index.

     Args:
         self: (todo): write your description
         index: (todo): write your description
     """
		return index.internalPointer()

	def getItemRow(self, item):
     """
     Return the row at the given item.

     Args:
         self: (todo): write your description
         item: (str): write your description
     """
		try:
			idx = self.simplex.falloffs.index(item)
		except ValueError:
			return None
		except AttributeError:
			return None
		return idx

