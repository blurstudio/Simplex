#pylint:disable=missing-docstring,unused-argument,no-self-use
import os, sys, copy, json, itertools, gc
from alembic.Abc import OArchive, IArchive, OStringProperty
from alembic.AbcGeom import OXform, OPolyMesh, IXform, IPolyMesh
from Qt.QtCore import QAbstractItemModel, QModelIndex, Qt, QSortFilterProxyModel, QAbstractProxyModel
from Qt.QtGui import QColor
from fnmatch import fnmatchcase
from utils import getNextName, nested
from contextlib import contextmanager

CONTEXT = os.path.basename(sys.executable)
if CONTEXT == "maya.exe":
	from mayaInterface import DCC
elif CONTEXT == "XSI.exe":
	from xsiInterface import DCC
else:
	from dummyInterface import DCC



# Abstract Items
class Falloff(object):
	def __init__(self, name, simplex, *data):
		self.name = name
		self.children = []
		self._buildIdx = None
		self.splitType = data[0]
		self.expanded = {}
		self.color = QColor(128, 128, 128)
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

	@property
	def models(self):
		return self.simplex.models

	@classmethod
	def createPlanar(cls, name, simplex, axis, maxVal, maxHandle, minHandle, minVal):
		return cls(name, simplex, 'planar', axis, maxVal, maxHandle, minHandle, minVal)

	@classmethod
	def createMap(cls, name, simplex, mapName):
		return cls(name, simplex, 'map', mapName)

	def buildDefinition(self, simpDict):
		if self._buildIdx is None:
			x = {
				"type": self.splitType,
				"axis": self.axis,
				"maxVal": self.maxVal,
				"maxHandle": self.maxHandle,
				"minHandle": self.minHandle,
				"minVal": self.minVal,
				"mapName": self.mapName,
				"color": self.color.getRgb()[:3],
			}
			self._buildIdx = len(simpDict["falloffs"])
			simpDict.setdefault("falloffs", []).append(x)
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
		self.expanded = {}
		self.color = QColor(128, 128, 128)
		self.simplex = simplex
		# maybe Build thing on creation?

	@property
	def models(self):
		return self.simplex.models

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
	def name(self):
		return self._name

	@name.setter
	def name(self, value):
		self._name = value
		self.simplex.DCC.renameShape(self, value)
		for model in self.models:
			model.itemDataChanged(self)

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
			x = {
				"name": self.name,
				"color": self.color.getRgb()[:3],
			}
			self._buildIdx = len(simpDict["shapes"])
			simpDict.setdefault("shapes", []).append(x)
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
		self._value = value
		self.prog = None
		self.minValue = -1.0
		self.maxValue = 1.0
		self.expanded = {}

	@property
	def models(self):
		return self.prog.simplex.models

	@property
	def name(self):
		return self.shape.name

	def buildDefinition(self, simpDict):
		idx = self.shape.buildDefinition(simpDict)
		return idx, self.value

	def __lt__(self, other):
		return self.value < other.value

	@property
	def value(self):
		return self._value

	@value.setter
	def value(self, val):
		self._value = val
		for model in self.models:
			model.itemDataChanged(self)


class Progression(object):
	classDepth = 5
	def __init__(self, name, simplex, pairs=None, interp="spline", falloffs=None):
		self.simplex = simplex
		self.name = name
		self.interp = interp
		self.falloffs = falloffs or []
		self.controller = None

		if pairs is None:
			self.pairs = [ProgPair(self.simplex.restShape, 0.0)]
		else:
			self.pairs = pairs

		for pair in self.pairs:
			pair.prog = self

		for falloff in self.falloffs:
			falloff.children.append(self)
		self._buildIdx = None
		self.expanded = {}

	@property
	def models(self):
		return self.simplex.models

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
			x = {
				"name": self.name,
				"shapes": idxs,
				"values": values,
				"interp": self.interp,
				"falloffs": foIdxs,
			}
			self._buildIdx = len(simpDict["progressions"])
			simpDict.setdefault("progressions", []).append(x)
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

	def setShapesValues(self, values):
		""" Set the shape's value in it's progression """
		for pp, val in zip(self.pairs, values):
			pp.value = val
			for model in self.models:
				model.itemDataChanged(pp)

		if isinstance(self.controller, Slider):
			self.simplex.DCC.updateSlidersRange([self.controller])
			for model in self.models:
				model.itemDataChanged(self.controller)

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

	def createShape(self, shapeName=None, tVal=None):
		""" create a shape and add it to a progression """
		if tVal is None:
			tVal = self.guessNextTVal()

		if shapeName is None:
			if abs(tVal) == 1.0:
				shapeName = self.controller.name
			else:
				shapeName = "{0}_{1}".format(self.controller.name, int(abs(tVal)*100))
			currentNames = [i.name for i in self.simplex.shapes]
			shapeName = getNextName(shapeName, currentNames)

		shape = Shape(shapeName, self.simplex)
		pp = ProgPair(shape, tVal)

		mgrs = [model.insertItemManager(self) for model in self.models]
		with nested(*mgrs):
			pp.prog = self
			self.pairs.append(pp)

		self.simplex.DCC.createShape(shapeName, pp)
		if isinstance(self.controller, Slider):
			self.simplex.DCC.updateSlidersRange([self.controller])

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

		pp = self.pairs[ridx]
		mgrs = [model.removeItemManager(pp) for model in self.models]
		with nested(*mgrs):
			self.pairs.pop(ridx)
			if not shape.isRest:
				self.simplex.shapes.remove(shape)
				self.simplex.DCC.deleteShape(shape)

	def delete(self):
		mgrs = [model.removeItemManager(self) for model in self.models]
		with nested(*mgrs):
			for pp in self.pairs[:]:
				if pp.shape.isRest:
					continue
				self.simplex.shapes.remove(pp.shape)
				self.simplex.DCC.deleteShape(pp.shape)


