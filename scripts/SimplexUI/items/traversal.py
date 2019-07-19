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
from .group import Group
from .progression import Progression

class TravPair(SimplexAccessor):
	classDepth = 3
	def __init__(self, controller, value, usage):
		simplex = controller.simplex
		super(TravPair, self).__init__(simplex)

		self.traversal = None
		self.controller = controller
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

	def treeRow(self):
		return self.usageIndex()

	def treeParent(self):
		return self.traversal

	def treeData(self, column):
		if column == 0:
			return self.controller.name
		elif column == 1:
			return self.value
		elif column == 2:
			return self.usage.upper()
		return None


class Traversal(SimplexAccessor):
	classDepth = 2
	def __init__(self, name, simplex, multCtrl, progCtrl, prog, group, color=QColor(128, 128, 128)):
		super(Traversal, self).__init__(simplex)
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
			return self.progressCtrl
		elif row == 1:
			return self.multiplierCtrl
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

	@staticmethod
	def buildTraversalName(progressor, multiplier, progFlip, multFlip):
		pfV = 'n' if progFlip else ''
		mfV = 'n' if multFlip else ''
		return 'TvP{0}_{1}_TvM{2}_{3}'.format(pfV, progressor.name, mfV, multiplier.name, )

	def controllerNameLinks(self):
		""" Return whether the multiplier and progressor names in the current
		traversal depends on its name """
		tSurr = '_{0}_'.format(self.name)
		mSurr = '_{0}_'.format(self.multiplierCtrl.name)
		pSurr = '_{0}_'.format(self.progressCtrl.name)
		return [mSurr in tSurr, pSurr in tSurr]

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

