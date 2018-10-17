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
from functools import wraps

# UNDO STACK INTEGRATION
@contextmanager
def undoContext(inst=None):
	if inst is None:
		DCC.staticUndoOpen()
	else:
		inst.undoOpen()
	try:
		yield
	finally:
		if inst is None:
			DCC.staticUndoClose()
		else:
			inst.undoClose()

def undoable(f):
	@wraps(f)
	def stacker(self, *args, **kwargs):
		with undoContext():
			return f(self, *args, **kwargs)
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
		pass

	def loadConnections(self, simp, pBar=None):
		pass

	def getShapeThing(self, shapeName):
		return DummyNode(shapeName)

	def getSliderThing(self, sliderName):
		return DummyNode(sliderName)

	@staticmethod
	@undoable
	def buildRestAbc(abcMesh, name):
		pass

	@undoable
	def loadAbc(self, abcMesh, js, pBar=None):
		pass

	def exportAbc(self, dccMesh, abcMesh, js, world=False, pBar=None):
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

	@undoable
	def deleteSystem(self):
		pass

	# Shapes
	@undoable
	def createShape(self, shapeName, live=False, offset=10):
		pass

	@undoable
	def extractWithDeltaShape(self, shape, live=True, offset=10.0):
		""" Make a mesh representing a shape. Can be live or not.
			Also, make a shapenode that is the delta of the change being made
		"""
		pass

	@undoable
	def extractWithDeltaConnection(self, shape, delta, value, live=True, offset=10.0):
		""" Extract a shape with a live partial delta added in.
			Useful for updating progressive shapes
		"""
		pass


	@undoable
	def extractShape(self, shape, live=True, offset=10.0):
		""" Make a mesh representing a shape. Can be live or not.
			Can also store its starting shape and delta data
		"""
		pass

	@undoable
	def connectShape(self, shape, mesh=None, live=False, delete=False):
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
		pass

	@undoable
	def deleteShape(self, toDelShape):
		pass

	@undoable
	def renameShape(self, shape, name):
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
	def createSlider(self, name, index, minVal, maxVal):
		pass

	@undoable
	def renameSlider(self, slider, name, multiplier=1):
		pass

	@undoable
	def setSliderRange(self, slider, multiplier):
		pass

	@undoable
	def deleteSlider(self, toDelSlider):
		pass

	@undoable
	def addProgFalloff(self, prog, falloff):
		pass # for eventual live splits

	@undoable
	def removeProgFalloff(self, prog, falloff):
		pass # for eventual live splits

	@undoable
	def setSlidersWeights(self, sliders, weights):
		pass

	@undoable
	def setSliderWeight(self, slider, weight):
		cmds.setAttr(slider.thing, weight)

	@undoable
	def updateSlidersRange(self, sliders):
		pass

	@undoable
	def extractTraversalShape(self, trav, shape, live=True, offset=10.0):
		pass

	@undoable
	def connectTraversalShape(self, trav, shape, mesh=None, live=True, delete=False):
		pass

	# Combos
	@undoable
	def extractComboShape(self, combo, shape, live=True, offset=10.0):
		pass

	@undoable
	def connectComboShape(self, combo, shape, mesh=None, live=True, delete=False):
		pass

	@staticmethod
	def setDisabled(op):
		pass

	@staticmethod
	def reEnable(helpers):
		pass

	@undoable
	def renameCombo(self, combo, name):
		""" Set the name of a Combo """
		pass

	# Data Access
	@staticmethod
	def getSimplexOperators():
		""" return any simplex operators on an object """
		return cmds.ls(type="simplex_maya")

	@staticmethod
	def getSimplexOperatorsByName(name):
		""" return all simplex operators with a given name"""
		return cmds.ls(name, type="simplex_maya")

	@staticmethod
	def getSimplexOperatorsOnObject(thing):
		""" return all simplex operators on an object """
		return [thing.op]

	@staticmethod
	def getSimplexString(op):
		""" return the definition string from a simplex operator """
		return op.definition

	@staticmethod
	def getSimplexStringOnThing(thing, systemName):
		""" return the simplex string of a specific system on a specific object """
		return None

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
	def staticUndoOpen():
		pass

	@staticmethod
	def staticUndoClose():
		pass

	def undoOpen(self):
		pass

	def undoClose(self):
		pass

	@classmethod
	def getPersistentShape(cls, thing):
		return cls.getObjectName(thing)

	@classmethod
	def loadPersistentShape(cls, thing):
		return cls.getObjectByName(thing)

	@classmethod
	def getPersistentSlider(cls, thing):
		return cls.getObjectName(thing)

	@classmethod
	def loadPersistentSlider(cls, thing):
		return cls.getObjectByName(thing)

	@staticmethod
	def getSelectedObjects():
		""" return the currently selected DCC objects """
		# For maya, only return transform nodes
		return [DummyNode("thing")]




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