class Slider(object):
	classDepth = 4
	def __init__(self, name, simplex, prog, group):
		if group.groupType != type(self):
			raise ValueError("Cannot add this slider to a combo group")

		self.simplex = simplex
		self._name = name
		self._thing = None
		self._thingRepr = None
		self.prog = prog
		self.split = False
		self.prog.controller = self
		self._buildIdx = None
		self._value = 0.0
		self.minValue = -1.0
		self.maxValue = 1.0
		self.expanded = {}
		self.color = QColor(128, 128, 128)
		self.multiplier = 1
		self.setRange(self.multiplier)

		mgrs = [model.insertItemManager(group) for model in self.models]
		with nested(*mgrs):
			self.group = group
			self.group.items.append(self)
		self.simplex.sliders.append(self)

	@property
	def models(self):
		return self.simplex.models

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

		currentNames = [s.name for s in simplex.sliders]
		name = getNextName(name, currentNames)

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
	def name(self):
		return self._name

	@name.setter
	def name(self, value):
		""" Set the name of a slider """
		self.name = value
		self.prog.name = value
		self.simplex.DCC.renameSlider(self, value, self.multiplier)
		# TODO Also rename the combos
		for model in self.models:
			model.itemDataChanged(self)

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

	@property
	def value(self):
		return self._value

	@value.setter
	def value(self, val):
		self._value = val
		for model in self.models:
			model.itemDataChanged(self)

	def buildDefinition(self, simpDict):
		if self._buildIdx is None:
			x = {
				"name": self.name,
				"prog": self.prog.buildDefinition(simpDict),
				"group": self.group.buildDefinition(simpDict),
				"color": self.color.getRgb()[:3],
			}
			self._buildIdx = len(simpDict["sliders"])
			simpDict.setdefault("sliders", []).append(x)
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
		values = [i.value for i in self.prog.pairs]
		self.minValue = min(values)
		self.maxValue = max(values)
		self.simplex.DCC.setSliderRange(self, multiplier)

	def delete(self):
		""" Delete a slider, any shapes it contains, and all downstream combos """
		self.simplex.deleteDownstreamCombos(self)
		mgrs = [model.removeItemManager(self) for model in self.models]
		with nested(*mgrs):
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


class ComboPair(object):
	classDepth = 3
	def __init__(self, slider, value):
		self.slider = slider
		self._value = float(value)
		self.minValue = -1.0
		self.maxValue = 1.0
		self.combo = None
		self.expanded = {}

	@property
	def models(self):
		return self.combo.simplex.models

	@property
	def name(self):
		return self.slider.name

	@property
	def value(self):
		return self._value

	@value.setter
	def value(self, val):
		self._value = val
		for model in self.models:
			model.itemDataChanged(self)

	def buildDefinition(self, simpDict):
		sIdx = self.slider.buildDefinition(simpDict)
		return sIdx, self.value


class Combo(object):
	classDepth = 2
	def __init__(self, name, simplex, pairs, prog, group):
		self.simplex = simplex
		if group.groupType != type(self):
			raise ValueError("Cannot add this slider to a combo group")
		self._name = name
		self.pairs = pairs
		self.prog = prog
		self._buildIdx = None
		self.expanded = {}
		self.color = QColor(128, 128, 128)

		mgrs = [model.insertItemManager(group) for model in self.models]
		with nested(*mgrs):

			self.group = group
			for p in self.pairs:
				p.combo = self
			self.prog.controller = self
			self.group.items.append(self)
			self.simplex.combos.append(self)

	@property
	def models(self):
		return self.simplex.models

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
	def name(self):
		return self._name

	@name.setter
	def name(self, value):
		""" Set the name of a combo """
		self._name = value
		self.prog.name = value
		self.simplex.DCC.renameCombo(self, value)
		for model in self.models:
			model.itemDataChanged(self)

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
			x = {
				"name": self.name,
				"prog": self.prog.buildDefinition(simpDict),
				"pairs": [p.buildDefinition(simpDict) for p in self.pairs],
				"group": self.group.buildDefinition(simpDict),
				"color": self.color.getRgb()[:3],
			}
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

	def delete(self):
		""" Delete a combo and any shapes it contains """
		mgrs = [model.removeItemManager(self) for model in self.models]
		with nested(*mgrs):
			g = self.group
			if self not in g.items:
				return # Can happen when deleting multiple groups
			g.items.remove(self)
			self.group = None
			self.simplex.combos.remove(self)
			pairs = self.prog.pairs[:] # gotta make a copy
			for pair in pairs:
				pair.delete()

	def setInterpolation(self, interp):
		""" Set the interpolation of a combo """
		self.prog.interp = interp
		for model in self.models:
			model.itemDataChanged(self)

	def setComboValue(self, slider, value):
		""" Set the Slider/value pairs for a combo """
		idx = self.getSliderIndex(slider)
		pair = self.pairs[idx]
		pair.value = value
		for model in self.models:
			model.itemDataChanged(pair)

	def appendComboValue(self, slider, value):
		""" Append a Slider/value pair for a combo """
		cp = ComboPair(slider, value)
		mgrs = [model.insertItemManager(self) for model in self.models]
		with nested(*mgrs):
			self.pairs.append(cp)
			cp.combo = self

	def deleteComboPair(self, comboPair):
		""" delete a Slider/value pair for a combo """
		mgrs = [model.removeItemManager(comboPair) for model in self.models]
		with nested(*mgrs):
			# We specifically don't move the combo to the proper depth group
			# That way the user can make multiple changes to the combo without
			# it popping all over in the heirarchy
			self.pairs.remove(comboPair)
			comboPair.combo = None


