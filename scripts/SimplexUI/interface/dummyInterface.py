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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.

#pylint: disable=invalid-name, unused-argument
""" A placeholder interface that takes arguments and does nothing with them """
import json, copy
from contextlib import contextmanager
from ..Qt import QtCore
from ..Qt.QtCore import Signal
from functools import wraps
try:
	import numpy as np
except ImportError:
	np = None
from ..commands.alembicCommon import getSampleArray, mkSampleIntArray, getStaticMeshData, getUvArray, getUvSample, mkSampleVertexPoints
from ..Qt.QtWidgets import QApplication
from alembic.AbcGeom import OPolyMeshSchemaSample, OV2fGeomParamSample, GeometryScope

# UNDO STACK INTEGRATION
@contextmanager
def undoContext(inst=None):
	''' A context that wraps undo chunks

	Parameters
	----------
	inst : DCC
		 An instantiated DCC if available. (Default value = None)

	Returns
	-------

	'''
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
	''' A decorator that wraps a function in an undoContext '''
	@wraps(f)
	def stacker(self, *args, **kwargs):
		''' The wrapper closure '''
		with undoContext():
			return f(self, *args, **kwargs)
	return stacker

class DummyScene(object):
	''' A dcc scene containing existing dummy objects '''
	def __init__(self):
		self.nodes = {} # Generic nodes
		self.ops = {} # simplex operators
		self.bss = {} # blendshape operators
		self.meshes = {} # existing meshes
		self.falloffs = {} # weightmaps
DB = DummyScene()

class DummyAttr(object):
	''' A generic named object attribute '''
	def __init__(self, name, value, parent):
		self.name = name
		self.value = value
		self.parent = parent
		parent.attrs[name] = self

class DummyNode(object):
	''' A generic DCC node '''
	def __init__(self, name, scnDict=None):
		self.name = name
		self.attrs = {}
		self.ops = []
		if scnDict is None:
			scnDict = DB.nodes
		scnDict[self.name] = self

class DummySimplex(DummyNode):
	''' A generic simplex node '''
	def __init__(self, name, parent):
		super(DummySimplex, self).__init__(name, DB.ops)
		self.definition = ""
		parent.ops.append(self)

class DummyFalloff(DummyNode):
	''' A generic simplex node '''
	def __init__(self, name, parent):
		super(DummyFalloff, self).__init__(name, DB.falloffs)
		self.weightmap = None

class DummyShape(object):
	''' A generic named blendshape shape '''
	def __init__(self, name, shapeNode):
		self.name = name
		self.value = 0.0
		self.points = None
		self.shapeNode = shapeNode
		shapeNode.shapes[name] = self

class DummyBlendshape(DummyNode):
	''' A generic blendshape node '''
	def __init__(self, name, parent):
		super(DummyBlendshape, self).__init__(name, DB.ops)
		self.shapes = {}
		parent.ops.append(self)

class DummyMesh(DummyNode):
	''' A generic mesh '''
	def __init__(self, name):
		super(DummyMesh, self).__init__(name, DB.meshes)
		self.importPath = ""
		self.faces = None
		self.counts = None
		self.uvs = None
		self.verts = None


