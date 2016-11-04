#pylint: disable=invalid-name
import re, json, sys
from contextlib import contextmanager
from functools import wraps
import maya.cmds as cmds
import maya.OpenMaya as om
from loadUiType import QtCore, Signal, QApplication, QSplashScreen, QDialog, QMainWindow

sys.path.insert(0, r'C:\Program Files\Autodesk\Maya2016\Python\lib\site-packages')
import alembic
from alembic.Abc import V3fTPTraits, Int32TPTraits
from alembic.AbcGeom import OPolyMeshSchemaSample
sys.path.pop(0) # make sure to undo my stupid little hack


# UNDO STACK INTEGRATION
@contextmanager
def undoContext():
	cmds.undoInfo(openChunk=True)
	try:
		yield
	finally:
		cmds.undoInfo(closeChunk=True)

def undoable(f):
	@wraps(f)
	def stacker(*args, **kwargs):
		with undoContext():
			return f(*args, **kwargs)
	return stacker

# temporarily disconnect inputs from a list of nodes and plugs
@contextmanager
def disconnected(targets, testCnxType="float"):
	if not isinstance(targets, (list, tuple)):
		targets = [targets]
	cnxs = {}
	for target in targets:
		cnx = cmds.listConnections(target, plugs=True, destination=False, source=True, connections=True)
		if cnx is None:
			cnx = []
		for i in range(0, len(cnx), 2):
			cnxType = cmds.getAttr(cnx[i], type=True)
			if cnxType != testCnxType:
				continue
			cnxs[cnx[i+1]] = cnx[i]
			cmds.disconnectAttr(cnx[i+1], cnx[i])
	try:
		yield cnxs
	finally:
		for s, d in cnxs.iteritems():
			if not cmds.isConnected(s, d):
				cmds.connectAttr(s, d, force=True)


