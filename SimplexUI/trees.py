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

from interface import (Combo, Slider, Progression, ComboPair, ProgPair, undoContext, Simplex)

from constants import (PRECISION, COLUMNCOUNT, THING_ROLE, VALUE_ROLE, WEIGHT_ROLE,
					   TYPE_ROLE, PARENT_ROLE, THING_NAME_COL, SLIDER_VALUE_COL,
					   SHAPE_WEIGHT_COL, S_SHAPE_TYPE, S_SLIDER_TYPE, S_GROUP_TYPE, S_COMBO_TYPE,
					   S_SYSTEM_TYPE, C_SHAPE_TYPE, C_SHAPE_PAR_TYPE, C_SLIDER_TYPE,
					   C_SLIDER_PAR_TYPE, C_COMBO_TYPE, C_GROUP_TYPE, C_SYSTEM_TYPE,
					  )

from dragFilter import DragFilter


# If the decorated method is a slot for some Qt Signal
# and the method signature is *NOT* the same as the
# signal signature, you must double decorate the method like:
#
# @Slot(**signature)
# @stackable
# def method(**signature)

def stackable(method):
	'''
	A Decorator that handles building DCC undo contexts,
	and keeps track of the undo stack for Simplex
	'''
	@wraps(method)
	def stacked(self, *data, **kwdata):
		''' The undo stack worker function '''
		with undoContext():
			ret = None
			self.system.stack.depth += 1
			ret = method(self, *data, **kwdata)
			self.system.stack.depth -= 1

			if self.system.stack.depth == 0:
				srevision = self.system.incrementRevision()
				scopy = copy.deepcopy(self.system.simplex)
				self.system.stack[srevision] = (scopy, self.system, None, [], {})
			return ret
	return stacked

class singleShot(QObject):
	""" Decorator class used to implement a QTimer.singleShot(0, function)

	This is useful so your refresh function only gets called once even if
	its connected to a signal that gets emitted several times at once.

	Note:
		The values passed to the decorated method will be accumulated
		and run all at once, then reset for the next go-round

	From the Qt Docs:
		As a special case, a QTimer with a timeout of 0 will time out as
		soon as all the events in the window system's event queue have
		been processed. This can be used to do heavy work while providing
		a snappy user interface
	"""
	def __init__(self):
		super(singleShot, self).__init__()
		self._function = None
		self._callScheduled = False
		self._args = []
		self._inst = None

	def __call__(self, function):
		self._function = function
		def newFunction(inst, *args):
			''' Single Shot worker function '''
			self._args.extend(args)
			if not self._callScheduled:
				self._inst = inst
				self._callScheduled = True
				QTimer.singleShot(0, self.callback)
		newFunction.__name__ = function.__name__
		newFunction.__doc__ = function.__doc__
		return newFunction

	def callback(self):
		""" Calls the decorated function and resets singleShot for the next group of calls
		"""
		self._callScheduled = False
		# self._args needs to be cleared before we call self._function
		args = self._args
		inst = self._inst
		self._inst = None
		self._args = []
		self._function(inst, args)

class SliderContextMenu(QMenu):
	''' Right-click menu for the Slider tree '''
	def __init__(self, parent=None):
		super(SliderContextMenu, self).__init__(parent)

		self.uiAddGroupACT = self.addAction("Add Group")
		self.uiAddSliderACT = self.addAction("Add Slider")
		self.uiAddShapeACT = self.addAction("Add Shape")

		self.addSeparator()

		self.uiComboActiveACT = self.addAction("Combo Active")
		self.uiComboSelectedACT = self.addAction("Combo Selected")

		self.addSeparator()

		self.uiDeleteACT = self.addAction("Delete Selected")

		self.addSeparator()

		self.uiZeroACT = self.addAction("Zero Selected")
		self.uiZeroAllACT = self.addAction("Zero All")

		self.addSeparator()

		self.uiExtractShapeACT = self.addAction("Extract Shape")
		self.uiConnectShapeACT = self.addAction("Connect Shape")
		self.uiMatchShapeACT = self.addAction("Match Shape")
		self.uiClearShapeACT = self.addAction("Clear Shape")

		self.addSeparator()

		self.uiIsolateSelectedACT = self.addAction("Isolate Selected")
		self.uiExitIsolationACT = self.addAction("Exit Isolation")