class DCC(object):
	''' '''
	program = "dummy"
	def __init__(self, simplex, stack=None):
		self.simplex = simplex # the abstract representation of the setup
		self.name = simplex.name

		self.mesh = None
		self.ctrl = None
		self.shapeNode = None
		self.op = None

		self._live = True
		self._revision = 0
		#self._shapes = {} # hold the shapes from the .smpx file as a dict
		#self._faces = None # Faces for the mesh (Alembic-style)
		#self._counts = None # Face counts for the mesh (Alembic-style)
		#self._uvs = None # UV data for the mesh
		#self._numVerts = None
		self._falloffs = {} # weightPerVert values
		self.sliderMul = self.simplex.sliderMul

	def preLoad(self, simp, simpDict, create=True, pBar=None):
		''' Code to execute before loading a simplex system into a dcc

		Parameters
		----------
		simp : Simplex
			The simplex system that will be created
		simpDict : dict
			The dictionary definition of the simplex to be created
		create : bool
			Whether to create the missing objects in the DCC (Default value = True)
		pBar : QProgressDialog, optional
			An optional progress dialog (Default value = None)

		Returns
		-------
			object :
				A generic python object to be used in the post-load
		'''
		return None

	def postLoad(self, simp, preRet):
		''' Code to execute after loading a simplex system into a dcc

		Parameters
		----------
		simp : Simplex
			The simplex system that was created
		preRet : object
			The object returnd from the preload method

		Returns
		-------

		'''
		pass

	# System IO
	@undoable
	def loadNodes(self, simp, thing, create=True, pBar=None):
		''' Load the nodes from a simplex system onto a thing

		Parameters
		----------
		simp : Simplex
			The system we're loading for
		thing : object
			The DCC thing we're reading
		create : bool
			Whether to create the missing nodes (Default value = True)
		pBar : QProgressDialog, optional
			 (Default value = None)

		Returns
		-------

		'''
		self.name = simp.name
		self.mesh = thing

		self.shapeNode = DB.bss.get(self.name)
		if self.shapeNode is None:
			if not create:
				raise RuntimeError("Blendshape operator not found with creation turned off: {0}".format(self.name))
			self.shapeNode = DummyBlendshape(self.name, self.mesh)

		self.op = DB.ops.get(self.name)
		if self.op is None:
			if not create:
				raise RuntimeError("Simplex operator not found with creation turned off")
			self.op = DummySimplex(self.name, self.mesh)

		self.ctrl = DB.nodes.get(self.name)
		if self.ctrl is None:
			if not create:
				raise RuntimeError("Control object not found with creation turned off")
			self.ctrl = DummyNode(self.name, self.mesh)

	def loadConnections(self, simp, pBar=None):
		''' Load the connections that exist in a simplex system

		Parameters
		----------
		simp : Simplex
			The simplex system to load connections for
		pBar : QProgressDialog, optional
			 (Default value = None)

		Returns
		-------

		'''
		pass

	def getShapeThing(self, shapeName):
		''' Get the DCC Thing for a given shape name

		Parameters
		----------
		shapeName : str
			The name of the shape to get

		Returns
		-------
		object :
			The DCC Thing

		'''
		return self.shapeNode.shapes.get(shapeName)

	def getSliderThing(self, sliderName):
		''' Get the DCC Thing for a given slider name

		Parameters
		----------
		sliderName : str
			The name of the slider to get

		Returns
		-------
		object :
			The DCC Thing
		'''
		return self.ctrl.attrs.get(sliderName)

	@staticmethod
	@undoable
	def buildRestAbc(abcMesh, name):
		''' Build the rest Alembic node in the dcc

		Parameters
		----------
		abcMesh : IPolyMesh
			The Alembic mesh object
		name : str
			The name of the object to create

		Returns
		-------

		'''
		mesh = DummyMesh(name, DB)
		mesh.verts = getSampleArray(abcMesh)
		mesh.faces, mesh.counts = getStaticMeshData(abcMesh)
		mesh.uvs = getUvSample(abcMesh)

	@staticmethod
	def vertCount(meshName):
		''' Get the vert count of the given DCC Object

		Parameters
		----------
		meshName : str
			The name of the mesh to check

		Returns
		-------
		int :
			The Number of verts
		'''
		mesh = DB.meshes[meshName]
		return len(mesh.verts)

	@undoable
	def loadAbc(self, abcMesh, js, pBar=None):
		''' Load the shapes from an alembic file onto an already-created system

		Parameters
		----------
		abcMesh : IPolyMesh
			The Alembic mesh to load shapes from
		js : dict
			The simplex definition dictionary
		pBar : QProgressDialog, optional
			 (Default value = None)

		Returns
		-------

		'''
		shapes = js["shapes"]
		if js['encodingVersion'] > 1:
			shapes = [i['name'] for i in shapes]
		pointPositions = getSampleArray(abcMesh)
		for name, ppos in zip(shapes, pointPositions):
			dummyShape = self.shapeNode.shapes[name]
			dummyShape.points = ppos

	def getAllShapeVertices(self, shapes, pBar=None):
		''' Load all shape vertices into the simplex system for processing

		Parameters
		----------
		shapes : [Shape, ...]
			A list of simplex Shape objects to get positions for

		pBar : QProgressDialog, optional
			 (Default value = None)

		Returns
		-------

		'''
		for i, shape in enumerate(shapes):
			verts = self.getShapeVertices(shape)
			shape.verts = verts

	def getShapeVertices(self, shape):
		''' Get the point positions of a shape

		Parameters
		----------
		shape : Shape
			A simplex Shape object to get the vertices for

		Returns
		-------
		np.array :
			A numpy array of the point positions

		'''
		return shape.thing.points

	def pushAllShapeVertices(self, shapes, pBar=None):
		''' Push the computed vertex positions for the given shapes back to the DCC

		Parameters
		----------
		shapes : [Shape, ...]
			A list of simplex Shape objects

		pBar : QProgressDialog, optional
			 (Default value = None)

		Returns
		-------

		'''
		for shape in shapes:
			self.pushShapeVertices(shape)

	def pushShapeVertices(self, shape):
		''' Push the computed vertex positions for the given shape back to the DCC
		Parameters
		----------
		shape : Shape
			The Simplex Shape object to update

		Returns
		-------

		'''
		shape.thing.points = shape.verts

	def loadMeshTopology(self):
		''' Load the mesh topology from the DCC into the simplex interface '''
		# Here in Dummy I either have the data already or I don't, So nothing to do
		pass

	def exportAbc(self, dccMesh, abcMesh, js, world=False, pBar=None):
		''' Export a .smpx file

		Parameters
		----------
		dccMesh : object
			The DCC Mesh to export
		abcMesh : OPolyMesh
			The Alembic output mesh
		js : dict
			The definition dictionary
		world : bool
			Do the export in worldspace (Default value = False)
		pBar : QProgressDialog, optional
			 (Default value = None)

		Returns
		-------

		'''
		# export the data to alembic
		if dccMesh is None:
			dccMesh = self.mesh

		shapeDict = {i.name:i for i in self.simplex.shapes}

		shapeNames = js['shapes']
		if js['encodingVersion'] > 1:
			shapeNames = [i['name'] for i in shapeNames]
		shapes = [shapeDict[i] for i in shapeNames]

		schema = abcMesh.getSchema()

		if pBar is not None:
			pBar.show()
			pBar.setMaximum(len(shapes))
			spacerName = '_' * max(map(len, shapeNames))
			pBar.setLabelText('Exporting:\n{0}'.format(spacerName))
			QApplication.processEvents()

		for i, shape in enumerate(shapes):
			if pBar is not None:
				pBar.setLabelText('Exporting:\n{0}'.format(shape.name))
				pBar.setValue(i)
				QApplication.processEvents()
				if pBar.wasCanceled():
					return
			verts = mkSampleVertexPoints(shape.thing.points)
			if self.mesh.uvs is not None:
				# Alembic doesn't allow for self._uvs=None for some reason
				abcSample = OPolyMeshSchemaSample(verts, self.mesh.faces, self.mesh.counts, self.mesh.uvs)
			else:
				abcSample = OPolyMeshSchemaSample(verts, self.mesh.faces, self.mesh.counts)
			schema.set(abcSample)

	# Revision tracking
	def getRevision(self):
		''' Get the simplex revision number '''
		return self._revision

	def incrementRevision(self):
		''' Increment the revision number '''
		self._revision += 1
		return self._revision

	def setRevision(self, val):
		''' Manually set the revision numer

		Parameters
		----------
		val : int
			The value to set

		Returns
		-------

		'''
		self._revision = val

	# System level
	@undoable
	def renameSystem(self, name):
		''' Rename a simplex system

		Parameters
		----------
		name : str
			The new name


		Returns
		-------

		'''
		oldName = self.name
		self.name = name

		for dd in (DB.nodes, DB.ops, DB.bss, DB.meshes):
			oo = dd.get(oldName)
			if oo is not None:
				oo.name = self.name
				dd[self.name] = oo
				del dd[oldName]

	@undoable
	def deleteSystem(self):
		''' Delete the current system '''
		for dd in (DB.nodes, DB.ops, DB.bss, DB.meshes):
			if self.name in dd:
				del dd[self.name]
		self.name = None
		self.simplex = None


	# Shapes
	@undoable
	def createShape(self, shape, live=False, offset=10):
		''' Create a dcc shape

		Parameters
		----------
		shape : Shape
			A simplex shape object
		live : bool
			Whether this shape is live-connected (Default value = False)
		offset : float
			The offset of the created shape (Default value = 10)

		Returns
		-------

		'''
		newShape = DummyShape(shape.name, self.shapeNode)
		newShape.points = self.getShapeVertices(self.simplex.restShape)
		return newShape

	@undoable
	def extractWithDeltaShape(self, shape, live=True, offset=10.0):
		'''Make a mesh representing a shape. Can be live or not.
			Also, make a shapenode that is the delta of the change being made

		Parameters
		----------
		shape :

		live :
			 (Default value = True)
		offset :
			 (Default value = 10.0)

		Returns
		-------

		'''
		pass

	@undoable
	def extractWithDeltaConnection(self, shape, delta, value, live=True, offset=10.0):
		'''Extract a shape with a live partial delta added in.
			Useful for updating progressive shapes

		Parameters
		----------
		shape :

		delta :

		value :

		live :
			 (Default value = True)
		offset :
			 (Default value = 10.0)

		Returns
		-------

		'''
		pass

	@undoable
	def extractShape(self, shape, live=True, offset=10.0):
		'''Make a mesh representing a shape. Can be live or not.
			Can also store its starting shape and delta data

		Parameters
		----------
		shape :

		live :
			 (Default value = True)
		offset :
			 (Default value = 10.0)

		Returns
		-------

		'''
		pass

	@undoable
	def connectShape(self, shape, mesh=None, live=False, delete=False):
		'''Force a shape to match a mesh
			The "connect shape" button is:
				mesh=None, delete=True
			The "match shape" button is:
				mesh=someMesh, delete=False
			There is a possibility of a "make live" button:
				live=True, delete=False

		Parameters
		----------
		shape :

		mesh :
			 (Default value = None)
		live :
			 (Default value = False)
		delete :
			 (Default value = False)

		Returns
		-------

		'''
		pass

	@undoable
	def extractPosedShape(self, shape):
		''' ???

		Parameters
		----------
		shape :


		Returns
		-------

		'''
		pass

	@undoable
	def zeroShape(self, shape):
		''' Set a shape back to rest

		Parameters
		----------
		shape : Shape
			The simplex shpae to zero out

		Returns
		-------

		'''
		shape.thing.points = self.getShapeVertices(self.simplex.restShape)

	@undoable
	def deleteShape(self, toDelShape):
		''' Delete a shape from the system

		Parameters
		----------
		toDelShape :


		Returns
		-------

		'''
		del self.shapeNode[toDelShape.name]

	@undoable
	def renameShape(self, shape, name):
		''' Rename a shape

		Parameters
		----------
		shape : Shape
			The simplex Shape object to rename
		name : str
			The new name

		Returns
		-------

		'''
		shape.thing.name = name
		del self.shapeNode.shapes[shape.thing.name]
		self.shapeNode.shapes[name] = shape.thing

	@undoable
	def convertShapeToCorrective(self, shape):
		''' ???

		Parameters
		----------
		shape :


		Returns
		-------

		'''
		pass

	# Falloffs
	def createFalloff(self, falloff):
		''' Create a per-vert falloff weightmap

		Parameters
		----------
		falloff : Falloff
			The simplex Falloff object to create

		Returns
		-------

		'''
		DB.falloffs[falloff.name] = np.zeros(len(self.mesh.verts))
		# TODO: set the per-vert falloffs

	def duplicateFalloff(self, falloff, newFalloff):
		''' Create a new falloff from an already existing one

		Parameters
		----------
		falloff : Falloff
			The already existing falloff
		newFalloff : Falloff
			The newly created falloff to store the newly duplicated data

		Returns
		-------

		'''
		DB.falloffs[newFalloff.name] = copy.copy(DB.falloffs[falloff.name])

	def deleteFalloff(self, falloff):
		''' Delete a falloff object

		Parameters
		----------
		falloff : Falloff
			The Falloff object to delete

		Returns
		-------

		'''
		DB.falloffs.pop(falloff.name, None)

	def setFalloffData(self, falloff, splitType, axis, minVal, minHandle, maxHandle, maxVal, mapName):
		''' Set the data of a falloff object

		Parameters
		----------
		falloff :

		splitType :

		axis :

		minVal :

		minHandle :

		maxHandle :

		maxVal :

		mapName :


		Returns
		-------

		'''
		# TODO: set the per-vert falloffs
		pass # for eventual live splits

	def getFalloffThing(self, falloff):
		''' Get the thing for a given falloff

		Parameters
		----------
		falloff : Falloff
			The simplex falloff object to get


		Returns
		-------

		'''
		DB.falloffs.get(falloff.name)


	# Sliders
	@undoable
	def createSlider(self, slider):
		''' Create a slider object

		Parameters
		----------
		slider : Slider
			The simplex slider object to create

		Returns
		-------

		'''
		return DummyAttr(slider.name, 0.0, self.ctrl)

	@undoable
	def renameSlider(self, slider, name):
		''' Rename a slider

		Parameters
		----------
		slider : Slider
			The slider to rename
		name : str
			The new name

		Returns
		-------

		'''
		del self.ctrl[slider.thing.name]
		self.ctrl[name] = slider.thing
		slider.thing.name = name

	@undoable
	def setSliderRange(self, slider):
		''' Set the min and max of a slider

		Parameters
		----------
		slider : Slider
			The slider to set

		Returns
		-------

		'''
		pass

	@undoable
	def deleteSlider(self, toDelSlider):
		''' Delete a slider

		Parameters
		----------
		toDelSlider : Slider
			The slider to delete

		Returns
		-------

		'''
		del self.ctrl[toDelSlider.name]

	@undoable
	def addProgFalloff(self, prog, falloff):
		'''

		Parameters
		----------
		prog :

		falloff :


		Returns
		-------

		'''
		pass # for eventual live splits

	@undoable
	def removeProgFalloff(self, prog, falloff):
		'''

		Parameters
		----------
		prog :

		falloff :


		Returns
		-------

		'''
		pass # for eventual live splits

	@undoable
	def setSlidersWeights(self, sliders, weights):
		''' Set the values for the given sliders

		Parameters
		----------
		sliders : [Slider, ...]
			The sliders to set values for
		weights : [float, ...]
			The values to set

		Returns
		-------

		'''
		for slider, val in zip(sliders, weights):
			slider.thing.value = val

	@undoable
	def setSliderWeight(self, slider, weight):
		''' Set the value for a given slider

		Parameters
		----------
		slider : Slider
			The slider
		weight : float
			The value

		Returns
		-------

		'''
		slider.thing.value = weight

	@undoable
	def updateSlidersRange(self, sliders):
		''' Update the range of the given sliders

		Parameters
		----------
		sliders :


		Returns
		-------

		'''
		pass

	@undoable
	def extractTraversalShape(self, trav, shape, live=True, offset=10.0):
		''' Extract a shape from a traversal progression

		Parameters
		----------
		trav :

		shape :

		live :
			 (Default value = True)
		offset :
			 (Default value = 10.0)

		Returns
		-------

		'''
		pass

	@undoable
	def connectTraversalShape(self, trav, shape, mesh=None, live=True, delete=False):
		''' Connect a shape to a traversal progression

		Parameters
		----------
		trav :

		shape :

		mesh :
			 (Default value = None)
		live :
			 (Default value = True)
		delete :
			 (Default value = False)

		Returns
		-------

		'''
		pass

	# Combos
	@undoable
	def extractComboShape(self, combo, shape, live=True, offset=10.0):
		''' Extract a shape from a combo progression

		Parameters
		----------
		combo :

		shape :

		live :
			 (Default value = True)
		offset :
			 (Default value = 10.0)

		Returns
		-------

		'''
		pass

	@undoable
	def connectComboShape(self, combo, shape, mesh=None, live=True, delete=False):
		''' Connect a shape to a combo progression

		Parameters
		----------
		combo :

		shape :

		mesh :
			 (Default value = None)
		live :
			 (Default value = True)
		delete :
			 (Default value = False)

		Returns
		-------

		'''
		pass

	@staticmethod
	def setDisabled(op):
		''' Disable the output of any simplex systems

		Parameters
		----------
		op : The operator to disable


		Returns
		-------
		object :
			Some object that will allow us to re-enable the system

		'''
		return None

	@staticmethod
	def reEnable(helpers):
		''' Re-enable a simplex system

		Parameters
		----------
		helpers : object
			The helper object returned from setDisabled


		Returns
		-------

		'''
		pass

	@undoable
	def renameCombo(self, combo, name):
		'''Set the name of a Combo

		Parameters
		----------
		combo : Combo
			The combo to rename
		name : str
			The new name

		Returns
		-------

		'''
		pass

	# Data Access
	@staticmethod
	def getSimplexOperators():
		''' Get all simplex operators in the DCC '''
		return DB.ops.values()

	@staticmethod
	def getSimplexOperatorsByName(name):
		''' Get a simplex operator

		Parameters
		----------
		name : str
			The name to search for


		Returns
		-------
		object :
			The simplex operator for the DCC

		'''
		return DB.ops.get(name)

	@staticmethod
	def getSimplexOperatorsOnObject(thing):
		''' Get all simplex operators controlling an object

		Parameters
		----------
		thing : object
			A dcc object to check for simplex operators

		Returns
		-------
		[object, ...] :
			A list of simplex operators

		'''
		return thing.ops

	@staticmethod
	def getSimplexString(op):
		''' Get the simplex string from the given operator

		Parameters
		----------
		op : object
			The Simplex operator to get the definition from

		Returns
		-------
		str :
			The simplex definition

		'''
		return op.definition

	@staticmethod
	def getSimplexStringOnThing(thing, systemName):
		''' Get the definition on an object by name

		Parameters
		----------
		thing : object
			The DCC object to check for a simplex operator
		systemName : str
			The system name to check for

		Returns
		-------
		str :
			The simplex definition

		'''
		ops = thing.ops
		for op in thing.ops:
			if op.name == systemName:
				return op.definition
		return None

	@staticmethod
	def setSimplexString(op, val):
		''' Set the definition string on an object

		Parameters
		----------
		op : object
			The operator to set the definition on
		val : str
			The definition to set

		Returns
		-------
		type


		'''
		op.definition = val

	@staticmethod
	def selectObject(thing):
		'''Select an object in the DCC

		Parameters
		----------
		thing :


		Returns
		-------

		'''
		pass

	def selectCtrl(self):
		'''Select the system's control object'''
		pass

	@staticmethod
	def getObjectByName(name):
		''' Get an object by name

		Parameters
		----------
		name : str
			The name to search for

		Returns
		-------
		object :
			The found object

		'''
		# TODO: maybe also filter by type??
		return DB.meshes.get(name)

	@staticmethod
	def getObjectName(thing):
		''' Get the name of an object

		Parameters
		----------
		thing :


		Returns
		-------
		type


		'''
		return thing.name

	@staticmethod
	def staticUndoOpen():
		''' Open an undo chunk without knowledge of Simplex '''
		pass

	@staticmethod
	def staticUndoClose():
		''' Close an undo chunk without knowledge of Simplex '''
		pass

	def undoOpen(self):
		''' Open an undo chunk with knowledge of Simplex '''
		pass

	def undoClose(self):
		''' Close an undo chunk with knowledge of Simplex '''
		pass

	@classmethod
	def getPersistentFalloff(cls, thing):
		''' Get a representation of the given object that won't get deleted or garbage collected

		Parameters
		----------
		thing : object
			The thing to get a persistent representation of

		Returns
		-------
		object :
			The requested persistent object

		'''
		return cls.getObjectName(thing)

	@classmethod
	def loadPersistentFalloff(cls, thing):
		''' Get the usable representation of the given persistent thing

		Parameters
		----------
		thing : object
			A persistent representation

		Returns
		-------
		object :
			The requested volatile object

		'''
		return cls.getObjectByName(thing)

	@classmethod
	def getPersistentShape(cls, thing):
		''' Get a representation of the given object that won't get deleted or garbage collected

		Parameters
		----------
		thing : object
			The thing to get a persistent representation of

		Returns
		-------
		object :
			The requested persistent object

		'''
		return cls.getObjectName(thing)

	@classmethod
	def loadPersistentShape(cls, thing):
		''' Get the usable representation of the given persistent thing

		Parameters
		----------
		thing : object
			A persistent representation

		Returns
		-------
		object :
			The requested volatile object

		'''
		return cls.getObjectByName(thing)

	@classmethod
	def getPersistentSlider(cls, thing):
		''' Get a representation of the given object that won't get deleted or garbage collected

		Parameters
		----------
		thing : object
			The thing to get a persistent representation of

		Returns
		-------
		object :
			The requested persistent object

		'''
		return cls.getObjectName(thing)

	@classmethod
	def loadPersistentSlider(cls, thing):
		''' Get the usable representation of the given persistent thing

		Parameters
		----------
		thing : object
			A persistent representation

		Returns
		-------
		object :
			The requested volatile object

		'''
		return cls.getObjectByName(thing)

	@staticmethod
	def getSelectedObjects():
		''' Get the selected objects '''
		# Here in the dummy interface, we short-circuit this
		# And return a default selected object called "thing"
		return [DummyNode("thing")]


