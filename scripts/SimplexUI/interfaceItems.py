"""
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

"""

#pylint:disable=missing-docstring,unused-argument,no-self-use
import copy, json, itertools, math
try:
	import numpy as np
except ImportError:
	np = None
from alembic.Abc import OArchive, IArchive, OStringProperty
from alembic.AbcGeom import OXform, OPolyMesh, IXform, IPolyMesh
from SimplexUI.Qt.QtGui import QColor
from utils import getNextName, nested, singleShot, caseSplit, makeUnique
from contextlib import contextmanager
from collections import OrderedDict
from functools import wraps
from interface import DCC, rootWindow, undoContext
from dummyInterface import DCC as DummyDCC
from SimplexUI.Qt.QtWidgets import QApplication

# UNDO STACK SETUP
class Stack(object):
	''' Integrate simplex into the DCC undo stack '''
	def __init__(self):
		self._stack = OrderedDict()
		self.depth = 0
		self.currentRevision = 0
		self.enabled = True

	def __setitem__(self, key, value):
		gt = []
		# when setting a new key, remove all keys from
		# the previous branch
		for k in reversed(self._stack): #pylint: disable=bad-reversed-sequence
			if k > key:
				gt.append(k)
			else:
				# yay ordered dict
				break
		for k in gt:
			del self._stack[k]
		#traceback.print_stack()
		self._stack[key] = value

	def getRevision(self, revision):
		''' Every time a change is made to the simplex definition,
		the revision counter is updated, and the revision/definition
		pair is put on the undo stack
		'''
		# This method will ***ONLY*** be called by the undo callback
		# Seriously, don't call this yourself
		if revision != self.currentRevision:
			if revision in self._stack:
				data = self._stack[revision]
				self.currentRevision = revision
				return data
		return None

	def purge(self):
		''' Clear the undo stack. This should be done on new-file '''
		self._stack = OrderedDict()
		self.depth = 0
		self.currentRevision = 0

	@contextmanager
	def store(self, wrapObj):
		if self.enabled:
			with undoContext(wrapObj.DCC):
				self.depth += 1
				try:
					yield
				finally:
					self.depth -= 1

				if self.depth == 0:
					# Only store the top Level of the stack
					srevision = wrapObj.DCC.incrementRevision()
					if not isinstance(wrapObj, Simplex):
						wrapObj = wrapObj.simplex
					self[srevision] = copy.deepcopy(wrapObj)
		else:
			yield

def stackable(method):
	''' A Decorator to make a method auto update the stack
	This decorator can only be used on methods of an object
	that has its .simplex value set with a stack. If you need
	to wrap an init method, use the stack .store contextmanager
	'''
	@wraps(method)
	def stacked(self, *data, **kwdata):
		''' Decorator closure that handles the stack '''
		ret = None
		with self.stack.store(self):
			ret = method(self, *data, **kwdata)
		return ret
	return stacked


# Base level properties applied to all non-pair objects
class SimplexAccessor(object):
	def __init__(self, simplex):
		self.simplex = simplex 

	@property
	def models(self):
		return self.simplex.models

	@property
	def falloffModels(self):
		return self.simplex.falloffModels

	@property
	def DCC(self):
		return self.simplex.DCC

	@property
	def stack(self):
		return self.simplex.stack

	def __deepcopy__(self, memo):
		cls = self.__class__
		result = cls.__new__(cls)
		memo[id(self)] = result
		for k, v in self.__dict__.iteritems():
			if k == "_thing":
				# DO NOT make a copy of the DCC thing
				# as it may or may not be a persistent object
				#setattr(result, k, self._thing)
				setattr(result, k, None)
			elif k == "expanded":
				# Skip the expanded dict because it deals with the Qt models
				setattr(result, k, {})
			else:
				setattr(result, k, copy.deepcopy(v, memo))
		return result


# Abstract Items
class Falloff(SimplexAccessor):
	LEFTSIDE = "L"
	RIGHTSIDE = "R"
	TOPSIDE = "U"
	BOTTOMSIDE = "D"
	FRONTSIDE = "F"
	BACKSIDE = "B"
	ALLSIDES = LEFTSIDE + RIGHTSIDE + TOPSIDE + BOTTOMSIDE + FRONTSIDE + BACKSIDE

	CENTERS = "MC"

	VERTICAL_SPLIT = "V"
	VERTICAL_RESULTS = TOPSIDE + BOTTOMSIDE
	VERTICAL_AXIS = "Y"
	VERTICAL_AXISINDEX = 1

	HORIZONTAL_SPLIT = "X"
	HORIZONTAL_RESULTS = LEFTSIDE + RIGHTSIDE
	HORIZONTAL_AXIS = "X"
	HORIZONTAL_AXISINDEX = 0

	DEPTH_SPLIT = "Z"
	DEPTH_RESULTS = FRONTSIDE + BACKSIDE
	DEPTH_AXIS = "Z"
	DEPTH_AXISINDEX = 2

	RESTNAME = "Rest"
	SEP = "_"
	SYMMETRIC = "S"

	UNSPLIT_GUESS_TOLERANCE = 0.33

	def __init__(self, name, simplex, *data):
		self.simplex = simplex
		with self.stack.store(self):
			self.splitType = data[0]
			self.axis = None
			self.maxVal = None
			self.maxHandle = None
			self.minHandle = None
			self.minVal = None
			self.mapName = None

			self._bezier = None
			self._search = None
			self._rep = None
			self._weights = None
			self._thing = None
			self._thingRepr = None

			if self.splitType == "planar":
				self.axis = data[1]
				self.maxVal = data[2]
				self.maxHandle = data[3]
				self.minHandle = data[4]
				self.minVal = data[5]
			elif self.splitType == "map":
				self.mapName = data[1]

			self._name = name
			self.children = []
			self._buildIdx = None
			self.expanded = {}
			self.color = QColor(128, 128, 128)

			mgrs = [model.insertItemManager(None) for model in self.falloffModels]
			with nested(*mgrs):
				self.simplex.falloffs.append(self)

			#newThing = self.DCC.getFalloffThing(self)
			#if newThing is None:
				#self.thing = self.DCC.createFalloff(self)
			#else:
				#self.thing = newThing

	#@property
	#def thing(self):
		## if this is a deepcopied object, then self._thing will
		## be None.	Rebuild the thing connection by its representation
		#if self._thing is None and self._thingRepr:
			#self._thing = self.DCC.loadPersistentFalloff(self._thingRepr)
		#return self._thing

	#@thing.setter
	#def thing(self, value):
		#self._thing = value
		#self._thingRepr = self.DCC.getPersistentFalloff(value)

	@property
	def name(self):
		return self._name

	@name.setter
	@stackable
	def name(self, value):
		""" Set the name of a Falloff """
		self._name = value
		for model in self.falloffModels:
			model.itemDataChanged(self)

	@classmethod
	def createPlanar(cls, name, simplex, axis, maxVal, maxHandle, minHandle, minVal):
		return cls(name, simplex, 'planar', axis, maxVal, maxHandle, minHandle, minVal)

	@classmethod
	def createMap(cls, name, simplex, mapName):
		return cls(name, simplex, 'map', mapName)

	@classmethod
	def loadV2(cls, simplex, data):
		tpe = data['type']
		name = data['name']
		if tpe == 'map':
			return cls.createMap(name, simplex, data['mapName'])
		elif tpe == 'planar':
			axis = data['axis']
			maxVal = data['maxVal']
			maxHandle = data['maxHandle']
			minHandle = data['minHandle']
			minVal = data['minVal']
			return cls.createPlanar(name, simplex, axis, maxVal, maxHandle, minHandle, minVal)

	def buildDefinition(self, simpDict, legacy):
		if self._buildIdx is None:
			self._buildIdx = len(simpDict["falloffs"])
			if legacy:
				if self.splitType == "planar":
					line = ["planar", self.axis, self.maxVal, self.maxHandle, self.minHandle, self.minVal]
				else:
					line = ["map", self.mapName]
				simpDict.setdefault("falloffs", []).append([self.name] + line)
			else:
				x = {
					"name": self.name,
					"type": self.splitType,
					"axis": self.axis,
					"maxVal": self.maxVal,
					"maxHandle": self.maxHandle,
					"minHandle": self.minHandle,
					"minVal": self.minVal,
					"mapName": self.mapName,
					"color": self.color.getRgb()[:3],
				}
				simpDict.setdefault("falloffs", []).append(x)
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None

	@stackable
	def duplicate(self, newName):
		""" duplicate a falloff with a new name """
		nf = copy.copy(self)
		nf.name = newName
		nf.children = []
		nf.clearBuildIndex()
		mgrs = [model.insertItemManager(self) for model in self.falloffModels]
		with nested(*mgrs):
			self.simplex.falloffs.append(nf)
		self.DCC.duplicateFalloff(self, nf)
		return nf

	@stackable
	def delete(self):
		""" delete a falloff """
		fIdx = self.simplex.falloffs.index(self)
		for child in self.children:
			child.falloff = None

		mgrs = [model.removeItemManager(None) for model in self.falloffModels]
		with nested(*mgrs):
			self.simplex.falloffs.pop(fIdx)
		self.DCC.deleteFalloff(self)

	@stackable
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

	@stackable
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
		self.DCC.setFalloffData(self, self.splitType, self.axis, self.minVal,
						  self.minHandle, self.maxHandle, self.maxVal, self.mapName)

	# Split code
	@property
	def bezier(self):
		if self._bezier is None:
			# Based on method described at
			# http://edmund.birotanker.com/monotonic-bezier-curves-for-animation.html
			# No longer exists. Check the internet archive
			p0x = 0.0
			p1x = self.minHandle
			p2x = self.maxHandle
			p3x = 1.0

			f = (p1x - p0x)
			g = (p3x - p2x)
			d = 3*f + 3*g - 2
			n = 2*f + g - 1
			r = (n*n - f*d) / (d*d)
			qq = ((3*f*d*n - 2*n*n*n) / (d*d*d))
			self._bezier = (qq, r, d, n)
		return self._bezier

	def getMultiplier(self, xVal):
		# Vertices are assumed to be at (0,0) and (1,1)
		if xVal <= self.minVal:
			return 0.0
		if xVal >= self.maxVal:
			return 1.0

		tVal = float(xVal - self.minVal) / float(self.maxVal - self.minVal)
		qq, r, d, n = self.bezier
		q = qq - tVal/d
		discriminant = q*q - 4*r*r*r
		if discriminant >= 0:
			pm = (discriminant**0.5)/2
			w = (-q/2 + pm)**(1/3.0)
			u = w + r/w
		else:
			theta = math.acos(-q / (2*r**(3/2.0)))
			phi = theta/3 + 4*math.pi/3
			u = 2 * r**(0.5) * math.cos(phi)
		t = u + n/d
		t1 = 1-t
		return 3*t1*t**2*1 + t**3*1

	def _setSearchRep(self):
		if self.axis.lower() == self.HORIZONTAL_AXIS.lower():
			self._search = self.HORIZONTAL_SPLIT
			self._rep = self.HORIZONTAL_RESULTS
		elif self.axis.lower() == self.VERTICAL_AXIS.lower():
			self._search = self.VERTICAL_SPLIT
			self._rep = self.VERTICAL_RESULTS
		elif self.axis.lower() == self.DEPTH_AXIS.lower():
			self._search = self.DEPTH_SPLIT
			self._rep = self.DEPTH_RESULTS

	@property
	def search(self):
		if self._search is None:
			self._setSearchRep()
		return self._search

	@property
	def rep(self):
		if self._rep is None:
			self._setSearchRep()
		return self._rep

	def setVerts(self, verts):
		if self.axis.lower() == self.HORIZONTAL_AXIS.lower():
			component = 0
		elif self.axis.lower() == self.VERTICAL_AXIS.lower():
			component = 1
		elif self.axis.lower() == self.DEPTH_AXIS.lower():
			component = 2
		elif self._weights is None:
			raise ValueError("Non-Planar Falloff found with no weights set")
		else:
			return
		self._weights = np.array([self.getMultiplier(v[component]) for v in verts])

	@property
	def weights(self):
		if self._weights is None:
			raise RuntimeError("Must set verts before requesting weights")
		return self._weights

	@weights.setter
	def weights(self, val):
		self._weights = val

	def getSidedName(self, name, sIdx):
		search = self.search
		replace = self.rep[sIdx]

		nn = name
		s = "{0}{1}{0}".format(self.SEP, search)
		r = "{0}{1}{0}".format(self.SEP, replace)
		nn = nn.replace(s, r)

		s = "{0}{1}".format(self.SEP, search) # handle Postfix
		r = "{0}{1}".format(self.SEP, replace)
		if nn.endswith(s):
			nn = r.join(nn.rsplit(s, 1))

		s = "{1}{0}".format(self.SEP, search) # handle Prefix
		r = "{1}{0}".format(self.SEP, replace)
		if nn.startswith(s):
			nn = nn.replace(s, r, 1)
		return nn

	def splitRename(self, item, sIdx):
		if isinstance(item, (Shape, Slider, Combo, Traversal)):
			item.name = self.getSidedName(item.name, sIdx)

	def applyFalloff(self, shape, sIdx):
		rest = self.simplex.restShape
		restVerts = rest.verts

		weights = self.weights
		if sIdx == 1:
			weights = 1 - weights

		weightedDeltas = (shape.verts - restVerts) * weights[:, None]
		shape.verts = weightedDeltas + restVerts


