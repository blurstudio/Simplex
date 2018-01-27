#pylint:disable=missing-docstring,unused-argument,no-self-use
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

def getNextName(name, currentNames):
	''' Get the next available name '''
	i = 0
	s = set(currentNames)
	while True:
		if not i:
			nn = name
		else:
			nn = name + str(i)
		if nn not in s:
			return nn
		i += 1
	return name

# ABSTRACT CLASSES FOR HOLDING DATA
# Probably can be in a separate file
# In fact, most of this can be in an
# abstract base class file
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

	@classmethod
	def createPlanar(cls, name, simplex, axis, maxVal, maxHandle, minHandle, minVal):
		return cls(name, simplex, 'planar', axis, maxVal, maxHandle, minHandle, minVal)

	@classmethod
	def createMap(cls, name, simplex, mapName):
		return cls(name, simplex, 'map', mapName)

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
		nf.children = []
		nf.clearBuildIndex()
		self.simplex.falloffs.append(nf)
		self.simplex.DCC.duplicateFalloff(self, nf, newName)
		return nf

	def delete(self):
		""" delete a falloff """
		fIdx = self.simplex.falloffs.index(self)
		for child in self.children:
			child.falloff = None
		self.simplex.falloffs.pop(fIdx)

		self.simplex.DCC.deleteFalloff(self)

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

	def setMapData(self, mapName):
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
		self.simplex.DCC.setFalloffData(self, self.splitType, self.axis, self.minVal,
						  self.minHandle, self.maxHandle, self.maxVal, self.mapName)

class Shape(object):
	classDepth = 7
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

	@classmethod
	def createShape(cls, name, simplex, slider=None):
		''' Convenience method for creating a new shape
		This will create all required parent objects to have a new shape
		'''
		if simplex.restShape is None:
			raise RuntimeError("Simplex system is missing rest shape")

		if slider is None:
			# Implicitly creates a shape
			slider = Slider.createSlider(name, simplex)
			for p in slider.prog.pairs:
				if p.shape.name == name:
					return p.shape
			raise RuntimeError("Problem creating shape with proper name")
		else:
			if slider.simplex != simplex:
				raise RuntimeError("Slider does not belong to the provided Simplex")
			tVal = slider.prog.guessNextTVal()
			pp = slider.prog.createShape(name, tVal)
			return pp.shape

	@property
	def sliderModel(self):
		return self.simplex.sliderModel

	@property
	def comboModel(self):
		return self.simplex.comboModel

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, value): ### Data Changed (Slider, Combo)
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

	def zeroShape(self):
		""" Set the shape to be completely zeroed """
		self.simplex.DCC.zeroShape(self)

	@staticmethod
	def zeroShapes(shapes):
		for shape in shapes:
			if not shape.isRest:
				shape.zeroShape()

	def connectShape(self, mesh=None, live=False, delete=False):
		""" Force a shape to match a mesh
			The "connect shape" button is:
				mesh=None, delete=True
			The "match shape" button is:
				mesh=someMesh, delete=False
			There is a possibility of a "make live" button:
				live=True, delete=False
		"""
		self.simplex.DCC.connectShape(self, mesh, live, delete)

	@staticmethod
	def connectShapes(shapes, meshes, live=False, delete=False):
		for shape, mesh in zip(shapes, meshes):
			shape.connectShape(mesh, live, delete)

