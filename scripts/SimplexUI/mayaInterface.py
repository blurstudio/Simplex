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

#pylint: disable=invalid-name
import re, json, sys
from contextlib import contextmanager
from functools import wraps
import maya.cmds as cmds
import maya.OpenMaya as om
from SimplexUI.Qt import QtCore
from SimplexUI.Qt.QtCore import Signal
from SimplexUI.Qt.QtWidgets import QApplication, QSplashScreen, QDialog, QMainWindow
from alembic.AbcGeom import OPolyMeshSchemaSample, OV2fGeomParamSample, GeometryScope
from imath import V2fArray, V3fArray, IntArray, UnsignedIntArray
from ctypes import c_float
try:
	import numpy as np
except ImportError:
	np = None



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
	def stacker(*args, **kwargs):
		inst = None
		if args and isinstance(args[0], DCC):
			inst = args[0]
		with undoContext(inst):
			return f(*args, **kwargs)
	return stacker

# temporarily disconnect inputs from a list of nodes and plugs
def doDisconnect(targets, testCnxType=("double", "float")):
	if not isinstance(targets, (list, tuple)):
		targets = [targets]
	cnxs = {}
	for target in targets:
		tcnx = {}
		cnxs[target] = tcnx

		cnx = cmds.listConnections(target, plugs=True, destination=False, source=True, connections=True)
		if cnx is None:
			cnx = []

		for i in range(0, len(cnx), 2):
			cnxType = cmds.getAttr(cnx[i], type=True)
			if cnxType not in testCnxType:
				continue
			tcnx[cnx[i+1]] = cnx[i]
			cmds.disconnectAttr(cnx[i+1], cnx[i])
	return cnxs

def doReconnect(cnxs):
	for tdict in cnxs.itervalues():
		for s, d in tdict.iteritems():
			if not cmds.isConnected(s, d):
				cmds.connectAttr(s, d, force=True)

@contextmanager
def disconnected(targets, testCnxType=("double", "float")):
	cnxs = doDisconnect(targets, testCnxType=testCnxType)
	try:
		yield cnxs
	finally:
			doReconnect(cnxs)


