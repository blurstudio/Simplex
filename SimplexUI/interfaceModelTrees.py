
import copy
from functools import wraps
from fnmatch import fnmatchcase
import weakref

# This module imports QT from PyQt4, PySide or PySide2
# Depending on what's available

from Qt.QtCore import Qt, QModelIndex, QItemSelection
from Qt.QtWidgets import QTreeView, QApplication

from dragFilter import DragFilter
from utils import singleShot


class SimplexTree(QTreeView):
	''' Abstract base tree for concrete trees '''
	def __init__(self, parent):
		super(SimplexTree, self).__init__(parent)

		self.expandModifier = Qt.ControlModifier

		self._menu = None
		self._drag = None
		self.makeConnections()

	def makeConnections(self):
		''' Build the basic qt signal/slot connections '''
		self.expanded.connect(self.expandTree)
		self.collapsed.connect(self.collapseTree)

		dragFilter = DragFilter(self.viewport())
		self._drag = weakref.ref(dragFilter)
		self.viewport().installEventFilter(dragFilter)

		dragFilter.dragPressed.connect(self.dragStart)
		dragFilter.dragReleased.connect(self.dragStop)
		dragFilter.dragTick.connect(self.dragTick)

		self.setColumnWidth(1, 50)
		self.setColumnWidth(2, 20)

	def unifySelection(self):
		''' Clear the selection if no modifiers are being held '''
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
		''' Update the filter model to show/hide single shapes '''
		model = self.model()
		model.filterShapes = check
		model.invalidateFilter()

	def stringFilter(self, filterString):
		''' Update the filter model with a filter string '''
		model = self.model()
		model.filterString = str(filterString)
		model.invalidateFilter()

	def isolate(self, sliderNames):
		''' Update the filter model with a whitelist of names '''
		model = self.model()
		model.isolateList = sliderNames
		model.invalidateFilter()

	def isolateSelected(self):
		''' Isolate the selected items '''
		items = self.getSelectedItems()
		isoList = [i.name for i in items]
		self.isolate(isoList)
		#self.uiSliderExitIsolateBTN.show()

	def exitIsolate(self):
		''' Remove all items from isolation '''
		self.isolate([])
		#self.uiSliderExitIsolateBTN.hide()


	# Tree expansion/collapse code
	def expandTree(self, index):
		''' Expand all items under index '''
		self.toggleTree(index, True)

	def collapseTree(self, index):
		''' Collapse all items under index '''
		self.toggleTree(index, False)

	def resizeColumns(self):
		''' Resize all columns to their contents "smartly" '''
		model = self.model()
		for i in xrange(model.columnCount()-1):
			oldcw = self.columnWidth(i)
			self.resizeColumnToContents(i)
			newcw = self.columnWidth(i) + 10
			self.setColumnWidth(i, max(oldcw, newcw, 30))
		self.setColumnWidth(model.columnCount()-1, 5)

	def toggleTree(self, index, expand):
		''' Expand or collapse an entire sub-tree of an index '''
		# Separate function to deal with filtering capability
		if not index.isValid():
			return

		model = self.model()
		mods = QApplication.keyboardModifiers()
		thing = model.itemFromIndex(index)
		thing.expanded[id(self)] = expand

		if mods & self.expandModifier:
			queue = [index]
			self.blockSignals(True)
			try:
				while queue:
					idx = queue.pop()
					thing = model.itemFromIndex(idx)
					#print "THING", thing
					thing.expanded[id(self)] = expand
					self.setExpanded(idx, expand)
					for i in xrange(model.rowCount(idx)):
						child = model.index(i, 0, idx)
						if child and child.isValid():
							queue.append(child)
			finally:
				self.blockSignals(False)

		if expand:
			self.resizeColumns()

	def expandTo(self, item):
		''' Make sure that all parents leading to `item` are expanded '''
		model = self.model()
		index = model.indexFromItem(item)
		while index and index.isValid():
			self.setExpanded(index, True)
			thing = model.itemFromIndex(index)
			thing.expanded[id(self)] = True
			index = index.parent()
		self.resizeColumns()

	def storeExpansion(self):
		''' Store the expansion state of the tree for the undo stack'''
		queue = [QModelIndex()]
		model = self.model()
		while queue:
			index = queue.pop()
			item = model.itemFromIndex(index)
			item.expanded[id(self)] = self.isExpanded(index)
			for row in xrange(item.rowCount()):
				queue.append(model.index(row, 0, index))

	def setItemExpansion(self):
		''' Part of the data put into the undo state graph is
		the expansion of the individual items in the graph
		Load those expansions onto the tree
		'''
		queue = [QModelIndex()]
		model = self.model()
		self.blockSignals(True)
		try:
			while queue:
				index = queue.pop()
				item = model.itemFromIndex(index)
				exp = item.expanded.get(id(self), False)
				self.setExpanded(index, exp)
				for row in xrange(item.rowCount()):
					queue.append(model.index(row, 0, index))
		finally:
			self.blockSignals(False)

	def dragTick(self, ticks, mul):
		''' Deal with the ticks coming from the drag handler '''
		selModel = self.selectionModel()
		if not selModel:
			return
		selIdxs = selModel.selectedIndexes()
		selIdxs = [i for i in selIdxs if i.column() == 0]
		model = self.model()
		for idx in selIdxs:
			item = model.itemFromIndex(idx)
			if hasattr(item, 'value'):
				val = item.value
				val += (0.05) * ticks * mul
				if abs(val) < 1.0e-5:
					val = 0.0
				val = max(min(val, item.maxValue), item.minValue)
				item.value = val
		self.viewport().update()

	def dragStart(self):
		''' Open a top-level undo bead for dragging '''
		try:
			self.model().simplex.DCC.undoOpen()
		except AttributeError:
			pass

	def dragStop(self):
		''' Close the undo bead when done dragging '''
		try:
			self.model().simplex.DCC.undoClose()
		except AttributeError:
			pass

	# Menus and Actions
	def connectMenus(self):
		''' Setup the QT signal/slot connections to the context menus '''
		self.setContextMenuPolicy(Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.openMenu)

	# Selection
	def getSelectedItems(self, typ=None):
		''' Get the selected tree items '''
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
		''' Get selected indexes for either the filtered
		or unfiltered models
		'''
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
		''' Set the selection based on a list of items '''
		model = self.model()
		idxs = [model.indexFromItem(i) for i in items]
		idxs = [i for i in idxs if i and i.isValid()]

		toSel = QItemSelection()	
		for idx in idxs:
			toSel.merge(QItemSelection(idx, idx))

		selModel = self.selectionModel()
		selModel.select(toSel, QItemSelection.ClearAndSelect)


# Currently, there's no difference between these two
# Later on, though, they may be different
class SliderTree(SimplexTree):
	pass

class ComboTree(SimplexTree):
	pass


