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
from ..Qt.QtGui import QColor
from ..utils import nested
from .accessor import SimplexAccessor
from .stack import stackable
from .slider import Slider
from .combo import Combo
from .group import Group
from .progression import Progression

class TravPair(SimplexAccessor):
	classDepth = 4
	def __init__(self, slider, value):
		simplex = slider.simplex
		super(TravPair, self).__init__(simplex)
		self.slider = slider
		self._value = float(value)
		self.minValue = -1.0
		self.maxValue = 1.0
		self.travPoint = None
		self.expanded = {}

	@property
	def models(self):
		return self.simplex.models

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

	def treeRow(self):
		return self.travPoint.pairs.index(self)

	def treeParent(self):
		return self.travPoint

	def treeData(self, column):
		if column == 0:
			return self.name
		if column == 1:
			return self.value
		return None


class TravPoint(SimplexAccessor):
	classDepth = 3
	def __init__(self, pairs, row):
		if not pairs:
			raise ValueError("Pairs must be provided for a TravPoint")
		simplex = pairs[0].slider.simplex
		super(TravPoint, self).__init__(simplex)

		self.pairs = pairs
		for pair in pairs:
			pair.travPoint = self
		self.row = row
		self.traversal = None
		self.expanded = {}

	def sliders(self):
		return [i.slider for i in self.pairs]

	@staticmethod
	def _wideCeiling(val, eps=0.001):
		if val > eps:
			return 1.0
		elif val < -eps:
			return -1.0
		return 0.0

	@stackable
	def addPair(self, pair):
		mgrs = [model.insertItemManager(self) for model in self.traversal.models]
		with nested(*mgrs):
			self.pairs.append(pair)

	def addSlider(self, slider, val=None):
		val = val if val is not None else slider.value
		val = self._wideCeiling(val)
		sliders = self.sliders()
		try:
			idx = sliders.index(slider)
		except IndexError:
			self.addPair(TravPair(slider, val))
		else:
			self.pairs[idx].value = val

	def addItem(self, item):
		if isinstance(item, Slider):
			self.addSlider(item)
		elif isinstance(item, Combo):
			for cp in item.pairs:
				self.addSlider(cp.slider, cp.value)

	@property
	def name(self):
		return "START" if self.row == 0 else "END"

	def treeData(self, column):
		if column == 0:
			return self.name
		return None

	def treeChild(self, row):
		return self.pairs[row]

	def treeRow(self):
		return self.row

	def treeParent(self):
		return self.traversal

	def treeChildCount(self):
		return len(self.pairs)

	def buildDefinition(self, simpDict, legacy):
		return [p.buildDefinition(simpDict, legacy) for p in self.pairs]