class DCC(object):
	program = "maya"
	def __init__(self, simplex, stack=None):
		if not cmds.pluginInfo("simplex_maya", query=True, loaded=True):
			cmds.loadPlugin("simplex_maya")
		self.undoDepth = 0
		self.name = None # the name of the system
		self.mesh = None # the mesh object with the system
		self.ctrl = None # the object that has all the controllers on it
		self.shapeNode = None # the deformer object
		self.op = None # the simplex object
		self.simplex = simplex # the abstract representation of the setup
		self._live = True
		self.sliderMul = self.simplex.sliderMul

	#def __deepcopy__(self, memo):
		# '''
		# I don't actually need to define this here because I know that
		# all of the maya "objects" store here are just strings
		# But if they *weren't* (like in XSI) I would need to skip
		# the maya objects when deepcopying, otherwise I might access
		# a deleted scene node and crash everything
		# And if we did skip things, I would also need to store a
		# persistent accessor to use in case we get back to here
		# through an undo
		# '''
		#pass

	def _checkAllShapeValidity(self, shapeNames):
		''' Check shapes to see if they exist, and either gather the missing files, or
		Load the proper data onto the shapes
		'''
		# Keep the set ordered, but make a set for quick checking
		missingNameSet = set()
		missingNames = []
		seen = set()

		# Get the blendshape weight names
		try:
			# GOOD GOD. This is because in maya 2016.5, if you delete a multi-instance
			# then listAttr, *it lists the deleted ones, and skips the ones at the end*
			# So I have to use aliasAttr and filter for the weights
			aliases = cmds.aliasAttr(self.shapeNode, query=True) or []
			attrs = [aliases[i] for i in range(0, len(aliases), 2)
					if aliases[i+1].startswith('weight[')]
			attrs = set(attrs)

		except ValueError:
			attrs = set()

		for shapeName in shapeNames:
			if shapeName in seen:
				continue
			seen.add(shapeName)
			if shapeName not in attrs:
				if shapeName not in missingNameSet:
					missingNameSet.add(shapeName)
					missingNames.append(shapeName)
		return missingNames, len(attrs)

	def preLoad(self, simp, simpDict, create=True, pBar=None):
		cmds.undoInfo(state=False)
		if pBar is not None:
			pBar.setLabelText("Loading Connections")
			QApplication.processEvents()
		ev = simpDict['encodingVersion']

		shapeNames = simpDict.get('shapes')
		if not shapeNames:
			return

		if ev > 1:
			shapeNames = [i['name'] for i in shapeNames]

		toMake, nextIndex = self._checkAllShapeValidity(shapeNames)

		if toMake:
			if not create:
				raise RuntimeError("Missing Shapes: {}".format(toMake))

			if pBar is not None:
				spacer = "_" * max(map(len, toMake))
				pBar.setMaximum(len(toMake))
				pBar.setLabelText("Creating Empty Shape:\n{0}".format(spacer))
				pBar.setValue(0)
				QApplication.processEvents()

			for i, shapeName in enumerate(toMake):
				if pBar is not None:
					pBar.setLabelText("Creating Empty Shape:\n{0}".format(shapeName))
					pBar.setValue(i)
					QApplication.processEvents()

				newShape = cmds.duplicate(self.mesh, name=shapeName)[0]
				cmds.delete(newShape, constructionHistory=True)
				index = self._firstAvailableIndex()
				cmds.blendShape(self.shapeNode, edit=True, target=(self.mesh, index, newShape, 1.0))
				weightAttr = "{0}.weight[{1}]".format(self.shapeNode, index)
				thing = cmds.ls(weightAttr)[0]
				cmds.connectAttr("{0}.weights[{1}]".format(self.op, nextIndex), thing)
				cmds.delete(newShape)
				nextIndex += 1
		return None

	def postLoad(self, simp, preRet):
		self._tmp = None
		cmds.undoInfo(state=True)

	# System IO
	@undoable
	def loadNodes(self, simp, thing, create=True, pBar=None):
		"""
		Create a new system based on the simplex tree
		Build any DCC objects that are missing if create=True
		Raises a runtime error if missing objects are found and
		create=False
		"""
		self.name = simp.name
		self.mesh = thing

		# find/build the shapeNode
		bsn = '{0}_BS'.format(self.name)
		shapeNodes = [h for h in cmds.listHistory(thing) if cmds.nodeType(h) == "blendShape"]
		shapeNodes = [i for i in shapeNodes if i.endswith(bsn)]

		if not shapeNodes:
			if not create:
				raise RuntimeError("Blendshape operator not found with creation turned off: {0}".format(bsn))
			# Unlock the normals on the rest head because blendshapes don't work with locked normals
			# and you can't really do this after the blendshape has been created
			cmds.polyNormalPerVertex(self.mesh, ufn=True)
			cmds.polySoftEdge(self.mesh, a=180, ch=1)
			cmds.delete(self.mesh, constructionHistory=True)

			self.shapeNode = cmds.blendShape(self.mesh, name="{0}_BS".format(self.name))[0]
		else:
			self.shapeNode = shapeNodes[0]

		# find/build the operator
		# GODDAMMIT, why does maya return None instead of an empty list?????
		ops = cmds.listConnections("{0}.{1}".format(self.shapeNode, "message"), source=False, destination=True, type="simplex_maya")
		if not ops:
			if not create:
				raise RuntimeError("Simplex operator not found with creation turned off")
			self.op = cmds.createNode("simplex_maya", name=self.name)
			cmds.addAttr(self.op, longName="revision", attributeType="long")
			cmds.addAttr(self.op, longName="shapeMsg", attributeType="message")
			cmds.addAttr(self.op, longName="ctrlMsg", attributeType="message")
			cmds.connectAttr("{0}.{1}".format(self.shapeNode, "message"), "{0}.{1}".format(self.op, "shapeMsg"))
		else:
			ops = [i for i in ops if i.endswith(self.name)]
			self.op = ops[0]

		# find/build the ctrl object
		ctrlCnx = cmds.listConnections("{0}.{1}".format(self.op, "ctrlMsg"), source=True, destination=False)
		if not ctrlCnx:
			if not create:
				raise RuntimeError("Control object not found with creation turned off")
			self.ctrl = cmds.group(empty=True, name="{0}_CTRL".format(self.name))
			for attr in [".tx", ".ty", ".tz", ".rx", ".ry", ".rz", ".sx", ".sy", ".sz", ".v"]:
				cmds.setAttr(self.ctrl+attr, keyable=False, channelBox=False)
			cmds.addAttr(self.ctrl, longName="solver", attributeType="message")
			cmds.connectAttr("{0}.{1}".format(self.ctrl, "solver"), "{0}.{1}".format(self.op, "ctrlMsg"))
		else:
			self.ctrl = ctrlCnx[0]

	def getShapeThing(self, shapeName):
		s = cmds.ls("{0}.{1}".format(self.shapeNode, shapeName))
		if not s:
			return None
		return s[0]

	def getSliderThing(self, sliderName):
		things = cmds.ls("{0}.{1}".format(self.ctrl, sliderName))
		if not things:
			return None
		return things[0]

	@staticmethod
	@undoable
	def buildRestAbc(abcMesh, name):
		if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
			cmds.loadPlugin("AbcImport")
			if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
				raise RuntimeError("Unable to load the AbcImport plugin")

		abcPath = str(abcMesh.getArchive())

		abcNode = cmds.createNode('AlembicNode')
		cmds.setAttr(abcNode + ".abc_File", abcPath, type="string")
		cmds.setAttr(abcNode + ".speed", 24) # Is this needed anymore?
		cmds.setAttr(abcNode + ".time", 0)

		importHead = cmds.polySphere(name='{0}_SIMPLEX'.format(name), constructionHistory=False)[0]
		importHeadShape = [i for i in cmds.listRelatives(importHead, shapes=True)][0]

		cmds.connectAttr(abcNode+".outPolyMesh[0]", importHeadShape + ".inMesh")
		vertCount = cmds.polyEvaluate(importHead, vertex=True) # force update
		cmds.disconnectAttr(abcNode+".outPolyMesh[0]", importHeadShape + ".inMesh")
		cmds.sets(importHead, e=True, forceElement="initialShadingGroup")
		cmds.delete(abcNode)
		return importHead

	@undoable
	def loadAbc(self, abcMesh, js, pBar=None):
		# UGH, I *REALLY* hate that this is faster
		# But if I want to be "pure" about it, I should just bite the bullet
		# and do the direct alembic manipulation in C++

		if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
			cmds.loadPlugin("AbcImport")
			if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
				raise RuntimeError("Unable to load the AbcImport plugin")

		abcPath = str(abcMesh.getArchive())

		abcNode = cmds.createNode('AlembicNode')
		cmds.setAttr(abcNode + ".abc_File", abcPath, type="string")
		cmds.setAttr(abcNode + ".speed", 24) # Is this needed anymore?
		shapes = js["shapes"]
		shapeDict = {i.name:i for i in self.simplex.shapes}

		if js['encodingVersion'] > 1:
			shapes = [i['name'] for i in shapes]

		importHead = cmds.polySphere(name='importHead', constructionHistory=False)[0]
		importHeadShape = [i for i in cmds.listRelatives(importHead, shapes=True)][0]

		cmds.connectAttr(abcNode+".outPolyMesh[0]", importHeadShape + ".inMesh")
		vertCount = cmds.polyEvaluate(importHead, vertex=True) # force update
		cmds.disconnectAttr(abcNode+".outPolyMesh[0]", importHeadShape + ".inMesh")

		importBS = cmds.blendShape(self.mesh, importHead)[0]
		cmds.blendShape(importBS, edit=True, weight=[(0, 1.0)])
		# Maybe get shapeNode from self.mesh??
		inTarget = importBS + '.inputTarget[0].inputTargetGroup[0].inputTargetItem[6000].inputGeomTarget'
		cmds.disconnectAttr(self.mesh + '.worldMesh[0]', inTarget)
		importOrig = [i for i in cmds.listRelatives(importHead, shapes=True) if i.endswith('Orig')][0]
		cmds.connectAttr(abcNode + ".outPolyMesh[0]", importOrig + ".inMesh")

		if pBar is not None:
			pBar.show()
			pBar.setMaximum(len(shapes))
			longName = max(shapes, key=len)
			pBar.setValue(1)
			pBar.setLabelText("Loading:\n{0}".format("_" * len(longName)))

		for i, shapeName in enumerate(shapes):
			if pBar is not None:
				pBar.setValue(i)
				pBar.setLabelText("Loading:\n{0}".format(shapeName))
				QApplication.processEvents()
				if pBar.wasCanceled():
					return
			index = self._getShapeIndex(shapeDict[shapeName])
			cmds.setAttr(abcNode + ".time", i)

			outAttr = "{0}.worldMesh[0]".format(importHead)
			tgn = "{0}.inputTarget[0].inputTargetGroup[{1}]".format(self.shapeNode, index)
			inAttr = "{0}.inputTargetItem[6000].inputGeomTarget".format(tgn)

			cmds.connectAttr(outAttr, inAttr, force=True)
			cmds.disconnectAttr(outAttr, inAttr)
		cmds.delete(abcNode)
		cmds.delete(importHead)

	def getAllShapeVertices(self, shapes, pBar=None):
		sl = om.MSelectionList()
		sl.add(self.mesh)
		thing = om.MDagPath()
		sl.getDagPath(0, thing)
		meshFn = om.MFnMesh(thing)
		ptCount = meshFn.numVertices()
		with disconnected(self.shapeNode) as cnx:
			shapeCnx = cnx[self.shapeNode]
			for v in shapeCnx.itervalues():
				cmds.setAttr(v, 0.0)

			if pBar is not None:
				# find the longest name for displaying stuff
				sns = '_' * max(map(len, [s.name for s in shapes]))
				pBar.setLabelText("Getting Shape:\n{0}".format(sns))
				QApplication.processEvents()

			for i, shape in enumerate(shapes):
				if pBar is not None:
					pBar.setLabelText("Getting Shape:\n{0}".format(shape.name))
					pBar.setValue((100.0 * i) / len(shapes))
					QApplication.processEvents()

				cmds.setAttr(shape.thing, 1.0)

				if np is not None:
					rawPts = meshFn.getRawPoints()
					cta = (c_float * ptCount * 3).from_address(int(rawPts))
					out = np.ctypeslib.as_array(cta)
					out = np.copy(out)
					out = out.reshape((-1, 3))
				else:
					flatverts = cmds.xform("{0}.vtx[*]".format(self.mesh), translation=1, query=1, worldSpace=False)
					args = [iter(flatverts)] * 3
					out = zip(*args)

				cmds.setAttr(shape.thing, 0.0)
				shape.verts = out

	def getShapeVertices(self, shape):
		with disconnected(self.shapeNode) as cnx:
			shapeCnx = cnx[self.shapeNode]
			for v in shapeCnx.itervalues():
				cmds.setAttr(v, 0.0)
			cmds.setAttr(shape.thing, 1.0)
			if np is None:
				flatverts = cmds.xform("{0}.vtx[*]".format(self.mesh), translation=1, query=1, worldSpace=False)
				args = [iter(flatverts)] * 3
				out = zip(*args)
			else:
				sl = om.MSelectionList()
				sl.add(self.mesh)
				thing = om.MDagPath()
				sl.getDagPath(0, thing)
				meshFn = om.MFnMesh(thing)
				rawPts = meshFn.getRawPoints()
				ptCount = meshFn.numVertices()
				cta = (c_float * ptCount * 3).from_address(int(rawPts))
				out = np.ctypeslib.as_array(cta)
				out = np.copy(out)
				out = out.reshape((-1, 3))
			return out

	def pushAllShapeVertices(self, shapes, pBar=None):
		# take all the verts stored on the shapes
		# and push them back to the DCC
		for shape in shapes:
			self.pushShapeVertices(shape)

	def pushShapeVertices(self, shape):
		# Push the vertices for a specific shape back to the DCC
		pass

	def loadMeshTopology(self):
		self._faces, self._counts, self._uvs = self._exportAbcFaces(self.mesh)

	def _getMeshVertices(self, mesh, world=False):
		# Get the MDagPath from the name of the mesh
		sl = om.MSelectionList()
		sl.add(mesh)
		thing = om.MDagPath()
		sl.getDagPath(0, thing)
		meshFn = om.MFnMesh(thing)
		vts = om.MPointArray()
		if world:
			space = om.MSpace.kWorld
		else:
			space = om.MSpace.kObject
		meshFn.getPoints(vts, space)
		return vts

	def _exportAbcVertices(self, mesh, world=False):
		vts = self._getMeshVertices(mesh, world=world)
		vertices = V3fArray(vts.length())
		for i in range(vts.length()):
			vertices[i] = (vts[i].x, vts[i].y, vts[i].z)
		return vertices

	def _exportAbcFaces(self, mesh):
		# Get the MDagPath from the name of the mesh
		sl = om.MSelectionList()
		sl.add(mesh)
		thing = om.MDagPath()
		sl.getDagPath(0, thing)
		meshFn = om.MFnMesh(thing)

		faces = []
		faceCounts = []
		#uvArray = []
		uvIdxArray = []
		vIdx = om.MIntArray()

		util = om.MScriptUtil()
		util.createFromInt(0)
		uvIdxPtr = util.asIntPtr()
		uArray = om.MFloatArray()
		vArray = om.MFloatArray()
		meshFn.getUVs(uArray, vArray)
		hasUvs = uArray.length() > 0

		for i in range(meshFn.numPolygons()):
			meshFn.getPolygonVertices(i, vIdx)
			face = []
			for j in reversed(xrange(vIdx.length())):
				face.append(vIdx[j])
				if hasUvs:
					meshFn.getPolygonUVid(i, j, uvIdxPtr)
					uvIdx = util.getInt(uvIdxPtr)
					if uvIdx >= uArray.length() or uvIdx < 0:
						uvIdx = 0
					uvIdxArray.append(uvIdx)

			face = [vIdx[j] for j in reversed(xrange(vIdx.length()))]
			faces.extend(face)
			faceCounts.append(vIdx.length())

		abcFaceIndices = IntArray(len(faces))
		for i in xrange(len(faces)):
			abcFaceIndices[i] = faces[i]

		abcFaceCounts = IntArray(len(faceCounts))
		for i in xrange(len(faceCounts)):
			abcFaceCounts[i] = faceCounts[i]

		if hasUvs:
			abcUVArray = V2fArray(len(uArray))
			for i in xrange(len(vArray)):
				abcUVArray[i] = (uArray[i], vArray[i])
			abcUVIdxArray = UnsignedIntArray(len(uvIdxArray))
			for i in xrange(len(uvIdxArray)):
				abcUVIdxArray[i] = uvIdxArray[i]
			uv = OV2fGeomParamSample(abcUVArray, abcUVIdxArray, GeometryScope.kFacevaryingScope)
		else:
			uv = None

		return abcFaceIndices, abcFaceCounts, uv

	def exportAbc(self, dccMesh, abcMesh, js, world=False, pBar=None):
		# export the data to alembic
		if dccMesh is None:
			dccMesh = self.mesh

		shapeDict = {i.name:i for i in self.simplex.shapes}

		shapeNames = js['shapes']
		if js['encodingVersion'] > 1:
			shapeNames = [i['name'] for i in shapeNames]
		shapes = [shapeDict[i] for i in shapeNames]

		faces, counts, uvs = self._exportAbcFaces(dccMesh)
		schema = abcMesh.getSchema()

		if pBar is not None:
			pBar.show()
			pBar.setMaximum(len(shapes))
			spacerName = '_' * max(map(len, shapeNames))
			pBar.setLabelText('Exporting:\n{0}'.format(spacerName))
			QApplication.processEvents()

		with disconnected(self.shapeNode) as cnx:
			shapeCnx = cnx[self.shapeNode]
			for v in shapeCnx.itervalues():
				cmds.setAttr(v, 0.0)
			for i, shape in enumerate(shapes):
				if pBar is not None:
					pBar.setLabelText('Exporting:\n{0}'.format(shape.name))
					pBar.setValue(i)
					QApplication.processEvents()
					if pBar.wasCanceled():
						return
				cmds.setAttr(shape.thing, 1.0)
				verts = self._exportAbcVertices(dccMesh, world=world)
				if uvs is not None:
					abcSample = OPolyMeshSchemaSample(verts, faces, counts, uvs)
				else:
					abcSample = OPolyMeshSchemaSample(verts, faces, counts)
				schema.set(abcSample)
				cmds.setAttr(shape.thing, 0.0)

	# Revision tracking
	def getRevision(self):
		try:
			return cmds.getAttr("{0}.{1}".format(self.op, "revision"))
		except ValueError:
			return None # object does not exist

	@undoable
	def incrementRevision(self):
		value = self.getRevision()
		if value is None:
			return
		cmds.setAttr("{0}.{1}".format(self.op, "revision"), value + 1)
		jsString = self.simplex.dump()
		self.setSimplexString(self.op, jsString)
		return value + 1

	@undoable
	def setRevision(self, val):
		cmds.setAttr("{0}.{1}".format(self.op, "revision"), val)

	# System level
	@undoable
	def renameSystem(self, name):
		nn = self.mesh.replace(self.name, name)
		self.mesh = cmds.rename(self.mesh, nn)

		nn = self.ctrl.replace(self.name, name)
		self.ctrl = cmds.rename(self.ctrl, nn)

		nn = self.shapeNode.replace(self.name, name)
		self.shapeNode = cmds.rename(self.shapeNode, nn)

		nn = self.op.replace(self.name, name)
		self.op = cmds.rename(self.op, nn)

		self.name = name

	@undoable
	def deleteSystem(self):
		cmds.delete(self.ctrl)
		cmds.delete(self.shapeNode)
		cmds.delete(self.op)
		self.ctrl = None # the object that has all the controllers on it
		self.shapeNode = None # the deformer object
		self.op = None # the simplex object
		self.simplex = None

	# Shapes
	@undoable
	def createShape(self, shape, live=False, offset=10):
		with disconnected(self.shapeNode):
			try:
				attrs = cmds.listAttr("{0}.weight[*]".format(self.shapeNode))
			except ValueError:
				pass
				# Maya throws an error if there aren't any instead of 
				# just returning an empty list
			else:
				for attr in attrs:
					cmds.setAttr("{0}.{1}".format(self.shapeNode, attr), 0.0)
			newShape = cmds.duplicate(self.mesh, name=shape.name)[0]

		cmds.delete(newShape, constructionHistory=True)
		index = self._firstAvailableIndex()
		cmds.blendShape(self.shapeNode, edit=True, target=(self.mesh, index, newShape, 1.0))
		weightAttr = "{0}.weight[{1}]".format(self.shapeNode, index)
		thing = cmds.ls(weightAttr)[0]

		shapeIndex = len(shape.simplex.shapes) - 1
		cmds.connectAttr("{0}.weights[{1}]".format(self.op, shapeIndex), thing)

		if live:
			cmds.xform(newShape, relative=True, translation=[offset, 0, 0])
		else:
			cmds.delete(newShape)

		return thing

	def _firstAvailableIndex(self):
		aliases = cmds.aliasAttr(self.shapeNode, query=True)
		idxs = set()
		if not aliases:
			return 0
		for alias in aliases:
			match = re.search(r'\[\d+\]', alias)
			if not match:
				continue # No index found for the current shape
			idxs.add(int(match.group().strip('[]')))

		for i in xrange(len(idxs) + 1):
			if i not in idxs:
				return i
		# there should be no way to get here, but just in case:
		return len(idxs) + 1

	def _getShapeIndex(self, shape):
		aName = cmds.attributeName(shape.thing)
		aliases = cmds.aliasAttr(self.shapeNode, query=True)
		idx = aliases.index(aName)
		raw = aliases[idx+1]
		matches = re.findall(r'\[\d+\]', raw)
		if not matches:
			raise IndexError("No index found for the current shape")
		return int(matches[-1].strip('[]'))

	@undoable
	def extractWithDeltaShape(self, shape, live=True, offset=10.0):
		""" Make a mesh representing a shape. Can be live or not.
			Also, make a shapenode that is the delta of the change being made
		"""
		with disconnected(self.shapeNode) as cnx:
			shapeCnx = cnx[self.shapeNode]
			for v in shapeCnx.itervalues():
				cmds.setAttr(v, 0.0)

			# store the delta shape
			delta = cmds.duplicate(self.mesh, name="{0}_Delta".format(shape.name))[0]

			# Extract the shape
			cmds.setAttr(shape.thing, 1.0)
			extracted = cmds.duplicate(self.mesh, name="{0}_Extract".format(shape.name))[0]

			# Store the initial shape
			init = cmds.duplicate(extracted, name="{0}_Init".format(shape.name))[0]

		# clear old orig objects
		for item in [delta, extracted, init]:
			self._clearShapes(item, doOrig=True)

		# build the deltaObj system
		bs = cmds.blendShape(delta, name="{0}_DeltaBS".format(shape.name))[0]

		cmds.blendShape(bs, edit=True, target=(delta, 0, init, 1.0))
		cmds.blendShape(bs, edit=True, target=(delta, 1, extracted, 1.0))

		cmds.setAttr("{0}.{1}".format(bs, init), -1.0)
		cmds.setAttr("{0}.{1}".format(bs, extracted), 1.0)

		# Cleanup
		nodeDict = dict(Delta=delta, Init=init)
		repDict = self._reparentDeltaShapes(extracted, nodeDict, bs)

		# Shift the extracted shape to the side
		cmds.xform(extracted, relative=True, translation=[offset, 0, 0])

		if live:
			self.connectShape(shape, extracted, live, delete=False)

		return extracted, repDict['Delta']

	@undoable
	def extractWithDeltaConnection(self, shape, delta, value, live=True, offset=10.0):
		""" Extract a shape with a live partial delta added in.
			Useful for updating progressive shapes
		"""
		with disconnected(self.shapeNode):
			for attr in cmds.listAttr("{0}.weight[*]".format(self.shapeNode)):
				cmds.setAttr("{0}.{1}".format(self.shapeNode, attr), 0.0)

			# Pull out the rest shape. we will blend this guy to the extraction
			extracted = cmds.duplicate(self.mesh, name="{0}_Extract".format(shape.name))[0]

			cmds.setAttr(shape.thing, 1.0)
			# Store the initial shape
			init = cmds.duplicate(self.mesh, name="{0}_Init".format(shape.name))[0]

		# clear old orig objects
		for item in [init, extracted]:
			self._clearShapes(item, doOrig=True)

		deltaPar = cmds.listRelatives(delta, parent=True)[0]
		idx = 1

		# build the restObj system
		cmds.select(clear=True) # 'cause maya
		bs = cmds.blendShape(extracted, name="{0}_DeltaBS".format(shape.name))[0]
		cmds.blendShape(bs, edit=True, target=(extracted, 0, init, 1.0))
		cmds.blendShape(bs, edit=True, target=(extracted, 1, deltaPar, 1.0))

		cmds.setAttr("{0}.{1}".format(bs, init), 1.0)
		cmds.setAttr("{0}.{1}".format(bs, deltaPar), value)

		outCnx = '{0}.worldMesh[0]'.format(delta)
		inCnx = '{0}.inputTarget[0].inputTargetGroup[{1}].inputTargetItem[6000].inputGeomTarget'.format(bs, 1)
		cmds.connectAttr(outCnx, inCnx, force=True)
		cmds.aliasAttr(delta, '{0}.{1}'.format(bs, deltaPar))

		# Cleanup
		nodeDict = dict(Init=init)
		repDict = self._reparentDeltaShapes(extracted, nodeDict, bs)

		# Remove the tweak node, otherwise editing the input progressives
		# *inverts* the shape
		exShape = cmds.listRelatives(extracted, noIntermediate=1, shapes=1)[0]
		tweak = cmds.listConnections(exShape+'.tweakLocation', source=1, destination=0)
		if tweak:
			cmds.delete(tweak)

		# Shift the extracted shape to the side
		cmds.xform(extracted, relative=True, translation=[offset, 0, 0])

		if live:
			self.connectShape(shape, extracted, live, delete=False)

		return extracted

	@undoable
	def extractShape(self, shape, live=True, offset=10.0):
		""" Make a mesh representing a shape. Can be live or not.
			Can also store its starting shape and delta data
		"""
		with disconnected(self.shapeNode):
			for attr in cmds.listAttr("{0}.weight[*]".format(self.shapeNode)):
				cmds.setAttr("{0}.{1}".format(self.shapeNode, attr), 0.0)

			cmds.setAttr(shape.thing, 1.0)
			extracted = cmds.duplicate(self.mesh, name="{0}_Extract".format(shape.name))[0]

		# Shift the extracted shape to the side
		cmds.xform(extracted, relative=True, translation=[offset, 0, 0])

		if live:
			self.connectShape(shape, extracted, live, delete=False)
		return extracted

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
		if mesh is None:
			attrName = cmds.attributeName(shape.thing, long=True)
			mesh = "{0}_Extract".format(attrName)

		if not cmds.objExists(mesh):
			return

		index = self._getShapeIndex(shape)
		tgn = "{0}.inputTarget[0].inputTargetGroup[{1}]".format(self.shapeNode, index)
		cnx = mesh + 'Shape' if cmds.nodeType(mesh) == 'transform' else mesh

		outAttr = "{0}.worldMesh[0]".format(cnx) # Make sure to check the right shape object
		inAttr = "{0}.inputTargetItem[6000].inputGeomTarget".format(tgn)

		if not cmds.isConnected(outAttr, inAttr):
			cmds.connectAttr(outAttr, inAttr, force=True)

		if not live:
			cmds.disconnectAttr(outAttr, inAttr)
		if delete:
			cmds.delete(mesh)

	@undoable
	def extractPosedShape(self, shape):
		pass

	@undoable
	def zeroShape(self, shape):
		""" Set the shape to be completely zeroed """
		index = self._getShapeIndex(shape)
		tgn = "{0}.inputTarget[0].inputTargetGroup[{1}]".format(self.shapeNode, index)
		shapeInput = "{0}.inputTargetItem[6000]".format(tgn)
		cmds.setAttr("{0}.inputPointsTarget".format(shapeInput), 0, (), type='pointArray')
		cmds.setAttr("{0}.inputComponentsTarget".format(shapeInput), 0, '', type='componentList')

	@undoable
	def deleteShape(self, toDelShape):
		""" Remove a shape from the system """
		index = self._getShapeIndex(toDelShape)
		tgn = "{0}.inputTarget[0].inputTargetGroup[{1}]".format(self.shapeNode, index)
		cmds.removeMultiInstance(toDelShape.thing, b=True)
		cmds.removeMultiInstance(tgn, b=True)
		cmds.aliasAttr(toDelShape.thing, remove=True)
		self._rebuildConnections()

	def _rebuildConnections(self):
		# Rebuild the shape connections in the proper order
		cnxs = cmds.listConnections(self.op, plugs=True, source=False, destination=True, connections=True) or []
		for i, cnx in enumerate(cnxs):
			if i%2 == 0 and cnx.startswith('{0}.weights['.format(self.op)):
				cmds.disconnectAttr(cnxs[i], cnxs[i+1])

		for i, shape in enumerate(self.simplex.shapes):
			cmds.connectAttr("{0}.weights[{1}]".format(self.op, i), shape.thing)

	@undoable
	def forceRebuildConnections(self):
		self._rebuildConnections()

	@undoable
	def renameShape(self, shape, name):
		""" Change the name of the shape """
		cmds.aliasAttr(name, shape.thing)
		shape.thing = "{0}.{1}".format(self.shapeNode, name)

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

	def getFalloffThing(self, falloff):
		shape = [i for i in cmds.listRelatives(self.mesh, shapes=True)][0]
		return shape + "." + falloff.name

	# Sliders
	@undoable
	def createSlider(self, slider):
		index = slider.simplex.sliders.index(slider)
		cmds.addAttr(self.ctrl, longName=slider.name, attributeType="double", keyable=True, min=slider.minValue * self.sliderMul, max=slider.maxValue * self.sliderMul)
		thing = "{0}.{1}".format(self.ctrl, slider.name)
		cmds.connectAttr(thing, "{0}.sliders[{1}]".format(self.op, index))
		return thing

	@undoable
	def renameSlider(self, slider, name):
		""" Set the name of a slider """
		vals = [v.value for v in slider.prog.pairs]
		cnx = cmds.listConnections(slider.thing, plugs=True, source=False, destination=True)
		cmds.deleteAttr(slider.thing)
		cmds.addAttr(self.ctrl, longName=name, attributeType='double', keyable=True, min=self.sliderMul*min(vals), max=self.sliderMul*max(vals))
		newThing = "{0}.{1}".format(self.ctrl, name)
		slider.thing = newThing
		for c in cnx:
			cmds.connectAttr(newThing, c)

	@undoable
	def setSliderRange(self, slider):
		""" Set the range of a slider """
		vals = [v.value for v in slider.prog.pairs]
		attrName = '{0}.{1}'.format(self.ctrl, slider.name)
		cmds.addAttr(attrName, edit=True, min=self.sliderMul*min(vals), max=self.sliderMul*max(vals))

	@undoable
	def deleteSlider(self, toDelSlider):
		cmds.deleteAttr(toDelSlider.thing)

		# Rebuild the slider connections in the proper order
		# Get the sliders connections
		cnxs = cmds.listConnections(self.op, plugs=True, source=True, destination=False, connections=True)
		pairs = []
		for i, cnx in enumerate(cnxs):
			if cnx.startswith('{0}.sliders'.format(self.op)):
				cmds.disconnectAttr(cnxs[i+1], cnxs[i])

		for i, slider in enumerate(self.simplex.sliders):
			cmds.connectAttr(slider.thing, "{0}.sliders[{1}]".format(self.op, i))

	@undoable
	def addProgFalloff(self, prog, falloff):
		pass # for eventual live splits

	@undoable
	def removeProgFalloff(self, prog, falloff):
		pass # for eventual live splits

	@undoable
	def setSlidersWeights(self, sliders, weights):
		""" Set the weight of a slider. This does not change the definition """
		for slider, weight in zip(sliders, weights):
			cmds.setAttr(slider.thing, weight)

	@undoable
	def setSliderWeight(self, slider, weight):
		cmds.setAttr(slider.thing, weight)

	@undoable
	def updateSlidersRange(self, sliders):
		for slider in sliders:
			vals = [v.value for v in slider.prog.pairs]
			cmds.addAttr(slider.thing, edit=True, min=min(vals)*self.sliderMul, max=max(vals)*self.sliderMul)

	def _doesDeltaExist(self, combo, target):
		dshape = "{0}_DeltaShape".format(combo.name)
		if not cmds.ls(dshape):
			return None
		par = cmds.listRelatives(dshape, allParents=1)
		if not par:
			# there is apparently a transform object with the name
			return None

		par = cmds.ls(par[0], absoluteName=1)
		tar = cmds.ls(target, absoluteName=1)

		if par != tar:
			# the shape exists under a different transform ... ugh
			return None
		return par + "|" + dshape

	def _clearShapes(self, item, doOrig=False):
		aname = cmds.ls(item, long=1)[0]
		shapes = cmds.ls(cmds.listRelatives(item, shapes=1), long=1)
		baseName = aname.split('|')[-1]

		primary = '{0}|{1}Shape'.format(aname, baseName)
		orig = '{0}|{1}ShapeOrig'.format(aname, baseName)

		for shape in shapes:
			if shape == primary:
				continue
			elif shape == orig:
				if doOrig:
					cmds.delete(shape)
			else:
				cmds.delete(shape)

	# Combos
	def _reparentDeltaShapes(self, par, nodeDict, bsNode, toDelete=None):
		''' Reparent and clean up a single-transform delta system

		Put all the relevant shape nodes from the nodeDict under the par,
		and rename the shapes to maya's convention. Then build a callback
		to ensure the blendshape node isn't left floating

		par: The parent transform node
		nodeDict: A {simpleName: node} dictionary.
		bsNode: The blendshape node.
		toDelete: Any extra nodes to delte after all the node twiddling
		'''
		# Get the shapes and origs
		shapeDict = {}
		origDict = {}

		for name, node in nodeDict.iteritems():
			shape = cmds.listRelatives(node, noIntermediate=1, shapes=1)[0]
			shape = cmds.ls(shape, absoluteName=1)[0]
			if shape:
				shapeDict[name] = shape

			orig = shape + 'Orig'
			orig = cmds.ls(orig)
			if orig:
				origDict[name] = orig

		for name in nodeDict:
			for d, fmt in [(shapeDict, '{0}Shape{1}'), (origDict, '{0}Shape{1}Orig')]:
				shape = d.get(name)
				if shape is None:
					continue
				shapeUUID = cmds.ls(shape, uuid=1)[0]
				cmds.parent(shape, par, shape=True, relative=True)
				newShape = cmds.rename(cmds.ls(shapeUUID)[0], fmt.format(par, name))
				d[name] = newShape
				cmds.setAttr(newShape+'.intermediateObject', 1)
				cmds.hide(newShape)

			cmds.delete(nodeDict[name])

		if toDelete:
			cmds.delete(toDelete)

		# build the callback setup so the blendshape is deleted with the delta setup
		# along with a persistent scriptjob
		buildDeleterCallback(par, bsNode)
		buildDeleterScriptJob()

		return shapeDict

	def _createDelta(self, combo, target, tVal):
		""" Part of the combo extraction process.
		Combo shapes are fixit shapes added on top of any sliders.
		This means that the actual combo-shape by itself will not look good by itself,
		and that's bad for artist interaction.
		So we must create a setup to take the final sculpted shape, and subtract
		the any direct slider deformations to get the actual "combo shape" as a delta
		It is this delta shape that is then plugged into the system
		"""
		exists = self._doesDeltaExist(combo, target)
		if exists is not None:
			return exists

		# get floaters
		# As floaters can appear anywhere along any combo, they must
		# always be evaluated in isolation. For this reason, we will
		# always disconnect all floaters
		floatShapes = [i.thing for i in self.simplex.getFloatingShapes()]

		# get my shapes
		myShapes = [i.thing for i in combo.prog.getShapes()]

		with disconnected([self.op] + floatShapes + myShapes) as cnx:
			sliderCnx = cnx[self.op]

			# zero all slider vals on the op
			for a in sliderCnx.itervalues():
				cmds.setAttr(a, 0.0)

			# pull out the rest shape
			rest = cmds.duplicate(self.mesh, name="{0}_Rest".format(combo.name))[0]

			# set the combo values
			sliderVals = []
			for pair in combo.pairs:
				cmds.setAttr(sliderCnx[pair.slider.thing], pair.value*tVal)

			# Get the resulting slider values for later
			#weightPairs = []
			#self.shapeNode = None # the deformer object
			
			deltaObj = cmds.duplicate(self.mesh, name="{0}_Delta".format(combo.name))[0]
			base = cmds.duplicate(deltaObj, name="{0}_Base".format(combo.name))[0]

		# clear out all non-primary shapes so we don't have those 'Orig1' things floating around
		for item in [rest, deltaObj, base]:
			self._clearShapes(item, doOrig=True)

		# Build the delta blendshape setup
		bs = cmds.blendShape(deltaObj, name="{0}_DeltaBS".format(combo.name))[0]
		cmds.blendShape(bs, edit=True, target=(deltaObj, 0, target, 1.0))
		cmds.blendShape(bs, edit=True, target=(deltaObj, 1, base, 1.0))
		cmds.blendShape(bs, edit=True, target=(deltaObj, 2, rest, 1.0))
		cmds.setAttr("{0}.{1}".format(bs, target), 1.0)
		cmds.setAttr("{0}.{1}".format(bs, base), 1.0)
		cmds.setAttr("{0}.{1}".format(bs, rest), 1.0)

		# Cleanup
		nodeDict = dict(Delta=deltaObj)
		repDict = self._reparentDeltaShapes(target, nodeDict, bs, [rest, base])

		return repDict['Delta']

	def _createTravDelta(self, trav, target, tVal):
		""" Part of the traversal extraction process.
		Very similar to the combo extraction
		"""
		exists = self._doesDeltaExist(trav, target)
		if exists is not None:
			return exists

		# Traversals *MAY* depend on floaters, but that's complicated
		# I'm just gonna ignore them for now
		floatShapes = [i.thing for i in self.simplex.getFloatingShapes()]

		# Get all traversal shapes
		tShapes = []
		for oTrav in self.simplex.traversals:
			tShapes.extend([i.thing for i in oTrav.prog.getShapes()])

		with disconnected(self.op) as cnx:
			sliderCnx = cnx[self.op]

			# zero all slider vals on the op
			for a in sliderCnx.itervalues():
				cmds.setAttr(a, 0.0)

			with disconnected(floatShapes + tShapes):
				# pull out the rest shape
				rest = cmds.duplicate(self.mesh, name="{0}_Rest".format(trav.name))[0]

				mc = trav.multiplierCtrl
				if mc.controllerTypeName() == "Slider":
					cmds.setAttr(sliderCnx[mc.controller.thing], mc.value)
				else: #Combo
					combo = mc.controller
					for pair in combo.pairs:
						cmds.setAttr(sliderCnx[pair.slider.thing], pair.value)

				pc = trav.progressCtrl
				if pc.controllerTypeName() == "Slider":
					cmds.setAttr(sliderCnx[pc.controller.thing], tVal)
				else: #Combo
					combo = mc.controller
					for pair in combo.pairs:
						cmds.setAttr(sliderCnx[pair.slider.thing], tVal * pair.value)

				deltaObj = cmds.duplicate(self.mesh, name="{0}_Delta".format(trav.name))[0]
				base = cmds.duplicate(deltaObj, name="{0}_Base".format(trav.name))[0]

		# clear out all non-primary shapes so we don't have those 'Orig1' things floating around
		for item in [rest, deltaObj, base]:
			self._clearShapes(item, doOrig=True)

		# Build the delta blendshape setup
		bs = cmds.blendShape(deltaObj, name="{0}_DeltaBS".format(trav.name))[0]
		cmds.blendShape(bs, edit=True, target=(deltaObj, 0, target, 1.0))
		cmds.blendShape(bs, edit=True, target=(deltaObj, 1, base, 1.0))
		cmds.blendShape(bs, edit=True, target=(deltaObj, 2, rest, 1.0))
		cmds.setAttr("{0}.{1}".format(bs, target), 1.0)
		cmds.setAttr("{0}.{1}".format(bs, base), 1.0)
		cmds.setAttr("{0}.{1}".format(bs, rest), 1.0)

		# Cleanup
		nodeDict = dict(Delta=deltaObj)
		repDict = self._reparentDeltaShapes(target, nodeDict, bs, [rest, base])

		return repDict['Delta']

	@undoable
	def extractTraversalShape(self, trav, shape, live=True, offset=10.0):
		""" Extract a shape from a Traversal progression """
		floatShapes = self.simplex.getFloatingShapes()
		floatShapes = [i.thing for i in floatShapes]

		shapeIdx = trav.prog.getShapeIndex(shape)
		val = trav.prog.pairs[shapeIdx].value

		# TODO: There's probably a "better" way to handle this
		# I'm guessing that I might only want to gather traversals
		# that overlap, or maybe ones that are "contained" within this one?
		# Or ones that contain this one?
		# Or maybe ones that use the exact same controllers (but a different order)?
		# For now, just get 'em all
		tShapes = []
		for oTrav in self.simplex.traversals:
			tShapes.extend([i.thing for i in oTrav.prog.getShapes()])

		with disconnected(self.op) as cnx:
			sliderCnx = cnx[self.op]
			for a in sliderCnx.itervalues():
				cmds.setAttr(a, 0.0)

			with disconnected(floatShapes + tShapes):
				# zero all slider vals on the op

				mc = trav.multiplierCtrl
				if mc.controllerTypeName() == "Slider":
					cmds.setAttr(sliderCnx[mc.controller.thing], mc.value)
				else: #Combo
					combo = mc.controller
					for pair in combo.pairs:
						cmds.setAttr(sliderCnx[pair.slider.thing], pair.value)

				pc = trav.progressCtrl
				if pc.controllerTypeName() == "Slider":
					cmds.setAttr(sliderCnx[pc.controller.thing], val)
				else: #Combo
					combo = mc.controller
					for pair in combo.pairs:
						cmds.setAttr(sliderCnx[pair.slider.thing], val * pair.value)

				extracted = cmds.duplicate(self.mesh, name="{0}_Extract".format(shape.name))
				extracted = extracted[0]
				self._clearShapes(extracted)
				cmds.xform(extracted, relative=True, translation=[offset, 0, 0])
		self.connectTraversalShape(trav, shape, extracted, live=live, delete=False)
		cmds.select(extracted)
		return extracted

	@undoable
	def connectTraversalShape(self, trav, shape, mesh=None, live=True, delete=False):
		""" Connect a shape into a Traversal progression"""
		if mesh is None:
			attrName = cmds.attributeName(shape.thing, long=True)
			mesh = "{0}_Extract".format(attrName)
		shapeIdx = trav.prog.getShapeIndex(shape)
		tVal = trav.prog.pairs[shapeIdx].value
		delta = self._createTravDelta(trav, mesh, tVal)
		self.connectShape(shape, delta, live, delete)
		if delete:
			cmds.delete(mesh)

	@undoable
	def extractComboShape(self, combo, shape, live=True, offset=10.0):
		""" Extract a shape from a combo progression """
		floatShapes = self.simplex.getFloatingShapes()
		floatShapes = [i.thing for i in floatShapes]

		with disconnected(self.op) as cnx:
			sliderCnx = cnx[self.op]
			# zero all slider vals on the op
			for a in sliderCnx.itervalues():
				cmds.setAttr(a, 0.0)

			with disconnected(floatShapes):
				# set the combo values
				for pair in combo.pairs:
					cmds.setAttr(sliderCnx[pair.slider.thing], pair.value)

				extracted = cmds.duplicate(self.mesh, name="{0}_Extract".format(shape.name))[0]
				self._clearShapes(extracted)
				cmds.xform(extracted, relative=True, translation=[offset, 0, 0])
		self.connectComboShape(combo, shape, extracted, live=live, delete=False)
		cmds.select(extracted)
		return extracted

	@undoable
	def connectComboShape(self, combo, shape, mesh=None, live=True, delete=False):
		""" Connect a shape into a combo progression"""
		if mesh is None:
			attrName = cmds.attributeName(shape.thing, long=True)
			mesh = "{0}_Extract".format(attrName)
		shapeIdx = combo.prog.getShapeIndex(shape)
		tVal = combo.prog.pairs[shapeIdx].value
		delta = self._createDelta(combo, mesh, tVal)
		self.connectShape(shape, delta, live, delete)
		if delete:
			cmds.delete(mesh)

	@staticmethod
	def setDisabled(op):
		bss = list(set(cmds.listConnections(op, type='blendShape')))
		helpers = []
		for bs in bss:
			prop = '{0}.envelope'.format(bs)
			val = cmds.getAttr(prop)
			cmds.setAttr(prop, 0.0)
			if val != 0.0:
				helpers.append((prop, val))
		return helpers

	@staticmethod
	def reEnable(helpers):
		for prop, val in helpers:
			cmds.setAttr(prop, val)

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
		ops = cmds.ls(type="simplex_maya")
		out = []
		for op in ops:
			shapeNode = cmds.listConnections("{0}.{1}".format(op, "shapeMsg"), source=True, destination=False)
			if not shapeNode:
				continue

			# Now that I've got the connected blendshape node, I can walk down the deformer history
			# to see if I find my object. Eventually, I should probably set this up to deal with
			# multi-objects, or branched hierarchies. But for now, it works
			while shapeNode:
				try:
					shapeNode = cmds.listConnections("{0}.outputGeometry".format(shapeNode[0]), source=False, destination=True)
					if not shapeNode:
						break
					if shapeNode[0] == thing:
						out.append(op)
						break
				except ValueError:
					# object has no 'outputGeometry' plug
					break
		return out

	@staticmethod
	def getSimplexString(op):
		""" return the definition string from a simplex operator """
		return cmds.getAttr(op+".definition")

	@staticmethod
	def getSimplexStringOnThing(thing, systemName):
		""" return the simplex string of a specific system on a specific object """
		ops = DCC.getSimplexOperatorsOnObject(thing)
		for op in ops:
			js = DCC.getSimplexString(op)
			jdict = json.loads(js)
			if jdict["systemName"] == systemName:
				return js
		return None

	@staticmethod
	def setSimplexString(op, val):
		""" return the definition string from a simplex operator """
		return cmds.setAttr(op+".definition", val, type="string")

	@staticmethod
	def selectObject(thing):
		""" Select an object in the DCC """
		cmds.select([thing])

	def selectCtrl(self):
		""" Select the system's control object """
		if self.ctrl:
			self.selectObject(self.ctrl)

	@staticmethod
	def getObjectByName(name):
		""" return an object from the DCC by name """
		objs = cmds.ls(name)
		if not objs:
			return None
		return objs[0]

	@staticmethod
	def getObjectName(thing):
		""" return the text name of an object """
		return thing

	@staticmethod
	def staticUndoOpen():
		cmds.undoInfo(chunkName="SimplexOperation", openChunk=True)

	@staticmethod
	def staticUndoClose():
		cmds.undoInfo(closeChunk=True)

	def undoOpen(self):
		if self.undoDepth == 0:
			self.staticUndoOpen()
		self.undoDepth += 1

	def undoClose(self):
		self.undoDepth -= 1
		if self.undoDepth == 0:
			self.staticUndoClose()

	@classmethod
	def getPersistentFalloff(cls, thing):
		return cls.getObjectName(thing)

	@classmethod
	def loadPersistentFalloff(cls, thing):
		return cls.getObjectByName(thing)

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
		return cmds.ls(sl=True, transforms=True)

	@undoable
	def importObj(self, path):
		current = set(cmds.ls(transforms=True))
		cmds.file(path, i=True, type="OBJ", ignoreVersion=True)
		new = set(cmds.ls(transforms=True))
		shapes = set(cmds.ls(shapes=True))
		new = new - current - shapes
		imp = new.pop()
		return imp


