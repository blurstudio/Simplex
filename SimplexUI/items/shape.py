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
from ..interface import DCC, undoContext
from .accessor import SimplexAccessor
from .stack import stackable

class Shape(SimplexAccessor):
	classDepth = 9
	def __init__(self, name, simplex, create=True, color=QColor(128, 128, 128)):
		super(Shape, self).__init__(simplex)
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
			self.progPairs = []

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
			from .slider import Slider
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

	def _buildLinkedRename(self, newName, maxDepth, currentLinks):
		# Now that all the bookkeeping has been handled by the main method
		# I can handle recursing for the object specific stuff here
		shape = None #TEMP

		from .slider import Slider
		from .combo import Combo
		from .traversal import Traversal

		for pp in self.progPairs:
			currentLinks = pp.prog.siblingRename(shape, newName, currentLinks)


			ctrl = pp.prog.controller
			if isinstance(ctrl, Slider):
				nn = None
				currentLinks = ctrl.buildLinkedRename(nn, maxDepth=maxDepth-1, currentLinks=currentLinks)
			elif isinstance(ctrl, Combo):
				nn = None
				currentLinks = ctrl.buildLinkedRename(nn, maxDepth=maxDepth-1, currentLinks=currentLinks)
			elif isinstance(ctrl, Traversal):
				nn = None
				currentLinks = ctrl.buildLinkedRename(nn, maxDepth=maxDepth-1, currentLinks=currentLinks)

		return currentLinks



		# First, check for a slider rename,
			# if so, recurse into that slider
			# Check for combo renames (because combos use the shape names)

		#if isinstance(item, Shape):
			# Check if the parent is a slider
				# Check if the slider needs renamed
					# Check if the item's siblings need renamed
				# Check if there are any combos that depend on this shape name
					# If so, rename *both* the combo and its linked children
			# Check if the parent is a combo
				# Check if the combo needs renamed
					# If so, check if the item's siblings need renamed too
			# Check if the parent is a traversal
				# Check if the traversal needs renamed
					# If so, check if the item's siblings need renamed too
		#elif isinstance(item, Slider):
			# Check if the name change is linked to any of my shapes
				# Go through the shape linked rename for one of those instead, maybe?
					# There are possible ambiguities if you do a *full* slider rename
					# with both positive and negatively named shapes.
			# Otherwise
				# Check for linked combos, and rename down that branch
				# Check for linked traversals, and rename down that branch
		#elif isinstance(item, Combo):
			#pass
		#elif isinstance(item, Traversal):
			#pass

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
	
	@staticmethod
	def isNumberField(val):
		if not val:
			return False
		if val[0].lower() == 'n':
			val = val[1:]
		return val.isdigit()

	@property
	def verts(self):
		if self._verts is None:
			self._verts = self.DCC.getShapeVertices(self)
		return self._verts

	@verts.setter
	def verts(self, value):
		self._verts = value