class ProgPair(object):
	classDepth = 6
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
	classDepth = 5
	def __init__(self, name, simplex, pairs=None, interp="spline", falloffs=None): ### Adds Rows (combo)
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

	@property
	def sliderModel(self):
		return self.simplex.sliderModel

	@property
	def comboModel(self):
		return self.simplex.comboModel

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

	def moveShapeToProgression(self, shapePair): ### Moves Rows (Slider, Combo)
		""" Remove the shapePair from its current progression
		and set it in a new progression """
		oldProg = shapePair.prog
		oldProg.pairs.remove(shapePair)
		self.pairs.append(shapePair)
		shapePair.prog = self

	def setShapesValues(self, values): ### Data Changed (Slider, Combo)
		""" Set the shape's value in it's progression """
		for pp, val in zip(self.pairs, values):
			pp.value = val
		if isinstance(self.parent, Slider):
			self.simplex.DCC.updateSlidersRange([self.parent])

	def addFalloff(self, falloff):
		""" Add a falloff to a slider's falloff list """
		self.falloffs.append(falloff)
		falloff.children.append(self)
		self.simplex.DCC.addProgFalloff(self, falloff)

	def removeFalloff(self, falloff):
		""" Remove a falloff from a slider's falloff list """
		self.falloffs.remove(falloff)
		falloff.children.remove(self)
		self.simplex.DCC.removeProgFalloff(self, falloff)

	def createShape(self, shapeName, tVal): ### Adds Rows (Slider, Combo)
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

	def deleteShape(self, shape): ### Removes Rows (Slider, Combo)
		ridx = None
		for i, pp in enumerate(self.pairs):
			if pp.shape == shape:
				ridx = i
		if ridx is None:
			raise RuntimeError("Shape does not exist to remove")
		self.pairs.pop(ridx)
		if not shape.isRest:
			self.simplex.shapes.remove(shape)
			self.simplex.DCC.deleteShape(shape)

	def delete(self): ### Removes Rows (Combo)
		for pp in self.pairs[:]:
			if pp.shape.isRest:
				continue
			self.simplex.shapes.remove(pp.shape)
			self.simplex.DCC.deleteShape(pp.shape)

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
	classDepth = 4
	def __init__(self, name, simplex, prog, group): ### Adds Row (Slider)
		if group.groupType != type(self):
			raise ValueError("Cannot add this slider to a combo group")
		self._name = name
		self._thing = None
		self._thingRepr = None
		self.prog = prog
		self.group = group
		self.split = False
		self.prog.controller = self
		self.group.items.append(self)
		self.simplex = None
		self._buildIdx = None
		self.value = 0.0
		self.minValue = -1.0
		self.maxValue = 1.0
		self.expanded = False
		self.simplex = simplex
		self.simplex.sliders.append(self)
		self.multiplier = 1

	@classmethod
	def createSlider(cls, name, simplex, group=None, shape=None, tVal=1.0, multiplier=1):
		"""
		Create a new slider with a name in a group.
		Possibly create a single default shape for this slider
		"""

		if simplex.restShape is None:
			raise RuntimeError("Simplex system is missing rest shape")

		if group is None:
			if simplex.sliderGroups:
				group = simplex.sliderGroups[0]
			else:
				group = Group('{0}_GROUP'.format(name), simplex, Slider)

		prog = Progression(name, simplex)
		if shape is None:
			prog.createShape(name, tVal)
		else:
			prog.pairs.append(ProgPair(shape, tVal))

		sli = cls(name, simplex, prog, group)
		simplex.DCC.createSlider(name, sli, multiplier=multiplier)
		sli.multiplier = multiplier
		return sli

	@property
	def sliderModel(self):
		return self.simplex.sliderModel

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, value): ### Data Changed (Slider, Combo)
		""" Set the name of a slider """
		self.name = value
		self.prog.name = value
		self.simplex.DCC.renameSlider(self, value, self.multiplier)
		# TODO Also rename the combo

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
		self.simplex.DCC.setSliderRange(self, multiplier)

	def delete(self): ### Removes Rows (Slider, Combo)
		""" Delete a slider, any shapes it contains, and all downstream combos """
		self.simplex.deleteDownstreamCombos(self)
		g = self.group
		g.items.remove(self)
		self.group = None
		self.simplex.sliders.remove(self)
		self.prog.delete()
		self.simplex.DCC.deleteSlider(self)

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
			ext, deltaShape = self.simplex.DCC.extractWithDeltaShape(shape, live, shift)
			for value, shape, shift in prog[:-1]:
				ext = self.simplex.DCC.extractWithDeltaConnection(shape, deltaShape, value/xtVal, live, shift)

	def extractShape(self, shape, live=True, offset=10.0):
		return self.simplex.DCC.extractShape(shape, live, offset)

	def connectShape(self, shape, mesh=None, live=False, delete=False):
		self.simplex.DCC.connectShape(shape, mesh, live, delete)

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
		return self.group.items.index(self)

	def rowCount(self, tree):
		return len(self.prog.pairs)

class ComboPair(object):
	classDepth = 3
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
				return self.value
		return None

	def getRow(self, tree):
		return self.combo.pairs.index(self)

	def rowCount(self, tree):
		return 0

