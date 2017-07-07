'''
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
'''

import os
import xml.etree.ElementTree as xml
from cStringIO import StringIO

try:
	from PySide import QtGui, QtCore
	from PySide.QtCore import Signal, Slot
	from PySide.QtCore import Qt, QObject, QTimer, QPoint, QEvent, QSettings, QModelIndex
	from PySide.QtGui import QMessageBox, QInputDialog, QFileDialog, QMenu, QApplication, QSortFilterProxyModel, QAction
	from PySide.QtGui import QDialog, QMainWindow, QSplashScreen, QShortcut, QItemSelection, QProgressDialog
	from PySide.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QCursor, QMouseEvent
	import pysideuic as uic
	def toPyObject(thing):
		return thing

except ImportError:
	try:
		from PyQt4 import QtGui, QtCore
		from PyQt4.QtCore import pyqtSignal as Signal, pyqtSlot as Slot
		from PyQt4.QtCore import Qt, QObject, QTimer, QPoint, QEvent, QSettings, QModelIndex
		from PyQt4.QtGui import QMessageBox, QInputDialog, QFileDialog, QMenu, QApplication, QSortFilterProxyModel, QAction
		from PyQt4.QtGui import QDialog, QMainWindow, QSplashScreen, QShortcut, QItemSelection, QProgressDialog
		from PyQt4.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QCursor, QMouseEvent
		import PyQt4.uic as uic
		def toPyObject(thing):
			return thing.toPyObject()

	except ImportError:
		from PySide2 import QtGui, QtCore
		from PySide2.QtCore import Signal, QSortFilterProxyModel, Slot, QModelIndex
		from PySide2.QtCore import Qt, QObject, QTimer, QPoint, QEvent, QItemSelection, QSettings
		from PySide2.QtWidgets import QMessageBox, QInputDialog, QFileDialog, QMenu, QApplication, QAction
		from PySide2.QtWidgets import QDialog, QMainWindow, QSplashScreen, QShortcut, QProgressDialog
		from PySide2.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QCursor, QMouseEvent
		import pyside2uic as uic
		def toPyObject(thing):
			return thing


def loadUiType(fileVar, subFolder="ui", uiName=None):
	"""
	To use this, pass the path to a UI file, and capture the output
	as FormClass and BaseClass.  Define your class inheriting from both
	and call self.setupUi(self) in the __init__
	"""
	uiFolder, filename = os.path.split(fileVar)
	if uiName is None:
		uiName = os.path.splitext(filename)[0]
	if subFolder:
		uiFile = os.path.join(uiFolder, subFolder, uiName+".ui")

	parsed = xml.parse(uiFile)
	widget_class = parsed.find('widget').get('class')
	form_class = parsed.find('class').text

	with open(uiFile, 'r') as f:
		o = StringIO()
		frame = {}

		uic.compileUi(f, o, indent=0)
		pyc = compile(o.getvalue(), '<string>', 'exec')
		exec pyc in frame

		#Fetch the base_class and form class based on their type in the xml from designer
		form_class = frame['Ui_{0}'.format(form_class)]

		try:
			base_class = eval('QtGui.{0}'.format(widget_class))
		except:
			base_class = eval('QtWidgets.{0}'.format(widget_class))

	return form_class, base_class

