''' Build the slider/combo tree widgets for use in the Simplex ui '''
# Ignore a bunch of linter errors that show up because of my choice of abstraction
#pylint: disable=too-few-public-methods,superfluous-parens,too-many-ancestors,unused-import
#pylint: disable=unused-variable,unused-argument,too-many-public-methods,too-many-lines
#pylint: disable=protected-access,too-many-statements,invalid-name,no-self-use,relative-import
#pylint: disable=too-many-instance-attributes,too-many-branches

import copy
from functools import wraps
from fnmatch import fnmatchcase
import weakref

# This module imports QT from PyQt4, PySide or PySide2
# Depending on what's available
from loadUiType import (Slot, Qt, QObject, QTimer, QTreeView, QApplication,
						QItemSelection, QStandardItemModel, QStandardItem, QModelIndex,
						QMessageBox, loadUiType, toPyObject, QMenu, QSortFilterProxyModel)

from constants import (PRECISION, COLUMNCOUNT, THING_ROLE, VALUE_ROLE, WEIGHT_ROLE,
					   TYPE_ROLE, PARENT_ROLE, THING_NAME_COL, SLIDER_VALUE_COL,
					   SHAPE_WEIGHT_COL, S_SHAPE_TYPE, S_SLIDER_TYPE, S_GROUP_TYPE, S_COMBO_TYPE,
					   S_SYSTEM_TYPE, C_SHAPE_TYPE, C_SHAPE_PAR_TYPE, C_SLIDER_TYPE,
					   C_SLIDER_PAR_TYPE, C_COMBO_TYPE, C_GROUP_TYPE, C_SYSTEM_TYPE,
					  )

from dragFilter import DragFilter
from interfaceModel import (Shape, Group, Falloff, ProgPair, Progression,
							Slider, ComboPair, Combo, Simplex, SimplexModel) 



class SimplexFilterModel(QSortFilterProxyModel):
	''' A base proxy model for setting up filtering on the concrete trees '''
	def __init__(self, parent=None):
		super(SimplexFilterModel, self).__init__(parent)
		self.filterString = ""
		self.isolateList = []

	def filterAcceptsRow(self, sourceRow, sourceParent):
		''' Return "True" if the row should be shown '''
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			if self.filterString or self.isolateList:
				data = toPyObject(self.sourceModel().data(sourceIndex, THING_ROLE))
				if isinstance(data, (ProgPair, Slider, Combo)):
					sourceItem = self.sourceModel().itemFromIndex(sourceIndex)
					if not self.checkChildren(sourceItem):
						return False

		return super(SimplexFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)

	def checkChildren(self, sourceItem):
		''' Recursively check the children of this object.
		If any child matches the filter, then this object should be shown
		'''
		itemString = str(toPyObject(sourceItem.data(Qt.DisplayRole)))

		if self.isolateList:
			if itemString in self.isolateList:
				if self.filterString:
					if fnmatchcase(itemString, "*{0}*".format(self.filterString)):
						return True
				else:
					return True
		elif fnmatchcase(itemString, "*{0}*".format(self.filterString)):
			return True

		if sourceItem.hasChildren():
			for row in xrange(sourceItem.rowCount()):
				if self.checkChildren(sourceItem.child(row, 0)):
					return True
		return False

class ComboFilterModel(SimplexFilterModel):
	""" Filter by slider when Show Dependent Combos is checked """
	def __init__(self, parent=None):
		super(ComboFilterModel, self).__init__(parent)
		self.requires = []
		self.filterRequiresAll = False
		self.filterRequiresAny = False
		self.filterShapes = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			data = toPyObject(self.sourceModel().data(sourceIndex, THING_ROLE))
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
			if (self.filterRequiresAny or self.filterRequiresAll) and self.requires:
				# Ignore items that don't use the required sliders if requested
				if isinstance(data, Combo):
					sliders = [i.slider for i in data.pairs]
					if self.filterRequiresAll:
						if not all(r in sliders for r in self.requires):
							return False
					elif self.filterRequiresAny:
						if not any(r in sliders for r in self.requires):
							return False
		return super(ComboFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)

class SliderFilterModel(SimplexFilterModel):
	""" Hide single shapes under a slider """
	def __init__(self, parent=None):
		super(SliderFilterModel, self).__init__(parent)
		self.doFilter = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			if self.doFilter:
				data = toPyObject(self.sourceModel().data(sourceIndex, THING_ROLE))
				if isinstance(data, ProgPair):
					if len(data.prog.pairs) <= 2:
						return False
					elif data.shape.isRest:
						return False

		return super(SliderFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)




