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
import copy, math
try:
	import numpy as np
except ImportError:
	np = None
from ..Qt.QtGui import QColor
from ..utils import nested
from .accessor import SimplexAccessor
from .stack import stackable

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
		super(Falloff, self).__init__(simplex)
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
		raise ValueError("Bad data passed to Falloff creation")

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

		mgrs = [model.removeItemManager(self) for model in self.falloffModels]
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

	def canRename(self, item):
		nn = self.getSidedName(item.name, 0)
		return nn != item.name

	def splitRename(self, item, sIdx):
		from .shape import Shape
		from .slider import Slider
		from .combo import Combo
		from .traversal import Traversal

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