class Group(object):
	classDepth = 1
	def __init__(self, name, simplex, groupType):
		self._name = name
		self.items = []
		self._buildIdx = None
		self.expanded = {}
		self.color = QColor(128, 128, 128)
		self.groupType = groupType
		self.simplex = simplex

		mgrs = [model.insertItemManager(simplex) for model in self.models]
		with nested(*mgrs):
			if self.groupType is Slider:
				self.simplex.sliderGroups.append(self)
			elif self.groupType is Combo:
				self.simplex.comboGroups.append(self)

	@property
	def models(self):
		return self.simplex.models

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, value):
		self._name = value
		for model in self.models:
			model.itemDataChanged(self)

	@classmethod
	def createGroup(cls, name, simplex, things=None, groupType=None):
		''' Convenience method for creating a group '''
		g = cls(name, simplex, groupType)
		if things is not None:
			g.add(things)
		return g

	@classmethod
	def loadV2(cls, simplex, defDict):
		pass

	def buildDefinition(self, simpDict):
		if self._buildIdx is None:
			x = {
				"name": self.name,
				"color": self.color.getRgb()[:3],
			}
			self._buildIdx = len(simpDict["groups"])
			simpDict.setdefault("groups", []).append(x)
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None

	def delete(self):
		""" Delete a group. Any objects in this group will be deleted """
		if self.groupType is Slider:
			if len(self.simplex.sliderGroups) == 1:
				return
			gList = self.simplex.sliderGroups
		elif self.groupType is Combo:
			if len(self.simplex.comboGroups) == 1:
				return
			gList = self.simplex.comboGroups
		else:
			raise RuntimeError("Somehow this group has no type")

		mgrs = [model.removeItemManager(self) for model in self.models]
		with nested(*mgrs):
			gList.remove(self)
			# Gotta iterate over copies of the lists
			# as .delete removes the items from the list
			for item in self.items[:]:
				item.delete()

	def add(self, things): ### Moves Rows (Slider)
		if self.groupType is None:
			self.groupType = type(things[0])

		if not all([isinstance(i, self.groupType) for i in things]):
			raise ValueError("All items in this group must be of type: {}".format(self.groupType))

		# do it this way instead of using set() to keep order
		for thing in things:
			if thing not in self.items:
				self.items.append(thing)
				thing.group = self


