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

# This module imports QT from PyQt4, PySide or PySide2
# Depending on what's available
from SimplexUI.Qt import QtCompat
from SimplexUI.Qt.QtGui import QStandardItemModel
from SimplexUI.Qt.QtWidgets import QInputDialog, QDataWidgetMapper
from SimplexUI.Qt.QtWidgets import QDialog

from SimplexUI.utils import getUiFile, getNextName
from SimplexUI.interfaceItems import Falloff
from SimplexUI.interfaceModel import FalloffDataModel

class FalloffDialog(QDialog):
	''' The main ui for simplex '''
	def __init__(self, parent):
		super(FalloffDialog, self).__init__(parent)
		uiPath = getUiFile(__file__)
		QtCompat.loadUi(uiPath, self)
		self.simplex = None
		self.parent().simplexLoaded.connect(self.loadSimplex)

		## Falloff connections
		self.uiShapeFalloffNewBTN.clicked.connect(self.newFalloff)
		self.uiShapeFalloffDuplicateBTN.clicked.connect(self.duplicateFalloff)
		self.uiShapeFalloffDeleteBTN.clicked.connect(self.deleteFalloff)
		self.uiShapeFalloffRenameBTN.clicked.connect(self.renameFalloff)

		self._falloffMapper = QDataWidgetMapper()
		self.loadSimplex()

	def loadSimplex(self):
		parent = self.parent()
		system = parent.simplex

		if system is None:
			self.uiShapeFalloffCBOX.setModel(QStandardItemModel())
			if self._falloffMapper is not None:
				self._falloffMapper.clearMapping()
				self._falloffMapper.setModel(QStandardItemModel())
			self.uiFalloffSettingsGRP.setEnabled(False)
			self.simplex = system
			return
		else:
			self.uiFalloffSettingsGRP.setEnabled(True)

		if system == self.simplex:
			return

		self.simplex = system
		# Populate Settings widgets
		falloffDataModel = FalloffDataModel(self.simplex, None)
		self.uiShapeFalloffCBOX.setModel(falloffDataModel)

		self._falloffMapper.setModel(falloffDataModel)
		self._falloffMapper.addMapping(self.uiFalloffTypeCBOX, 1, 'currentIndex')
		self._falloffMapper.addMapping(self.uiFalloffAxisCBOX, 2, 'currentIndex')
		self._falloffMapper.addMapping(self.uiFalloffMinSPN, 3)
		self._falloffMapper.addMapping(self.uiFalloffMinHandleSPN, 4)
		self._falloffMapper.addMapping(self.uiFalloffMaxHandleSPN, 5)
		self._falloffMapper.addMapping(self.uiFalloffMaxSPN, 6)

	# Falloff Settings
	def newFalloff(self):
		foNames = [f.name for f in self.simplex.falloffs]
		nn = getNextName('NewFalloff', foNames)
		Falloff.createPlanar(nn, self.simplex, 'X', 1.0, 0.66, 0.33, -1.0)
		self.uiShapeFalloffCBOX.setCurrentIndex(len(self.simplex.falloffs) - 1)

	def duplicateFalloff(self):
		idx = self.uiShapeFalloffCBOX.currentIndex()
		if not self.simplex.falloffs:
			self.newFalloff()
			return
		fo = self.simplex.falloffs[idx]

		foNames = [f.name for f in self.simplex.falloffs]
		nn = getNextName(fo.name, foNames)
		fo.duplicate(nn)

	def deleteFalloff(self):
		idx = self.uiShapeFalloffCBOX.currentIndex()
		if not self.simplex.falloffs:
			self.newFalloff()
			return

		if idx > 0:
			self.uiShapeFalloffCBOX.setCurrentIndex(idx - 1)

		fo = self.simplex.falloffs[idx]
		fo.delete()

		if not self.simplex.falloffs:
			idx = self.uiShapeFalloffCBOX.lineEdit().setText('')

	def renameFalloff(self):
		if not self.simplex.falloffs:
			return
		idx = self.uiShapeFalloffCBOX.currentIndex()
		fo = self.simplex.falloffs[idx]
		foNames = [f.name for f in self.simplex.falloffs]

		newName, good = QInputDialog.getText(self, "Rename Falloff", "Enter a new name for the Falloff", text=fo.name)
		if not good:
			return
		nn = getNextName(newName, foNames)
		fo.name = nn