class Shape(SimplexAccessor):
	classDepth = 9
	def __init__(self, name, simplex, create=True, color=QColor(128, 128, 128)):
		self.simplex = simplex
		with self.stack.store(self):
			self._thing = None
			self._verts = None
			self._thingRepr = None
			self._name = name
			self._buildIdx = None
			simplex.shapes.append(self)
			self.isRest = False
			self.expanded = {}
			self.color = color

			newThing = self.DCC.getShapeThing(self._name)
			if newThing is None:
				if create:
					self.thing = self.DCC.createShape(self)
				else:
					raise RuntimeError("Unable to find existing shape: {0}".format(self.name))
			else:
				self.thing = newThing

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

	@classmethod
	def buildRest(cls, simplex):
		""" create/find the system's rest shape"""
		rest = cls(simplex.getRestName(), simplex, create=True)
		rest.isRest = True
		return rest

	@property
	def name(self):
		return self._name

	@name.setter
	@stackable
	def name(self, value):
		if value == self._name:
			return
		self.DCC.renameShape(self, value)
		self._name = value
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
		self._thingRepr = self.DCC.getPersistentShape(value)

	@classmethod
	def loadV2(cls, simplex, data, create):
		return cls(data['name'], simplex, create, QColor(*data.get('color', (0, 0, 0))))

	def buildDefinition(self, simpDict, legacy):
		if self._buildIdx is None:
			self._buildIdx = len(simpDict["shapes"])
			if legacy:
				simpDict.setdefault("shapes", []).append(self.name)
			else:
				x = {
					"name": self.name,
					"color": self.color.getRgb()[:3],
				}
				simpDict.setdefault("shapes", []).append(x)
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None

	def zeroShape(self):
		""" Set the shape to be completely zeroed """
		self.DCC.zeroShape(self)

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
		self.DCC.connectShape(self, mesh, live, delete)

	@staticmethod
	def connectShapes(shapes, meshes, live=False, delete=False):
		with undoContext():
			for shape, mesh in zip(shapes, meshes):
				shape.connectShape(mesh, live, delete)

	@property
	def verts(self):
		if self._verts is None:
			self._verts = self.DCC.getShapeVertices(self)
		return self._verts

	@verts.setter
	def verts(self, value):
		self._verts = value


class ProgPair(SimplexAccessor):
	classDepth = 8
	def __init__(self, simplex, shape, value):
		self.simplex = simplex
		self.shape = shape
		self._value = value
		self.prog = None
		self.minValue = -1.0
		self.maxValue = 1.0
		self.expanded = {}

	@property
	def name(self):
		return self.shape.name

	@name.setter
	def name(self, value):
		self.shape.name = value

	def buildDefinition(self, simpDict, legacy):
		idx = self.shape.buildDefinition(simpDict, legacy)
		return idx, self.value

	def __lt__(self, other):
		return self.value < other.value

	@property
	def value(self):
		return self._value

	@value.setter
	@stackable
	def value(self, val):
		self._value = val
		for model in self.models:
			model.itemDataChanged(self)

	@stackable
	def delete(self):
		ridx = self.prog.pairs.index(self)
		mgrs = [model.removeItemManager(self) for model in self.models]
		with nested(*mgrs):
			pp = self.prog.pairs.pop(ridx)
			if not self.shape.isRest:
				self.simplex.shapes.remove(pp.shape)
				self.DCC.deleteShape(pp.shape)