class Simplex(object):
	classDepth = 0
	'''
	The main Top-level abstract object that controls an entire simplex setup

	Note: There are no "Load a system over the current one" type methods.
	To accomplish that, just construct a new Simplex object over top of it
	'''
	def __init__(self, name="", models=None):
		self._name = name # The name of the system
		self.sliders = [] # List of contained sliders
		self.combos = [] # List of contained combos
		self.sliderGroups = [] # List of groups containing sliders
		self.comboGroups = [] # List of groups containing combos
		self.falloffs = [] # List of contained falloff objects
		self.shapes = [] # List of contained shape objects
		self.models = models or [] # connected Qt Item Models
		self.restShape = None # Name of the rest shape
		self.clusterName = "Shape" # Name of the cluster (XSI use only)
		self.expanded = {} # Am I expanded by model
		self.comboExpanded = False # Am I expanded in the combo tree
		self.sliderExpanded = False # Am I expanded in the slider tree
		self.DCC = DCC(self) # Interface to the DCC


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
		self.expanded = {} # Am I expanded? (Keep around for consistent interface)
		self.color = QColor(128, 128, 128)
		self.comboExpanded = False # Am I expanded in the combo tree
		self.sliderExpanded = False # Am I expanded in the slider tree

	# Alternate Constructors
	@classmethod
	def buildBaseObject(cls, smpxPath, name=None):
		iarch, abcMesh, js = cls.getAbcDataFromPath(smpxPath)
		try:
			if name is None:
				name = js['systemName']
			return DCC.buildRestAbc(abcMesh, name)
		finally:
			del iarch

	@classmethod
	def buildEmptySystem(cls, thing, name):
		''' Create a new system on a given mesh, ready to go '''
		self = cls(name)
		self.buildRest()
		self.DCC.loadNodes(self, thing, create=True)
		return self

	@classmethod
	def buildSystemFromJson(cls, jsPath, thing, name=None):
		with open(jsPath, 'r') as f:
			jsDict = json.load(f)

		if name is None:
			name = jsDict['systemName']

		return cls._buildSystemFromDict(jsDict, thing, name=name)

	@classmethod
	def buildSystemFromSmpx(cls, smpxPath, thing=None, name=None):
		""" Build a system from a simplex abc file """
		if thing is None:
			thing = cls.buildBaseObject(smpxPath)

		iarch, abcMesh, js = cls.getAbcDataFromPath(smpxPath)
		del iarch, abcMesh # release the files
		if name is None:
			name = js['systemName']
		self = cls._buildSystemFromDict(js, thing, name)
		self.loadSmpxShapes(smpxPath)
		return self

	@classmethod
	def buildSystemFromMesh(cls, thing, name):
		jsDict = json.loads(DCC.getSimplexStringOnThing(thing, name))
		return cls._buildSystemFromDict(jsDict, thing, name, False)

	@classmethod
	def _buildSystemFromDict(cls, jsDict, thing, name=None, create=True):
		''' Utility for building a cleared system from a dictionary '''
		if name is None:
			name = jsDict['systemName']
		self = cls.buildEmptySystem(thing, name)
		self.DCC.loadNodes(self, thing, create=create)
		self.DCC.loadConnections(self, create=create)
		self.loadDefinition(jsDict)
		return self

	def loadSmpxShapes(self, smpxPath):
		iarch, abcMesh, js = self.getAbcDataFromPath(smpxPath)
		try:
			self.DCC.loadAbc(abcMesh, js)
		finally:
			del iarch

	def buildRest(self):
		""" create/find the system's rest shape"""
		if self.restShape is None:
			self.restShape = Shape(self._buildRestName(), self)
			self.restShape.isRest = True

		if not self.restShape.thing:
			pp = ProgPair(self.restShape, 1.0) # just to pass to createShape
			self.DCC.createShape(self.restShape.name, pp)
		return self.restShape

	# Properties
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

		for model in self.models:
			model.itemDataChanged(self)

	@property
	def progs(self):
		out = []
		for slider in self.sliders:
			out.append(slider.prog)
		for combo in self.combos:
			out.append(combo.prog)
		return out

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
			return None, None, None

		# Must return the archive, otherwise it gets GC'd
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
		models, self.models = self.models, None
		mgrs = [model.resetModelManager() for model in self.models]
		with nested(*mgrs):
			self.DCC.deleteSystem()
			self._initValues()
			self.DCC = DCC(self)
		self.models = models

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
		d["encodingVersion"] = 2
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
		if simpDict["encodingVersion"] == 1:
			self.loadV1(simpDict)
		elif simpDict["encodingVersion"] == 2:
			self.loadV2(simpDict)

	def loadV2(self, simpDict):
		self.falloffs = [Falloff.loadV2(self, f) for f in simpDict['falloffs']]
		self.groups = [Group.loadV2(self, g) for g in simpDict['groups']]
		self.progs = [Progression.loadV2(self, p) for p in simpDict['progressions']]
		self.sliders = [Slider.loadV2(self, s) for s in simpDict['sliders']]
		self.combos = [Combo.loadV2(self, c) for c in simpDict['combos']]
		for x in itertools.chain(self.sliders, self.combos):
			x.prog.name = x.name

	def loadV1(self, simpDict):
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
		createdSlidergroups = {}
		for s in simpDict["sliders"]:
			sliderProg = progs[s[1]]

			gn = groupNames[s[2]]
			if gn in createdSlidergroups:
				sliderGroup = createdSlidergroups[gn]
			else:
				sliderGroup = Group(gn, self, Slider)
				createdSlidergroups[gn] = sliderGroup

			Slider(s[0], self, sliderProg, sliderGroup)

		self.combos = []
		self.comboGroups = []
		createdComboGroups = {}
		for c in simpDict["combos"]:
			prog = progs[c[1]]
			sliderIdxs, sliderVals = zip(*c[2])
			sliders = [self.sliders[i] for i in sliderIdxs]
			pairs = map(ComboPair, sliders, sliderVals)
			if len(c) >= 4:
				gn = groupNames[c[3]]
			else:
				gn = "DEPTH_0"

			if gn in createdComboGroups:
				comboGroup = createdComboGroups[gn]
			else:
				comboGroup = Group(groupNames[c[3]], self, Combo)
				createdComboGroups[gn] = comboGroup

			cmb = Combo(c[0], self, pairs, prog, comboGroup)
			cmb.simplex = self
			self.combos.append(cmb)

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
		for model in self.models:
			for slider in sliders:
				model.itemDataChanged(slider)



