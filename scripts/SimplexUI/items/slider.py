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
import itertools
from ..Qt.QtGui import QColor
from ..utils import getNextName, nested, singleShot, caseSplit, makeUnique
from ..interface import undoContext

from .stack import stackable
from .accessor import SimplexAccessor
from .group import Group
from .progression import Progression, ProgPair
from .shape import Shape


class Slider(SimplexAccessor):
	classDepth = 7
	def __init__(self, name, simplex, prog, group, color=QColor(128, 128, 128), create=True):
		if group.groupType != type(self):
			raise ValueError("Cannot add this slider to a combo group")

		super(Slider, self).__init__(simplex)
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
		for model in self.models:
			model.itemDataChanged(self)

	@classmethod
	def createSlider(cls, name, simplex, group=None, shape=None, tVal=1.0):
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

		sli = cls(name, simplex, prog, group)
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
		self.DCC.renameSlider(self, value)
		# TODO Also rename the combos
		for model in self.models:
			model.itemDataChanged(self)

	def treeChild(self, row):
		return self.prog.pairs[row]

	def treeRow(self):
		return self.group.items.index(self)

	def treeParent(self):
		return self.group

	def treeChildCount(self):
		return len(self.prog.pairs)

	def treeData(self, column):
		if column == 0:
			return self.name
		if column == 1:
			return self.value
		return None

	def treeChecked(self):
		return self.enabled

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
			for i, s in enumerate(shapeNames):
				if check == s:
					out[i] = True
			if all(out):
				break
		return out

	@classmethod
	def buildSliderName(cls, pairs):
		''' This method is mainly used for figuring out what
		The new name for a slider will be if its shapes are renamed
		'''
		# In this case, pairs is *not* a list of ProgPairs
		# but a list of (name, value) tuples

		# First, I'm just going to ignore anything with values that aren't 1.0
		# This simplifies the logic greatly
		extPairs = [p for p in pairs if abs(p[1]) == 1.0]
		if len(extPairs) == 1:
			return extPairs[0]
		if extPairs[0] == 1:
			extPairs = extPairs.reversed()

		names = []
		for ep in extPairs:
			sp = ep[0].split('_')
			if Shape.isNumberField(sp[-1]):
				sp = sp[:-1]
			names.append(sp)

		return '_'.join([''.join(makeUnique(n)) for n in names])

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

	def updateValue(self):
		pass

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

	def setRange(self):
		values = [i.value for i in self.prog.pairs]
		self.minValue = min(values)
		self.maxValue = max(values)
		self.DCC.setSliderRange(self)

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