class SliderDispatch(QtCore.QObject):
	''' '''
	valueChanged = Signal()
	def __init__(self, node, parent=None):
		super(SliderDispatch, self).__init__(parent)

	def emitValueChanged(self, *args, **kwargs):
		'''

		Parameters
		----------
		*args :

		**kwargs :


		Returns
		-------

		'''
		self.valueChanged.emit()


class Dispatch(QtCore.QObject):
	''' '''
	beforeNew = Signal()
	afterNew = Signal()
	beforeOpen = Signal()
	afterOpen = Signal()
	undo = Signal()
	redo = Signal()

	def __init__(self, parent=None):
		super(Dispatch, self).__init__(parent)

	def connectCallbacks(self):
		''' '''
		pass

	def disconnectCallbacks(self):
		''' '''
		pass

	def emitBeforeNew(self, *args, **kwargs):
		'''

		Parameters
		----------
		*args :

		**kwargs :


		Returns
		-------

		'''
		self.beforeNew.emit()

	def emitAfterNew(self, *args, **kwargs):
		'''

		Parameters
		----------
		*args :

		**kwargs :


		Returns
		-------

		'''
		self.afterNew.emit()

	def emitBeforeOpen(self, *args, **kwargs):
		'''

		Parameters
		----------
		*args :

		**kwargs :


		Returns
		-------

		'''
		self.beforeOpen.emit()

	def emitAfterOpen(self, *args, **kwargs):
		'''

		Parameters
		----------
		*args :

		**kwargs :


		Returns
		-------

		'''
		self.afterOpen.emit()

	def emitUndo(self, *args, **kwargs):
		'''

		Parameters
		----------
		*args :

		**kwargs :


		Returns
		-------

		'''
		self.undo.emit()

	def emitRedo(self, *args, **kwargs):
		'''

		Parameters
		----------
		*args :

		**kwargs :


		Returns
		-------

		'''
		self.redo.emit()

DISPATCH = Dispatch()

def rootWindow():
	''' '''
	return None