class ComboContextMenu(QMenu):
	''' Right-click menu for the Combo tree '''
	def __init__(self, parent=None):
		super(ComboContextMenu, self).__init__(parent)

		self.uiAddGroupACT = self.addAction("Add Group")
		self.uiAddShapeACT = self.addAction("Add Shape")

		self.addSeparator()

		self.uiDeleteACT = self.addAction("Delete Selected")

		self.addSeparator()

		self.uiSetValsACT = self.addAction("Set Selected Values")

		self.addSeparator()

		self.uiExtractShapeACT = self.addAction("Extract Shape")
		self.uiConnectShapeACT = self.addAction("Connect Shape")
		self.uiMatchShapeACT = self.addAction("Match Shape")
		self.uiClearShapeACT = self.addAction("Clear Shape")

		self.addSeparator()

		self.uiIsolateSelectedACT = self.addAction("Isolate Selected")
		self.uiExitIsolationACT = self.addAction("Exit Isolation")



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
	def __init__(self, parent):
		super(SimplexTree, self).__init__(parent)
		self._itemMap = {}
		self._menu = None
		self._drag = None
		self.system = None
		self.makeConnections()

	def setSystem(self, system):
		''' Set the underlying simplex system for the current tree '''
		self.system = system

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

		model = QStandardItemModel(self)
		model.setColumnCount(3)
		model.itemChanged.connect(self.treeItemChanged)
		proxyModel = self.filterModel(self)
		proxyModel.setSourceModel(model)
		self.setModel(proxyModel)

		self.setColumnWidth(1, 50)
		self.setColumnWidth(2, 20)
		model.setHorizontalHeaderLabels(["Items", "Slide", "Value"])

	def unifySelection(self):
		''' Clear the selection if no modifiers are being held '''
		mods = QApplication.keyboardModifiers()
		if not (mods & (Qt.ControlModifier | Qt.ShiftModifier)):
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
		isoList = []
		for item in items:
			isoList.append(str(toPyObject(item.data(Qt.DisplayRole))))
		self.isolate(isoList)
		#self.uiSliderExitIsolateBTN.show()

	def exitIsolate(self):
		''' Remove all items from isolation '''
		self.isolate([])
		#self.uiSliderExitIsolateBTN.hide()

	# Shape and combo Extraction and connection
	def getFilteredChildSelection(self, role):
		''' Get a list of shape indices of a specific role
		Selections containing parents of the role fall down to their children
		Selections containing children of the role climb up to their parents
		'''
		selIdxs = self.getSelectedIndexes(filtered=True)
		selIdxs = [i for i in selIdxs if i.column() == 0]
		typDict = {}
		for idx in selIdxs:
			typ = toPyObject(idx.model().data(idx, TYPE_ROLE))
			if typ is not None:
				typDict.setdefault(typ, []).append(idx)

		shapeIdxs = []
		for typ in sorted(typDict.keys()):
			idxs = typDict[typ]
			if typ > role:
				ext = [self.searchParentsForTypeIndex(idx, role) for idx in idxs]
				shapeIdxs.extend(ext)
			elif typ == role:
				shapeIdxs.extend(idxs) # It's a proper selection, easy peasy
			elif typ < role:
				if typ < self.baseType:
					# if the parent is above the filtering baseType for the tree
					# search filtered down to that cutoff
					filtSearch = []
					for idx in idxs:
						filtSearch.extend(self.searchTreeForTypeIndex(self.baseType, idx, filtered=True))
				else:
					filtSearch = idxs
				# Then search unfiltered past the cutoff
				unfiltSearch = [i.model().mapToSource(i) for i in filtSearch]
				for idx in unfiltSearch:
					shapeIdxs.extend(self.searchTreeForTypeIndex(role, idx, filtered=False))
		shapeIdxs = list(set(shapeIdxs)) #TODO Possibly reorder by system list
		return shapeIdxs

	def shapeConnect(self):
		''' Gather indexes for shapes to connect '''
		indexes = self.getSelectedIndexes(filtered=False)
		indexes = [i for i in indexes if i.column() == 0]
		shapes = []
		for i in indexes:
			ss = self.searchTreeForTypeIndex(self.baseType, parIdx=i, filtered=False)
			shapes.extend(ss)
		self.connectIndexes(shapes)

	def shapeClear(self):
		''' Set the current shape to be equal to the rest shape'''
		shapeIndexes = self.getFilteredChildSelection(S_SHAPE_TYPE)
		model = self.model()
		for si in shapeIndexes:
			progPair = toPyObject(model.data(si, THING_ROLE))
			if not progPair.shape.isRest:
				self.system.zeroShape(progPair.shape)

	def setSelectedGroup(self, group):
		''' Set the parent of the selected items to the passed groupItem '''
		groupItems = self._itemMap[group]
		groupItem = groupItems[0]

		selItems = self.getSelectedItems()
		selItems = self.filterItemsByType(selItems, self.baseType)
		self.setItemsGroup(selItems, groupItem)

	@stackable
	def setItemsGroup(self, items, groupItem):
		''' Set the parent groupItem for a list of other items '''
		group = toPyObject(groupItem.data(THING_ROLE))
		things = []
		groups = []
		for item in items:
			thing = toPyObject(item.data(THING_ROLE))
			if not isinstance(thing, self.coreType):
				continue
			things.append(thing)
			groups.append(group)
			par = item.parent()
			row = par.takeRow(item.row())
			groupItem.appendRow(row)

		self.system.setSlidersGroups(things, groups)


	@stackable
	def treeItemChanged(self, item):
		''' Handle a tree item changing
		Depending on its value, weight, and type update the
		underlying simplex system to reflect the changes
		'''
		v = toPyObject(item.data(VALUE_ROLE))
		w = toPyObject(item.data(WEIGHT_ROLE))
		if v or w:
			thing = toPyObject(item.data(THING_ROLE))
			value = toPyObject(item.data(Qt.EditRole))
			if isinstance(thing, Slider):
				self.system.setSlidersWeights([thing], [value])
			elif isinstance(thing, ProgPair):
				self.system.setShapesValues([thing], [value])
				if isinstance(thing.prog.parent, Slider):
					self.updateSliderRange(thing.prog.parent)
		else:
			t = toPyObject(item.data(TYPE_ROLE))
			thing = toPyObject(item.data(THING_ROLE))
			disp = str(toPyObject(item.data(Qt.DisplayRole)))
			if thing is None:
				return

			if t == self.shapeType:
				nn = self.getNextName(disp, [i.name for i in self.system.simplex.shapes])
				if thing.shape.name != nn:
					self.system.renameShape(thing.shape, nn)
					self.updateLinkedItems(thing)

			elif t == self.sliderType:
				nn = self.getNextName(disp, [i.name for i in self.system.simplex.sliders])
				if thing.name != nn:
					self.system.renameSlider(thing, nn)
					self.updateLinkedItems(thing)

			elif t == self.groupType:
				nn = self.getNextName(disp, [i.name for i in self.system.simplex.groups])
				if thing.name != nn:
					self.system.renameGroup(thing, nn)
					self.updateLinkedItems(thing)

			elif t == self.comboType:
				nn = self.getNextName(disp, [i.name for i in self.system.simplex.combos])
				if thing.name != nn:
					self.system.renameCombo(thing, nn)
					self.updateLinkedItems(thing)

	def _getDeleteItems(self):
		# Sort selected items by type, then only delete
		# the topmost type in the hierarchy
		# This protects against double-deleting
		sel = self.getSelectedItems()
		seps = {}
		for item in sel:
			if item.column() == 0:
				typ = toPyObject(item.data(TYPE_ROLE))
				if typ is not None:
					seps.setdefault(typ, []).append(item)
		if not seps:
			return []

		parkey = min(seps.iterkeys()) # gets the highest level selection
		delItems = sorted(seps[parkey], key=lambda x: x.row(), reverse=True)
		delItems = [i for i in delItems if i.column() == 0]
		return delItems

	def _deleteTreeItems(self, items):
		# removes these items from their UI tree
		for item in items:
			par = item.parent()
			par.takeRow(item.row())

	def _deleteGroupItems(self, items):
		# If I'm deleting a slider group, make sure
		# to delete the combos with it
		for groupItem in items:
			typ = toPyObject(groupItem.data(TYPE_ROLE))
			if typ == self.groupType:
				sliderItems = []
				for row in xrange(groupItem.rowCount()):
					sliderItems.append(groupItem.child(row, 0))
				doit, comboItems = self._sliderDeleteCheck(sliderItems)
				if not doit:
					return
				self.deleteComboItems(comboItems)

		# Delete the group item from the settings box
		things = []
		for groupItem in items:
			thing = toPyObject(groupItem.data(THING_ROLE))
			things.append(thing)
			for row in xrange(self.uiWeightGroupCBOX.count()):
				if thing == toPyObject(self.uiWeightGroupCBOX.itemData(row)):
					self.uiWeightGroupCBOX.removeItem(row)
					break

		self.system.deleteGroups(things)
		self._deleteTreeItems(items)

	@stackable
	def createGroup(self, name, items=None):
		''' Create a group object in the current tree
		Make any items passed a child of this new group object
		'''
		groupNames = [i.name for i in self.system.simplex.groups]
		newName = self.getNextName(name, groupNames)
		systemGroup = self.system.createGroup(newName)
		root = self.getTreeRoot()
		if self.coreType == Slider:
			groupItem = self.buildSliderGroupItem(root, systemGroup)
		else:
			groupItem = self.buildComboGroupItem(root, systemGroup)

		if items:
			self.setItemsGroup(items, groupItem)

		self.expandTo(groupItem)
		self.buildItemMap()

		return groupItem, systemGroup

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


	@singleShot()
	def updateTickValues(self, updatePairs):
		''' Update all the drag-tick values at once '''
		# Don't make this mouse-tick be stackable. That way
		# we don't update the whole System for a slider value changes
		sliderList = []
		progs = []
		for i in updatePairs:
			if isinstance(i[0], Slider):
				sliderList.append(i)
			elif isinstance(i[0], ProgPair):
				progs.append(i)

		if progs:
			progPairs, values = zip(*progs)
			self.system.setShapesValues(progPairs, values)
			for pp in progPairs:
				if isinstance(pp.prog.parent, Slider):
					self.updateSliderRange(pp.prog.parent)

		if sliderList:
			sliders, values = zip(*sliderList)
			self.system.setSlidersWeights(sliders, values)

		self.viewport().update()

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

	def buildTreeRoot(self, thing):
		''' Build the top level "system" item for this tree '''
		model = self.model().sourceModel()
		topRoot = model.invisibleRootItem()

		topRoot.setFlags(topRoot.flags() ^ Qt.ItemIsDropEnabled)

		root = QStandardItem(thing.name)
		root.setFlags(root.flags() ^ Qt.ItemIsDragEnabled)

		root.setData(self.systemType, TYPE_ROLE)
		root.setData(thing, THING_ROLE)
		topRoot.setChild(0, 0, root)
		return root


	# Selection
	def getSelectedItems(self):
		''' Get the selected tree items '''
		selIdxs = self.selectionModel().selectedIndexes()
		filterModel = self.model()
		model = filterModel.sourceModel()
		items = []
		for selIdx in selIdxs:
			items.append(model.itemFromIndex(filterModel.mapToSource(selIdx)))
		return items

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

	def getTreeRoot(self):
		''' Get the top level "system" item for this tree '''
		model = self.model().sourceModel()
		topRoot = model.invisibleRootItem()
		root = topRoot.child(0, 0)
		return root

	def searchTreeForType(self, role, par=None):
		''' Search down the hierarchy from `par` and collect
		any items with the TYPE_ROLE `role`
		'''
		if par is None:
			par = self.getTreeRoot()
			if par is None:
				return []
		queue = [par]
		ret = []
		while queue:
			item = queue.pop()
			for row in xrange(item.rowCount()):
				queue.append(item.child(row, 0))

			typ = toPyObject(item.data(TYPE_ROLE))
			if typ == role:
				ret.append(item)
		return ret

	def searchParentsForType(self, item, typeRole):
		''' Search up the hierarchy from `item` and collect
		any items with the TYPE_ROLE `role`
		'''
		while True:
			if toPyObject(item.data(TYPE_ROLE)) == typeRole:
				return item
			item = item.parent()
			if not item or not item.index().isValid():
				break
		return QStandardItem()

	# Tree Index Traversal
	def getTreeRootIndex(self, filtered):
		''' Get the root of the filtered
		or unfiltered tree models
		'''
		filterModel = self.model()
		model = filterModel.sourceModel()
		topRoot = model.invisibleRootItem()
		root = topRoot.child(0, 0)
		rootIndex = root.index()
		if filtered and rootIndex.isValid():
			return filterModel.mapFromSource(rootIndex)
		return rootIndex

	def searchTreeForTypeIndex(self, role, parIdx=None, filtered=False):
		''' Search a qt tree rooted at parIdx for items that have
		the TYPE_ROLE 'role'
		'''
		if parIdx is None:
			parIdx = self.getTreeRootIndex(filtered)
			if not parIdx.isValid():
				return []

		queue = [parIdx]
		ret = []
		while queue:
			index = queue.pop()
			if not index.isValid():
				continue
			model = index.model()
			for row in xrange(model.rowCount(index)):
				queue.append(index.child(row, 0))
			typ = toPyObject(model.data(index, TYPE_ROLE))
			if typ == role:
				ret.append(index)
		return ret

	def searchParentsForTypeIndex(self, index, typeRole):
		''' Search up the tree from an index for a specific type '''
		while True:
			if toPyObject(index.model().data(index, TYPE_ROLE)) == typeRole:
				return index
			index = index.parent()
			if not index or not index.isValid():
				break
		return QModelIndex()


	# Utility
	@staticmethod #TODO: Figure out where to actually put this
	def getNextName(name, currentNames):
		''' Get the next available name '''
		i = 0
		s = set(currentNames)
		while True:
			if not i:
				nn = name
			else:
				nn = name + str(i)
			if nn not in s:
				return nn
			i += 1

