#pylint:disable=missing-docstring,unused-argument
import os, sys, copy, json, itertools, gc
from alembic.Abc import OArchive, IArchive, OStringProperty
from alembic.AbcGeom import OXform, OPolyMesh, IXform, IPolyMesh
from Qt.QtCore import QAbstractItemModel, QModelIndex, Qt

CONTEXT = os.path.basename(sys.executable)
if CONTEXT == "maya.exe":
	from .mayaInterface import DCC
elif CONTEXT == "XSI.exe":
	from .xsiInterface import DCC
else:
	from .dummyInterface import DCC


THING_ROLE = Qt.UserRole + 1


# ABSTRACT CLASSES FOR HOLDING DATA
# Probably can be in a separate file
# In fact, most of this can be in an
# abstract base class file

class Shape(object):
	def __init__(self, name, simplex):
		self._thing = None
		self._thingRepr = None
		self._name = name
		self._buildIdx = None
		simplex.shapes.append(self)
		self.isRest = False
		self.expanded = False
		self.simplex = simplex
		# maybe Build thing on creation?

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, value):
		self._name = value
		self.simplex.DCC.renameShape(self, value)

	@property
	def thing(self):
		# if this is a deepcopied object, then self._thing will
		# be None.	Rebuild the thing connection by its representation
		if self._thing is None and self._thingRepr:
			self._thing = DCC.loadPersistentShape(self._thingRepr)
		return self._thing

	@thing.setter
	def thing(self, value):
		self._thing = value
		self._thingRepr = DCC.getPersistentShape(value)

	def buildDefinition(self, simpDict):
		if self._buildIdx is None:
			simpDict.setdefault("shapes", []).append(self.name)
			self._buildIdx = len(simpDict["shapes"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None

	def __deepcopy__(self, memo):
		# DO NOT make a copy of the DCC thing
		# as it may or may not be a persistent object
		cls = self.__class__
		result = cls.__new__(cls)
		memo[id(self)] = result
		for k, v in self.__dict__.iteritems():
			if k == "_thing":
				setattr(result, k, None)
			else:
				setattr(result, k, copy.deepcopy(v, memo))
		return result

	def zeroShape(self, shape):
		""" Set the shape to be completely zeroed """
		self.simplex.DCC.zeroShape(shape)

class Group(object):
	def __init__(self, name, simplex):
		self.name = name
		self.sliders = []
		self.combos = []
		self._buildIdx = None
		self.expanded = False
		self.simplex = simplex
		self.simplex.groups.append(self)

	def buildDefinition(self, simpDict):
		if self._buildIdx is None:
			simpDict.setdefault("groups", []).append(self.name)
			self._buildIdx = len(simpDict["groups"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None

	def delete(self):
		""" Delete a group. Any objects in this group will
		be deleted """
		if len(self.simplex.groups) == 1:
			return
		self.simplex.groups.remove(self)

		# Gotta iterate over copies of the lists
		# as .delete removes the items from the list
		for slider in self.sliders[:]:
			slider.delete()

		for combo in self.combos[:]:
			combo.delete()

	# Qt Model methods
	def parent(self, tree):
		return self.simplex

	def child(self, tree, row):
		if tree == "Slider":
			return self.sliders[row]
		elif tree == "Combo":
			return self.combos[row]
		return None

	def data(self, tree, index, role):
		if index.column() == 0:
			if role in (Qt.DisplayRole, Qt.EditRole):
				return self.name
		return None

	def getRow(self, tree):
		if tree == "Slider":
			return self.simplex.sliderGroups.index(self)
		elif tree == "Combo":
			return self.simplex.comboGroups.index(self)
		return -1

	def rowCount(self, tree):
		if tree == "Slider":
			return len(self.simplex.sliderGroups)
		elif tree == "Combo":
			return len(self.simplex.comboGroups)
		return -1

class Falloff(object):
	def __init__(self, name, simplex, *data):
		self.name = name
		self.children = []
		self._buildIdx = None
		self.splitType = data[0]
		self.expanded = False
		self.simplex = simplex
		self.simplex.falloffs.append(self)

		if self.splitType == "planar":
			self.axis = data[1]
			self.maxVal = data[2]
			self.maxHandle = data[3]
			self.minHandle = data[4]
			self.minVal = data[5]
			self.mapName = None
		elif self.splitType == "map":
			self.axis = None
			self.maxVal = None
			self.maxHandle = None
			self.minHandle = None
			self.minVal = None
			self.mapName = data[1]

	def buildDefinition(self, simpDict):
		if self._buildIdx is None:
			if self.splitType == "planar":
				line = ["planar", self.axis, self.maxVal, self.maxHandle, self.minHandle, self.minVal]
			else:
				line = ["map", self.mapName]
			simpDict.setdefault("falloffs", []).append([self.name] + line)
			self._buildIdx = len(simpDict["falloffs"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None

	def duplicate(self, newName):
		""" duplicate a falloff with a new name """
		nf = copy.copy(self)
		nf.name = newName
		nf.data = copy.copy(self.data)
		nf.children = []
		self.simplex.falloffs.append(nf)
		self.DCC.duplicateFalloff(self, nf, newName)
		return nf

	def delete(self):
		""" delete a falloff """
		fIdx = self.simplex.falloffs.index(self)
		for child in self.children:
			child.falloff = None
		self.simplex.falloffs.pop(fIdx)

		self.DCC.deleteFalloff(self)

	def setPlanarData(self, splitType, axis, minVal, minHandle, maxHandle, maxVal):
		""" set the type/data for a falloff """
		self.splitType = "planar"
		self.axis = axis
		self.minVal = minVal
		self.minHandle = minHandle
		self.maxHandle = maxHandle
		self.maxVal = maxVal
		self.mapName = None
		self._updateDCC()

	def setPlanarData(self, mapName):
		""" set the type/data for a falloff """
		self.splitType = "map"
		self.axis = None
		self.minVal = None
		self.minHandle = None
		self.maxHandle = None
		self.maxVal = None
		self.mapName = mapName
		self._updateDCC()

	def _updateDCC(self):
		self.DCC.setFalloffData(self, self.splitType, self.axis, self.minVal,
						  self.minHandle, self.maxHandle, self.maxVal, self.mapName)

class ProgPair(object):
	def __init__(self, shape, value):
		self.shape = shape
		self.value = value
		self.prog = None
		self.minValue = -1.0
		self.maxValue = 1.0
		self.expanded = False

	def buildDefinition(self, simpDict):
		idx = self.shape.buildDefinition(simpDict)
		return idx, self.value

	def __lt__(self, other):	
		return self.value < other.value

	# Qt Model methods
	def parent(self, tree):
		if tree == 'Slider':
			return self.prog.controller
		elif tree == 'Combo':
			return self.prog
		return None

	def child(self, tree, row):
		return None

	def data(self, tree, index, role):
		if index.column() == 0:
			if role in (Qt.DisplayRole, Qt.EditRole):
				return self.shape.name
		elif index.column() == 2:
			if role in (Qt.DisplayRole, Qt.EditRole):
				return self.value
		return None

	def getRow(self, tree):
		return self.prog.pairs.index(self)

	def rowCount(self, tree):
		return len(self.prog.pairs)

class Progression(object):
	def __init__(self, name, simplex, pairs=None, interp="spline", falloffs=None):
		self.name = name
		self.interp = interp
		self.falloffs = falloffs or []
		self.controller = None

		self.simplex = simplex
		if pairs is None:
			self.pairs = [ProgPair(self.simplex.restShape, 0.0)]
		else:
			self.pairs = pairs

		for pair in self.pairs:
			pair.prog = self

		for falloff in self.falloffs:
			falloff.children.append(self)
		self._buildIdx = None
		self.expanded = False

	def getShapeIndex(self, shape):
		for i, p in enumerate(self.pairs):
			if p.shape == shape:
				return i
		raise ValueError("Provided shape:{0} is not in the list".format(shape.name))

	def getShapes(self):
		return [i.shape for i in self.pairs]

	def buildDefinition(self, simpDict):
		if self._buildIdx is None:
			idxPairs = [pair.buildDefinition(simpDict) for pair in self.pairs]
			idxPairs.sort(key=lambda x: x[1])
			idxs, values = zip(*idxPairs)
			foIdxs = [f.buildDefinition(simpDict) for f in self.falloffs]
			x = [self.name, idxs, values, self.interp, foIdxs]
			simpDict.setdefault("progressions", []).append(x)
			self._buildIdx = len(simpDict["progressions"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None
		for pair in self.pairs:
			pair.shape.clearBuildIndex()
		for fo in self.falloffs:
			fo.clearBuildIndex()

	def moveShapeToProgression(self, shapePair):
		""" Remove the shapePair from its current progression
		and set it in a new progression """
		oldProg = shapePair.prog
		oldProg.pairs.remove(shapePair)
		self.pairs.append(shapePair)
		shapePair.prog = self

	def setShapesValues(self, values):
		""" Set the shape's value in it's progression """
		for pp, val in zip(self.pairs, values):
			pp.value = val
		if isinstance(self.parent, Slider):
			self.DCC.updateSlidersRange([sliders])

	def addFalloff(self, falloff):
		""" Add a falloff to a slider's falloff list """
		self.falloffs.append(falloff)
		falloff.children.append(self)
		self.DCC.addProgFalloff(self, falloff)

	def removeFalloff(self, falloff):
		""" Remove a falloff from a slider's falloff list """
		self.falloffs.remove(falloff)
		falloff.children.remove(self)
		self.DCC.removeProgFalloff(self, falloff)

	def createShape(self, shapeName, tVal):
		""" create a shape and add it to a progression """
		shape = Shape(shapeName, self.simplex)
		pp = ProgPair(shape, tVal)
		pp.prog = self
		self.pairs.append(pp)

		self.simplex.DCC.createShape(shapeName, pp)
		if isinstance(self.parent, Slider):
			self.simplex.DCC.updateSlidersRange([self.parent])
		return pp

	def guessNextTVal(self):
		''' Given the current progression values, make an
		educated guess what's next.
		'''
		# The question remains if negative or
		# intermediate values are more important
		# I think intermediate
		vals = [i.value for i in self.pairs]
		mnv = min(vals)
		mxv = max(vals)
		if mnv == 0.0 and mxv == 1.0:
			for c in [0.5, 0.25, 0.75, -1.0]:
				if c not in vals:
					return c
		if mnv == -1.0 and mxv == 1.0:
			for c in [0.5, -0.5, 0.25, -0.25, 0.75, -0.75]:
				if c not in vals:
					return c
		return 1.0

	def deleteShape(self, shape):
		ridx = None
		for i, pp in enumerate(self.pairs):
			if pp.shape == shape:
				ridx = i
		if ridx is None:
			raise RuntimeError("Shape does not exist to remove")
		self.pairs.pop(ridx)
		if not shape.isRest:
			self.simplex.shapes.remove(shape)
			self.DCC.deleteShape(shape)

	# Qt Model methods
	def parent(self, tree):
		return self.controller

	def child(self, tree, row):
		return self.pairs[row]

	def data(self, tree, index, role):
		if tree == "Combo":
			if index.column() == 0:
				if role in (Qt.DisplayRole, Qt.EditRole):
					#return self.name
					return "SHAPES"
		return None

	def getRow(self, tree):
		if tree == "Combo":
			return len(self.controller.pairs)
		return 0

	def rowCount(self, tree):
		return len(self.pairs)

class Slider(object):
	def __init__(self, name, prog, group):
		self._name = name
		self._thing = None
		self._thingRepr = None
		self.prog = prog
		self.group = group
		self.split = False
		self.prog.controller = self
		self.group.sliders.append(self)
		self.simplex = None
		self._buildIdx = None
		self.value = 0.0
		self.minValue = -1.0
		self.maxValue = 1.0
		self.expanded = False

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, value):
		""" Set the name of a slider """
		slider.name = value
		slider.prog.name = value
		#self.DCC.renameSlider(self, value, multiplier=1) # TODO
		self.DCC.renameSlider(self, value)

	@property
	def thing(self):
		# if this is a deepcopied object, then self._thing will
		# be None.	Rebuild the thing connection by its representation
		if self._thing is None and self._thingRepr:
			self._thing = DCC.loadPersistentSlider(self._thingRepr)
		return self._thing

	@thing.setter
	def thing(self, value):
		self._thing = value
		self._thingRepr = DCC.getPersistentSlider(value)

	def buildDefinition(self, simpDict):
		if self._buildIdx is None:
			gIdx = self.group.buildDefinition(simpDict)
			pIdx = self.prog.buildDefinition(simpDict)
			simpDict.setdefault("sliders", []).append([self.name, pIdx, gIdx])
			self._buildIdx = len(simpDict["sliders"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None
		self.prog.clearBuildIndex()
		self.group.clearBuildIndex()

	def __deepcopy__(self, memo):
		# DO NOT make a copy of the DCC thing
		# as it may or may not be a persistent object
		cls = self.__class__
		result = cls.__new__(cls)
		memo[id(self)] = result
		for k, v in self.__dict__.iteritems():
			if k == "_thing":
				setattr(result, k, None)
			else:
				setattr(result, k, copy.deepcopy(v, memo))
		return result

	def setRange(self, multiplier):
		self.DCC.setSliderRange(self, multiplier)

	def delete(self):
		""" Delete a slider and any shapes it contains """
		g = self.group
		g.sliders.remove(self)
		self.group = None
		self.simplex.sliders.remove(self)
		pairs = self.prog.pairs[:] #gotta make a copy
		#for pair in self.prog.pairs:
		for pair in pairs:
			self.deleteProgPair(pair)
		self.DCC.deleteSlider(self)

	def setGroup(self, group):
		""" Set the group of a slider """
		self.group.sliders.remove(self)
		self.group = group
		group.sliders.append(self)

	def setInterpolation(self, interp):
		""" Set the interpolation of a slider """
		self.prog.interp = interp

	def extractProgressive(self, live=True, offset=10.0, separation=5.0):
		pos, neg = [], []
		for pp in sorted(self.prog.pairs):
			if pp.value < 0.0:
				neg.append((pp.value, pp.shape, offset))
				offset += separation
			elif pp.value > 0.0:
				pos.append((pp.value, pp.shape, offset))
				offset += separation
			#skip the rest value at == 0.0
		neg = reversed(neg)

		for prog in [pos, neg]:
			xtVal, shape, shift = prog[-1]
			ext, deltaShape = self.DCC.extractWithDeltaShape(shape, live, shift)
			for value, shape, shift in prog[:-1]:
				ext = self.DCC.extractWithDeltaConnection(shape, deltaShape, value/xtVal, live, shift)

	def extractShape(self, shape, live=True, offset=10.0):
		return self.DCC.extractShape(shape, live, offset)

	def connectShape(self, shape, mesh=None, live=False, delete=False):
		self.DCC.connectShape(shape, mesh, live, delete)

	# Qt Model methods
	def parent(self, tree):
		return self.group

	def child(self, tree, row):
		return self.prog.pairs[row]

	def data(self, tree, index, role):
		if index.column() == 0:
			if role in (Qt.DisplayRole, Qt.EditRole):
				return self.name
		return None

	def getRow(self, tree):
		return self.group.sliders.index(self)

	def rowCount(self, tree):
		return len(self.prog.pairs)

class ComboPair(object):
	def __init__(self, slider, value):
		self.slider = slider
		self.value = float(value)
		self.minValue = -1.0
		self.maxValue = 1.0
		self.combo = None
		self.expanded = False

	def buildDefinition(self, simpDict):
		sIdx = self.slider.buildDefinition(simpDict)
		return sIdx, self.value

	# Qt Model methods
	def parent(self, tree):
		return self.combo

	def child(self, tree, row):
		return None

	def data(self, tree, index, role):
		if index.column() == 0:
			if role in (Qt.DisplayRole, Qt.EditRole):
				return self.slider.name
		elif index.column() == 1:
			if role in (Qt.DisplayRole, Qt.EditRole):
				self.value
		return None

	def getRow(self, tree):
		return self.combo.pairs.index(self)

	def rowCount(self, tree):
		return 0

class Combo(object):
	def __init__(self, name, simplex, pairs, prog, group):
		self._name = name
		self.pairs = pairs
		self.prog = prog
		self.group = group
		self.prog.controller = self
		self.group.combos.append(self)
		self.simplex = simplex
		self._buildIdx = None
		for p in self.pairs:
			p.combo = self
		self.expanded = False
		self.simplex.combos.append(self)

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, value):
		""" Set the name of a combo """
		self._name = value
		self.prog.name = value
		self.simplex.DCC.renameCombo(self, value)

	def getSliderIndex(self, slider):
		for i, p in enumerate(self.pairs):
			if p.slider == slider:
				return i
		raise ValueError("Provided slider:{0} is not in the list".format(slider.name))

	def isFloating(self):
		for pair in self.pairs:
			if abs(pair.value) != 1.0:
				return True
		return False

	def getSliders(self):
		return [i.slider for i in self.pairs]

	def buildDefinition(self, simpDict):
		if self._buildIdx is None:
			gIdx = self.group.buildDefinition(simpDict)
			pIdx = self.prog.buildDefinition(simpDict)
			idxPairs = [p.buildDefinition(simpDict) for p in self.pairs]
			x = [self.name, pIdx, idxPairs, gIdx]
			simpDict.setdefault("combos", []).append(x)
			self._buildIdx = len(simpDict["combos"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None
		self.prog.clearBuildIndex()
		self.group.clearBuildIndex()

	def extractProgressive(self, live=True, offset=10.0, separation=5.0):
		raise RuntimeError('Currently just copied from Sliders, Not actually real')
		pos, neg = [], []
		for pp in sorted(self.prog.pairs):
			if pp.value < 0.0:
				neg.append((pp.value, pp.shape, offset))
				offset += separation
			elif pp.value > 0.0:
				pos.append((pp.value, pp.shape, offset))
				offset += separation
			#skip the rest value at == 0.0
		neg = reversed(neg)

		for prog in [pos, neg]:
			xtVal, shape, shift = prog[-1]
			ext, deltaShape = self.DCC.extractWithDeltaShape(shape, live, shift)
			for value, shape, shift in prog[:-1]:
				ext = self.DCC.extractWithDeltaConnection(shape, deltaShape, value/xtVal, live, shift)

	def extractShape(self, shape, live=True, offset=10.0):
		""" Extract a shape from a combo progression """
		return self.simplex.DCC.extractComboShape(self, shape, live, offset)

	def connectComboShape(self, shape, mesh=None, live=False, delete=False):
		""" Connect a shape into a combo progression"""
		self.simplex.DCC.connectComboShape(self, shape, mesh, live, delete)

	def delete(self):
		""" Delete a combo and any shapes it contains """
		g = self.group
		if self not in g.combos:
			return # Can happen when deleting multiple groups
		g.combos.remove(self)
		self.group = None
		self.simplex.combos.remove(self)
		pairs = self.prog.pairs[:] # gotta make a copy
		for pair in pairs:
			pair.delete()

	def setGroup(self, group):
		""" Set the group of a combo """
		self.group.combos.remove(self)
		self.group = group
		group.combos.append(self)

	def setInterpolation(self, interp):
		""" Set the interpolation of a combo """
		self.prog.interp = interp

	def setComboValue(self, slider, value):
		""" Set the Slider/value pairs for a combo """
		idx = self.getSliderIndex(slider)
		self.pairs[idx].value = value

	def appendComboValue(self, slider, value):
		""" Append a Slider/value pair for a combo """
		cp = ComboPair(slider, value)
		self.pairs.append(cp)
		cp.combo = self

	def deleteComboPair(self, comboPair):
		""" delete a Slider/value pair for a combo """
		self.pairs.remove(comboPair)
		comboPair.combo = None

	# Qt Model methods
	def parent(self, tree):
		return self.group

	def child(self, tree, row):
		if row == len(self.pairs):
			return self.prog
		return self.pairs[row]

	def data(self, tree, index, role):
		if index.column() == 0:
			if role in (Qt.DisplayRole, Qt.EditRole):
				return self.name
		return None

	def getRow(self, tree):
		return self.group.combos.index(self)

	def rowCount(self, tree):
		# the extra is for the Shape sub-parent
		return len(self.pairs) + 1

class Simplex(object):
	'''
	The main Top-level abstract object that encapsulates
	and controls an entire simplex setup
	'''
	# CONSTRUCTORS
	def __init__(self, name=""):
		self._name = name
		self.sliders = []
		self.combos = []
		self.sliderGroups = []
		self.comboGroups = []
		self.falloffs = []
		# must keep track of shapes for
		# connection order stuff
		self.shapes = []
		self.restShape = None
		self.clusterName = "Shape"
		self.expanded = False
		self.comboExpanded = False
		self.sliderExpanded = False
		self.DCC = DCC(self)

	@property
	def name(self):
		''' Property getter for the simplex name '''
		return self._name

	@name.setter
	def name(self, value):
		""" rename a system and all objects in it """
		self._name = value
		self.DCC.renameSystem(value) #??? probably needs work
		if self.restShape is not None:
			self.restShape.name = self._buildRestName()

	@classmethod
	def buildBlank(cls, thing, name):
		''' Create a new system on a given mesh, ready to go '''
		self = cls(name)
		self.DCC.loadNodes(self, thing, create=True)
		self.buildRest()
		return self

	@classmethod
	def buildFromJson(cls, thing, jsonPath):
		""" Create a new system based on a path to a json file """
		with open(jsonPath, 'r') as f:
			js = json.load(f)
		return cls.buildFromDict(thing, js)

	@classmethod
	def buildFromDict(cls, thing, simpDict):
		""" Create a new system based on a parsed simplex dictionary """
		self = cls.buildBlank(thing, simpDict['systemName'])
		self.loadFromDict(simpDict, True)

	@classmethod
	def buildFromAbc(cls, abcPath):
		""" Build a system from a simplex abc file """
		iarch, abcMesh, js = cls.getAbcDataFromPath(abcPath)
		try:
			rest = DCC.buildRestAbc(abcMesh, js)
			self = cls.buildBlank(rest, js['systemName'])
			self.loadFromAbc(iarch, abcMesh, js)
		finally:
			del iarch, abcMesh
			gc.collect()
		return self

	# LOADERS
	def buildRest(self):
		""" create/find the system's rest shape"""
		if self.restShape is None:
			self.restShape = Shape(self._buildRestName(), self)
			self.restShape.isRest = True

		if not self.restShape.thing:
			pp = ProgPair(self.restShape, 1.0) # just to pass to createShape
			self.DCC.createShape(self.restShape.name, pp)
		return self.restShape

	def loadFromDict(self, simpDict, create):
		''' Load the data from a dictionary onto the current system
		Build any DCC objects that are missing if create=True '''
		self.loadDefinition(simpDict)
		self.DCC.loadNodes(self, create=create)
		self.DCC.loadConnections(self, create=create)

	def loadFromAbc(self, iarch, abcMesh, simpDict):
		''' Load a system and shapes from a parsed smpx file
		Uses the return values from `self.getAbcDataFromPath`
		'''
		self.loadFromDict(simpDict, True)
		self.DCC.loadAbc(abcMesh, simpDict)

	# HELPER
	@staticmethod
	def getAbcDataFromPath(abcPath):
		''' Read and return the relevant data from a simplex alembic '''
		iarch = IArchive(str(abcPath)) # because alembic hates unicode
		try:
			top = iarch.getTop()
			par = top.children[0]
			par = IXform(top, par.getName())
			abcMesh = par.children[0]
			abcMesh = IPolyMesh(par, abcMesh.getName())

			systemSchema = par.getSchema()
			props = systemSchema.getUserProperties()
			prop = props.getProperty("simplex")
			jsString = prop.getValue()
			js = json.loads(jsString)

		except Exception: #pylint: disable=broad-except
			del iarch
		return iarch, abcMesh, js


	# DESTRUCTOR
	def deleteSystem(self):
		''' Delete an existing system from file '''
		self.DCC.deleteSystem()
		self.name = None
		self.DCC = DCC(self)


	# USER METHODS
	def getFloatingShapes(self):
		''' Find combos that don't have fully extreme activations '''
		floaters = [c for c in self.combos if c.isFloating()]
		floatShapes = []
		for f in floaters:
			floatShapes.extend(f.prog.getShapes())
		return floatShapes

	def buildDefinition(self):
		''' Create a simplex dictionary
		Loop through all the objects managed by this simplex system, and
		build a dictionary that defines it
		'''
		things = [self.sliders, self.combos, self.sliderGroups, self.comboGroups, self.falloffs]
		for thing in things:
			for i in thing:
				i.clearBuildIndex()

		# Make sure that all parts are defined first
		d = {}
		d["encodingVersion"] = 1
		d["systemName"] = self.name
		d["clusterName"] = self.clusterName
		d["falloffs"] = []
		d["combos"] = []
		d["shapes"] = []
		d["sliders"] = []
		d["groups"] = []
		d["progressions"] = []

		# rest shape should *ALWAYS* be index 0
		for shape in self.shapes:
			shape.buildDefinition(d)

		for group in self.sliderGroups:
			group.buildDefinition(d)

		for group in self.comboGroups:
			group.buildDefinition(d)

		for falloff in self.falloffs:
			falloff.buildDefinition(d)

		for slider in self.sliders:
			slider.buildDefinition(d)

		for combo in self.combos:
			combo.buildDefinition(d)

		return d

	def loadDefinition(self, simpDict):
		''' Build the structure of objects in this system
		based on a provided dictionary'''
		self.name = simpDict["systemName"]
		self.clusterName = simpDict["clusterName"] # for XSI
		self.falloffs = [Falloff(f[0], self, *f[1]) for f in simpDict["falloffs"]]
		allGroups = [Group(g, self) for g in simpDict["groups"]]
		shapes = [Shape(s, self) for s in simpDict["shapes"]]
		self.restShape = shapes[0]
		self.restShape.isRest = True

		progs = []
		for p in simpDict["progressions"]:
			progShapes = [shapes[i] for i in p[1]]
			progFalloffs = [self.falloffs[i] for i in p[4]]
			progPairs = map(ProgPair, progShapes, p[2])
			progs.append(Progression(p[0], self, progPairs, p[3], progFalloffs))

		self.sliders = []
		self.sliderGroups = []
		for s in simpDict["sliders"]:
			sliderProg = progs[s[1]]
			sliderGroup = allGroups[s[2]]
			sli = Slider(s[0], sliderProg, sliderGroup)
			sli.simplex = self
			self.sliders.append(sli)
			self.sliderGroups.append(sli.group)

		self.combos = []
		self.comboGroups = []
		for c in simpDict["combos"]:
			prog = progs[c[1]]
			sliderIdxs, sliderVals = zip(*c[2])
			sliders = [self.sliders[i] for i in sliderIdxs]
			pairs = map(ComboPair, sliders, sliderVals)
			if len(c) >= 4:
				comboGroup = allGroups[c[3]]
			else:
				comboGroup = allGroups[0] # TEMPORARY
			cmb = Combo(c[0], pairs, prog, comboGroup)
			cmb.simplex = self
			self.combos.append(cmb)
			self.comboGroups.append(cmb.group)

		for x in itertools.chain(self.sliders, self.combos):
			x.prog.name = x.name

	def loadJSON(self, jsString):
		''' Convenience method to load a JSON string definition '''
		self.loadDefinition(json.loads(jsString))

	def getRestName(self):
		''' Unified rest object name creation '''
		return "Rest_{0}".format(self.name)

	def dump(self):
		''' Dump the definition dictionary to a json string '''
		return json.dumps(self.buildDefinition())

	def exportAbc(self, path, pBar=None):
		''' Export the current mesh to a file '''
		self.extractExternal(path, self.DCC.mesh, pBar)

	def extractExternal(self, path, dccMesh, pBar=None):
		''' Extract shapes from an arbitrary mesh based on the current simplex '''
		defDict = self.buildDefinition()
		jsString = json.dumps(defDict)

		arch = OArchive(str(path)) # alembic does not like unicode filepaths
		try:
			par = OXform(arch.getTop(), str(self.name))
			props = par.getSchema().getUserProperties()
			prop = OStringProperty(props, "simplex")
			prop.setValue(str(jsString))
			abcMesh = OPolyMesh(par, str(self.name))
			self.DCC.exportAbc(dccMesh, abcMesh, defDict, pBar)

		finally:
			del arch

	def _buildRestName(self):
		''' Customize the restshape name '''
		return "Rest_{0}".format(self.name)

	# Conveninece creation methods
	def createGroup(self, name, sliders=None, combos=None):
		''' Convenience method for creating a group '''
		g = Group(name, self)
		if sliders is not None:
			pass #TODO
		elif combos is not None:
			pass #TODO
		return g

	def createShape(self, name, slider=None):
		''' Convenience method for creating a new shape
		This will create all required parent objects to have a new shape
		'''
		if self.restShape is None:
			raise RuntimeError("Simplex system is missing rest shape")

		if slider is None:
			slider = self.createSlider(name)
		else:
			tVal = slider.prog.guessNextTVal()
			slider.prog.createShape(name, tVal)

		for p in slider.prog.pairs:
			if p.shape.name == name:
				return p.shape

	def createSlider(self, name, group=None, shape=None, tVal=1.0, multiplier=1):
		"""
		Create a new slider with a name in a group.
		Possibly create a single default shape for this slider
		"""
		if self.restShape is None:
			raise RuntimeError("Simplex system is missing rest shape")

		if group is None:
			if self.sliderGroups:
				group = self.sliderGroups[0]
			else:
				group = Group('{0}_GROUP'.format(name), self)

		prog = Progression(name, self)
		if shape is None:
			prog.createShape(name, tVal)
		else:
			prog.pairs.append(ProgPair(shape, tVal))

		sli = Slider(name, prog, group)
		self.sliders.append(sli)

		self.DCC.createSlider(name, sli, multiplier=multiplier)
		return sli

	def createCombo(self, name, sliders, values, group=None, shape=None, tVal=1.0):
		""" Create a combo of sliders at values """
		if self.restShape is None:
			raise RuntimeError("Simplex system is missing rest shape")
		if group is None:
			gname = "DEPTH_{0}".format(len(sliders))
			matches = [i for i in self.comboGroups if i.name == gname]
			if matches:
				group = matches[0]
			else:
				group = Group(gname, self)

		cPairs = [ComboPair(slider, value) for slider, value in zip(sliders, values)]
		prog = Progression(name, self)
		if shape:
			prog.pairs.append(ProgPair(shape, tVal))

		cmb = Combo(name, self, cPairs, prog, group)

		if shape is None:
			pp = prog.createShape(name, tVal)
			self.DCC.zeroShape(pp.shape)

		return cmb

	def createFalloff(self, name):
		""" Create a new falloff.  Planar, mid, X axis """
		# When we finally get map falloffs, this will be a *LOT* more complicated
		fo = Falloff(name, self, 'planar', 'x', 1.0, 0.66, 0.33, -1.0)
		return fo

	def setSlidersWeights(self, sliders, weights):
		''' Set the weights of multiple sliders as one action '''
		for slider, weight in zip(sliders, weights):
			slider.value = weight
		self.DCC.setSlidersWeights(sliders, weights)

	def comboExists(self, sliders, values):
		''' Check if a combo exists with these specific sliders and values
		Because combo names aren't necessarily always in the same order
		'''
		checkSet = set([(s.name, v) for s, v in zip(sliders, values)])
		for cmb in self.combos:
			cmbSet = set([(p.slider.name, p.value) for p in cmb.pairs])
			if checkSet == cmbSet:
				return cmb
		return None

	# Qt Model methods
	def parent(self, tree):
		return None

	def child(self, tree, row):
		if tree == "Slider":
			return self.sliderGroups[row]
		elif tree == "Combo":
			return self.comboGroups[row]
		return None

	def data(self, tree, index, role):
		if index.column() == 0:
			if role in (Qt.DisplayRole, Qt.EditRole):
				return self.name
		return None

	def getRow(self, tree):
		return 0

	def rowCount(self, tree):
		if tree == "Slider":
			return len(self.sliderGroups)
		elif tree == "Combo":
			return len(self.comboGroups)
		return 0




class SimplexModel(QAbstractItemModel):
	def __init__(self, simplex, tree, parent):
		self.simplex = simplex
		self.tree = tree # "Slider" or "Combo"

	def index(self, row, column, parent):
		obj = parent.internalPointer()
		child = obj.child(self.tree, row)
		if child is None:
			return QModelIndex()
		return self.createIndex(row, column, child)

	def parent(self, index):
		child = index.internalPointer()
		par = child.parent(self.tree)
		if par is None:
			return QModelIndex()
		return self.createIndex(par.getRow(self.tree), 0, par)

	def rowCount(self, parent):
		obj = parent.internalPointer()
		return obj.rowCount(self.tree)

	def columnCount(self, parent):
		return 3

	def data(self, index, role):
		obj = index.internalPointer()
		return obj.data(self.tree, index, role)

	def setData(self, index, value, role):
		self.dataChanged(index, index, [role])

	def flags(self, index):
		return None

	def headerData(self, section, orientation, role):
		if orientation == Qt.Horizontal:
			sects = ("Items", "Slide", "Value")
			try:
				return sects[section]
			except Exception:
				return None
		return None

	def insertRows(self, row, count, parent):
		self.beginInsertRows()
		pass
		self.endInsertRows()

	def removeRows(self, row, count, parent):
		self.beginRemoveRows()
		pass
		self.endRemoveRows()