# Hierarchy Helpers
def coerceToType(items, typ, tree):
	''' Get a list of indices of a specific role based on a given index list
	Lists containing parents of the role fall down to their children
	Lists containing children of the role climb up to their parents
	'''
	targetDepth = typ.classDepth

	children = []
	parents = []
	out = []
	for item in items:
		depth = item.classDepth
		if depth < targetDepth:
			parents.append(item)
		elif depth > targetDepth:
			children.append(item)
		else:
			out.append(item)

	out.extend(coerceToChildType(parents, typ, tree))
	out.extend(coerceToParentType(children, typ, tree))
	out = list(set(out))
	return out

def coerceToChildType(items, typ, tree):
	''' Get a list of indices of a specific role based on a given index list
	Lists containing parents of the role fall down to their children
	'''
	targetDepth = typ.classDepth
	out = []

	for item in items:
		depth = item.classDepth
		if depth < targetDepth:
			# Too high up, grab children
			queue = [item]
			depthItems = []
			while queue:
				check = queue.pop()
				if check.depth < targetDepth:
					for row in check.rowCount(tree):
						queue.append(check.child(tree, row))
				else:
					depthItems.append(item)
			# I'm Paranoid
			depthItems = [i for i in depthItems if i.classDepth == targetDepth]
			out.extend(depthItems)
		elif depth == targetDepth:
			out.append(item)

	out = list(set(out))
	return out

def coerceToParentType(items, typ, tree):
	''' Get a list of indices of a specific role based on a given index list
	Lists containing children of the role climb up to their parents
	'''
	targetDepth = typ.classDepth
	out = []
	for item in items:
		depth = item.classDepth
		if depth > targetDepth:
			ii = item
			while ii.classDepth > targetDepth:
				ii = ii.parent(tree)
			if ii.classDepth == targetDepth:
				out.append(ii)
		elif depth == targetDepth:
			out.append(item)

	out = list(set(out))
	return out

def coerceToRoots(items, tree):
	''' Get the topmost items for each brach in the hierarchy '''
	items = sorted(items, key=lambda x: x.classDepth, reverse=True)
	# Check each item to see if any of it's ancestors
	# are in the selection list.  If not, it's a root
	roots = []
	for item in items:
		par = item.parent(tree)
		while par is not None:
			if par in items:
				break
			par = par.parent(tree)
		else:
			roots.append(item)
	return roots