class Combo(object):
	classDepth = 2
	def __init__(self, name, simplex, pairs, prog, group): ### Creates Row (Combo)
		if group.groupType != type(self):
			raise ValueError("Cannot add this slider to a combo group")
		self._name = name
		self.pairs = pairs
		self.prog = prog
		self.group = group
		self.prog.controller = self
		self.group.items.append(self)
		self.simplex = simplex
		self._buildIdx = None
		for p in self.pairs:
			p.combo = self
		self.expanded = False
		self.simplex.combos.append(self)

	@classmethod
	def createCombo(cls, name, simplex, sliders, values, group=None, shape=None, tVal=1.0):
		""" Create a combo of sliders at values """
		if simplex.restShape is None:
			raise RuntimeError("Simplex system is missing rest shape")

		if group is None:
			gname = "DEPTH_{0}".format(len(sliders))
			matches = [i for i in simplex.comboGroups if i.name == gname]
			if matches:
				group = matches[0]
			else:
				group = Group(gname, simplex, Combo)

		cPairs = [ComboPair(slider, value) for slider, value in zip(sliders, values)]
		prog = Progression(name, simplex)
		if shape:
			prog.pairs.append(ProgPair(shape, tVal))

		cmb = Combo(name, simplex, cPairs, prog, group)

		if shape is None:
			pp = prog.createShape(name, tVal)
			simplex.DCC.zeroShape(pp.shape)

		return cmb

	@property
	def comboModel(self):
		return self.simplex.comboModel

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, value): ### Data Changed (Combo)
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
			ext, deltaShape = self.simplex.DCC.extractWithDeltaShape(shape, live, shift)
			for value, shape, shift in prog[:-1]:
				ext = self.simplex.DCC.extractWithDeltaConnection(shape, deltaShape, value/xtVal, live, shift)

	def extractShape(self, shape, live=True, offset=10.0):
		""" Extract a shape from a combo progression """
		return self.simplex.DCC.extractComboShape(self, shape, live, offset)

	def connectComboShape(self, shape, mesh=None, live=False, delete=False):
		""" Connect a shape into a combo progression"""
		self.simplex.DCC.connectComboShape(self, shape, mesh, live, delete)

	def delete(self): ### Removes Rows (Combo)
		""" Delete a combo and any shapes it contains """
		g = self.group
		if self not in g.combos:
			return # Can happen when deleting multiple groups
		g.items.remove(self)
		self.group = None
		self.simplex.combos.remove(self)
		pairs = self.prog.pairs[:] # gotta make a copy
		for pair in pairs:
			pair.delete()

	def setInterpolation(self, interp): ### Data Changed (Combo)
		""" Set the interpolation of a combo """
		self.prog.interp = interp

	def setComboValue(self, slider, value): ### Data Changed (Combo)
		""" Set the Slider/value pairs for a combo """
		idx = self.getSliderIndex(slider)
		self.pairs[idx].value = value

	def appendComboValue(self, slider, value): ### Add Rows (Combo)
		""" Append a Slider/value pair for a combo """
		cp = ComboPair(slider, value)
		self.pairs.append(cp)
		cp.combo = self

	def deleteComboPair(self, comboPair): ### Removes Rows (Combo)
		""" delete a Slider/value pair for a combo """
		self.pairs.remove(comboPair)
		comboPair.combo = None
		# Move this combo to the proper depth group??

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
		return self.group.items.index(self)

	def rowCount(self, tree):
		# the extra is for the Shape sub-parent
		return len(self.pairs) + 1