class Progression(SimplexAccessor):
	classDepth = 7
	def __init__(self, name, simplex, pairs=None, interp="spline", falloffs=None):
		self.simplex = simplex
		with self.stack.store(self):
			self.name = name
			self._interp = interp
			self.falloffs = falloffs or []
			self.controller = None

			if pairs is None:
				self.pairs = [ProgPair(self.simplex, self.simplex.restShape, 0.0)]
			else:
				self.pairs = pairs

			for pair in self.pairs:
				pair.prog = self

			for falloff in self.falloffs:
				falloff.children.append(self)
			self._buildIdx = None
			self.expanded = {}

	@property
	def interp(self):
		return self._interp

	@interp.setter
	@stackable
	def interp(self, value):
		self._interp = value

	def getShapeIndex(self, shape):
		for i, p in enumerate(self.pairs):
			if p.shape == shape:
				return i
		raise ValueError("Provided shape:{0} is not in the list".format(shape.name))

	def getShapes(self):
		return [i.shape for i in self.pairs]

	def getValues(self):
		return [i.value for i in self.pairs]

	def getInsertIndex(self, tVal):
		values = self.getValues()
		if not values:
			return 0
		elif tVal <= values[0]:
			return 0
		elif tVal >= values[-1]:
			return len(self.pairs)
		else:
			for i in range(1, len(values)):
				if values[i-1] <= tVal < values[i]:
					return i
		return 0

	def getShapeAtValue(self, val):
		for pp in self.pairs:
			if abs(pp.value - val) < 0.0001:
				return pp.shape
		return None

	@classmethod
	def loadV2(cls, simplex, data):
		name = data["name"]
		pairs = data["pairs"]
		interp = data.get("interp", 'spline')
		foIdxs = data.get("falloffs", [])
		pairs = [ProgPair(simplex, simplex.shapes[s], v) for s, v in pairs]
		fos = [simplex.falloffs[i] for i in foIdxs]
		return cls(name, simplex, pairs=pairs, interp=interp, falloffs=fos)

	def buildDefinition(self, simpDict, legacy):
		if self._buildIdx is None:
			idxPairs = [pair.buildDefinition(simpDict, legacy) for pair in self.pairs]
			idxPairs.sort(key=lambda x: x[1])
			idxs, values = zip(*idxPairs)
			foIdxs = [f.buildDefinition(simpDict, legacy) for f in self.falloffs]
			self._buildIdx = len(simpDict["progressions"])
			if legacy:
				x = [self.name, idxs, values, self.interp, foIdxs]
				simpDict.setdefault("progressions", []).append(x)
			else:
				x = {
					"name": self.name,
					"pairs": idxPairs,
					"interp": self.interp,
					"falloffs": foIdxs,
				}
				simpDict.setdefault("progressions", []).append(x)
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None
		for pair in self.pairs:
			pair.shape.clearBuildIndex()
		for fo in self.falloffs:
			fo.clearBuildIndex()

	@stackable
	def moveShapeToProgression(self, shapePair): ### Moves Rows (Slider, Combo)
		""" Remove the shapePair from its current progression
		and set it in a new progression """
		oldProg = shapePair.prog
		oldProg.pairs.remove(shapePair)
		self.pairs.append(shapePair)
		shapePair.prog = self

	@stackable
	def setShapesValues(self, values):
		""" Set the shape's value in it's progression """
		for pp, val in zip(self.pairs, values):
			pp.value = val
			for model in self.models:
				model.itemDataChanged(pp)

		if isinstance(self.controller, Slider):
			self.controller.updateRange()
			for model in self.models:
				model.itemDataChanged(self.controller)

	@stackable
	def addFalloff(self, falloff):
		""" Add a falloff to a slider's falloff list """
		if falloff not in self.falloffs:
			self.falloffs.append(falloff)
			falloff.children.append(self)
			self.DCC.addProgFalloff(self, falloff)

	@stackable
	def removeFalloff(self, falloff):
		""" Remove a falloff from a slider's falloff list """
		if falloff in self.falloffs:
			self.falloffs.remove(falloff)
			falloff.children.remove(self)
			self.DCC.removeProgFalloff(self, falloff)

	@stackable
	def createShape(self, shapeName=None, tVal=None):
		""" create a shape and add it to a progression """
		pp, idx = self.newProgPair(shapeName, tVal)
		mgrs = [model.insertItemManager(self, idx) for model in self.models]
		with nested(*mgrs):
			pp.prog = self
			self.pairs.insert(idx, pp)

		if isinstance(self.controller, Slider):
			self.controller.updateRange()

		return pp

	def newProgPair(self, shapeName=None, tVal=None):
		""" create a shape and DO NOT add it to a progression """
		if tVal is None:
			tVal = self.guessNextTVal()

		if shapeName is None:
			if abs(tVal) == 1.0:
				shapeName = self.controller.name
			else:
				neg = 'n' if tVal < 0.0 else ''
				shapeName = "{0}_{1}{2}".format(self.controller.name, neg, int(abs(tVal)*100))

			currentNames = [i.name for i in self.simplex.shapes]
			shapeName = getNextName(shapeName, currentNames)

		idx = self.getInsertIndex(tVal)
		shape = Shape(shapeName, self.simplex)
		pp = ProgPair(self.simplex, shape, tVal)
		return pp, idx

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

	@stackable
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
				self.DCC.deleteShape(shape)

	@stackable
	def delete(self):
		mgrs = [model.removeItemManager(self) for model in self.models]
		with nested(*mgrs):
			for pp in self.pairs[:]:
				if pp.shape.isRest:
					continue
				self.simplex.shapes.remove(pp.shape)
				self.DCC.deleteShape(pp.shape)

	def getRange(self):
		vals = [i.value for i in self.pairs]
		return min(vals), max(vals)

	def getExtremePairs(self):
		ret = []
		for pp in self.pairs:
			if abs(pp.value) != 1.0:
				continue
			ret.append(pp)
		return ret


