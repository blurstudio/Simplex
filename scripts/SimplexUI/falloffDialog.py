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

# This module imports QT from PyQt4, PySide or PySide2
# Depending on what's available
import re
from .Qt import QtCompat
from .Qt.QtCore import QSettings
from .Qt.QtGui import QStandardItemModel
from .Qt.QtWidgets import QInputDialog, QDataWidgetMapper, QMessageBox, QDialog

from .utils import getUiFile, getNextName
from .items import Falloff
from .interfaceModel import FalloffDataModel

try:
	# This module is unique to Blur Studio
	import blurdev
except ImportError:
	blurdev = None


NAME_CHECK = re.compile(r'[A-Za-z][\w.]*')


class FalloffDialog(QDialog):
	''' The ui for interacting with Falloffs '''
	def __init__(self, parent):
		super(FalloffDialog, self).__init__(parent)
		uiPath = getUiFile(__file__)
		QtCompat.loadUi(uiPath, self)
		self.simplex = None
		self.parent().simplexLoaded.connect(self.loadSimplex)

		self._falloffMapper = QDataWidgetMapper(self)

		## Falloff connections
		self.uiShapeFalloffNewBTN.clicked.connect(self.newFalloff)
		self.uiShapeFalloffDuplicateBTN.clicked.connect(self.duplicateFalloff)
		self.uiShapeFalloffDeleteBTN.clicked.connect(self.deleteFalloff)
		self.uiShapeFalloffRenameBTN.clicked.connect(self.renameFalloff)
		self.uiShapeFalloffCBOX.currentIndexChanged.connect(self._falloffMapper.setCurrentIndex)

		self.loadSimplex()

	def loadSimplex(self):
		''' Load the Simplex system from the parent UI '''
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
		falloffDataModel = FalloffDataModel(self.simplex, self)
		self.simplex.falloffModels.append(falloffDataModel)
		self.uiShapeFalloffCBOX.setModel(falloffDataModel)
		self._falloffMapper.setModel(falloffDataModel)
		self._falloffMapper.addMapping(self.uiFalloffTypeCBOX, 1, 'currentIndex')
		self._falloffMapper.addMapping(self.uiFalloffAxisCBOX, 2, 'currentIndex')
		self._falloffMapper.addMapping(self.uiFalloffMinSPN, 3)
		self._falloffMapper.addMapping(self.uiFalloffMinHandleSPN, 4)
		self._falloffMapper.addMapping(self.uiFalloffMaxHandleSPN, 5)
		self._falloffMapper.addMapping(self.uiFalloffMaxSPN, 6)

		self.uiShapeFalloffCBOX.setCurrentIndex(0)
		self._falloffMapper.setCurrentIndex(0)

	# Falloff Settings
	def newFalloff(self):
		''' Create a new Falloff object '''
		foNames = [f.name for f in self.simplex.falloffs]
		tempName = getNextName("NewFalloff", foNames)

		newName, good = QInputDialog.getText(self, "Rename Falloff", "Enter a new name for the Falloff", text=tempName)
		if not good:
			return

		if not NAME_CHECK.match(newName):
			message = 'Falloff name can only contain letters and numbers, and cannot start with a number'
			QMessageBox.warning(self, 'Warning', message)
			return

		nn = getNextName(newName, foNames)
		Falloff.createPlanar(nn, self.simplex, 'X', 1.0, 0.66, 0.33, -1.0)

	def duplicateFalloff(self):
		''' Duplicate the selected falloff '''
		if not self.simplex.falloffs:
			self.newFalloff()
			return

		idx = self.uiShapeFalloffCBOX.currentIndex()
		if idx < 0:
			return

		fo = self.simplex.falloffs[idx]

		foNames = [f.name for f in self.simplex.falloffs]
		nn = getNextName(fo.name, foNames)
		fo.duplicate(nn)

	def deleteFalloff(self):
		''' Delete the selected falloff '''
		if not self.simplex.falloffs:
			return
		idx = self.uiShapeFalloffCBOX.currentIndex()
		if idx < 0:
			return

		fo = self.simplex.falloffs[idx]
		fo.delete()

	def renameFalloff(self):
		''' Rename the selected falloff '''
		if not self.simplex.falloffs:
			return
		idx = self.uiShapeFalloffCBOX.currentIndex()
		if idx < 0:
			return
		fo = self.simplex.falloffs[idx]
		foNames = [f.name for f in self.simplex.falloffs]
		foNames.pop(idx)

		newName, good = QInputDialog.getText(self, "Rename Falloff", "Enter a new name for the Falloff", text=fo.name)
		if not good:
			return

		if not NAME_CHECK.match(newName):
			message = 'Falloff name can only contain letters and numbers, and cannot start with a number'
			QMessageBox.warning(self, 'Warning', message)
			return

		nn = getNextName(newName, foNames)
		fo.name = nn

	def storeSettings(self):
		if blurdev is None:
			pref = QSettings("Blur", "Simplex3")
			pref.setValue("fogeometry", self.saveGeometry())
		else:
			pref = blurdev.prefs.find("tools/simplex3")
			pref.recordProperty("fogeometry", self.saveGeometry())
			pref.save()

	def loadSettings(self):
		if blurdev is None:
			pref = QSettings("Blur", "Simplex3")
			self.restoreGeometry(pref.value("fogeometry"))
		else:
			pref = blurdev.prefs.find("tools/simplex3")
			geo = pref.restoreProperty('fogeometry', None)
			if geo is not None:
				self.restoreGeometry(geo)

	def hideEvent(self, event):
		self.storeSettings()
		super(FalloffDialog, self).hideEvent(event)

	def showEvent(self, event):
		super(FalloffDialog, self).showEvent(event)
		self.loadSettings()