# BASE MODEL
class SimplexModel(QAbstractItemModel):
	''' The base model for all interaction with a simplex system.
	All ui interactions with a simplex system must go through this model
	Any special requirements, or reorganizations of the trees will only
	be implemented as proxy models.
	'''
	def __init__(self, simplex, parent):
		super(SimplexModel, self).__init__(parent)
		self.simplex = simplex
		self.simplex.models.append(self)

	def index(self, row, column, parIndex):
		par = parIndex.internalPointer()
		child = self.getChildItem(par, row)
		if child is None:
			return QModelIndex()
		return self.createIndex(row, column, child)

	def parent(self, index):
		if not index.isValid():
			return QModelIndex()
		item = index.internalPointer()
		if item is None:
			return QModelIndex()
		par = self.getParentItem(item)
		row = self.getItemRow(par)
		if row is None:
			return QModelIndex()
		return self.createIndex(row, 0, par)

	def rowCount(self, parIndex):
		parent = parIndex.internalPointer()
		ret = self.getItemRowCount(parent)
		return ret

	def columnCount(self, parIndex):
		return 3

	def data(self, index, role):
		if not index.isValid():
			return None
		item = index.internalPointer()
		return self.getItemData(item, index.column(), role)

	def flags(self, index):
		if not index.isValid():
			return Qt.ItemIsEnabled
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

	def headerData(self, section, orientation, role):
		if orientation == Qt.Horizontal:
			if role == Qt.DisplayRole:
				sects = ("Items", "Slide", "Value")
				return sects[section]
		return None


	# Methods for dealing with items only
	# These will be used to build the indexes
	# and will be public for utility needs
	def getChildItem(self, parent, row):
		child = None
		try:
			if isinstance(parent, Simplex):
				groups = parent.sliderGroups + parent.comboGroups
				child = groups[row]
			elif isinstance(parent, Group):
				child = parent.items[row]
			elif isinstance(parent, Slider):
				child = parent.prog.pairs[row]
			elif isinstance(parent, Combo):
				if row == len(parent.pairs):
					child = parent.prog
				else:
					child = parent.pairs[row]
			elif isinstance(parent, Progression):
				child = parent.pairs[row]
			elif parent is None:
				if row == 0:
					child = self.simplex
			#elif isinstance(parent, ComboPair):
				#child = None
			#elif isinstance(parent, ProgPair):
				#child = None
		except IndexError:
			pass
		return child

	def getItemRow(self, item):
		row = None
		try:
			if isinstance(item, Group):
				groups = item.simplex.sliderGroups + item.simplex.comboGroups
				row = groups.index(item)
			elif isinstance(item, Slider):
				row = item.group.items.index(item)
			elif isinstance(item, ProgPair):
				row = item.prog.pairs.index(item)
			elif isinstance(item, Combo):
				row = item.group.items.index(item)
			elif isinstance(item, ComboPair):
				row = item.combo.pairs.index(item)
			elif isinstance(item, Progression):
				row = len(item.pairs)
			elif isinstance(item, Simplex):
				row = 0
		except (ValueError, AttributeError):
			pass
		return row

	def getParentItem(self, item):
		par = None
		if isinstance(item, Group):
			par = item.simplex
		elif isinstance(item, Slider):
			par = item.group
		elif isinstance(item, Progression):
			par = item.controller
		elif isinstance(item, Combo):
			par = item.group
		elif isinstance(item, ComboPair):
			par = item.combo
		elif isinstance(item, ProgPair):
			par = item.prog
		return par

	def getItemRowCount(self, item):
		ret = 0
		if isinstance(item, Simplex):
			ret = len(item.sliderGroups) + len(item.comboGroups)
		elif isinstance(item, Group):
			ret = len(item.items)
		elif isinstance(item, Slider):
			ret = len(item.prog.pairs)
		elif isinstance(item, Combo):
			ret = len(item.pairs) + 1
		elif isinstance(item, Progression):
			ret = len(item.pairs)
		elif item is None:
			# Null parent means 1 row that is the simplex object
			ret = 1
		return ret

	def getItemData(self, item, column, role):
		if role in (Qt.DisplayRole, Qt.EditRole):
			if column == 0:
				if isinstance(item, (Simplex, Group, Slider, ProgPair, Combo, ComboPair, ProgPair)):
					return item.name
				elif isinstance(item, Progression):
					return "SHAPES"
			elif column == 1:
				if isinstance(item, Slider):
					return item.value
				elif isinstance(item, ComboPair):
					return item.value
				return None
			elif column == 2:
				if isinstance(item, ProgPair):
					return item.value
				return None
		return None

	# Supplimentary utility methods
	def indexFromItem(self, item, column=0):
		row = self.getItemRow(item)
		if row is None:
			return QModelIndex()
		return self.createIndex(row, column, item)

	def itemFromIndex(self, index):
		return index.internalPointer()

	def updateTickValues(self, updatePairs):
		''' Update all the drag-tick values at once. This should be called
		by a single-shot timer or some other once-per-refresh mechanism
		'''
		# Don't make this mouse-tick be stackable. That way
		# we don't update the whole System for a slider value changes
		sliderList = []
		progs = []
		comboList = []
		for i in updatePairs:
			if isinstance(i[0], Slider):
				sliderList.append(i)
			elif isinstance(i[0], ProgPair):
				progs.append(i)
			elif isinstance(i[0], ComboPair):
				comboList.append(i)

		if progs:
			progPairs, values = zip(*progs)
			self.simplex.setShapesValues(progPairs, values)

		if sliderList:
			sliders, values = zip(*sliderList)
			self.simplex.setSlidersWeights(sliders, values)

		if comboList:
			comboPairs, values = zip(*comboList)
			self.simplex.setCombosValues(comboPairs, values)

	def getItemAppendRow(self, item):
		if isinstance(item, Combo):
			# insert before the special "SHAPES" item
			return len(item.pairs)
		return self.getItemRowCount(item)

	@contextmanager
	def insertItemManager(self, parent, row=-1):
		parIdx = self.indexFromItem(parent)
		if parIdx.isValid():
			if row == -1:
				row = self.getItemAppendRow(parent)
			self.beginInsertRows(parIdx, row, row)
		try:
			yield
		finally:
			if parIdx.isValid():
				self.endInsertRows()

	@contextmanager
	def removeItemManager(self, item):
		idx = self.indexFromItem(item)
		if idx.isValid():
			parIdx = idx.parent()
			self.beginRemoveRows(parIdx, idx.row(), idx.row())
		try:
			yield
		finally:
			if idx.isValid():
				self.endRemoveRows()

	@contextmanager
	def moveItemManager(self, item, destPar, destRow=-1):
		itemIdx = self.indexFromItem(item)
		destParIdx = self.indexFromItem(destPar)
		handled = False
		if itemIdx.isValid() and destParIdx.isValid():
			handled = True
			srcParIdx = itemIdx.parent()
			row = itemIdx.row()
			if destRow == -1:
				destRow = self.getItemAppendRow(destPar)
			self.beginMoveRows(srcParIdx, row, row, destParIdx, destRow)
		try:
			yield
		finally:
			if handled:
				self.endMoveRows()

	@contextmanager
	def resetModelManager(self):
		self.beginResetModel()
		try:
			yield
		finally:
			self.endResetModel()

	def itemDataChanged(self, item):
		idx = self.indexFromItem(item)
		if idx.isValid():
			self.dataChanged.emit(idx, idx)



# VIEW MODELS
class BaseProxyModel(QSortFilterProxyModel):
	''' Holds the common item/index translation code '''
	def __init__(self, model, parent=None):
		super(BaseProxyModel, self).__init__(parent)
		self.setSourceModel(model)

	def indexFromItem(self, item, column=0):
		sourceModel = self.sourceModel()
		sourceIndex = sourceModel.indexFromItem(item, column)
		return self.mapFromSource(sourceIndex)

	def itemFromIndex(self, index):
		sourceModel = self.sourceModel()
		sIndex = self.mapToSource(index)
		return sourceModel.itemFromIndex(sIndex)