class DCC(object):
	program = "maya"
	def __init__(self, simplex, stack=None):
		self.name = None # the name of the system
		self.mesh = None # the mesh object with the system
		self.ctrl = None # the object that has all the controllers on it
		self.shapeNode = None # the deformer object
		self.op = None # the simplex object
		self.simplex = simplex # the abstract representation of the setup
		self._live = True


	# System IO
	@undoable
	def loadNodes(self, simp, thing, create=True):
		"""
		Create a new system based on the simplex tree
		Build any DCC objects that are missing if create=True
		Raises a runtime error if missing objects are found and
		create=False
		"""
		self.name = simp.name
		self.mesh = thing

		# find/build the shapeNode
		shapeNodes = [h for h in cmds.listHistory(thing) if cmds.nodeType(h) == "blendShape"]
		shapeNodes = [i for i in shapeNodes if i.startswith(self.name)]
		if not shapeNodes:
			if not create:
				raise RuntimeError("Blendshape operator not found with creation turned off")
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
			ops = [i for i in ops if i == self.name]
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

	@undoable
	def loadConnections(self, simp, create=True):
		# Build/create any shapes
		#shapes = set()
		#for i in [simp.combos, simp.sliders]:
			#for c in i:
				#for p in c.prog.pairs:
					#shapes.add(p.shape)

		shapes = simp.shapes
		if not shapes:
			shapes.append(simp.buildRestShape())

		for shape in shapes:
			s = cmds.ls("{0}.{1}".format(self.shapeNode, shape.name))
			if not s:
				if not create:
					raise RuntimeError("Shape {0} not found with creation turned off".format(shape.name))
				shp = self.createRawShape(shape.name, shape)
				cmds.delete(shp)
			else:
				shape.thing = s[0]
				shapeIdx = self.simplex.shapes.index(shape)
				weightAttr = "{0}.weights[{1}]".format(self.op, shapeIdx)
				if not cmds.isConnected(weightAttr, shape.thing):
					cmds.connectAttr(weightAttr, shape.thing, force=True)

		# Build/connect any sliders
		for slider in simp.sliders:
			things = cmds.ls("{0}.{1}".format(self.ctrl, slider.name))
			if not things:
				if not create:
					raise RuntimeError("Slider {0} not found with creation turned off".format(slider.name))
				self.createSlider(slider.name, slider)
			else:
				slider.thing = things[0]


	@undoable
	def buildRestABC(self, abcMesh, js):
		meshSchema = abcMesh.getSchema()
		rawFaces = meshSchema.getFaceIndicesProperty().samples[0]
		rawCounts = meshSchema.getFaceCountsProperty().samples[0]
		rawPos = meshSchema.getPositionsProperty().samples[0]
		name = js["systemName"]

		numVerts = len(rawPos)
		numFaces = len(rawCounts)

		counts = om.MIntArray()
		faces = om.MIntArray()
		ptr = 0
		for i in rawCounts:
			counts.append(i)
			for j in reversed(rawFaces[ptr: ptr+i]):
				faces.append(j)
			ptr += i

		vertexArray = om.MFloatPointArray()

		for j in xrange(numVerts):
			fp = om.MFloatPoint(rawPos[j][0], rawPos[j][1], rawPos[j][2])
			vertexArray.append(fp)

		meshFn = om.MFnMesh()
		meshMObj = meshFn.create(numVerts, numFaces, vertexArray, counts, faces)
		cName = "{0}_SIMPLEX".format(name)
		om.MFnDependencyNode(meshMObj).setName(cName)
		cmds.sets(cName, e=True, forceElement="initialShadingGroup")
		return cName


	#@undoable
	#def loadABC_OLD(self, abcMesh, js, pBar=None):
		#meshSchema = abcMesh.getSchema()
		#rawFaces = meshSchema.getFaceIndicesProperty().samples[0]
		#rawCounts = meshSchema.getFaceCountsProperty().samples[0]
		#rawPos = meshSchema.getPositionsProperty().samples[0]
		#shapes = js["shapes"]
		#shapeDict = {i.name:i for i in self.simplex.shapes}

		#numVerts = len(rawPos)
		#numFaces = len(rawCounts)

		#counts = om.MIntArray()
		#faces = om.MIntArray()
		#ptr = 0
		#for i in rawCounts:
			#counts.append(i)
			#for j in reversed(rawFaces[ptr: ptr+i]):
				#faces.append(j)
			#ptr += i

		#restVertArray = om.MFloatPointArray()
		#restVertArray.setLength(numVerts)
		#for i, v in enumerate(rawPos):
			#fp = om.MFloatPoint(v[0], v[1], v[2])
			#restVertArray.set(fp, i)

		##xferDeltas = []
		#xferDeltas = om.MVectorArray()
		#xferDeltas.setLength(numVerts)
		#restPos = self._getMeshVertices(self.mesh)
		#sameBase = True
		#for idx, (i, j) in enumerate(zip(restPos, rawPos)):
			#fp = om.MVector(i[0]-j[0], i[1]-j[1], i[2]-j[2])
			#if sameBase:
				#vlen = fp.length()
				#if vlen > 0.00001:
					#sameBase = False
			#xferDeltas.set(fp, idx)

		#if pBar is not None:
			#pBar.show()
			#pBar.setMaximum(len(shapes))
			#longName = max(shapes, key=len)
			#pBar.setValue(1)
			#pBar.setLabelText("Loading:\n{0}".format("_"*len(longName)))

		#posProp = meshSchema.getPositionsProperty()

		## Create the mesh only once
		#meshFn = om.MFnMesh()
		#meshMObj = meshFn.create(numVerts, numFaces, restVertArray, counts, faces)
		#cName = "AbcConnect"
		#om.MFnDependencyNode(meshMObj).setName(cName)

		#vertexArray = om.MPointArray()
		#vertexArray.setLength(numVerts)
		#for i, shapeName in enumerate(shapes):
			#if pBar is not None:
				#pBar.setValue(i)
				#pBar.setLabelText("Loading:\n{0}".format(shapeName))
				#QApplication.processEvents()
				#if pBar.wasCanceled():
					#return

			#verts = posProp.samples[i]
			#for j in xrange(numVerts):
				#fp = om.MPoint(verts[j][0], verts[j][1], verts[j][2])
				#if not sameBase:
					#fp += xferDeltas[j]
				#vertexArray.set(fp, j)

			#meshFn.setPoints(vertexArray)
			## Finally connect the blendshape
			#self.connectShape(shapeDict[shapeName], cName, live=False, delete=False)

		#cmds.delete(cName)

		#if pBar is not None:
			#pBar.setValue(len(shapes))

	@undoable
	def loadABC(self, abcMesh, js, pBar=None):
		# UGH, I *REALLY* hate that this is faster
		# But if I want to be "pure" about it, I should just bite the bullet
		# and do the direct alembic manipulation in C++
		abcPath = str(abcMesh.getArchive())

		abcNode = cmds.createNode('AlembicNode')
		cmds.setAttr(abcNode + ".abc_File", abcPath, type="string")
		cmds.setAttr(abcNode + ".speed", 24)
		shapes = js["shapes"]
		shapeDict = {i.name:i for i in self.simplex.shapes}

		importHead = cmds.polySphere(name='importHead', constructionHistory=False)[0]
		importHeadShape = [i for i in cmds.listRelatives(importHead, shapes=True)][0]

		cmds.connectAttr(abcNode+".outPolyMesh[0]", importHeadShape+".inMesh")
		vertCount = cmds.polyEvaluate(importHead, vertex=True) # force update
		cmds.disconnectAttr(abcNode+".outPolyMesh[0]", importHeadShape+".inMesh")

		importBS = cmds.blendShape(self.mesh, importHead)[0]
		cmds.blendShape(importBS, edit=True, weight=[(0, 1.0)])
		# Maybe get shapeNode from self.mesh??
		cmds.disconnectAttr(self.mesh+'.worldMesh[0]', importBS+'.inputTarget[0].inputTargetGroup[0].inputTargetItem[6000].inputGeomTarget')
		importOrig = [i for i in cmds.listRelatives(importHead, shapes=True) if i.endswith('Orig')][0]
		cmds.connectAttr(abcNode+".outPolyMesh[0]", importOrig+".inMesh")

		if pBar is not None:
			pBar.show()
			pBar.setMaximum(len(shapes))
			longName = max(shapes, key=len)
			pBar.setValue(1)
			pBar.setLabelText("Loading:\n{0}".format("_"*len(longName)))

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

	def _getMeshVertices(self, mesh):
		# Get the MDagPath from the name of the mesh
		sl = om.MSelectionList()
		sl.add(mesh)
		thing = om.MDagPath()
		sl.getDagPath(0, thing)
		meshFn = om.MFnMesh(thing)

		vts = om.MPointArray()
		meshFn.getPoints(vts)
		return vts

	def _exportABCVertices(self, mesh):
		vts = self._getMeshVertices(mesh)
		vertices = V3fTPTraits.arrayType(vts.length())
		for i in range(vts.length()):
			vertices[i] = (vts[i].x, vts[i].y, vts[i].z)
		return vertices

	def _exportABCFaces(self, mesh):
		# Get the MDagPath from the name of the mesh
		sl = om.MSelectionList()
		sl.add(mesh)
		thing = om.MDagPath()
		sl.getDagPath(0, thing)
		meshFn = om.MFnMesh(thing)

		faces = []
		faceCounts = []
		vIdx = om.MIntArray()
		for i in range(meshFn.numPolygons()):
			meshFn.getPolygonVertices(i, vIdx)
			face = [vIdx[j] for j in reversed(xrange(vIdx.length()))]
			faces.extend(face)
			faceCounts.append(vIdx.length())

		abcFaceIndices = Int32TPTraits.arrayType(len(faces))
		for i in xrange(len(faces)):
			abcFaceIndices[i] = faces[i]

		abcFaceCounts = Int32TPTraits.arrayType(len(faceCounts))
		for i in xrange(len(faceCounts)):
			abcFaceCounts[i] = faceCounts[i]

		return abcFaceIndices, abcFaceCounts

	def exportABC(self, abcMesh, js):
		# export the data to alembic
		shapeDict = {i.name:i for i in self.simplex.shapes}
		shapes = [shapeDict[i] for i in js["shapes"]]
		faces, counts = self._exportABCFaces(self.mesh)
		schema = abcMesh.getSchema()
		with disconnected(self.shapeNode) as shapeCnx:
			for v in shapeCnx.itervalues():
				cmds.setAttr(v, 0.0)
			for shape in shapes:
				cmds.setAttr(shape.thing, 1.0)
				verts = self._exportABCVertices(self.mesh)
				abcSample = OPolyMeshSchemaSample(verts, faces, counts)
				schema.set(abcSample)
				cmds.setAttr(shape.thing, 0.0)


	# Revision tracking
	def getRevision(self):
		try:
			return cmds.getAttr("{0}.{1}".format(self.op, "revision"))
		except ValueError:
			return None # object does not exist

	def incrementRevision(self):
		value = self.getRevision()
		if value is None:
			return
		cmds.setAttr("{0}.{1}".format(self.op, "revision"), value + 1)
		d = self.simplex.buildDefinition()
		jsString = json.dumps(d)
		self.setSimplexString(self.op, jsString)
		return value + 1

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
	def createShape(self, shapeName, pp, live=False):
		shape = pp.shape
		newShape = self.createRawShape(shapeName, shape)

		# TODO re-alias shape attr to be the shape name
		if live:
			cmds.xform(newShape, relative=True, translation=[10, 0, 0])
		else:
			cmds.delete(newShape)

	def createRawShape(self, shapeName, shape):
		newShape = cmds.duplicate(self.mesh, name=shapeName)[0]
		cmds.delete(newShape, constructionHistory=True)
		index = self._firstAvailableIndex()
		cmds.blendShape(self.shapeNode, edit=True, target=(self.mesh, index, newShape, 1.0))
		weightAttr = "{0}.weight[{1}]".format(self.shapeNode, index)
		thing = cmds.ls(weightAttr)[0]
		shape.thing = thing
		shapeIdx = self.simplex.shapes.index(shape)
		cmds.connectAttr("{0}.weights[{1}]".format(self.op, shapeIdx), thing)

		return newShape


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
	def extractShape(self, shape, live=True, offset=10.0):
		""" make a mesh representing a shape. Can be live or not """
		with disconnected(self.shapeNode):
			for attr in cmds.listAttr("{0}.weight[*]".format(self.shapeNode)):
				cmds.setAttr("{0}.{1}".format(self.shapeNode, attr), 0.0)
			cmds.setAttr(shape.thing, 1.0)
			extracted = cmds.duplicate(self.mesh, name="{0}_Extract".format(shape.name))[0]
			cmds.xform(extracted, relative=True, translation=[offset, 0, 0])
		if live:
			self.connectShape(shape, extracted, live, delete=False)

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
		outAttr = "{0}.worldMesh[0]".format(mesh)
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

		# Rebuild the shape connections in the proper order
		cnxs = cmds.listConnections(self.op, plugs=True, source=False, destination=True, connections=True)
		pairs = []
		for i, cnx in enumerate(cnxs):
			if cnx.startswith('{0}.weights['.format(self.op)):
				cmds.disconnectAttr(cnxs[i], cnxs[i+1])

		for i, shape in enumerate(self.simplex.shapes):
			cmds.connectAttr("{0}.weights[{1}]".format(self.op, i), shape.thing)


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


	# Sliders
	@undoable
	def createSlider(self, name, slider):
		""" Create a new slider with a name in a group.
		Possibly create a single default shape for this slider """
		vals = [v.value for v in slider.prog.pairs]
		cmds.addAttr(self.ctrl, longName=name, attributeType="double", keyable=True, min=2*min(vals), max=2*max(vals))
		thing = "{0}.{1}".format(self.ctrl, name)
		slider.thing = thing
		idx = self.simplex.sliders.index(slider)
		cmds.connectAttr(thing, "{0}.sliders[{1}]".format(self.op, idx))

	@undoable
	def renameSlider(self, slider, name):
		""" Set the name of a slider """
		vals = [v.value for v in slider.prog.pairs]
		cnx = cmds.listConnections(slider.thing, plugs=True, source=False, destination=True)
		cmds.deleteAttr(slider.thing)
		cmds.addAttr(self.ctrl, longName=name, attributeType='double', keyable=True, min=2*min(vals), max=2*max(vals))
		newThing = "{0}.{1}".format(self.ctrl, name)
		slider.thing = newThing
		for c in cnx:
			cmds.connectAttr(newThing, c)

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
	def updateSlidersRange(self, sliders):
		for slider in sliders:
			vals = [v.value for v in slider.prog.pairs]
			cmds.addAttr(slider.thing, edit=True, min=min(vals), max=max(vals))


	# Combos
	def _createDelta(self, combo, target, tVal):
		""" Part of the combo extraction process.
		Combo shapes are fixit shapes added on top of any sliders.
		This means that the actual combo-shape by itself will not look good by itself,
		and that's bad for artist interaction.
		So we must create a setup to take the final sculpted shape, and subtract
		the any direct slider deformations to get the actual "combo shape" as a delta
		It is this delta shape that is then plugged into the system
		"""
		# get floaters
		# As floaters can appear anywhere along any combo, they must
		# always be evaluated in isolation. For this reason, we will
		# always disconnect all floaters
		floatShapes = [i.thing for i in self.simplex.getFloatingShapes()]

		# get my shapes
		myShapes = [i.thing for i in combo.prog.getShapes()]

		with disconnected(self.op) as sliderCnx:
			with disconnected(floatShapes):
				with disconnected(myShapes):
					# zero all slider vals on the op
					for a in sliderCnx.itervalues():
						cmds.setAttr(a, 0.0)

					# pull out the rest shape
					orig = cmds.duplicate(self.mesh, name="Orig")[0]

					# set the combo values
					sliderVals = []
					for pair in combo.pairs:
						cmds.setAttr(sliderCnx[pair.slider.thing], pair.value*tVal)

					deltaObj = cmds.duplicate(self.mesh, name="{0}_Delta".format(combo.name))[0]
					cmds.xform(deltaObj, relative=True, translation=[10, 0, -10])
					cmds.setAttr("{0}.visibility".format(deltaObj), False)

					bs = cmds.blendShape(deltaObj, name="tempDelta_BS")[0]
					base = cmds.duplicate(deltaObj, name="Base")[0]

					cmds.blendShape(bs, edit=True, target=(deltaObj, 0, target, 1.0))
					cmds.blendShape(bs, edit=True, target=(deltaObj, 1, base, 1.0))
					cmds.blendShape(bs, edit=True, target=(deltaObj, 2, orig, 1.0))

					cmds.setAttr("{0}.{1}".format(bs, target), 1.0)
					cmds.setAttr("{0}.{1}".format(bs, base), 1.0)
					cmds.setAttr("{0}.{1}".format(bs, orig), 1.0)
					cmds.delete(base)
					cmds.delete(orig)

		return deltaObj

	@undoable
	def extractComboShape(self, combo, shape, live=True, offset=10.0):
		""" Extract a shape from a combo progression """
		floatShapes = self.simplex.getFloatingShapes()
		with disconnected(self.op) as sliderCnx:
			with disconnected(floatShapes):
				# zero all slider vals on the op
				for a in sliderCnx.itervalues():
					cmds.setAttr(a, 0.0)

				# set the combo values
				sliderVals = []
				for pair in combo.pairs:
					cmds.setAttr(sliderCnx[pair.slider.thing], pair.value)

				extracted = cmds.duplicate(self.mesh, name="{0}_Extract".format(shape.name))[0]
				cmds.xform(extracted, relative=True, translation=[offset, 0, 0])
		self.connectComboShape(combo, shape, extracted, live=live, delete=False)

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
		# TODO: Eventually take parallel blenders into account
		ops = cmds.ls(type="simplex_maya")
		out = []
		for op in ops:
			shapeNode = cmds.listConnections("{0}.{1}".format(op, "shapeMsg"), source=True, destination=False)
			if not shapeNode:
				continue
			checkMesh = cmds.listConnections("{0}.outputGeometry".format(shapeNode[0]), source=False, destination=True)
			if checkMesh and checkMesh[0] == thing:
				out.append(op)
		return out

	@staticmethod
	def getSimplexString(op):
		""" return the definition string from a simplex operator """
		return cmds.getAttr(op+".definition")

	def getSimplexStringOnThing(self, thing, systemName):
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
		return cmds.ls(name)[0]

	@staticmethod
	def getObjectName(thing):
		""" return the text name of an object """
		return thing

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