class Group(object):
	classDepth = 1
	def __init__(self, name, simplex, groupType):
		self._name = name
		self.items = []
		self._buildIdx = None
		self.expanded = False
		self.groupType = groupType
		self.simplex = simplex

		if self.groupType == Slider and self.sliderModel:
			par = self.parent('Slider')
			parIdx = self.sliderModel.itemToIndex(par, 0, 'Slider')
			self.sliderModel.beginInsertRows(parIdx, len(par.sliderGroups), len(par.sliderGroups))
		if self.groupType == Combo and self.comboModel:
			par = self.parent('Combo')
			parIdx = self.comboModel.itemToIndex(par, 0, 'Combo')
			self.comboModel.beginInsertRows(parIdx, len(par.comboGroups), len(par.comboGroups))

		if self.groupType is Slider:
			self.simplex.sliderGroups.append(self)
		elif self.groupType is Combo:
			self.simplex.comboGroups.append(self)

		if self.sliderModel:
			self.sliderModel.endInsertRows()
		if self.comboModel:
			self.comboModel.endInsertRows()

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, value):
		self._name = value
		if self.groupType == Slider and self.sliderModel:
			idx = self.sliderModel.itemToIndex(self)
			self.sliderModel.dataChanged.emit(idx, idx)
		if self.groupType == Combo and self.comboModel:
			idx = self.comboModel.itemToIndex(self)
			self.comboModel.dataChanged.emit(idx, idx)

	@classmethod
	def createGroup(cls, name, simplex, things=None, groupType=None):
		''' Convenience method for creating a group '''

		thingType = None
		if things is not None:
			tps = list(set([type(i) for i in things]))
			if len(tps) != 1:
				raise RuntimeError("Cannot set both sliders and combos of a group")
			thingType = tps[0]

		if groupType is None:
			if thingType is None:
				raise RuntimeError("Must pass either a list of things, or a groupType")
			groupType = thingType
		else:
			if thingType is not None:
				if groupType is not thingType:
					raise RuntimeError("Group Type must match the type of all things")

		g = cls(name, simplex, groupType)
		if things is not None:
			g.take(things)
		return g

	@property
	def sliderModel(self):
		return self.simplex.sliderModel

	@property
	def comboModel(self):
		return self.simplex.comboModel

	def buildDefinition(self, simpDict):
		if self._buildIdx is None:
			simpDict.setdefault("groups", []).append(self.name)
			self._buildIdx = len(simpDict["groups"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None

	def delete(self): ### Removes Row (Slider, Combo)
		""" Delete a group. Any objects in this group will
		be deleted """

		if self.sliderModel:
			par = self.sliderModel.itemToIndex(self.parent('Slider'))
			row = self.getRow('Slider')
			self.sliderModel.beginRemoveRows(par, row, row)
		if self.comboModel:
			par = self.comboModel.itemToIndex(self.parent('Combo'))
			row = self.getRow('Combo')
			self.comboModel.beginRemoveRows(par, row, row)

		if self.groupType is Slider:
			if len(self.simplex.sliderGroups) == 1:
				return
			self.simplex.sliderGroups.remove(self)
		elif self.groupType is Combo:
			if len(self.simplex.comboGroups) == 1:
				return
			self.simplex.comboGroups.remove(self)

		if self.sliderModel:
			self.sliderModel.endRemoveRows()
		if self.comboModel:
			self.comboModel.endRemoveRows()

		# Gotta iterate over copies of the lists
		# as .delete removes the items from the list
		for item in self.items[:]:
			item.delete()

	def take(self, things): ### Moves Rows (Slider)
		if not all([isinstance(i, self.groupType) for i in things]):
			raise ValueError("All items in this group must be of type: {}".format(self.groupType))

		# do it this way instead of using set() to keep order
		for thing in things:
			if thing not in self.items:
				self.items.append(thing)
				thing.group = self

	# Qt Model methods
	def parent(self, tree):
		return self.simplex

	def child(self, tree, row):
		if tree == "Slider" and self.groupType is Slider:
			return self.items[row]
		elif tree == "Combo" and self.groupType is Combo:
			return self.items[row]
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

class Simplex(object):
	classDepth = 0
	'''
	The main Top-level abstract object that controls an entire simplex setup
	'''
	# CONSTRUCTORS
	def __init__(self, name="", sliderModel=None, comboModel=None):
		self._name = name # The name of the system
		self.sliders = [] # List of contained sliders
		self.combos = [] # List of contained combos
		self.sliderGroups = [] # List of groups containing sliders
		self.comboGroups = [] # List of groups containing combos
		self.falloffs = [] # List of contained falloff objects
		self.shapes = [] # List of contained shape objects
		self.restShape = None # Name of the rest shape
		self.clusterName = "Shape" # Name of the cluster (XSI use only)
		self.expanded = False # Am I expanded? (Keep around for consistent interface)
		self.comboExpanded = False # Am I expanded in the combo tree
		self.sliderExpanded = False # Am I expanded in the slider tree
		self.DCC = DCC(self) # Interface to the DCC
		self.sliderModel = sliderModel # Link to the Qt Item Slider model
		self.comboModel = comboModel # Link to the Qt Item Combo model

	def _initValues(self):
		self._name = "" # The name of the system
		self.sliders = [] # List of contained sliders
		self.combos = [] # List of contained combos
		self.sliderGroups = [] # List of groups containing sliders
		self.comboGroups = [] # List of groups containing combos
		self.falloffs = [] # List of contained falloff objects
		self.shapes = [] # List of contained shape objects
		self.restShape = None # Name of the rest shape
		self.clusterName = "Shape" # Name of the cluster (XSI use only)
		self.expanded = False # Am I expanded? (Keep around for consistent interface)
		self.comboExpanded = False # Am I expanded in the combo tree
		self.sliderExpanded = False # Am I expanded in the slider tree

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

		if self.sliderModel:
			idx = self.sliderModel.indexFromItem(self, 0, 'Slider')
			self.sliderModel.dataChanged.emit(idx, idx)

		if self.comboModel:
			idx = self.comboModel.indexFromItem(self, 0, 'Combo')
			self.comboModel.dataChanged.emit(idx, idx)

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

	# DESTRUCTOR
	def deleteSystem(self):
		''' Delete an existing system from file '''
		# Store the models as temp so the model doesn't go crazy with the signals
		sliderModel, self.sliderModel = self.sliderModel, None
		comboModel, self.comboModel = self.comboModel, None
		if sliderModel:
			sliderModel.beginResetModel()
		if comboModel:
			comboModel.beginResetModel()

		self.DCC.deleteSystem()
		self._initValues()
		self.DCC = DCC(self)

		if sliderModel:
			sliderModel.endResetModel()
		if comboModel:
			comboModel.endResetModel()

		# Reset the models
		self.sliderModel = sliderModel
		self.comboModel = comboModel

	def deleteDownstreamCombos(self, slider):
		todel = []
		for c in self.combos:
			for pair in c.pairs:
				if pair.slider == slider:
					todel.append(c)
		for c in todel:
			c.delete()

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
		groupNames = simpDict["groups"]
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
			sliderGroup = Group(groupNames[s[2]], self, Slider)
			sli = Slider(s[0], self, sliderProg, sliderGroup)
			sli.simplex = self
			self.sliders.append(sli)
			self.sliderGroups.append(sli.group)

		self.combos = []
		self.comboGroups = []
		defaultGroup = None
		for c in simpDict["combos"]:
			prog = progs[c[1]]
			sliderIdxs, sliderVals = zip(*c[2])
			sliders = [self.sliders[i] for i in sliderIdxs]
			pairs = map(ComboPair, sliders, sliderVals)
			if len(c) >= 4:
				comboGroup = Group(groupNames[c[3]], self, Combo)
			else:
				if defaultGroup is None:
					comboGroup = Group("DEPTH_0", self, Combo)
				else:
					comboGroup = defaultGroup

			cmb = Combo(c[0], self, pairs, prog, comboGroup)
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

	def setSlidersWeights(self, sliders, weights):
		''' Set the weights of multiple sliders as one action '''
		for slider, weight in zip(sliders, weights):
			slider.value = weight
		self.DCC.setSlidersWeights(sliders, weights)
		if self.sliderModel:
			for slider in sliders:
				index = self.sliderModel.itemToIndex(slider, 1, 'Slider')
				self.sliderModel.dataChanged.emit(index, index)

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
		super(SimplexModel, self).__init__(parent)
		self.simplex = simplex
		self.tree = tree # "Slider" or "Combo"

	def index(self, row, column, parIndex):
		if not parIndex.isValid():
			obj = self.simplex
		else:
			obj = parIndex.internalPointer()

		child = obj.child(self.tree, row)
		if child is None:
			return QModelIndex()
		return self.createIndex(row, column, child)

	def parent(self, index):
		if not index.isValid():
			return QModelIndex()
		child = index.internalPointer()
		par = child.parent(self.tree)
		if par is None:
			return QModelIndex()
		return self.createIndex(par.getRow(self.tree), 0, par)

	def rowCount(self, parent):
		if not parent.isValid():
			obj = self.simplex
		else:
			obj = parent.internalPointer()
		return obj.rowCount(self.tree)

	def columnCount(self, parent):
		return 3

	def data(self, index, role):
		if not index.isValid():
			return None
		obj = index.internalPointer()
		return obj.data(self.tree, index, role)

	def setData(self, index, value, role):
		self.dataChanged.emit(index, index, role)

	def flags(self, index):
		if not index.isValid():
			return Qt.ItemIsEnabled
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

	def headerData(self, section, orientation, role):
		if orientation == Qt.Horizontal:
			sects = ("Items", "Slide", "Value")
			return sects[section]
		return None

	def itemToIndex(self, item, column, tree):
		return self.createIndex(item.getRow(tree), column, item)

	def indexToItem(self, index):
		return index.internalPointer()

	def coerceToType(self, idxs, typ):
		''' Get a list of indices of a specific role based on a given index list
		Lists containing parents of the role fall down to their children
		Lists containing children of the role climb up to their parents
		'''
		targetDepth = typ.classDepth

		children = []
		parents = []
		shapeIdxs = []
		for idx in idxs:
			depth = idx.internalPointer().classDepth
			if depth < targetDepth:
				parents.append(idx)
			elif depth > targetDepth:
				children.append(idx)
			else:
				shapeIdxs.append(idx)

		shapeIdxs.extend(self.coerceToChildType(parents, typ))
		shapeIdxs.extend(self.coerceToParentType(children, typ))
		shapeIdxs = list(set(shapeIdxs))
		return shapeIdxs

	def coerceToChildType(self, idxs, typ):
		''' Get a list of indices of a specific role based on a given index list
		Lists containing parents of the role fall down to their children
		'''
		targetDepth = typ.classDepth
		shapeIdxs = []
		for idx in idxs:
			depth = idx.internalPointer().classDepth
			if depth < targetDepth:
				# Too high up, grab children
				queue = [idx]
				out = []
				while queue:
					checkIdx = queue.pop()
					if depth < targetDepth:
						for row in self.rowCount(checkIdx):
							childIdx = self.index(checkIdx, row, 0)
							queue.append(childIdx)
					else:
						out.append(checkIdx)
				out = [i for i in out if i.internalPointer().classDepth == targetDepth]
				shapeIdxs.extend(out)
			elif depth == targetDepth:
				shapeIdxs.append(idx)
		shapeIdxs = list(set(shapeIdxs))
		return shapeIdxs

	def coerceToParentType(self, idxs, typ):
		''' Get a list of indices of a specific role based on a given index list
		Lists containing children of the role climb up to their parents
		'''
		targetDepth = typ.classDepth
		shapeIdxs = []
		for idx in idxs:
			depth = idx.internalPointer().classDepth
			if depth > targetDepth:
				ii = idx
				while ii.internalPointer().classDepth > targetDepth:
					ii = self.parent(ii)
				if ii.internalPointer().classDepth == targetDepth:
					shapeIdxs.append(ii)
			elif depth == targetDepth:
				shapeIdxs.append(idx)
		shapeIdxs = list(set(shapeIdxs))
		return shapeIdxs

	def coerceToRoots(self, idxs):
		''' Get the topmost index of each brach in the hierarchy '''
		# Sort by depth
		idxs = sorted(idxs, key=lambda x: x.internalPointer().classDepth, reverse=True)

		# Check each item to see if any of it's ancestors
		# are in the selection list.  If not, it's a root
		roots = []
		for item in idxs:
			par = self.parent(item)
			while par.isValid():
				if par in idxs:
					break
				par = self.parent(par)
			else:
				roots.append(item)
		return roots

	def updateTickValues(self, updatePairs):
		''' Update all the drag-tick values at once. This should be called
		by a single-shot timer or some other once-per-refresh mechanism
		'''
		# Don't make this mouse-tick be stackable. That way
		# we don't update the whole System for a slider value changes
		sliderList = []
		progs = []
		for i in updatePairs:
			if isinstance(i[0], Slider):
				sliderList.append(i)
			elif isinstance(i[0], ProgPair):
				progs.append(i)

		if progs:
			progPairs, values = zip(*progs)
			self.simplex.setShapesValues(progPairs, values)
			for pp in progPairs:
				if isinstance(pp.prog.parent, Slider):
					self.updateSliderRange(pp.prog.parent)

		if sliderList:
			sliders, values = zip(*sliderList)
			self.simplex.setSlidersWeights(sliders, values)