class SliderModel(BaseProxyModel):
	def filterAcceptsRow(self, sourceRow, sourceParent):
		sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
		if sourceIndex.isValid():
			item = self.sourceModel().itemFromIndex(sourceIndex)
			if isinstance(item, Group):
				if item.groupType != Slider:
					return False
		return super(SliderModel, self).filterAcceptsRow(sourceRow, sourceParent)


class ComboModel(BaseProxyModel):
	def filterAcceptsRow(self, sourceRow, sourceParent):
		sourceIndex = self.sourceModel().index(sourceRow, 0, sourceParent)
		if sourceIndex.isValid():
			item = self.sourceModel().itemFromIndex(sourceIndex)
			if isinstance(item, Group):
				if item.groupType != Combo:
					return False
		return super(ComboModel, self).filterAcceptsRow(sourceRow, sourceParent)



# FILTER MODELS
class SimplexFilterModel(BaseProxyModel):
	def __init__(self, model, parent=None):
		super(SimplexFilterModel, self).__init__(model, parent)
		self.setSourceModel(model)
		self._filterString = []
		self.isolateList = []

	@property
	def filterString(self):
		return ' '.join(self._filterString)

	@filterString.setter
	def filterString(self, val):
		self._filterString = val.split()

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			if self.filterString or self.isolateList:
				sourceItem = self.sourceModel().itemFromIndex(sourceIndex)
				if isinstance(sourceItem, (ProgPair, Slider, Combo, ComboPair, Progression)):
					if not self.checkChildren(sourceItem):
						return False

		return super(SimplexFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)

	def matchFilterString(self, itemString):
		if not self._filterString:
			return True
		for sub in self._filterString:
			if fnmatchcase(itemString, "*{0}*".format(sub)):
				return True
		return False

	def matchIsolation(self, itemString):
		if self.isolateList:
			return itemString in self.isolateList
		return True

	def checkChildren(self, sourceItem):
		itemString = sourceItem.name
		if self.matchFilterString(itemString) and self.matchIsolation(itemString):
			return True

		sourceModel = self.sourceModel()
		for row in xrange(sourceModel.getItemRowCount(sourceItem)):
			childItem = sourceModel.getChildItem(sourceItem, row)
			if childItem is not None:
				return self.checkChildren(childItem)

		return False


class SliderFilterModel(SimplexFilterModel):
	""" Hide single shapes under a slider """
	def __init__(self, model, parent=None):
		super(SliderFilterModel, self).__init__(model, parent)
		self.doFilter = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			if self.doFilter:
				data = self.sourceModel().itemFromIndex(sourceIndex)
				if isinstance(data, ProgPair):
					if len(data.prog.pairs) <= 2:
						return False
					elif data.shape.isRest:
						return False

		return super(SliderFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)


class ComboFilterModel(SimplexFilterModel):
	""" Filter by slider when Show Dependent Combos is checked """
	def __init__(self, model, parent=None):
		super(ComboFilterModel, self).__init__(model, parent)
		self.requires = []
		self.filterRequiresAll = False
		self.filterRequiresAny = False
		self.filterRequiresOnly = False

		self.filterShapes = True

	def filterAcceptsRow(self, sourceRow, sourceParent):
		column = 0 #always sort by the first column #column = self.filterKeyColumn()
		sourceIndex = self.sourceModel().index(sourceRow, column, sourceParent)
		if sourceIndex.isValid():
			data = self.sourceModel().itemFromIndex(sourceIndex)
			if self.filterShapes:
				# ignore the SHAPE par if there's nothing under there
				if isinstance(data, Progression):
					if len(data.pairs) <= 2:
						return False
				# Ignore shape things if requested
				if isinstance(data, ProgPair):
					if len(data.prog.pairs) <= 2:
						return False
					elif data.shape.isRest:
						return False
			if (self.filterRequiresAny or self.filterRequiresAll or self.filterRequiresOnly) and self.requires:
				# Ignore items that don't use the required sliders if requested
				if isinstance(data, Combo):
					sliders = [i.slider for i in data.pairs]
					if self.filterRequiresAll:
						if not all(r in sliders for r in self.requires):
							return False
					elif self.filterRequiresAny:
						if not any(r in sliders for r in self.requires):
							return False
					elif self.filterRequiresOnly:
						if not all(r in self.requires for r in sliders):
							return False

		return super(ComboFilterModel, self).filterAcceptsRow(sourceRow, sourceParent)



# SETTINGS MODELS
class SliderGroupModel(QAbstractItemModel):
	def __init__(self, simplex, parent):
		super(SliderGroupModel, self).__init__(parent)
		self.simplex = simplex
		self.simplex.models.append(self)

	def index(self, row, column=0, parIndex=QModelIndex()):
		if row <= 0:
			return self.createIndex(row, column, None)
		try:
			group = self.simplex.sliderGroups[row-1]
		except IndexError:
			return QModelIndex()
		return self.createIndex(row, column, group)

	def parent(self, index):
		return QModelIndex()

	def rowCount(self, parent):
		return len(self.simplex.sliderGroups) + 1

	def columnCount(self, parent):
		return 1

	def data(self, index, role):
		if not index.isValid():
			return None
		group = index.internalPointer()
		if group and role in (Qt.DisplayRole, Qt.EditRole):
			return group.name
		return None

	def flags(self, index):
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable

	def itemFromIndex(self, index):
		return index.internalPointer()

	def typeHandled(self, item):
		if isinstance(item, Group):
			return item.groupType == Slider
		return False

	def itemDataChanged(self, item):
		if self.typeHandled(item):
			idx = self.indexFromItem(item)
			if idx.isValid():
				self.dataChanged.emit(idx, idx)