class Slider(SimplexAccessor):
	classDepth = 6
	def __init__(self, name, simplex, prog, group, color=QColor(128, 128, 128), multiplier=1, create=True):
		if group.groupType != type(self):
			raise ValueError("Cannot add this slider to a combo group")

		self.simplex = simplex
		with self.stack.store(self):
			self._name = name
			self._thing = None
			self._thingRepr = None
			self.prog = prog
			self.split = False
			self.prog.controller = self
			self._buildIdx = None
			self._value = 0.0
			self.expanded = {}
			self.color = color
			self._enabled = True
			self.multiplier = multiplier

			mn, mx = self.prog.getRange()
			self.minValue = mn
			self.maxValue = mx

			mgrs = [model.insertItemManager(group) for model in self.models]
			with nested(*mgrs):
				self.group = group
				self.group.items.append(self)

			self.simplex.sliders.append(self)

			newThing = self.DCC.getSliderThing(self._name)
			if newThing is None:
				if create:
					self.thing = simplex.DCC.createSlider(self)
				else:
					raise RuntimeError("Unable to find existing shape: {0}".format(self.name))
			else:
				self.thing = newThing

	@property
	def enabled(self):
		return self._enabled

	@enabled.setter
	@stackable
	def enabled(self, value):
		self._enabled = value

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
			prog.pairs.append(ProgPair(simplex, shape, tVal))

		sli = cls(name, simplex, prog, group, multiplier=multiplier)
		return sli

	@property
	def name(self):
		return self._name

	@name.setter
	@stackable
	def name(self, value):
		""" Set the name of a slider """
		self._name = value
		self.prog.name = value
		self.DCC.renameSlider(self, value, self.multiplier)
		# TODO Also rename the combos
		for model in self.models:
			model.itemDataChanged(self)

	def nameLinks(self):
		""" Return whether the name of each shape in the current
		progression depends on this slider's name """
		# split by underscore
		sp = self._name.split('_')
		sliderPoss = []
		for orig in sp:
			s = caseSplit(orig) 
			if len(s) > 1:
				s = orig + s
			sliderPoss.append(s)

		# remove numbered chunks from the end
		shapeNames = []
		shapes = [p.shape for p in self.prog.pairs]
		for s in shapes:
			x = s.name.rsplit('_', 1)
			if len(x) == 2:
				base, sfx = x
				if sfx[0].lower() == 'n':
					sfx = sfx[1:]
				x = base if sfx.isdigit() else s.name
			shapeNames.append(x)

		out = [False] * len(shapeNames)
		for poss in itertools.product(*sliderPoss):
			check = ''.join(poss)
			allTrue = True
			for i, s in enumerate(shapeNames):
				if check == s:
					out[i] = True
				if not out[i]:
					allTrue = False
			if allTrue:
				break
		return out

	@property
	def thing(self):
		# if this is a deepcopied object, then self._thing will
		# be None.	Rebuild the thing connection by its representation
		if self._thing is None and self._thingRepr:
			self._thing = self.DCC.loadPersistentSlider(self._thingRepr)
		return self._thing

	@thing.setter
	def thing(self, value):
		self._thing = value
		self._thingRepr = self.DCC.getPersistentSlider(value)

	@property
	def value(self):
		return self._value

	@value.setter
	def value(self, val):
		self._value = val
		for model in self.models:
			model.itemDataChanged(self)
		self._setAllSliders(self)

	@singleShot()
	def _setAllSliders(self, sliders):
		with undoContext(self.DCC):
			for slider in sliders:
				self.DCC.setSliderWeight(slider, slider.value)

	@classmethod
	def loadV2(cls, simplex, progs, data, create):
		name = data["name"]
		prog = progs[data["prog"]]
		group = simplex.groups[data.get("group", 0)]
		color = QColor(*data.get("color", (0, 0, 0)))
		return cls(name, simplex, prog, group, create=create)

	def buildDefinition(self, simpDict, legacy):
		if self._buildIdx is None:
			self._buildIdx = len(simpDict["sliders"])
			if legacy:
				gIdx = self.group.buildDefinition(simpDict, legacy)
				pIdx = self.prog.buildDefinition(simpDict, legacy)
				simpDict.setdefault("sliders", []).append([self.name, pIdx, gIdx])
			else:
				x = {
					"name": self.name,
					"prog": self.prog.buildDefinition(simpDict, legacy),
					"group": self.group.buildDefinition(simpDict, legacy),
					"color": self.color.getRgb()[:3],
					"enabled": self._enabled,
				}
				simpDict.setdefault("sliders", []).append(x)
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None
		self.prog.clearBuildIndex()
		self.group.clearBuildIndex()

	def setRange(self, multiplier):
		values = [i.value for i in self.prog.pairs]
		self.minValue = min(values)
		self.maxValue = max(values)
		self.DCC.setSliderRange(self, multiplier)

	@stackable
	def delete(self):
		""" Delete a slider, any shapes it contains, and all downstream combos """
		self.simplex.deleteDownstream(self)
		mgrs = [model.removeItemManager(self) for model in self.models]
		with nested(*mgrs):
			g = self.group
			g.items.remove(self)
			self.group = None
			self.simplex.sliders.remove(self)

			pairs = self.prog.pairs[:] # gotta make a copy
			for pp in pairs:
				if not pp.shape.isRest:
					self.simplex.shapes.remove(pp.shape)
					self.DCC.deleteShape(pp.shape)

			self.DCC.deleteSlider(self)

	@stackable
	def setInterpolation(self, interp):
		""" Set the interpolation of a single slider """
		self.prog.interp = interp

	@stackable
	def setInterps(self, sliders, interp):
		""" Set the interpolation of multiple sliders """
		# This uses an instantiated slider to set the values
		# of multiple sliders. This is so we don't update the
		# DCC over and over again
		if not sliders:
			return
		with undoContext(self.DCC):
			for slider in sliders:
				slider.prog.interp = interp

	@stackable
	def createShape(self, shapeName=None, tVal=None):
		""" create a shape and add it to a progression """
		pp, idx = self.prog.newProgPair(shapeName, tVal)
		mgrs = [model.insertItemManager(self, idx) for model in self.models]
		with nested(*mgrs):
			pp.prog = self.prog
			self.prog.pairs.insert(idx, pp)
		self.updateRange()
		return pp

	def extractProgressive(self, live=True, offset=10.0, separation=5.0):
		with undoContext(self.DCC):
			pos, neg = [], []
			for pp in sorted(self.prog.pairs):
				if pp.value < 0.0:
					neg.append((pp.value, pp.shape, offset))
					offset += separation
				elif pp.value > 0.0:
					pos.append((pp.value, pp.shape, offset))
					offset += separation
				#skip the rest value at == 0.0
			neg = list(reversed(neg))

			for prog in [pos, neg]:
				if not prog:
					continue
				xtVal, shape, shift = prog[-1]
				ext, deltaShape = self.DCC.extractWithDeltaShape(shape, live, shift)
				for value, shape, shift in prog[:-1]:
					ext = self.DCC.extractWithDeltaConnection(shape, deltaShape, value/xtVal, live, shift)

	def extractShape(self, shape, live=True, offset=10.0):
		return self.DCC.extractShape(shape, live, offset)

	def connectShape(self, shape, mesh=None, live=False, delete=False):
		self.DCC.connectShape(shape, mesh, live, delete)

	def updateRange(self):
		self.DCC.updateSlidersRange([self])

	@stackable
	def setGroup(self, grp):
		if grp.groupType is None:
			grp.groupType = type(self)

		if not isinstance(self, grp.groupType):
			raise ValueError("All items in this group must be of type: {}".format(grp.groupType))

		mgrs = [model.moveItemManager(self, grp) for model in self.models]
		with nested(*mgrs):
			if self.group:
				self.group.items.remove(self)
			grp.items.append(self)
			self.group = grp

	def getInputVectors(self):
		inVecs = []
		for pp in self.prog.getExtremePairs():
			inVec = [0.0] * len(self.simplex.sliders)
			inVec[self.simplex.sliders.index(self)] = pp.value
			inVecs.append(inVec)
		return inVecs


class ComboPair(object):
	classDepth = 5
	def __init__(self, slider, value):
		self.slider = slider
		self.simplex = self.slider.simplex
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
	@stackable
	def value(self, val):
		self._value = val
		for model in self.models:
			model.itemDataChanged(self)

	def buildDefinition(self, simpDict, legacy):
		sIdx = self.slider.buildDefinition(simpDict, legacy)
		return sIdx, self.value


class Combo(SimplexAccessor):
	classDepth = 4
	def __init__(self, name, simplex, pairs, prog, group, color=QColor(128, 128, 128)):
		self.simplex = simplex
		with self.stack.store(self):
			if group.groupType != type(self):
				raise ValueError("Cannot add this slider to a combo group")
			self._name = name
			self.pairs = pairs
			self.prog = prog
			self._buildIdx = None
			self.expanded = {}
			self._enabled = True
			self.color = color

			mgrs = [model.insertItemManager(group) for model in self.models]
			with nested(*mgrs):

				self.group = group
				for p in self.pairs:
					p.combo = self
				self.prog.controller = self
				self.group.items.append(self)
				self.simplex.combos.append(self)

	@property
	def enabled(self):
		return self._enabled

	@enabled.setter
	@stackable
	def enabled(self, value):
		self._enabled = value


	@classmethod
	def comboAlreadyExists(cls, simplex, sliders, values):
		checker = set([(s.name, v) for s, v in zip(sliders, values)])
		for combo in simplex.combos:
			tester = set([(p.slider.name, p.value) for p in combo.pairs])
			if checker == tester:
				return combo
		return None

	@classmethod
	def createCombo(cls, name, simplex, sliders, values, group=None, shape=None, tVal=1.0):
		""" Create a combo of sliders at values """
		if simplex.restShape is None:
			raise RuntimeError("Simplex system is missing rest shape")

		#Make sure to check if this combo already exists. If so, just return it
		exist = cls.comboAlreadyExists(simplex, sliders, values)
		if exist is not None:
			return exist

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
			prog.pairs.append(ProgPair(simplex, shape, tVal))

		cmb = Combo(name, simplex, cPairs, prog, group)

		if shape is None:
			pp = prog.createShape(name, tVal)
			simplex.DCC.zeroShape(pp.shape)

		return cmb

	@property
	def name(self):
		return self._name

	@name.setter
	@stackable
	def name(self, value):
		""" Set the name of a combo """
		self._name = value
		self.prog.name = value
		self.DCC.renameCombo(self, value)
		for model in self.models:
			model.itemDataChanged(self)

	def sliderNameLinks(self):
		""" Return whether the name of each slider in the current
		combo depends on this combo's name """
		# If the combo name contains the slider name
		# surrounded by word boundary or underscore, then True
		sliNames = ["_{0}_".format(i.slider.name) for i in self.pairs]
		surr = "_{0}_".format(self.name)
		return [sn in surr for sn in sliNames]

	def nameLinks(self):
		""" Return whether the name of each shape in the current
		progression depends on this slider's name """
		# In this case, these names will *NOT* have the possibility of
		# a pos/neg name. Only the combo name, and possibly a percentage
		shapeNames = []
		shapes = [i.shape for i in self.prog.pairs]
		for s in shapes:
			x = s.name.rsplit('_', 1)
			if len(x) == 2:
				base, sfx = x
				x = base if sfx.isdigit() else s.name
			shapeNames.append(x)
		return [i == self.name for i in shapeNames]

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

	@classmethod
	def loadV2(cls, simplex, progs, data):
		name = data["name"]
		prog = progs[data["prog"]]
		group = simplex.groups[data.get("group", 1)]
		color = QColor(*data.get("color", (0, 0, 0)))
		pairs = [ComboPair(simplex.sliders[s], v) for s, v in data['pairs']]
		return cls(name, simplex, pairs, prog, group)

	def buildDefinition(self, simpDict, legacy):
		if self._buildIdx is None:
			self._buildIdx = len(simpDict["combos"])
			if legacy:
				gIdx = self.group.buildDefinition(simpDict, legacy)
				pIdx = self.prog.buildDefinition(simpDict, legacy)
				idxPairs = [p.buildDefinition(simpDict, legacy) for p in self.pairs]
				x = [self.name, pIdx, idxPairs, gIdx]
				simpDict.setdefault("combos", []).append(x)
			else:
				x = {
					"name": self.name,
					"prog": self.prog.buildDefinition(simpDict, legacy),
					"pairs": [p.buildDefinition(simpDict, legacy) for p in self.pairs],
					"group": self.group.buildDefinition(simpDict, legacy),
					"color": self.color.getRgb()[:3],
					"enabled": self._enabled,
				}
				simpDict.setdefault("combos", []).append(x)
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None
		self.prog.clearBuildIndex()
		self.group.clearBuildIndex()

	def extractProgressive(self, live=True, offset=10.0, separation=5.0):
		raise RuntimeError('Currently just copied from Sliders, Not actually real')
		with undoContext(self.DCC):
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
		return self.DCC.extractComboShape(self, shape, live, offset)

	def connectShape(self, shape, mesh=None, live=False, delete=False):
		""" Connect a shape into a combo progression"""
		self.DCC.connectComboShape(self, shape, mesh, live, delete)

	@stackable
	def delete(self):
		""" Delete a combo and any shapes it contains """
		self.simplex.deleteDownstream(self)
		mgrs = [model.removeItemManager(self) for model in self.models]
		with nested(*mgrs):
			g = self.group
			if self not in g.items:
				return # Can happen when deleting multiple groups
			g.items.remove(self)
			self.group = None
			self.simplex.combos.remove(self)
			pairs = self.prog.pairs[:] # gotta make a copy
			for pp in pairs:
				if not pp.shape.isRest:
					self.simplex.shapes.remove(pp.shape)
					self.DCC.deleteShape(pp.shape)

	@stackable
	def setInterpolation(self, interp):
		""" Set the interpolation of a combo """
		self.prog.interp = interp
		for model in self.models:
			model.itemDataChanged(self)

	@stackable
	def setComboValue(self, slider, value):
		""" Set the Slider/value pairs for a combo """
		idx = self.getSliderIndex(slider)
		pair = self.pairs[idx]
		pair.value = value
		for model in self.models:
			model.itemDataChanged(pair)

	@stackable
	def appendComboValue(self, slider, value):
		""" Append a Slider/value pair for a combo """
		cp = ComboPair(slider, value)
		mgrs = [model.insertItemManager(self) for model in self.models]
		with nested(*mgrs):
			self.pairs.append(cp)
			cp.combo = self

	@stackable
	def deleteComboPair(self, comboPair):
		""" delete a Slider/value pair for a combo """
		mgrs = [model.removeItemManager(comboPair) for model in self.models]
		with nested(*mgrs):
			# We specifically don't move the combo to the proper depth group
			# That way the user can make multiple changes to the combo without
			# it popping all over in the heirarchy
			self.pairs.remove(comboPair)
			comboPair.combo = None

	@stackable
	def setGroup(self, grp):
		if grp.groupType is None:
			grp.groupType = type(self)

		if not isinstance(self, grp.groupType):
			raise ValueError("All items in this group must be of type: {}".format(grp.groupType))

		mgrs = [model.moveItemManager(self, grp) for model in self.models]
		with nested(*mgrs):
			if self.group:
				self.group.items.remove(self)
			grp.items.append(self)
			self.group = grp

	@stackable
	def createShape(self, shapeName=None, tVal=None):
		""" create a shape and add it to a progression """
		pp, idx = self.prog.newProgPair(shapeName, tVal)
		mgrs = [model.insertItemManager(self, idx) for model in self.models]
		with nested(*mgrs):
			pp.prog = self.prog
			self.prog.pairs.insert(idx, pp)
		return pp

	def getInputVector(self):
		# Get all endpoint shapes from the progressions
		inVec = [0.0] * len(self.simplex.sliders)
		for cp in self.pairs:
			inVec[self.simplex.sliders.index(cp.slider)] = cp.value
		return inVec


