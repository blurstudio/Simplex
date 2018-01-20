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

#pylint: disable=invalid-name, unused-argument
""" A placeholder interface that takes arguments and does nothing with them """
import json
from contextlib import contextmanager
from Qt import QtCore
from Qt.QtCore import Signal
from tools.dummyTools import ToolActions
from functools import wraps

# UNDO STACK INTEGRATION
@contextmanager
def undoContext():
	DCC.undoOpen()
	try:
		yield
	finally:
		DCC.undoClose()

def undoable(f):
	@wraps(f)
	def stacker(*args, **kwargs):
		with undoContext():
			return f(*args, **kwargs)
	return stacker


class DCC(object):
	program = "dummy"
	def __init__(self, simplex, stack=None):
		self.name = None # the name of the system
		self.simplex = simplex # the abstract representation of the setup
		self._live = True
		self._revision = 0

	# System IO
	@undoable
	def loadNodes(self, simp, thing, create=True, pBar=None):
		"""
		Create a new system based on the simplex tree
		Build any DCC objects that are missing if create=True
		Raises a runtime error if missing objects are found and
		create=False
		"""
		thing.op.definition = simp.dump()

	@undoable
	def loadConnections(self, simp, create=True, multiplier=1, pBar=None):
		# Build/create any shapes
		pass

	@undoable
	def loadAbc(self, abcMesh, js, pBar=None):
		pass

	def exportAbc(self, dccMesh, abcMesh, js, world=False, pBar=None):		# export the data to alembic
		pass


	# Revision tracking
	def getRevision(self):
		return self._revision

	def incrementRevision(self):
		self._revision += 1
		return self._revision

	def setRevision(self, val):
		self._revision = val


	# System level
	@undoable
	def renameSystem(self, name):
		pass


	# Shapes
	@undoable
	def createShape(self, shapeName, shape, live=False):
		pass


	@undoable
	def extractShape(self, shape, live=True):
		""" make a mesh representing a shape. Can be live or not """
		pass


	@undoable
	def connectShape(self, shape, mesh=None, live=True, delete=False):
		""" Force a shape to match a mesh
			The "connect shape" button is:
				mesh=None, delete=True
			The "match shape" button is:
				mesh=someMesh, delete=False
			There is a possibility of a "make live" button:
				live=True, delete=False
		"""
		pass


	@undoable
	def extractPosedShape(self, shape):
		pass

	@undoable
	def zeroShape(self, shape):
		""" Set the shape to be completely zeroed """
		pass


	@undoable
	def deleteShape(self, shape):
		""" Remove a shape from the system """
		pass

	@undoable
	def renameShape(self, shape, name):
		""" Change the name of the shape """
		pass

	@undoable
	def convertShapeToCorrective(self, shape):
		pass



	# Falloffs
	def createFalloff(self, name):
		pass # for eventual live splits

	def duplicateFalloff(self, falloff, newFalloff, newName):
		pass # for eventual live splits

	def deleteFalloff(self, falloff):
		pass # for eventual live splits

	def setFalloffData(self, falloff, splitType, axis, minVal, minHandle, maxHandle, maxVal, mapName):
		pass # for eventual live splits


	# Sliders
	@undoable
	def createSlider(self, name, slider, multiplier=1):
		""" Create a new slider with a name in a group.
		Possibly create a single default shape for this slider """
		pass


	@undoable
	def renameSlider(self, slider, name, multiplier=1):
		""" Set the name of a slider """
		pass

	@undoable
	def setSliderRange(self, slider, multiplier):
		pass

	@undoable
	def renameCombo(self, combo, name):
		""" Set the name of a slider """
		pass

	@undoable
	def deleteSlider(self, slider):
		pass

	@undoable
	def addProgFalloff(self, prog, falloff):
		pass # for eventual live splits

	@undoable
	def removeProgFalloff(self, prog, falloff):
		pass # for eventual live splits

	@undoable
	def setSlidersWeights(self, sliders, weights):
		""" Set the weight of a slider. This does not change the definition """
		pass

	@undoable
	def updateSlidersRange(self, sliders):
		pass



	# Combos
	@undoable
	def extractComboShape(self, combo, shape, live=True):
		""" Extract a shape from a combo progression """
		pass

	@undoable
	def connectComboShape(self, combo, shape, mesh=None, live=True, delete=False):
		""" Connect a shape into a combo progression"""
		pass

	@staticmethod
	def setDisabled(op):
		return None

	@staticmethod
	def reEnable(helpers):
		pass

	# Data Access
	@staticmethod
	def getSimplexOperatorsOnObject(thing):
		""" return all simplex operators on an object """
		return [thing.op]

	@staticmethod
	def getSimplexString(op):
		""" return the definition string from a simplex operator """
		return op.definition

	@staticmethod
	def setSimplexString(op, val):
		""" return the definition string from a simplex operator """
		op.definition = val

	@staticmethod
	def selectObject(thing):
		""" Select an object in the DCC """
		pass

	def selectCtrl(self):
		""" Select the system's control object """
		pass

	@staticmethod
	def getObjectByName(name):
		""" return an object from the DCC by name """
		return DummyNode(name)

	@staticmethod
	def getObjectName(thing):
		""" return the text name of an object """
		return thing.name

	@staticmethod
	def getSelectedObjects():
		""" return the currently selected DCC objects """
		return [DummyNode("thing")]

	@staticmethod
	def undoOpen():
		pass

	@staticmethod
	def undoClose():
		pass


class Dispatch(QtCore.QObject):
	beforeNew = Signal()
	afterNew = Signal()
	beforeOpen = Signal()
	afterOpen = Signal()
	undo = Signal()
	redo = Signal()

	def __init__(self, parent=None):
		super(Dispatch, self).__init__(parent)

	def connectCallbacks(self):
		pass

	def disconnectCallbacks(self):
		pass

	def emitBeforeNew(self, *args, **kwargs):
		self.beforeNew.emit()

	def emitAfterNew(self, *args, **kwargs):
		self.afterNew.emit()

	def emitBeforeOpen(self, *args, **kwargs):
		self.beforeOpen.emit()

	def emitAfterOpen(self, *args, **kwargs):
		self.afterOpen.emit()

	def emitUndo(self, *args, **kwargs):
		self.undo.emit()

	def emitRedo(self, *args, **kwargs):
		self.redo.emit()

DISPATCH = Dispatch()

def rootWindow():
	return None




class DummyNode(object):
	def __init__(self, name):
		self.name = name
		self.op = DummyOp(name)
		self.importPath = ""

class DummyOp(object):
	def __init__(self, name):
		self.definition = ""