class Traversal(SimplexAccessor):
	classDepth = 2
	def __init__(self, name, simplex, startPoint, endPoint, prog, group, color=QColor(128, 128, 128)):
		super(Traversal, self).__init__(simplex)
		with self.stack.store(self):
			if group.groupType != type(self):
				raise ValueError("Cannot add this Traversal to a group of a different type")
			self._name = name
			self.startPoint = startPoint
			self.endPoint = endPoint
			self.prog = prog
			self._buildIdx = None
			self.expanded = {}
			self._enabled = True
			self.color = color

			mgrs = [model.insertItemManager(group) for model in self.models]
			with nested(*mgrs):
				self.group = group
				self.startPoint.traversal = self
				self.endPoint.traversal = self
				self.prog.controller = self
				self.group.items.append(self)
				self.simplex.traversals.append(self)

	@classmethod
	def createTraversal(cls, name, simplex, startPairs, endPairs, group=None, count=4):
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

		startPoint = TravPoint(startPairs, 0)
		endPoint = TravPoint(endPairs, 1)

		prog = Progression(name, simplex)
		trav = cls(name, simplex, startPoint, endPoint, prog, group)

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
		for model in self.models:
			model.itemDataChanged(self)

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

	def treeChild(self, row):
		if row == 0:
			return self.startPoint
		elif row == 1:
			return self.endPoint
		elif row == 2:
			return self.prog
		return None

	def treeRow(self):
		return self.group.items.index(self)

	def treeParent(self):
		return self.group

	def treeChildCount(self):
		return 3

	def treeChecked(self):
		return self.enabled

	def allSliders(self):
		startSliders = [p.slider for p in self.startPoint.pairs]
		endSliders = [p.slider for p in self.endPoint.pairs if p.slider not in startSliders]
		return startSliders + endSliders

	def ranges(self):
		startDict = {p.slider: p.value for p in self.startPoint.pairs}
		endDict = {p.slider: p.value for p in self.endPoint.pairs}
		allSliders = startDict.viewkeys() | endDict.viewkeys()

		rangeDict = {}
		for sli in allSliders:
			rangeDict[sli] = (startDict.get(sli, 0.0), endDict.get(sli, 0.0))
		return rangeDict

	@staticmethod
	def buildTraversalName(ranges):
		pfxs = {-1: 'N', 1: 'P', 0: ''}
		sliders = sorted(ranges.keys(), key=lambda x: x.name)
		parts = []
		for slider in sliders:
			start, end = ranges[slider]
			if start == end:
				pfx = pfxs[start]
			elif abs(start) == abs(end):
				pfx = 'R'
			else:
				val = max(start, end, key=abs)
				pfx = pfxs[val]
			parts.append(pfx)
			parts.append(slider.name)

		return 'Tv_' + '_'.join(parts)

	def controllerNameLinks(self):
		""" Return whether the slider names in the current traversal depends on its name """
		surr = '_{0}_'.format(self.name)
		return ['_{0}_'.format(sli) in surr for sli in self.allSliders()]

	def nameLinks(self):
		""" Return whether the name of each shape in the current
		progression depends on this traversal's name """
		# In this case, these names will *NOT* have the possibility of
		# a pos/neg name. Only the traversal name, and possibly a percentage
		shapeNames = []
		shapes = [i.shape for i in self.prog.pairs]
		for s in shapes:
			x = s.name.rsplit('_', 1)
			if len(x) == 2:
				base, sfx = x
				x = base if sfx.isdigit() else s.name
			shapeNames.append(x)
		return [i == self.name for i in shapeNames]

	@stackable
	def createShape(self, shapeName=None, tVal=None):
		""" create a shape and add it to a progression """
		pp, idx = self.prog.newProgPair(shapeName, tVal)
		mgrs = [model.insertItemManager(self.prog, idx) for model in self.models]
		with nested(*mgrs):
			pp.prog = self.prog
			self.prog.pairs.insert(idx, pp)
		return pp

	@classmethod
	def loadV2(cls, simplex, progs, data):
		name = data["name"]
		prog = progs[data["prog"]]
		group = simplex.groups[data.get("group", 2)]
		color = QColor(*data.get("color", (0, 0, 0)))

		rangeDict = {} # slider: [startVal, endVal]

		pFlip = -1.0 if data['progressFlip'] else 1.0
		pcIdx = data['progressControl']
		if data['progressType'].lower() == 'slider':
			sli = simplex.sliders[pcIdx]
			rangeDict[sli] = (0.0, pFlip)
		else:
			cmb = simplex.combos[pcIdx]
			for cp in cmb.pairs:
				rangeDict[cp.slider] = (0.0, cp.value)

		mFlip = -1.0 if data['multiplierFlip'] else 1.0
		mcIdx = data['multiplierControl']
		if data['multiplierType'].lower() == 'slider':
			sli = simplex.sliders[mcIdx]
			rangeDict[sli] = (mFlip, mFlip)
		else:
			cmb = simplex.combos[mcIdx]
			for cp in cmb.pairs:
				rangeDict[cp.slider] = (cp.value, cp.value)

		ssli = sorted(rangeDict.items(), key=lambda x: x[0].name)
		startPairs, endPairs = [], []
		for slider, (startVal, endVal) in ssli:
			startPairs.append(TravPair(slider, startVal))
			endPairs.append(TravPair(slider, endVal))

		startPoint = TravPoint(startPairs, 0)
		endPoint = TravPoint(endPairs, 1)

		return cls(name, simplex, startPoint, endPoint, prog, group, color)

	@classmethod
	def loadV3(cls, simplex, progs, data):
		name = data["name"]
		prog = progs[data["prog"]]
		group = simplex.groups[data.get("group", 2)]
		color = QColor(*data.get("color", (0, 0, 0)))

		startDict = dict(data["start"])
		endDict = dict(data["end"])
		sliIdxs = sorted(startDict.viewkeys() | endDict.viewkeys())
		startPairs, endPairs = [], []
		for idx in sliIdxs:
			startPairs.append(TravPair(simplex.sliders[idx], startDict.get(idx, 0.0)))
			endPairs.append(TravPair(simplex.sliders[idx], endDict.get(idx, 0.0)))
		startPoint = TravPoint(startPairs, 0)
		endPoint = TravPoint(endPairs, 1)

		return cls(name, simplex, startPoint, endPoint, prog, group, color)

	def buildDefinition(self, simpDict, legacy):
		if self._buildIdx is None:
			self._buildIdx = len(simpDict["traversals"])
			x = {
				"name": self.name,
				"prog": self.prog.buildDefinition(simpDict, legacy),
				"start": self.startPoint.buildDefinition(simpDict, legacy),
				"end": self.endPoint.buildDefinition(simpDict, legacy),
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
	def setPairs(self, pairs, idx):
		point = TravPoint([TravPair(s, v) for s, v in pairs], idx)
		if idx == 0:
			self.startPoint = point
		else:
			self.endPoint = point
		point.traversal = self
		for model in self.models:
			model.itemDataChanged(point)

	def setStartPairs(self, pairs):
		self.setPairs(pairs, 0)

	def setEndPairs(self, pairs):
		self.setPairs(pairs, 1)


