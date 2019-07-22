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
from ..utils import getNextName, nested
from .accessor import SimplexAccessor
from .stack import stackable

class ProgPair(SimplexAccessor):
	classDepth = 9
	def __init__(self, simplex, shape, value):
		super(ProgPair, self).__init__(simplex)
		self.shape = shape
		self._value = value
		self.prog = None
		self.minValue = -1.0
		self.maxValue = 1.0
		self.expanded = {}
		if not shape.isRest and self not in self.shape.progPairs:
			self.shape.progPairs.append(self)

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
		from .slider import Slider
		self._value = val
		for model in self.models:
			model.itemDataChanged(self)
		if isinstance(self.prog.controller, Slider):
			self.prog.controller.setRange()

	@stackable
	def delete(self):
		ppairs = self.prog.pairs
		ridx = ppairs.index(self)
		mgrs = [model.removeItemManager(self) for model in self.models]
		with nested(*mgrs):
			pp = ppairs.pop(ridx)
			if not pp.shape.isRest:
				pp.shape.progPairs.remove(pp)
				if not pp.shape.progPairs:
					self.simplex.shapes.remove(pp.shape)
					self.DCC.deleteShape(pp.shape)

	def treeRow(self):
		return self.prog.pairs.index(self)

	def treeParent(self):
		from .slider import Slider
		par = self.prog
		if isinstance(par.controller, Slider):
			par = par.controller
		return par

	def treeData(self, column):
		if column == 0:
			return self.name
		if column == 2:
			return self.value
		return None


class Progression(SimplexAccessor):
	classDepth = 8
	interpTypes = (('Linear', 'linear'), ('Spline', 'spline'), ('Split Spline', 'splitspline'))

	def __init__(self, name, simplex, pairs=None, interp="spline", falloffs=None):
		super(Progression, self).__init__(simplex)
		with self.stack.store(self):
			self._name = name
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

	def treeChild(self, row):
		return self.pairs[row]

	def treeRow(self):
		from .combo import Combo
		from .traversal import Traversal
		if isinstance(self.controller, Traversal):
			# Show the progression after the mult and prog
			return 2
		elif isinstance(self.controller, Combo):
			# Show the progression after the comboPairs
			return len(self.controller.pairs)
		return None

	def treeParent(self):
		return self.controller

	def treeChildCount(self):
		return len(self.pairs)

	def treeData(self, column):
		if column == 0:
			return "SHAPES"
		return None

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
		from .slider import Slider
		for pp, val in zip(self.pairs, values):
			pp.value = val
			for model in self.models:
				model.itemDataChanged(pp)

		if isinstance(self.controller, Slider):
			self.controller.updateRange()
			for model in self.models:
				model.itemDataChanged(self.controller)

	def siblingRename(self, shape, newName, currentLinks):
		pass
		# get name change

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
		from .slider import Slider
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
		from .shape import Shape
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

