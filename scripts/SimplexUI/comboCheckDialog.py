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
from SimplexUI.Qt import QtCompat
from SimplexUI.Qt.QtCore import Qt
from SimplexUI.Qt.QtGui import QBrush, QColor
from SimplexUI.Qt.QtWidgets import QMessageBox, QListWidgetItem, QDialog
from SimplexUI.utils import getUiFile
from SimplexUI.interfaceItems import Combo, Slider


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


class TooManyPossibilitiesError(Exception):
	pass


class ComboCheckDialog(QDialog):
	def __init__(self, sliders, parent):
		super(ComboCheckDialog, self).__init__(parent)

		uiPath = getUiFile(__file__)
		QtCompat.loadUi(uiPath, self)
		self.sliders = []

		self.uiCreateSelectedBTN.clicked.connect(self.createMissing)
		self.uiMinLimitSPIN.valueChanged.connect(self.populateCombos)
		self.uiMaxLimitSPIN.valueChanged.connect(self.populateCombos)
		self.uiCancelBTN.clicked.connect(self.close)
		self.parent().uiSliderTREE.selectionModel().selectionChanged.connect(self.populateCombos)

		self.populateCombos()


	def closeEvent(self, e):
		self.parent().uiSliderTREE.selectionModel().selectionChanged.disconnect(self.populateCombos)
		super(ComboCheckDialog, self).closeEvent(e)

	def populateCombos(self):
		""" Populate the list widgets in the UI """
		self.sliders = self.parent().uiSliderTREE.getSelectedItems(typ=Slider)

		# Get the range values for each slider
		allRanges = {}
		sliderDict = {}

		if not self.sliders:
			sliderList = list(self.sliders)
		else:
			sliderNames = set([i.name for i in self.sliders])
			sliderList = []
			for s in self.sliders:
				if s.name in sliderNames:
					sliderList.append(s)

		for slider in sliderList:
			rng = set(slider.prog.getRange())
			rng.discard(0) # ignore the zeros
			allRanges[slider] = sorted(list(rng))
			sliderDict[slider.name] = slider

		# Build all the slider/value possibility sets
		minDepth = self.uiMinLimitSPIN.value()
		maxDepth = self.uiMaxLimitSPIN.value()

		maxPoss = 1000
		poss = []
		try:
			for size in range(minDepth, maxDepth+1):
				for grp in combinations(sliderList, size):
					names = [i.name for i in grp]
					ranges = [allRanges[s] for s in grp]
					for vals in product(*ranges):
						poss.append(frozenset(zip(names, vals)))
						if len(poss) > maxPoss:
							raise TooManyPossibilitiesError("Don't melt your computer")
		except TooManyPossibilitiesError:
			self.uiWarningLBL.setText("Too many possibilities. Limiting to {0}".format(maxPoss))
		else:
			self.uiWarningLBL.setText("")

		# Get the "only" combo sets
		onlys = {}
		for combo in self.parent().simplex.combos:
			sls = [i.slider for i in combo.pairs]
			if all(r in self.sliders for r in sls):
				key = frozenset([(i.slider.name, i.value) for i in combo.pairs])
				onlys[key] = combo

		self.uiComboCheckLIST.clear()
		for p in poss:
			truePairs = [(sliderDict[n], v) for n, v in p]
			item = ComboCheckItem(truePairs, onlys.get(p))
			self.uiComboCheckLIST.addItem(item)

	def createMissing(self):
		""" Create the missing selected combos """
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
		self.close()