class SliderTree(SimplexTree):
	''' Concrete tree for dealing with Sliders '''
	systemType = S_SYSTEM_TYPE
	baseType = S_SLIDER_TYPE
	shapeType = S_SHAPE_TYPE
	sliderType = S_SLIDER_TYPE
	groupType = S_GROUP_TYPE
	comboType = S_COMBO_TYPE
	coreType = Slider
	expName = 'sliderExpanded'
	filterModel = SliderFilterModel

	def shapeMatch(self, mesh):
		''' Connect a mesh into the selected shapes '''
		shapeIndexes = self.getFilteredChildSelection(self.shapeType)
		for si in shapeIndexes:
			progPair = toPyObject(si.model().data(si, THING_ROLE))
			if not progPair.shape.isRest:
				self.system.connectShape(progPair.shape, mesh=mesh)

	@Slot()
	@stackable
	def sliderTreeDelete(self):
		''' Delete items in the tree '''
		delItems = self._getDeleteItems()
		typedDelItems = self.partitionItemsByType(delItems)
		for itype, ditems in typedDelItems.iteritems():
			if itype == self.groupType:
				self.deleteSliderGroupItems(ditems)
			elif itype == self.sliderType:
				self.deleteSliderItems(ditems)
			elif itype == self.shapeType:
				self.deleteProgPairItems(ditems)
		self.buildItemMap()

	def deleteGroupItems(self, items):
		''' Delete a group item. Move its children to another group '''
		# Don't delete the last group
		groupItems = self.searchTreeForType(self.groupType)
		if len(groupItems) == 1:
			QMessageBox.warning(self, 'warning', "Cannot delete the last group")
			return
		self._deleteGroupItems(items)

	def deleteSliderItems(self, items):
		''' Delete slider items and any dependent combos '''

		# TODO Connect this to the combo tree
		doit, comboItems = self._sliderDeleteCheck(items)
		if not doit:
			return
		self.deleteComboItems(comboItems)
		things = [toPyObject(i.data(THING_ROLE)) for i in items]
		self.system.deleteSliders(things)
		self._deleteTreeItems(items)

	def deleteProgPairItems(self, items):
		''' Delete a Shape from under a slider '''
		things = [toPyObject(i.data(THING_ROLE)) for i in items]
		sliderThings = [i.prog.parent for i in things]
		self.system.deleteProgPairs(things)
		for slider in sliderThings:
			self.updateSliderRange(slider)
		self._deleteTreeItems(items)

	# Shapes
	def newSliderShape(self):
		''' Create new shape items under the first selected slider '''
		sel = self.getSelectedItems()
		pars = self.filterItemsByType(sel, S_SLIDER_TYPE)
		if not pars:
			return
		parItem = pars[0]
		parThing = toPyObject(parItem.data(THING_ROLE))
		return self.newShape(parItem, parThing)

	def newShape(self, parItem, parThing):
		''' Build a shape item under a parent with default values '''
		if self.coreType == Slider:
			if parThing.value == 0.0:
				vals = [i.value for i in parThing.prog.pairs]
				if 1.0 not in vals:
					tVal = 1.0
				elif -1.0 not in vals:
					tVal = -1.0
				elif 0.5 not in vals:
					tVal = 0.5
				else:
					tVal = -0.5
			else:
				tVal = parThing.value
		else:
			tVal = 1.0
		if abs(tVal) == 1.0:
			newName = parThing.name
		else:
			newName = "{0}_{1}".format(parThing.name, int(abs(tVal)*100))
		self.createShape(newName, tVal, parItem, parThing)

	@stackable
	def createShape(self, name, value, parItem, parThing):
		''' Interface with the DCC and create a shape '''
		prog = parThing.prog

		shapeNames = [i.name for i in self.system.simplex.shapes]
		name = self.getNextName(name, shapeNames)
		thing = self.system.createShape(name, prog, value)

		if self.coreType == Slider:
			shapeItem = self.buildSliderShapeItem(parItem, thing)
			self.updateSliderRange(parThing)
		else:
			shapeItem = self.buildComboShapeItem(parItem, thing)
		self.expandTo(shapeItem)
		self.buildItemMap()

	def createSlider(self, name, parItem):
		''' Create a new slider item with a name '''
		group = toPyObject(parItem.data(THING_ROLE))

		# Build the slider
		slider = self.system.createSlider(name, group)

		# Build the slider tree items
		sliderItem = self.buildSliderSliderTree(parItem, slider)
		self.expandTo(sliderItem)
		self.buildItemMap()

	def pairExpansion(self, oldSimp, newSimp):
		''' Copy the expansion values from 'old' to 'new' based on name '''
		newSimp.comboExpanded = oldSimp.comboExpanded
		newSimp.sliderExpanded = oldSimp.sliderExpanded

		mains = (
			(oldSimp.combos, newSimp.combos),
			(oldSimp.sliders, newSimp.sliders),
			(oldSimp.groups, newSimp.groups),
		)

		for old, new in mains:
			newDict = {i.name: i for i in new}
			oldDict = {i.name: i for i in old}
			keys = set(newDict.keys()) & set(oldDict.keys())
			for key in keys:
				kNew = newDict[key]
				kOld = oldDict[key]
				kNew.expanded = kOld.expanded

				if isinstance(kNew, Combo):
					knpDict = {i.slider.name:i for i in kNew.pairs}
					kopDict = {i.slider.name:i for i in kOld.pairs}
					kkeys = set(knpDict.keys()) & set(kopDict.keys())
					for kk in kkeys:
						knpDict[kk].expadned = kopDict[kk].expanded
						n = knpDict[kk]
						o = knpDict[kk]

					knpDict = {i.shape.name:i for i in kNew.prog.pairs}
					kopDict = {i.shape.name:i for i in kOld.prog.pairs}
					kkeys = set(knpDict.keys()) & set(kopDict.keys())
					for kk in kkeys:
						knpDict[kk].expadned = kopDict[kk].expanded

	def openMenu(self, pos):
		''' Open the slider context menu and connect all the actions'''
		if self._menu is None:
			self._menu = SliderContextMenu(self)

			self._menu.uiAddGroupACT.triggered.connect(self.newSliderGroup)
			self._menu.uiAddSliderACT.triggered.connect(self.newSlider)
			self._menu.uiAddShapeACT.triggered.connect(self.newSliderShape)

			self._menu.uiComboActiveACT.triggered.connect(self.newActiveCombo)
			self._menu.uiComboSelectedACT.triggered.connect(self.newSelectedCombo)

			self._menu.uiDeleteACT.triggered.connect(self.sliderTreeDelete)

			self._menu.uiZeroACT.triggered.connect(self.zeroSelectedSliders)
			self._menu.uiZeroAllACT.triggered.connect(self.zeroAllSliders)

			#self._menu.uiExtractShapeACT.triggered.connect() # extract shape
			#self._menu.uiConnectShapeACT.triggered.connect() # connect shape
			#self._menu.uiMatchShapeACT.triggered.connect() # match shape
			#self._menu.uiClearShapeACT.triggered.connect() # clear shape

			self._menu.uiIsolateSelectedACT.triggered.connect(self.isolateSelected)
			self._menu.uiExitIsolationACT.triggered.connect(self.exitIsolate)

		self._menu.exec_(self.viewport().mapToGlobal(pos))

		return self._menu

	def buildSliderGroupTree(self, parItem, groupThing):
		''' Build a slider tree group item, and all of its children '''
		groupItem = self.buildSliderGroupItem(parItem, groupThing)
		for slider in groupThing.sliders:
			self.buildSliderSliderTree(groupItem, slider)
		return groupItem

	def buildSliderSliderTree(self, parItem, sliderThing):
		''' Build a slider tree slider item, and all of its children '''
		sliderItem = self.buildSliderSliderItem(parItem, sliderThing)

		for pair in sliderThing.prog.pairs:
			self.buildSliderShapeItem(sliderItem, pair)

		self.updateSliderRange(sliderThing)
		return sliderItem

	def buildSliderGroupItem(self, parItem, groupThing):
		''' Build a slider tree group item '''
		grpItem = QStandardItem(groupThing.name)
		grpItem.setData(groupThing, THING_ROLE)
		grpItem.setData(S_GROUP_TYPE, TYPE_ROLE)
		grpItem.setData(S_SYSTEM_TYPE, PARENT_ROLE)
		parItem.appendRow([grpItem, QStandardItem(), QStandardItem()])

		self.uiWeightGroupCBOX.blockSignals(True)
		self.uiWeightGroupCBOX.addItem(groupThing.name, groupThing)
		self.uiWeightGroupCBOX.blockSignals(False)

		return grpItem

	def buildSliderSliderItem(self, parItem, sliderThing):
		''' Build a slider tree slider item '''
		sliderItem = QStandardItem(sliderThing.name)
		sliderItem.setData(sliderThing, THING_ROLE)
		sliderItem.setData(S_SLIDER_TYPE, TYPE_ROLE)
		sliderItem.setData(S_GROUP_TYPE, PARENT_ROLE)

		sliderValueItem = QStandardItem()
		sliderValueItem.setData(float(sliderThing.value), Qt.EditRole)
		sliderValueItem.setData(True, VALUE_ROLE)
		sliderValueItem.setData(sliderThing, THING_ROLE)
		sliderValueItem.setData(S_SLIDER_TYPE, TYPE_ROLE)
		sliderValueItem.setData(S_GROUP_TYPE, PARENT_ROLE)

		parItem.appendRow([sliderItem, sliderValueItem, QStandardItem()])
		return sliderItem

	def buildSliderShapeItem(self, parItem, pairThing):
		''' Build a slider tree shape item '''
		pairItem = QStandardItem(pairThing.shape.name)
		pairItem.setData(pairThing, THING_ROLE)
		pairItem.setData(S_SHAPE_TYPE, TYPE_ROLE)
		pairItem.setData(S_SLIDER_TYPE, PARENT_ROLE)
		pairValueItem = QStandardItem()
		pairValueItem.setData(float(pairThing.value), Qt.EditRole)
		pairValueItem.setData(True, WEIGHT_ROLE)
		pairValueItem.setData(pairThing, THING_ROLE)
		pairValueItem.setData(S_SHAPE_TYPE, TYPE_ROLE)
		pairValueItem.setData(S_SLIDER_TYPE, PARENT_ROLE)

		parItem.appendRow([pairItem, QStandardItem(), pairValueItem])
		return pairItem

