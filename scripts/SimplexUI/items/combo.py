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
from ..interface import undoContext
from .accessor import SimplexAccessor
from .stack import stackable


# Abstract Items
class ComboPair(SimplexAccessor):
	classDepth = 6
	def __init__(self, slider, value):
		simplex = slider.simplex
		super(ComboPair, self).__init__(simplex)
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
	@stackable
	def value(self, val):
		self._value = val
		for model in self.models:
			model.itemDataChanged(self)

	def buildDefinition(self, simpDict, legacy):
		sIdx = self.slider.buildDefinition(simpDict, legacy)
		return sIdx, self.value

	def treeRow(self):
		return self.combo.pairs.index(self)

	def treeParent(self):
		return self.combo

	def treeData(self, column):
		if column == 0:
			return self.name
		if column == 1:
			return self.value
		return None


class Combo(SimplexAccessor):
	classDepth = 5
	solveTypes = (
		('Minimum', 'min'), ('Multiply All', 'allMul'), ('Multiply Extremes', 'extMul'),
		('Multiply Avg of Extremes', 'mulAvgExt'), ('Multiply Avg', 'mulAvgAll'), ('None', 'min')
	)

	def __init__(self, name, simplex, pairs, prog, group, solveType, color=QColor(128, 128, 128)):
		super(Combo, self).__init__(simplex)
		with self.stack.store(self):
			if group.groupType != type(self):
				raise ValueError("Cannot add this slider to a combo group")
			self._name = name
			self.pairs = pairs
			self.prog = prog
			self._solveType = solveType
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
		for model in self.models:
			model.itemDataChanged(self)

	@classmethod
	def comboAlreadyExists(cls, simplex, sliders, values):
		checker = set([(s.name, v) for s, v in zip(sliders, values)])
		for combo in simplex.combos:
			tester = set([(p.slider.name, p.value) for p in combo.pairs])
			if checker == tester:
				return combo
		return None

	@classmethod
	def createCombo(cls, name, simplex, sliders, values, group=None, shape=None, solveType=None, tVal=1.0):
		""" Create a combo of sliders at values """
		if simplex.restShape is None:
			raise RuntimeError("Simplex system is missing rest shape")

		#Make sure to check if this combo already exists. If so, just return it
		exist = cls.comboAlreadyExists(simplex, sliders, values)
		if exist is not None:
			return exist
		from .group import Group
		from .progression import Progression, ProgPair

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

		cmb = Combo(name, simplex, cPairs, prog, group, solveType)

		if shape is None:
			pp = prog.createShape(name, tVal)
			simplex.DCC.zeroShape(pp.shape)

		return cmb

	@staticmethod
	def buildComboName(sliders, values):
		pairs = zip(sliders, values)
		pairs = sorted(pairs, key=lambda x: x[0].name)
		parts = []
		for slider, value in pairs:
			shape = slider.prog.getShapeAtValue(value)
			if shape is not None:
				parts.append(shape.name)
			else:
				# get the extreme shape and percentage-ize its name
				extVal = 1.0 if value > 0.0 else -1.0

				valName = '{}'.format(abs(int(value * 100)))
				valName = 'n' + valName if value < 0.0 else valName

				shape = slider.prog.getShapeAtValue(extVal)
				if shape is not None:
					sn = shape.name
					sn = sn.split('_')
					if sn[-1].isnumeric() or (sn[-1][0] == 'n' and sn[-1][1:].isnumeric()):
						sn[-1] = valName
					else:
						sn.append(valName)
					nsn = '_'.join(sn)
					parts.append(nsn)
				else:
					parts.append(slider.name)

		return '_'.join(parts)

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

	@property
	def solveType(self):
		return self._solveType

	@solveType.setter
	@stackable
	def solveType(self, newType):
		stNames, stVals = zip(*self.solveTypes)
		if newType not in stVals:
			raise ValueError("Solve Type {0} not in allowed types {1}".format(newType, stVals))
		self._solveType = newType
		for model in self.models:
			model.itemDataChanged(self)

	def treeChild(self, row):
		if row == len(self.pairs):
			return self.prog
		return self.pairs[row]

	def treeRow(self):
		return self.group.items.index(self)

	def treeParent(self):
		return self.group

	def treeChildCount(self):
		return len(self.pairs) + 1

	def treeChecked(self):
		return self.enabled

	def sliderNameLinks(self):
		""" Return whether the name of each slider in the current
		combo depends on this combo's name """
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
		solveType = data.get('solveType')
		return cls(name, simplex, pairs, prog, group, solveType)

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
					"solveType": str(self._solveType),
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
		mgrs = [model.insertItemManager(self.prog, idx) for model in self.models]
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