class SliderDispatch(QtCore.QObject):
	valueChanged = Signal()
	def __init__(self, node, parent=None):
		super(SliderDispatch, self).__init__(parent)
		mObject = getMObject(node)
		self.callbackID = om.MNodeMessage.addAttributeChangedCallback(mObject, self.emitValueChanged)

	def emitValueChanged(self, *args, **kwargs):
		self.valueChanged.emit()

	def disconnectCallbacks(self):
		om.MMessage.removeCallback(self.callbackID)
		self.callbackID = None

	def __del__(self):
		self.disconnectCallbacks()


class Dispatch(QtCore.QObject):
	beforeNew = Signal()
	afterNew = Signal()
	beforeOpen = Signal()
	afterOpen = Signal()
	undo = Signal()
	redo = Signal()

	def __init__(self, parent=None):
		super(Dispatch, self).__init__(parent)
		self.callbackIDs = []
		self.connectCallbacks()

	def connectCallbacks(self):
		if self.callbackIDs:
			self.disconnectCallbacks()

		self.callbackIDs.append(om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeNew, self.emitBeforeNew))
		self.callbackIDs.append(om.MSceneMessage.addCallback(om.MSceneMessage.kAfterNew, self.emitAfterNew))
		self.callbackIDs.append(om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeOpen, self.emitBeforeOpen))
		self.callbackIDs.append(om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen, self.emitAfterOpen))
		self.callbackIDs.append(om.MEventMessage.addEventCallback("Undo", self.emitUndo))
		self.callbackIDs.append(om.MEventMessage.addEventCallback("Redo", self.emitRedo))

	def disconnectCallbacks(self):
		for i in self.callbackIDs:
			om.MMessage.removeCallback(i)
		self.callbackIDs = []

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

	def __del__(self):
		self.disconnectCallbacks()