class TravPair(SimplexAccessor):
	classDepth = 3
	def __init__(self, controller, value, usage):
		self.traversal = None
		self.controller = controller
		self.simplex = self.controller.simplex
		self._value = float(value)
		self.minValue = -1.0
		self.maxValue = 1.0
		self.expanded = {}
		self.usage = usage # "progress" or "multiplier"

	def usageIndex(self):
		if self.usage.lower() == "progress":
			return 0
		else: #self.usage.lower() == "multiplier":
			return 1

	def controllerTypeName(self):
		if isinstance(self.controller, Slider):
			return "Slider"
		else:
			return "Combo"

	@property
	def models(self):
		return self.controller.simplex.models

	@property
	def name(self):
		return self.controller.name

	@property
	def value(self):
		return self._value

	def getFlipRange(self):
		values = [i.value for i in self.controller.prog.pairs]
		mn = min(values)
		mx = max(values)
		if mn == 0.0 and mx == 0.0:
			# Should never happen, but just in case
			return 1.0, 1.0
		elif mn == 0.0:
			return mx, mx
		elif mx == 0.0:
			return mn, mn
		return mn, mx

	@value.setter
	@stackable
	def value(self, val):
		mn, mx = self.getFlipRange()
		newVal = self._value
		if val > 0:
			if val >= self._value:
				newVal = mx
			else:
				newVal = mn
		else:
			if val <= self._value:
				newVal = mn
			else:
				newVal = mx
		if self._value != newVal:
			self._value = newVal
			for model in self.models:
				model.itemDataChanged(self)

	def buildDefinition(self, simpDict, legacy):
		sIdx = self.controller.buildDefinition(simpDict, legacy)
		return sIdx


class Traversal(SimplexAccessor):
	classDepth = 2
	def __init__(self, name, simplex, multCtrl, progCtrl, prog, group, color=QColor(128, 128, 128)):
		self.simplex = simplex
		with self.stack.store(self):
			if group.groupType != type(self):
				raise ValueError("Cannot add this Traversal to a group of a different type")
			self._name = name
			self.multiplierCtrl = multCtrl
			self.progressCtrl = progCtrl
			self.prog = prog
			self._buildIdx = None
			self.expanded = {}
			self._enabled = True
			self.color = color

			mgrs = [model.insertItemManager(group) for model in self.models]
			with nested(*mgrs):
				self.group = group
				self.multiplierCtrl.traversal = self
				self.progressCtrl.traversal = self
				self.prog.controller = self
				self.group.items.append(self)
				self.simplex.traversals.append(self)

	@classmethod
	def createTraversal(cls, name, simplex, multItem, progItem, multFlip, progFlip, group=None, count=4):
		""" Create a Traversal between two items """
		if simplex.restShape is None:
			raise RuntimeError("Simplex system is missing rest shape")

		if group is None:
			gname = "TRAVERSALS"
			matches = [i for i in simplex.traversalGroups if i.name == gname]
			if matches:
				group = matches[0]
			else:
				group = Group(gname, simplex, Traversal)

		mm = TravPair(multItem, -1 if multFlip else 1, 'multiplier')
		pp = TravPair(progItem, -1 if progFlip else 1, 'progress')

		prog = Progression(name, simplex)
		trav = cls(name, simplex, mm, pp, prog, group)

		for c in reversed(range(count)):
			val = (100*(c+1)) / count
			pp = prog.createShape("{0}_{1}".format(name, val), val / 100.0)
			simplex.DCC.zeroShape(pp.shape)
		return trav

	@property
	def enabled(self):
		return self._enabled

	@enabled.setter
	@stackable
	def enabled(self, value):
		self._enabled = value

	@property
	def name(self):
		return self._name

	@name.setter
	@stackable
	def name(self, value):
		""" Set the name of a combo """
		self._name = value
		self.prog.name = value
		#self.DCC.renameTraversal(self, value)
		#for model in self.models:
			#model.itemDataChanged(self)

	@classmethod
	def loadV2(cls, simplex, progs, data):
		name = data["name"]
		prog = progs[data["prog"]]
		group = simplex.groups[data.get("group", 2)]
		color = QColor(*data.get("color", (0, 0, 0)))

		pcIdx = data['progressControl']
		if data['progressType'].lower() == 'slider':
			pc = simplex.sliders[pcIdx]
		else:
			pc = simplex.combos[pcIdx]
		pFlip = data['progressFlip']
		pp = TravPair(pc, -1 if pFlip else 1, 'progress')

		mcIdx = data['multiplierControl']
		if data['multiplierType'].lower() == 'slider':
			mc = simplex.sliders[mcIdx]
		else:
			mc = simplex.combos[mcIdx]
		mFlip = data['multiplierFlip']
		mm = TravPair(mc, -1 if mFlip else 1, 'multiplier')

		return cls(name, simplex, mm, pp, prog, group, color)

	def buildDefinition(self, simpDict, legacy):
		if self._buildIdx is None:
			self._buildIdx = len(simpDict["traversals"])
			x = {
				"name": self.name,
				"prog": self.prog.buildDefinition(simpDict, legacy),
				"progressType": type(self.progressCtrl.controller).__name__,
				"progressControl": self.progressCtrl.buildDefinition(simpDict, legacy),
				"progressFlip": self.progressCtrl.value < 0,
				"multiplierType": type(self.progressCtrl.controller).__name__,
				"multiplierControl": self.multiplierCtrl.buildDefinition(simpDict, legacy),
				"multiplierFlip": self.multiplierCtrl.value < 0,
				"group": self.group.buildDefinition(simpDict, legacy),
				"color": self.color.getRgb()[:3],
				"enabled": self._enabled,
			}
			simpDict.setdefault("traversals", []).append(x)
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None
		self.prog.clearBuildIndex()
		self.group.clearBuildIndex()

	@stackable
	def delete(self):
		""" Delete a traversal and any shapes it contains """
		mgrs = [model.removeItemManager(self) for model in self.models]
		with nested(*mgrs):
			g = self.group
			if self not in g.items:
				return # Can happen when deleting multiple groups
			g.items.remove(self)
			self.group = None
			self.simplex.traversals.remove(self)

			pairs = self.prog.pairs[:] # gotta make a copy
			for pp in pairs:
				if not pp.shape.isRest:
					self.simplex.shapes.remove(pp.shape)
					self.DCC.deleteShape(pp.shape)

	def extractShape(self, shape, live=True, offset=10.0):
		""" Extract a shape from a combo progression """
		return self.DCC.extractTraversalShape(self, shape, live, offset)

	@stackable
	def setMultiplier(self, item, value=None):
		if value is None:
			value = self.multiplierCtrl.value
		tp = TravPair(item, value, "multiplier")
		tp.traversal = self
		#old = self.multiplierCtrl
		self.multiplierCtrl = tp
		for model in self.models:
			model.itemDataChanged(self.multiplierCtrl)

	@stackable
	def setProgressor(self, item, value=None):
		if value is None:
			value = self.progressCtrl.value
		tp = TravPair(item, value, "progress")
		tp.traversal = self
		#old = self.progressCtrl
		self.progressCtrl = tp
		for model in self.models:
			model.itemDataChanged(self.progressCtrl)