class ComboTree(SimplexTree):
	''' Concrete tree for dealing with Combos '''
	systemType = C_SYSTEM_TYPE
	baseType = C_COMBO_TYPE
	shapeType = C_SHAPE_TYPE
	sliderType = C_SLIDER_TYPE
	groupType = C_GROUP_TYPE
	comboType = C_COMBO_TYPE
	coreType = Combo
	expName = 'comboExpanded'
	filterModel = ComboFilterModel

	def shapeMatch(self, mesh):
		''' Connect in a mesh to selected combos '''
		comboIndexes = self.getFilteredChildSelection(self.shapeType)
		for ci in comboIndexes:
			progPair = toPyObject(ci.model().data(ci, THING_ROLE))
			if not progPair.shape.isRest:
				combo = progPair.prog.parent
				self.system.connectComboShape(combo, progPair.shape, mesh=mesh)

	def setComboRequirements(self, dependAll, dependAny):
		''' Set the filter model dependency requirements
		dependAll shows combos that depend on *all* of the selected sliders
		dependAny shows combos that depend on *any* of the selected sliders
		'''
		model = self.model()
		model.filterRequiresAll = False
		model.filterRequiresAny = False
		if dependAll:
			model.filterRequiresAll = True
		elif dependAny:
			model.filterRequiresAny = True
		model.invalidateFilter()

	@Slot()
	@stackable
	def comboTreeDelete(self):
		''' Delete items from the combo tree '''
		delItems = self._getDeleteItems()
		typedDelItems = self.partitionItemsByType(delItems)
		for itype, ditems in typedDelItems.iteritems():
			if itype == self.groupType:
				self.deleteComboGroupItems(ditems)
			elif itype == self.shapeType:
				self.deleteProgPairItems(ditems)
			elif itype == self.baseType:
				self.deleteComboItems(ditems)
			elif itype == self.sliderType:
				self.deleteComboPairItems(ditems)
		self.buildItemMap()

	def deleteGroupItems(self, items):
		''' Groups are handled automatically in the combo tree
		so they can't be deleted
		'''
		QMessageBox.warning(self, 'warning', "Cannot delete depth groups")

	def deleteComboItems(self, items):
		''' Delete any combo items and the shapes underneath '''
		# check if the parent group is empty
		# and if so, delete that group
		groupThings = list(set(toPyObject(i.parent().data(THING_ROLE)) for i in items if i.parent() is not None))
		groupItems = [] # ugh, pyside items/indexes aren't hashable
		for gt in groupThings:
			groupItems.extend(self._comboTreeMap[gt])

		things = [toPyObject(i.data(THING_ROLE)) for i in items]
		self.system.deleteCombos(things)
		self._deleteTreeItems(items)

		groupDel = [i for i in groupItems if not i.hasChildren()]
		if groupDel:
			self.deleteGroupItems(groupDel)

	def deleteComboPairItems(self, items):
		''' Delete slider/value pair from a combo '''
		things = [toPyObject(i.data(THING_ROLE)) for i in items]
		self.system.deleteComboPairs(things)
		self._deleteTreeItems(items)

	def newComboShape(self):
		''' Create a new combo shape for a selected combo '''
		sel = self.getSelectedItems()
		comboItems = self.filterItemsByType(sel, C_COMBO_TYPE)
		if not comboItems:
			return

		comboItem = comboItems[0]
		tp = self.searchTreeForType(C_SHAPE_PAR_TYPE, comboItem)
		parItem = tp[0]
		comboThing = toPyObject(comboItem.data(THING_ROLE))
		return self.newShape(parItem, comboThing)

	def newShape(self, parItem, parThing):
		''' Create a new Shape item with defaults '''
		if self.coreType == Slider:
			if parThing.value == 0.0:
				vals = [i.value for i in parThing.prog.pairs]
				if 1.0 not in vals:
					tVal = 1.0
				elif -1.0 not in vals:
					tVal = -1.0
				elif 0.5 not in vals:
					tVal = 0.5
				else:
					tVal = -0.5
			else:
				tVal = parThing.value
		else:
			tVal = 1.0
		if abs(tVal) == 1.0:
			newName = parThing.name
		else:
			newName = "{0}_{1}".format(parThing.name, int(abs(tVal)*100))
		self.createShape(newName, tVal, parItem, parThing)

	@stackable
	def createShape(self, name, value, parItem, parThing):
		''' Interface with the DCC and create a new shape '''
		prog = parThing.prog

		shapeNames = [i.name for i in self.system.simplex.shapes]
		name = self.getNextName(name, shapeNames)
		thing = self.system.createShape(name, prog, value)

		if self.coreType == Slider:
			shapeItem = self.buildSliderShapeItem(parItem, thing)
			self.updateSliderRange(parThing)
		else:
			shapeItem = self.buildComboShapeItem(parItem, thing)
		self.expandTo(shapeItem)
		self.buildItemMap()

	def createCombo(self, name, sliderItems, groupItem):
		''' Create a new combo item based on slider items '''
		sliders = []
		values = []
		for si in sliderItems:
			thing = toPyObject(si.data(THING_ROLE))
			sliders.append(thing)
			if thing.value == 0.0:
				values.append(1.0)
			else:
				values.append(thing.value)

		group = toPyObject(groupItem.data(THING_ROLE))
		combo = self.system.createCombo(name, sliders, values, group)
		comboItem = self.buildComboComboTree(groupItem, combo)
		self.expandTo(comboItem)
		self.buildItemMap()

	def pairExpansion(self, oldSimp, newSimp):
		''' Copy the expansion values from 'old' to 'new' based on name '''
		newSimp.comboExpanded = oldSimp.comboExpanded
		newSimp.sliderExpanded = oldSimp.sliderExpanded

		mains = (
			(oldSimp.combos, newSimp.combos),
			(oldSimp.sliders, newSimp.sliders),
			(oldSimp.groups, newSimp.groups),
		)

		for old, new in mains:
			newDict = {i.name: i for i in new}
			oldDict = {i.name: i for i in old}
			keys = set(newDict.keys()) & set(oldDict.keys())
			for key in keys:
				kNew = newDict[key]
				kOld = oldDict[key]
				kNew.expanded = kOld.expanded

				if isinstance(kNew, Combo):
					knpDict = {i.slider.name:i for i in kNew.pairs}
					kopDict = {i.slider.name:i for i in kOld.pairs}
					kkeys = set(knpDict.keys()) & set(kopDict.keys())
					for kk in kkeys:
						knpDict[kk].expadned = kopDict[kk].expanded
						n = knpDict[kk]
						o = knpDict[kk]

					knpDict = {i.shape.name:i for i in kNew.prog.pairs}
					kopDict = {i.shape.name:i for i in kOld.prog.pairs}
					kkeys = set(knpDict.keys()) & set(kopDict.keys())
					for kk in kkeys:
						knpDict[kk].expadned = kopDict[kk].expanded

	def openMenu(self, pos):
		''' Open the combo context menu and build action connections if needed '''
		if self._menu is None:
			self._menu = ComboContextMenu(self)

			self._menu.uiAddGroupACT.triggered.connect(self.newComboGroup)
			self._menu.uiAddShapeACT.triggered.connect(self.newComboShape)

			self._menu.uiDeleteACT.triggered.connect(self.comboTreeDelete)

			self._menu.uiSetValsACT.triggered.connect(self.setSliderVals)

			#self._menu.uiExtractShapeACT.triggered.connect() # extract shape
			#self._menu.uiConnectShapeACT.triggered.connect() # connect shape
			#self._menu.uiMatchShapeACT.triggered.connect() # match shape
			#self._menu.uiClearShapeACT.triggered.connect() # clear shape

			self._menu.uiIsolateSelectedACT.triggered.connect(self.comboTreeIsolate)
			self._menu.uiExitIsolationACT.triggered.connect(self.comboTreeExitIsolate)

		self._menu.exec_(self.viewport().mapToGlobal(pos))

		return self._menu

	def buildComboGroupTree(self, parItem, groupThing):
		''' Build a combo tree group item, and all of its children '''
		grpItem = self.buildComboGroupItem(parItem, groupThing)
		ordered = sorted(groupThing.combos, key=lambda x: len(x.pairs))
		for combo in ordered:
			self.buildComboComboTree(grpItem, combo)
		return grpItem

	def buildComboComboTree(self, parItem, comboThing):
		''' Build a combo tree combo item, and all of its children '''
		comboItem = self.buildComboComboItem(parItem, comboThing)
		for pair in comboThing.pairs:
			self.buildComboSliderItem(comboItem, pair)

		self.buildComboShapeParTree(comboItem, comboThing.prog)
		return comboItem

	def buildComboShapeParTree(self, parItem, progThing):
		''' Build a combo tree shapePar item, and all of its children '''
		shapesItem = self.buildComboParItem(parItem, "SHAPES", progThing)
		for pair in progThing.pairs:
			self.buildComboShapeItem(shapesItem, pair)
		return shapesItem

	def buildComboGroupItem(self, parItem, groupThing):
		''' Build a combo tree Group item '''
		grpItem = QStandardItem(groupThing.name)
		grpItem.setData(groupThing, THING_ROLE)
		grpItem.setData(C_GROUP_TYPE, TYPE_ROLE)
		grpItem.setData(C_SYSTEM_TYPE, PARENT_ROLE)
		parItem.appendRow([grpItem, QStandardItem(), QStandardItem()])

		self.uiWeightGroupCBOX.blockSignals(True)
		self.uiWeightGroupCBOX.addItem(groupThing.name, groupThing)
		self.uiWeightGroupCBOX.blockSignals(False)

		return grpItem

	def buildComboComboItem(self, parItem, comboThing):
		''' Build a combo tree Combo item '''
		comboItem = QStandardItem(comboThing.name)
		comboItem.setData(comboThing, THING_ROLE)
		comboItem.setData(C_COMBO_TYPE, TYPE_ROLE)
		comboItem.setData(C_GROUP_TYPE, PARENT_ROLE)
		parItem.appendRow([comboItem, QStandardItem(), QStandardItem()])
		return comboItem

	def buildComboParItem(self, parItem, name, parThing):
		''' Build a combo tree SliderPar item '''
		slidersItem = QStandardItem(name)
		slidersItem.setData(parThing, THING_ROLE)
		slidersItem.setData(C_SHAPE_PAR_TYPE, TYPE_ROLE)
		slidersItem.setData(C_COMBO_TYPE, PARENT_ROLE)
		parItem.appendRow([slidersItem, QStandardItem(), QStandardItem()])
		return slidersItem

	def buildComboSliderItem(self, parItem, comboPair):
		''' Build a combo tree Slider item '''
		pairItem = QStandardItem(comboPair.slider.name)
		pairItem.setData(comboPair, THING_ROLE)
		pairItem.setData(C_SLIDER_TYPE, TYPE_ROLE)
		pairItem.setData(C_SLIDER_PAR_TYPE, PARENT_ROLE)
		comboPair.minValue = comboPair.slider.minValue
		comboPair.maxValue = comboPair.slider.maxValue
		pairValueItem = QStandardItem()
		pairValueItem.setData(float(comboPair.value), Qt.EditRole)
		pairValueItem.setData(True, VALUE_ROLE)
		pairValueItem.setData(comboPair, THING_ROLE)
		pairValueItem.setData(C_SLIDER_TYPE, TYPE_ROLE)
		pairValueItem.setData(C_SLIDER_PAR_TYPE, PARENT_ROLE)

		parItem.appendRow([pairItem, pairValueItem, QStandardItem()])
		return pairItem

	def buildComboShapeItem(self, parItem, progThing):
		''' Build a combo tree Shape item '''
		pairItem = QStandardItem(progThing.shape.name)
		pairItem.setData(progThing, THING_ROLE)
		pairItem.setData(C_SHAPE_TYPE, TYPE_ROLE)
		pairItem.setData(C_SHAPE_PAR_TYPE, PARENT_ROLE)
		progThing.minValue = 0.0
		progThing.maxValue = 1.0
		pairValueItem = QStandardItem()
		pairValueItem.setData(float(progThing.value), Qt.EditRole)
		pairValueItem.setData(True, WEIGHT_ROLE)
		pairValueItem.setData(progThing, THING_ROLE)
		pairValueItem.setData(C_SHAPE_TYPE, TYPE_ROLE)
		pairValueItem.setData(C_SHAPE_PAR_TYPE, PARENT_ROLE)
		parItem.appendRow([pairItem, QStandardItem(), pairValueItem])
		return pairItem




