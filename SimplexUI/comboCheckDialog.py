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
from itertools import combinations, product
from .Qt import QtCompat
from .Qt.QtCore import Qt
from .Qt.QtGui import QBrush, QColor
from .Qt.QtWidgets import QMessageBox, QListWidgetItem, QDialog, QTreeWidget, QTreeWidgetItem
from .utils import getUiFile
from .items import Combo, Slider
from .dragFilter import DragFilter

class TooManyPossibilitiesError(Exception):
	pass

def buildPossibleCombos(simplex, sliders, minDepth, maxDepth, lockDict=None, maxPoss=100):
	""" Build a list of possible combos """
	# Get the range values for each slider
	allRanges = {}
	sliderDict = {}
	lockDict = lockDict or {}

	for slider in sliders:
		rng = set(lockDict.get(slider, slider.prog.getRange()))
		rng.discard(0) # ignore the zeros
		allRanges[slider] = sorted(rng)
		sliderDict[slider.name] = slider

	poss = []
	tooMany = False
	try:
		for size in range(minDepth, maxDepth+1):
			for grp in combinations(sliders, size):
				names = [i.name for i in grp]
				ranges = [allRanges[s] for s in grp]
				for vals in product(*ranges):
					poss.append(frozenset(zip(names, vals)))
					if len(poss) > maxPoss:
						raise TooManyPossibilitiesError("Don't melt your computer")
	except TooManyPossibilitiesError:
		tooMany = True

	# Get the "only" combo sets
	onlys = {}
	for combo in simplex.combos:
		sls = [i.slider for i in combo.pairs]
		if all(r in sliders for r in sls):
			key = frozenset([(i.slider.name, i.value) for i in combo.pairs])
			onlys[key] = combo

	toAdd = []
	for p in poss:
		truePairs = [(sliderDict[n], v) for n, v in p]
		toAdd.append((truePairs, onlys.get(p)))
	return tooMany, toAdd




class ComboCheckItem(QListWidgetItem):
	def __init__(self, pairs, combo, *args, **kwargs):
		super(ComboCheckItem, self).__init__(*args, **kwargs)
		self.pairs = pairs
		self.combo = combo

		if self.combo is None:
			# We can create it!!
			sliders, vals = zip(*self.pairs)
			newName = Combo.buildComboName(sliders, vals)
			self.setText(newName)
		else:
			self.setText(self.combo.name)
			self.setForeground(QBrush(QColor(128, 128, 128)))