DISPATCH = Dispatch()

def rootWindow():
	"""
	Returns the currently active QT main window
	Only works for QT UI's like Maya
	"""
	# for MFC apps there should be no root window
	window = None
	if QApplication.instance():
		inst = QApplication.instance()
		window = inst.activeWindow()
		# Ignore QSplashScreen's, they should never be considered the root window.
		if isinstance(window, QSplashScreen):
			return None
		# If the application does not have focus try to find A top level widget
		# that doesn't have a parent and is a QMainWindow or QDialog
		if window == None:
			windows = []
			dialogs = []
			for w in QApplication.instance().topLevelWidgets():
				if w.parent() == None:
					if isinstance(w, QMainWindow):
						windows.append(w)
					elif isinstance(w, QDialog):
						dialogs.append(w)
			if windows:
				window = windows[0]
			elif dialogs:
				window = dialogs[0]

		# grab the root window
		if window:
			while True:
				parent = window.parent()
				if not parent:
					break
				if isinstance(parent, QSplashScreen):
					break
				window = parent

	return window



SIMPLEX_RESET_SCRIPTJOB = '''
try:
	from SimplexUI.mayaInterface import rebuildCallbacks
except:
	pass
finally:
	rebuildCallbacks()
'''

def buildDeleterScriptJob():
	dcbName = 'SimplexDeleterCallback'
	if not cmds.ls(dcbName):
		cmds.scriptNode(scriptType=2, beforeScript=SIMPLEX_RESET_SCRIPTJOB, name=dcbName, sourceType='python')

def simplexDelCB(node, dgMod, clientData):
	xNode, dName = clientData
	dNode = getMObject(dName)
	if dNode and not dNode.isNull():
		dgMod.deleteNode(dNode)

def getMObject(name):
	selected = om.MSelectionList()
	try:
		selected.add(name, True)
	except RuntimeError:
		return None
	if selected.isEmpty():
		return None
	thing = om.MObject()
	selected.getDependNode(0, thing)
	return thing

def buildDeleterCallback(parName, delName):
	pNode = getMObject(parName)
	dNode = getMObject(delName)
	idNum = om.MNodeMessage.addNodeAboutToDeleteCallback(pNode, simplexDelCB, (dNode, delName))
	return idNum

def rebuildCallbacks():
	sds = cmds.ls("*ShapeDelta", shapes=True)
	callbackIDs = []
	for sd in sds:
		bs = cmds.listConnections(sd + '.inMesh')
		if not bs:
			continue
		par = cmds.listRelatives(sd, parent=1)
		if not par:
			continue
		callbackIDs.append(buildDeleterCallback(par[0], bs[0]))
	return callbackIDs