class Group(SimplexAccessor):
	classDepth = 1
	def __init__(self, name, simplex, groupType, color=QColor(128, 128, 128)):
		self.simplex = simplex
		with self.stack.store(self):
			self._name = name
			self.items = []
			self._buildIdx = None
			self.expanded = {}
			self.color = color
			self.groupType = groupType

			mgrs = [model.insertItemManager(simplex) for model in self.models]
			with nested(*mgrs):
				if self.groupType is Slider:
					self.simplex.sliderGroups.append(self)
				elif self.groupType is Combo:
					self.simplex.comboGroups.append(self)
				elif self.groupType is Traversal:
					self.simplex.traversalGroups.append(self)

	@property
	def name(self):
		return self._name

	@name.setter
	@stackable
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
	def loadV2(cls, simplex, data):
		name = data['name']
		color = data.get('color', (0, 0, 0))
		typeName = data['type']
		if typeName == 'Slider':
			groupType = Slider
		elif typeName == 'Combo':
			groupType = Combo
		elif typeName == 'Traversal':
			groupType = Traversal
		else:
			raise RuntimeError("Malformed simplex json string: Improper group type")
		return cls(name, simplex, groupType, QColor(*color))

	def buildDefinition(self, simpDict, legacy):
		if self._buildIdx is None:
			self._buildIdx = len(simpDict["groups"])
			if legacy:
				simpDict.setdefault("groups", []).append(self.name)
			else:
				x = {
					"name": self.name,
					"color": self.color.getRgb()[:3],
					"type": self.groupType.__name__
				}
				simpDict.setdefault("groups", []).append(x)
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None

	@stackable
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

	@stackable
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

	@stackable
	def take(self, things):
		if self.groupType is None:
			self.groupType = type(things[0])

		if not all([isinstance(i, self.groupType) for i in things]):
			raise ValueError("All items in this group must be of type: {}".format(self.groupType))

		# do it this way instead of using set() to keep order
		for thing in things:
			thing.setGroup(self)