class SimplexTree(QTreeView):
	''' Abstract base tree for concrete trees '''
	def __init__(self, simplex, parent):
		super(SimplexTree, self).__init__(parent)
		self._drag = None
		self.simplex = simplex

		self.expanded.connect(self.expandTree)
		self.collapsed.connect(self.collapseTree)

		dragFilter = DragFilter(self.viewport())
		self._drag = weakref.ref(dragFilter)
		self.viewport().installEventFilter(dragFilter)

		dragFilter.dragPressed.connect(self.dragStart)
		dragFilter.dragReleased.connect(self.dragStop)
		dragFilter.dragTick.connect(self.dragTick)

		model = SimplexModel(self.simplex, "Slider", self)
		proxyModel = SliderFilterModel(self)
		proxyModel.setSourceModel(model)
		self.setModel(proxyModel)

		self.setColumnWidth(1, 50)
		self.setColumnWidth(2, 20)


	def hideRedundant(self, check):
		''' Update the filter model to show/hide single shapes '''
		model = self.model()
		model.filterShapes = check
		model.invalidateFilter()

	def stringFilter(self, filterString):
		''' Update the filter model with a filter string '''
		model = self.model()
		model.filterString = str(filterString)
		model.invalidateFilter()

	def isolate(self, names):
		''' Update the filter model with a whitelist of names '''
		model = self.model()
		model.isolateList = names
		model.invalidateFilter()

	def isolateSelected(self):
		''' Isolate the selected items '''
		items = self.getSelectedItems()
		isoList = []
		for item in items:
			isoList.append(str(toPyObject(item.data(Qt.DisplayRole))))
		self.isolate(isoList)

	def exitIsolate(self):
		''' Remove all items from isolation '''
		self.isolate([])

	def resizeColumns(self):
		''' Resize all columns to their contents "smartly" '''
		model = self.model()
		for i in xrange(model.columnCount()-1):
			oldcw = self.columnWidth(i)
			self.resizeColumnToContents(i)
			newcw = self.columnWidth(i) + 10
			self.setColumnWidth(i, max(oldcw, newcw, 30))
		self.setColumnWidth(model.columnCount()-1, 5)

	# Tree expansion/collapse code
	def expandTree(self, index):
		''' Expand all items under index '''
		self.toggleTree(index, True)

	def collapseTree(self, index):
		''' Collapse all items under index '''
		self.toggleTree(index, False)

	def toggleTree(self, index, expand):
		''' Expand or collapse an entire sub-tree of an index '''
		# Separate function to deal with filtering capability
		if not index.isValid():
			return

		filterModel = self.model()
		model = filterModel.sourceModel()
		mods = QApplication.keyboardModifiers()
		clickItem = model.itemFromIndex(filterModel.mapToSource(index))

		thing = toPyObject(clickItem.data(THING_ROLE))
		try:
			thing.expanded = expand
		except AttributeError:
			pass

		if mods & Qt.ControlModifier:
			queue = [clickItem]
			self.blockSignals(True)
			try:
				while queue:
					item = queue.pop()
					thing = toPyObject(item.data(THING_ROLE))
					thing.expanded = expand
					self.setExpanded(filterModel.mapFromSource(item.index()), expand)
					for i in xrange(item.rowCount()):
						child = item.child(i, 0)
						if child:
							queue.append(child)
			finally:
				self.blockSignals(False)

		if expand:
			self.resizeColumns()

	def expandTo(self, item):
		''' Make sure that all parents leading to `item` are expanded '''
		model = self.model()
		index = model.mapFromSource(item.index())

		while index:
			self.setExpanded(index, True)
			thing = toPyObject(model.data(index, THING_ROLE))
			thing.expanded = True
			index = index.parent()
			if not index or not index.isValid():
				break
		self.resizeColumns()

	def storeExpansion(self):
		''' Store the expansion state of the tree for the undo stack'''
		queue = [self.getTreeRoot()]
		model = self.model()
		while queue:
			item = queue.pop()
			thing = toPyObject(item.data(THING_ROLE))
			index = model.mapFromSource(item.index())
			thing.expanded = self.isExpanded(index)

			if isinstance(thing, Simplex): # TODO: Figure out a cleaner way to do this
				setattr(thing, self.expName, self.isExpanded(index))

			for row in xrange(item.rowCount()):
				queue.append(item.child(row, 0))

	def setItemExpansion(self):
		''' Part of the data put into the undo state graph is
		the expansion of the individual items in the graph
		Load those expansions onto the tree
		'''
		queue = [self.getTreeRoot()]
		model = self.model()
		self.blockSignals(True)
		while queue:
			item = queue.pop()
			thing = toPyObject(item.data(THING_ROLE))
			index = model.mapFromSource(item.index())
			exp = thing.expanded
			if isinstance(thing, Simplex):
				exp = getattr(thing, self.expName)

			self.setExpanded(index, exp)
			for row in xrange(item.rowCount()):
				queue.append(item.child(row, 0))
		self.blockSignals(False)

	def dragTick(self, ticks, mul):
		''' Deal with the ticks coming from the drag handler '''
		sel = self.getSelectedItems()
		dragRole = None
		for item in sel:
			if toPyObject(item.data(VALUE_ROLE)):
				dragRole = VALUE_ROLE
				break
			elif toPyObject(item.data(WEIGHT_ROLE)):
				dragRole = WEIGHT_ROLE

		if dragRole is None:
			return
		model = self.model().sourceModel()
		model.blockSignals(True)
		for item in sel:
			if toPyObject(item.data(dragRole)):
				val = toPyObject(item.data(Qt.EditRole))
				val += (0.05) * ticks * mul
				if abs(val) < 0.00001:
					val = 0.0
				thing = toPyObject(item.data(THING_ROLE))
				val = max(min(val, thing.maxValue), thing.minValue)
				item.setData(val, Qt.EditRole)
				self.updateTickValues((thing, val))
		model.blockSignals(False)

	def dragStart(self):
		''' Open a top-level undo bead for dragging '''
		self.system.DCC.undoOpen()

	def dragStop(self):
		''' Close the undo bead when done dragging '''
		self.system.DCC.undoClose()



	# Menus and Actions
	def connectMenus(self):
		''' Setup the QT signal/slot connections to the context menus '''
		self.setContextMenuPolicy(Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.openMenu)

	def clearTree(self):
		''' Clear all items from the tree '''
		model = self.model().sourceModel()
		topRoot = model.invisibleRootItem()
		model.removeRows(0, 1, topRoot.index())

	def getSelectedIndexes(self, filtered=False):
		''' Get selected indexes for either the filtered
		or unfiltered models
		'''
		selIdxs = self.selectionModel().selectedIndexes()
		if filtered:
			return selIdxs

		filterModel = self.model()
		model = filterModel.sourceModel()
		indexes = []
		for selIdx in selIdxs:
			indexes.append(filterModel.mapToSource(selIdx))
		return indexes