class ComboCheckDialog(QDialog):
	''' Dialog for checking what possible combos exist, and picking new combos

	This dialog displays the available combos for a number of input sliders

	In 'Create' mode, it provides a quick way of choosing the one specific combo
	that the user is looking for

	In 'Check' mode, it provides a convenient way to explore the possibilites
	and create any missing combos directly

	Arguments:
		sliders (list): The list of sliders to initialize the dialog with
		values (list): The list of values that those sliders default to
			in single mode. Defaults to None
		mode (str): The mode that the dialog will run. Defaults to 'create'
		parent (QWidget): The parent for the dialog. Defaults to None
	'''
	def __init__(self, sliders, values=None, mode='create', parent=None):
		super(ComboCheckDialog, self).__init__(parent)

		uiPath = getUiFile(__file__)
		QtCompat.loadUi(uiPath, self)
		self.mode = mode.lower()

		self.uiCreateSelectedBTN.clicked.connect(self.createMissing)
		self.uiMinLimitSPIN.valueChanged.connect(self.populateWithoutUpdate)
		self.uiMaxLimitSPIN.valueChanged.connect(self.populateWithoutUpdate)
		self.uiCancelBTN.clicked.connect(self.close)
		self.uiManualUpdateBTN.clicked.connect(self.populateWithUpdate)
		self.uiEditTREE.itemChanged.connect(self.populateWithoutUpdate)

		self.dragFilter = DragFilter(self)
		self.uiEditTREE.viewport().installEventFilter(self.dragFilter)
		self.dragFilter.dragTick.connect(self.dragTick)

		self.parent().uiSliderTREE.selectionModel().selectionChanged.connect(self.populateWithCheck)

		self.valueDict = values or {}
		self.setSliders(sliders)
		if self.mode == 'create':
			self.uiAutoUpdateCHK.setCheckState(Qt.Unchecked)
			self.uiAutoUpdateCHK.hide()
			self.uiManualUpdateBTN.hide()

		self.uiMaxLimitSPIN.setValue(max(len(sliders), 2))
		self.uiMinLimitSPIN.setValue(max(len(sliders)-2, 2))

		if sliders is None:
			self.populateWithUpdate()
		else:
			self._populate()

	def dragTick(self, ticks, mul):
		''' Deal with the ticks coming from the drag handler '''
		items = self.uiEditTREE.selectedItems()
		for item in items:
			val = item.data(3, Qt.EditRole)
			val += (0.05) * ticks * mul
			if abs(val) < 1.0e-5:
				val = 0.0
			val = max(min(val, 1.0), -1.0)
			item.setData(3, Qt.EditRole, val)
		self.uiEditTREE.viewport().update()

	def setSliders(self, val):
		''' Set the sliders displayed in this UI 
		
		Args:
			val (list of Sliders): The sliders to be displayed
		'''
		self.uiEditTREE.clear()
		dvs = [None, -1.0, 1.0, 0.5]
		roles = [Qt.UserRole, Qt.UserRole, Qt.UserRole, Qt.EditRole]
		val = val or []
		for slider in val:
			item = QTreeWidgetItem(self.uiEditTREE, [slider.name])
			item.setFlags(item.flags() | Qt.ItemIsEditable)
			vvv = self.valueDict.get(slider, [-1.0, 1.0])
			mvs = [i for i in vvv if abs(i) != 1.0]
			mvs = mvs[0] if mvs else 0.5

			item.setData(0, Qt.UserRole, slider)
			for col in range(1, 4):
				val = mvs if col == 3 else dvs[col]
				item.setData(col, roles[col], val)
				rng = slider.prog.getRange()
				if val in rng or col == 3:
					chk = Qt.Checked if val in vvv else Qt.Unchecked
					item.setCheckState(col, chk)

		for col in reversed(range(4)):
			self.uiEditTREE.resizeColumnToContents(col)

	def closeEvent(self, event):
		self.parent().uiSliderTREE.selectionModel().selectionChanged.disconnect(self.populateWithCheck)
		super(ComboCheckDialog, self).closeEvent(event)

	def populateWithUpdate(self):
		self.setSliders(self.parent().uiSliderTREE.getSelectedItems(typ=Slider))
		self._populate()

	def populateWithoutUpdate(self):
		self._populate()

	def populateWithCheck(self):
		if self.uiAutoUpdateCHK.isChecked():
			self.setSliders(self.parent().uiSliderTREE.getSelectedItems(typ=Slider))
		self._populate()

	def _populate(self):
		""" Populate the list widgets in the UI """
		minDepth = self.uiMinLimitSPIN.value()
		maxDepth = self.uiMaxLimitSPIN.value()
		maxPoss = 100

		root = self.uiEditTREE.invisibleRootItem()
		lockDict = {}
		sliderList = []
		roles = [Qt.UserRole, Qt.UserRole, Qt.UserRole, Qt.EditRole]
		for row in range(root.childCount()):
			item = root.child(row)
			slider = item.data(0, Qt.UserRole)
			if slider is not None:
				sliderList.append(slider)
				lv = [item.data(col, roles[col]) for col in range(1, 4) if item.checkState(col)]
				lockDict[slider] = lv

		tooMany, toAdd = buildPossibleCombos(self.parent().simplex, sliderList, minDepth, maxDepth, lockDict=lockDict, maxPoss=maxPoss)

		lbl = "Too many possibilities. Limiting to {0}".format(maxPoss) if tooMany else ''
		self.uiWarningLBL.setText(lbl)

		self.uiComboCheckLIST.clear()
		for pairs, combo in reversed(toAdd):
			item = ComboCheckItem(pairs, combo)
			self.uiComboCheckLIST.addItem(item)

		if self.mode == 'create':
			if self.uiComboCheckLIST.count() > 0:
				self.uiComboCheckLIST.item(0).setSelected(True)

	def createMissing(self):
		''' Create selected combos if they don't already exist '''
		simplex = self.parent().simplex
		created = []
		for item in self.uiComboCheckLIST.selectedItems():
			name = item.text()
			sliders, vals = zip(*item.pairs)
			# Double check that the user didn't create any extra sliders
			if Combo.comboAlreadyExists(simplex, sliders, vals) is None:
				c = Combo.createCombo(name, simplex, sliders, vals)
				created.append(c)

		self.parent().uiComboTREE.setItemSelection(created)
		if self.mode == 'create':
			self.close()
		else:
			self.populateWithoutUpdate()