class Simplex(object):
	classDepth = 0
	'''
	The main Top-level abstract object that controls an entire simplex setup

	Note: There are no "Load a system over the current one" type methods.
	To accomplish that, just construct a new Simplex object over top of it
	'''
	def __init__(self, name="", models=None, falloffModels=None, forceDummy=False):
		self._name = name # The name of the system
		self.sliders = [] # List of contained sliders
		self.combos = [] # List of contained combos
		self.traversals = [] # list of contained traversals
		self.sliderGroups = [] # List of groups containing sliders
		self.comboGroups = [] # List of groups containing combos
		self.traversalGroups = [] # List of groups containing traversals
		self.falloffs = [] # List of contained falloff objects
		self.shapes = [] # List of contained shape objects
		self.models = models or [] # connected Qt Item Models
		self.falloffModels = falloffModels or [] # connected Qt Falloff Models
		self.restShape = None # Name of the rest shape
		self.clusterName = "Shape" # Name of the cluster (XSI use only)
		self.expanded = {} # Am I expanded by model
		self.comboExpanded = False # Am I expanded in the combo tree
		self.sliderExpanded = False # Am I expanded in the slider tree
		self.DCC = DummyDCC(self) if forceDummy else DCC(self) # Interface to the DCC
		self.stack = Stack() # Reference to the Undo stack
		self._extras = {} # Any extra key data to store in the output json
		self._legacy = False # whether to write the legacy types

	def __deepcopy__(self, memo):
		cls = self.__class__
		result = cls.__new__(cls)
		memo[id(self)] = result
		for k, v in self.__dict__.iteritems():
			if k == "models":
				# do not make a copy of the connected models
				# a deepcopied simplex won't be connected to a UI
				setattr(result, k, [])
			elif k == "falloffModels":
				# do not make a copy of the connected models
				# a deepcopied simplex won't be connected to a UI
				setattr(result, k, [])
			elif k == "stack":
				# Make a disabled stack for new simplex
				s = Stack()
				s.enabled = False
				setattr(result, k, s)
			elif k == "DCC":
				# do not connect the deepcopied simplex to the DCC
				# we will want to change it without affecting the current scene
				# Requires the name be copied already
				setattr(result, '_name', copy.deepcopy(self._name, memo))
				setattr(result, k, DummyDCC(result))
			elif k == "expanded":
				# do not make a copy of the expansion
				# because it's keyed off the un-copied models
				setattr(result, k, {})
			else:
				setattr(result, k, copy.deepcopy(v, memo))
		return result

	def _initValues(self):
		self._name = "" # The name of the system
		self.sliders = [] # List of contained sliders
		self.combos = [] # List of contained combos
		self.sliderGroups = [] # List of groups containing sliders
		self.comboGroups = [] # List of groups containing combos
		self.traversalGroups = [] # List of groups containing combos
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
	def buildEmptySystem(cls, thing, name, forceDummy=False):
		''' Create a new system on a given mesh, ready to go '''
		self = cls(name, forceDummy=forceDummy)
		self.DCC.loadNodes(self, thing, create=True)
		self.restShape = Shape.buildRest(self)
		return self

	@classmethod
	def buildSystemFromJsonString(cls, jsString, thing, name=None, forceDummy=False, pBar=None):
		js = json.loads(jsString)
		if name is None:
			name = js['systemName']
		return cls.buildSystemFromDict(js, thing, name=name, forceDummy=forceDummy, pBar=pBar)

	@classmethod
	def buildSystemFromJson(cls, jsPath, thing, name=None, pBar=None):
		with open(jsPath, 'r') as f:
			jsString = f.read()
		return cls.buildSystemFromJsonString(jsString, thing, name=name, pBar=pBar)

	@classmethod
	def buildSystemFromSmpx(cls, smpxPath, thing=None, name=None, forceDummy=False, pBar=None):
		""" Build a system from a simplex abc file """
		if thing is None:
			thing = cls.buildBaseObject(smpxPath)

		iarch, abcMesh, js = cls.getAbcDataFromPath(smpxPath)
		del iarch, abcMesh # release the files
		if name is None:
			name = js['systemName']
		self = cls.buildSystemFromDict(js, thing, name=name, forceDummy=forceDummy, pBar=pBar)
		self.loadSmpxShapes(smpxPath, pBar=pBar)
		self.loadSmpxFalloffs(smpxPath, pBar=pBar)
		return self

	@classmethod
	def buildSystemFromMesh(cls, thing, name, forceDummy=False, pBar=None):
		jsDict = json.loads(DCC.getSimplexStringOnThing(thing, name))
		return cls.buildSystemFromDict(jsDict, thing, name=name, create=False, forceDummy=forceDummy, pBar=pBar)

	@classmethod
	def buildSystemFromDict(cls, jsDict, thing, name=None, create=True, forceDummy=False, pBar=None):
		''' Utility for building a cleared system from a dictionary '''
		if name is None:
			name = jsDict['systemName']
		self = cls(name, forceDummy=forceDummy)
		self.DCC.loadNodes(self, thing, create=create)
		self.loadDefinition(jsDict, create=create, pBar=pBar)
		return self

	def loadSmpxShapes(self, smpxPath, pBar=None):
		iarch, abcMesh, js  = self.getAbcDataFromPath(smpxPath)
		try:
			self.DCC.loadAbc(abcMesh, js, pBar=pBar)
		finally:
			del abcMesh, iarch

	def loadSmpxFalloffs(self, abcPath, pBar=None):
		''' Read and return the relevant data from a simplex alembic '''
		iarch = IArchive(str(abcPath)) # because alembic hates unicode
		try:
			top = iarch.getTop()
			par = top.children[0]
			par = IXform(top, par.getName())
			systemSchema = par.getSchema()
			props = systemSchema.getUserProperties()
			foDict = {}
			try:
				foPropPar = props.getProperty("falloffs")
			except KeyError:
				pass
			else:
				nps = foPropPar.getNumProperties()
				for i in range(nps):
					foProp = foPropPar.getProperty(i)
					fon = foProp.getName()
					fov = foProp.getValue() # imath.FloatArray
					fov = list(fov) if np is None else np.array(fov)
					foDict[fon] = fov
		except Exception: #pylint: disable=broad-except
			del iarch
			raise

		for fo in self.falloffs:
			foData = foDict.get(fo.name, None)
			if foData is not None:
				fo.weights = foData

	# Properties
	@property
	def name(self):
		''' Property getter for the simplex name '''
		return self._name

	@name.setter
	@stackable
	def name(self, value):
		""" rename a system and all objects in it """
		if value == self._name:
			return

		self._name = value
		self.DCC.renameSystem(value) #??? probably needs work
		if self.restShape is not None:
			self.restShape.name = self.getRestName()

		for model in self.models:
			model.itemDataChanged(self)

	@property
	def progs(self):
		out = []
		for slider in self.sliders:
			out.append(slider.prog)
		for combo in self.combos:
			out.append(combo.prog)
		for trav in self.traversals:
			out.append(trav.prog)
		return out

	@property
	def groups(self):
		return self.sliderGroups + self.comboGroups + self.traversalGroups

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
			if not props.valid():
				raise ValueError(".smpx file is missing the alembic user properties")
			prop = props.getProperty("simplex")
			if not prop.valid():
				raise ValueError(".smpx file is missing the definition string")
			jsString = prop.getValue()
			js = json.loads(jsString)
		except Exception: #pylint: disable=broad-except
			del iarch
			raise

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
		mgrs = [model.resetModelManager() for model in models]
		with nested(*mgrs):
			self.DCC.deleteSystem()
			self._initValues()
			self.DCC = DCC(self)
		self.models = models

	def getDownstreamTraversals(self, item):
		downstream = []
		for t in self.traversals:
			if (item == t.multiplierCtrl.controller) or (item == t.progressCtrl.controller):
				downstream.append(t)
		downstream = list(set(downstream))
		return downstream

	def getDownstreamCombos(self, slider):
		downstream = []
		if not isinstance(slider, Slider):
			return downstream
		for c in self.combos:
			for pair in c.pairs:
				if pair.slider == slider:
					downstream.append(c)
					break
		downstream = list(set(downstream))
		return downstream

	def deleteDownstream(self, item):
		todel = []
		todel.extend(self.getDownstreamCombos(item))
		todel.extend(self.getDownstreamTraversals(item))
		for c in todel:
			c.delete()

	# USER METHODS
	def setLegacy(self, legacy):
		self._legacy = legacy

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
		things = [self.shapes, self.sliders, self.combos, self.traversals, self.groups, self.falloffs]
		for thing in things:
			for i in thing:
				i.clearBuildIndex()

		# Make sure we start with the extras in
		# case we're overwriting with new data
		d = copy.deepcopy(self._extras)

		# Then set all the top-level system keys
		d["encodingVersion"] = 1 if self._legacy else 2
		d["systemName"] = self.name
		d["clusterName"] = self.clusterName
		d.setdefault("falloffs", [])
		d.setdefault("combos", [])
		d.setdefault("shapes", [])
		d.setdefault("sliders", [])
		d.setdefault("groups", [])
		d.setdefault("progressions", [])
		d.setdefault("traversals", [])

		# rest shape should *ALWAYS* be index 0
		for shape in self.shapes:
			shape.buildDefinition(d, self._legacy)

		for group in self.groups:
			group.buildDefinition(d, self._legacy)

		for falloff in self.falloffs:
			falloff.buildDefinition(d, self._legacy)

		for slider in self.sliders:
			slider.buildDefinition(d, self._legacy)

		for combo in self.combos:
			combo.buildDefinition(d, self._legacy)

		for trav in self.traversals:
			trav.buildDefinition(d, self._legacy)

		return d

	@stackable
	def loadDefinition(self, simpDict, create=True, pBar=None):
		''' Build the structure of objects in this system
		based on a provided dictionary'''

		self.name = simpDict["systemName"]
		self.clusterName = simpDict["clusterName"] # for XSI
		if simpDict["encodingVersion"] == 1:
			self.loadV1(simpDict, create=create, pBar=pBar)
		elif simpDict["encodingVersion"] == 2:
			self.loadV2(simpDict, create=create, pBar=pBar)
		self.storeExtras(simpDict)

	def _incPBar(self, pBar, txt, inc=1):
		if pBar is not None:
			pBar.setValue(pBar.value() + inc)
			pBar.setLabelText("Building:\n" + txt)
			QApplication.processEvents()
			return not pBar.wasCanceled()
		return True

	def loadV2(self, simpDict, create=True, pBar=None):
		self.DCC.preLoad(self, simpDict, create=create, pBar=pBar)
		fos = simpDict.get('falloffs', [])
		gs = simpDict.get('groups', [])
		for f in fos:
			Falloff.loadV2(self, f)
		if gs:
			for g in gs:
				Group.loadV2(self, g)
		else:
			Group("Group_0", self, Slider)
			Group("Group_1", self, Combo)
			Group("Group_2", self, Traversal)

		if pBar is not None:
			maxLen = max(len(i["name"]) for i in simpDict["shapes"])
			pBar.setLabelText("_"*maxLen)
			pBar.setValue(0)
			pBar.setMaximum(len(simpDict["shapes"]) + 1)
		self.shapes = []
		for s in simpDict["shapes"]:
			if not self._incPBar(pBar, s["name"]):
				return
			Shape.loadV2(self, s, create)

		self.restShape = self.shapes[0]
		self.restShape.isRest = True

		progs = [Progression.loadV2(self, p) for p in simpDict['progressions']]

		for s in simpDict['sliders']:
			Slider.loadV2(self, progs, s, create)
		for c in simpDict['combos']:
			Combo.loadV2(self, progs, c)
		for t in simpDict['traversals']:
			Traversal.loadV2(self, progs, t)

		for x in itertools.chain(self.sliders, self.combos, self.traversals):
			x.prog.name = x.name
		self.DCC.postLoad(self)

	def loadV1(self, simpDict, create=True, pBar=None):
		self.DCC.preLoad(self, simpDict, create=create, pBar=pBar)
		self.falloffs = [Falloff(f[0], self, *f[1:]) for f in simpDict["falloffs"]]
		groupNames = simpDict["groups"]

		if pBar is not None:
			maxLen = max(map(len, simpDict["shapes"]))
			pBar.setLabelText("_"*maxLen)
			pBar.setMaximum(len(simpDict["shapes"]) + 1)

		shapes = []
		for s in simpDict["shapes"]:
			if not self._incPBar(pBar, s): return
			shapes.append(Shape(s, self))

		self.restShape = shapes[0]
		self.restShape.isRest = True

		progs = []
		for p in simpDict["progressions"]:
			progShapes = [shapes[i] for i in p[1]]
			progFalloffs = [self.falloffs[i] for i in p[4]]
			progPairs = [ProgPair(self, s, pv) for s, pv in zip(progShapes, p[2])]
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
				comboGroup = Group(gn, self, Combo)
				createdComboGroups[gn] = comboGroup

			cmb = Combo(c[0], self, pairs, prog, comboGroup)
			cmb.simplex = self

		self.traversals = []
		self.traversalGroups = []
		createdTraversalGroups = {}
		if 'traversals' in simpDict:
			for t in simpDict['traversals']:
				name = t["name"]
				prog = progs[t["prog"]]

				pcIdx = t['progressControl']
				pcSearch = self.sliders if t['progressType'].lower() == 'slider' else self.combos
				pc = pcSearch[pcIdx]
				pFlip = t['progressFlip']
				pp = TravPair(pc, -1 if pFlip else 1, 'progress')

				mcIdx = t['multiplierControl']
				mcSearch = self.sliders if t['multiplierType'].lower() == 'slider' else self.combos
				mc = mcSearch[mcIdx]
				mFlip = t['multiplierFlip']
				mm = TravPair(mc, -1 if mFlip else 1, 'multiplier')

				gn = groupNames[t.get("group", 2)]
				if gn in createdTraversalGroups:
					travGroup = createdTraversalGroups[gn]
				else:
					travGroup = Group(gn, self, Traversal)
					createdTraversalGroups[gn] = travGroup

				color = QColor(*t.get("color", (0, 0, 0)))

				trav = Traversal(name, self, mm, pp, prog, travGroup, color)
				trav.simplex = self

		for x in itertools.chain(self.sliders, self.combos, self.traversals):
			x.prog.name = x.name
		self.DCC.postLoad(self)

	def storeExtras(self, simpDict):
		''' Store any unknown keys when dumping, just in case they're important elsewhere '''
		sd = copy.deepcopy(simpDict)
		knownTopLevel = ["encodingVersion", "systemName", "clusterName", "falloffs", "combos",
			"shapes", "sliders", "groups", "traversals", "progressions"]

		for ktn in knownTopLevel:
			if ktn in sd:
				del sd[ktn]
		self._extras = sd

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
		self.exportOther(path, self.DCC.mesh, world=True, pBar=pBar)

	def exportOther(self, path, dccMesh, world=False, pBar=None):
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
			self.DCC.exportAbc(dccMesh, abcMesh, defDict, world=world, pBar=pBar)

		finally:
			del arch

	def setSlidersWeights(self, sliders, weights):
		''' Set the weights of multiple sliders as one action '''
		with undoContext(self.DCC):
			for slider, weight in zip(sliders, weights):
				slider.value = weight
			self.DCC.setSlidersWeights(sliders, weights)
			for model in self.models:
				for slider in sliders:
					model.itemDataChanged(slider)

	def extractRestShape(self, offset=0):
		if self.restShape is not None:
			return self.DCC.extractShape(self.restShape, live=False, offset=offset)

	def buildRestShape(self):
		self.restShape = Shape.buildRest(self)
		return self.restShape

	# SPLIT CODE
	def buildSplitterList(self, splitFalloff):
		'''
			This is kinda fun. The way deepcopy works is that every object
			that is copied is added to the 'memo' which is a dict keyed off its id()
			That way, you don't have to re-copy an object if you've already seen it
			This means that if I make a memo that contains objects that I don't
			want copied, then I should just be able to use deepcopy, and let that
			handle the referencing 
		'''
		# Build the basic memo dict
		memo = {}
		memo[id(self)] = self
		stack = Stack()
		stack.enabled = False
		memo[id(self.stack)] = stack
		for g in self.groups: memo[id(g)] = g
		for s in self.sliders: memo[id(s)] = s
		for c in self.combos: memo[id(c)] = c
		for t in self.traversals: memo[id(t)] = t
		for f in self.falloffs: memo[id(f)] = f
		for s in self.shapes: memo[id(s)] = s
		for p in self.progs: memo[id(p)] = p

		# now get a list of objects used by the given falloff
		splitters = []
		for prog in self.progs:
			if splitFalloff in prog.falloffs:
				ctrl = prog.controller
				sidedName0 = splitFalloff.getSidedName(ctrl.name, 0)
				sidedName1 = splitFalloff.getSidedName(ctrl.name, 1)
				if sidedName0 == ctrl.name or sidedName1 == ctrl.name:
					continue

				splitters.append(prog)
				splitters.append(ctrl)
				for pair in prog.pairs:
					splitters.append(pair.shape)

				# Also add the downstream combos, and their progs
				dss = []
				if isinstance(ctrl, Slider):
					dss.extend(self.getDownstreamCombos(ctrl))
					dss.extend(self.getDownstreamTraversals(ctrl))

				if isinstance(ctrl, Combo):
					dss.extend(self.getDownstreamTraversals(ctrl))

				for ds in dss:
					sidedName0 = splitFalloff.getSidedName(ds.name, 0)
					sidedName1 = splitFalloff.getSidedName(ds.name, 1)
					if sidedName0 == ds.name or sidedName1 == ds.name:
						continue

					splitters.append(ds)
					splitters.append(ds.prog)
					for pair in ds.prog.pairs:
						splitters.append(pair.shape)

		splitters = set(splitters)
		splitters.discard(self.restShape)
		splitters = list(splitters)

		for sp in splitters:
			try:
				del memo[id(sp)]
			except KeyError:
				print "SP", sp, sp.name
				raise

		return splitters, memo

	def split(self, pBar=None):
		if np is None:
			raise RuntimeError("Numpy is not available, and splitting requires it")

		self.DCC.getAllShapeVertices(self.shapes, pBar)
		self.DCC.loadMeshTopology()

		if pBar is not None:
			pBar.setValue(0)
			pBar.setLabelText("Building Split System")

		splitSmpx = copy.deepcopy(self)
		splitSmpx.DCC._faces = self.DCC._faces
		splitSmpx.DCC._counts = self.DCC._counts
		splitSmpx.DCC._uvs = self.DCC._uvs

		# Make sure no DCC operations happen during the split
		restVerts = splitSmpx.restShape.verts
		for fo in splitSmpx.falloffs:
			fo.setVerts(restVerts)

		doLoop = True
		while doLoop:
			doLoop = False
			for fo in splitSmpx.falloffs:
				if pBar is not None:
					pBar.setLabelText("Splitting On\n{0}".format(fo.name))
					QApplication.processEvents()
				# Get all the objects that should be split with this falloff
				# along with the deepcopy memo
				splitList, memo = splitSmpx.buildSplitterList(fo)
				if not splitList:
					continue
				doLoop = True
				lSideSplitList = copy.deepcopy(splitList, memo=copy.copy(memo))
				rSideSplitList = copy.deepcopy(splitList, memo=copy.copy(memo))

				# Set the results onto the system
				# First remove the old items
				for item in splitList:
					if hasattr(item, 'group'):
						item.group.items.remove(item)
						item.group = None
					if isinstance(item, Slider):
						splitSmpx.sliders.remove(item)
					elif isinstance(item, Combo):
						splitSmpx.combos.remove(item)
					elif isinstance(item, Traversal):
						splitSmpx.traversals.remove(item)
					elif isinstance(item, Shape):
						splitSmpx.shapes.remove(item)
						# It's a DummyDCC, this just removes the shape verts
						# from the DCC dictionary if it exists
						splitSmpx.DCC.deleteShape(item)

				# set the sides of everything in those new lists
				# and apply the falloffs to the shapes
				for item in lSideSplitList:
					fo.splitRename(item, 0)
					if isinstance(item, Shape):
						fo.applyFalloff(item, 0)
					if hasattr(item, 'group'):
						item.group.items.append(item)
					if isinstance(item, Slider):
						splitSmpx.sliders.append(item)
					elif isinstance(item, Combo):
						splitSmpx.combos.append(item)
					elif isinstance(item, Traversal):
						splitSmpx.traversals.append(item)
					elif isinstance(item, Shape):
						splitSmpx.shapes.append(item)

				for item in rSideSplitList:
					fo.splitRename(item, 1)
					if isinstance(item, Shape):
						fo.applyFalloff(item, 1)
					if hasattr(item, 'group'):
						item.group.items.append(item)
					if isinstance(item, Slider):
						splitSmpx.sliders.append(item)
					elif isinstance(item, Combo):
						splitSmpx.combos.append(item)
					elif isinstance(item, Traversal):
						splitSmpx.traversals.append(item)
					elif isinstance(item, Shape):
						splitSmpx.shapes.append(item)
		splitSmpx.DCC.pushAllShapeVertices(splitSmpx.shapes)
		return splitSmpx

	def buildInputVectors(self, ignoreSliders=None, depthCutoff=None, ignoreFloaters=True, extremes=True):
		""" This is a kind of specialized function. Often, I have to turn combo deltas
		into the full sculpted shape. But to do that, I have to build the inputs to the
		solver that enable each shape, and I need a name for each shape.
		This function gives me both.
		"""
		# InputVector comes from the c++ std::vector
		# Get all endpoint shapes from the progressions
		shapeNames = []
		inVecs = []
		ignoreSliders = ignoreSliders or set()
		ignoreSliders = set(ignoreSliders)

		for slIdx, slider in enumerate(self.sliders):
			if slider.name in ignoreSliders:
				continue

			pairs = [p for p in slider.prog.pairs if not p.shape.isRest]
			if extremes:
				pairs = [p for p in pairs if abs(p.value) == 1.0]

			for pp in pairs:
				inVec = [0.0] * len(self.sliders)
				inVec[slIdx] = pp.value
				shapeNames.append(pp.shape.name)
				inVecs.append(inVec)

		for combo in self.combos:
			if ignoreFloaters and combo.isFloating():
				continue
			if depthCutoff is not None and len(combo.pairs) > depthCutoff:
				continue
			if ignoreSliders & set([i.name for i in combo.getSliders()]):
				# if the combo's sliders are in ignoreSliders
				continue

			pairs = [p for p in combo.prog.pairs if not p.shape.isRest]
			if extremes:
				pairs = [p for p in pairs if abs(p.value) == 1.0]

			iv = combo.getInputVector()
			for pp in pairs:
				inVecs.append([x*pp.value for x in iv])
				shapeNames.append(pp.shape.name)

		return shapeNames, inVecs