class FalloffModel(QAbstractItemModel):
	def __init__(self, simplex, parent):
		super(FalloffModel, self).__init__(parent)
		self.simplex = simplex
		self.simplex.models.append(self)
		self.sliders = []
		self._checks = {}
		self.line = ""

	def setSliders(self, sliders):
		self.beginResetModel()
		self.sliders = sliders
		self._checks = {}
		for slider in self.sliders:
			for fo in slider.prog.falloffs:
				self._checks.setdefault(fo, []).append(slider)
		self.endResetModel()
		self.buildLine()

	def buildLine(self):
		if not self.sliders:
			self.line = ''
			return
		fulls = []
		partials = []
		for fo in self.simplex.falloffs:
			cs = self._getCheckState(fo)
			if cs == Qt.Checked:
				fulls.append(fo.name)
			elif cs == Qt.PartiallyChecked:
				partials.append(fo.name)
		if partials:
			title = "{0} <<{1}>>".format(",".join(fulls), ",".join(partials))
		else:
			title = ",".join(fulls)
		self.line = title

	def index(self, row, column=0, parIndex=QModelIndex()):
		if row <= 0:
			return self.createIndex(row, column, None)
		try:
			falloff = self.simplex.falloffs[row-1]
		except IndexError:
			return QModelIndex()
		return self.createIndex(row, column, falloff)

	def parent(self, index):
		return QModelIndex()

	def rowCount(self, parent):
		return len(self.simplex.falloffs) + 1

	def columnCount(self, parent):
		return 1

	def _getCheckState(self, fo):
		sli = self._checks.get(fo, [])
		if len(sli) == len(self.sliders):
			return Qt.Checked
		elif len(sli) == 0:
			return Qt.Unchecked
		return Qt.PartiallyChecked

	def data(self, index, role):
		if not index.isValid():
			return None
		falloff = index.internalPointer()
		if not falloff:
			return None

		if role in (Qt.DisplayRole, Qt.EditRole):
			return falloff.name
		elif role == Qt.CheckStateRole:
			return self._getCheckState(falloff)
		return None

	def setData(self, index, value, role):
		if role == Qt.CheckStateRole:
			fo = index.internalPointer()
			if not fo:
				return
			if value == Qt.Checked:
				for s in self.sliders:
					if fo not in s.prog.falloffs:
						s.prog.falloffs.append(fo)
						self._checks.setdefault(fo, []).append(s)
			elif value == Qt.Unchecked:
				for s in self.sliders:
					if fo in s.prog.falloffs:
						s.prog.falloffs.remove(fo)
						if s in self._checks[fo]:
							self._checks[fo].remove(s) 
			self.buildLine()
			self.dataChanged.emit(index, index)
			return True
		return False

	def flags(self, index):
		return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsUserCheckable

	def itemFromIndex(self, index):
		return index.internalPointer()

	def typeHandled(self, item):
		return isinstance(item, Falloff)

	def itemDataChanged(self, item):
		if self.typeHandled(item):
			idx = self.indexFromItem(item)
			if idx.isValid():
				self.dataChanged.emit(idx, idx)



'''
class FlatProxyModel(QAbstractProxyModel):
	def __init__(self, parent=None):
		super(FlatProxyModel, self).__init__(parent)
		self.rowMap = {}
		self.indexMap = {}

	def sourceDataChanged(self, topLeft, bottomRight):
		self.dataChanged.emit(self.mapFromSource(topLeft), self.mapFromSource(bottomRight))

	def buildMap(self, model, parent=QModelIndex(), row=0):
		if row == 0:
			self.rowMap = {}
			self.indexMap = {}
		rows = model.rowCount(parent)
		for r in range(rows):
			index = model.index(r, 0, parent)
			self.rowMap[index] = row
			self.indexMap[row] = index
			row = row + 1
			if model.hasChildren(index):
				row = self.buildMap(model, index, row)
		return row

	def setSourceModel(self, model):
		super(FlatProxyModel, self).setSourceModel(self, model)
		self.buildMap(model)
		model.dataChanged.connect(self.sourceDataChanged)

	def mapFromSource(self, index):
		if index not in self.rowMap:
			return QModelIndex()
		return self.createIndex(self.rowMap[index], index.column())

	def mapToSource(self, index):
		if not index.isValid() or index.row() not in self.indexMap:
			return QModelIndex()
		return self.indexMap[index.row()]

	def columnCount(self, parent):
		return QAbstractProxyModel.sourceModel(self).columnCount(self.mapToSource(parent))

	def rowCount(self, parent):
		if parent.isValid():
			return 0
		return len(self.rowMap)

	def index(self, row, column, parent):
		if parent.isValid():
			return QModelIndex()
		return self.createIndex(row, column)

	def parent(self, index):
		return QModelIndex()
'''

