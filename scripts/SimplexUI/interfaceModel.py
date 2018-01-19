import os, sys, copy, json, itertools
from collections import OrderedDict
from functools import wraps
from alembic.Abc import OArchive, IArchive, OStringProperty
from alembic.AbcGeom import OXform, IPolyMesh, IXform, OPolyMesh
from Qt.QtCore import QAbstractItemModel, QModelIndex, Qt

CONTEXT = os.path.basename(sys.executable)
if CONTEXT == "maya.exe":
	from mayaInterface import DCC, DISPATCH, rootWindow, ToolActions, undoable, undoContext
elif CONTEXT == "XSI.exe":
	from xsiInterface import DCC, DISPATCH, rootWindow, ToolActions, undoable, undoContext
else:
	from dummyInterface import DCC, DISPATCH, rootWindow, ToolActions, undoable, undoContext





# ABSTRACT CLASSES FOR HOLDING DATA
# Probably can be in a separate file
# In fact, most of this can be in an
# abstract base class file

class Shape(object):
	def __init__(self, name, simplex):
		self._thing = None
		self._thingRepr = None
		self.name = name
		self._buildIdx = None
		simplex.shapes.append(self)
		self.isRest = False
		self.expanded = False

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

	def buildDefinition(self, d):
		if self._buildIdx is None:
			d.setdefault("shapes", []).append(self.name)
			self._buildIdx = len(d["shapes"]) - 1
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

class Group(object):
	def __init__(self, name):
		self.name = name
		self.sliders = []
		self.combos = []
		self._buildIdx = None
		self.expanded = False

	def buildDefinition(self, d):
		if self._buildIdx is None:
			d.setdefault("groups", []).append(self.name)
			self._buildIdx = len(d["groups"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None

class Falloff(object):
	def __init__(self, name, *data):
		self.name = name
		self.children = []
		self._buildIdx = None
		self.splitType = data[0]
		self.expanded = False

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

	def buildDefinition(self, d):
		if self._buildIdx is None:
			if self.splitType == "planar":
				line = ["planar", self.axis, self.maxVal, self.maxHandle, self.minHandle, self.minVal]
			else:
				line = ["map", self.mapName]
			d.setdefault("falloffs", []).append([self.name] + line)
			self._buildIdx = len(d["falloffs"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None

class ProgPair(object):
	def __init__(self, shape, value):
		self.shape = shape
		self.value = value
		self.prog = None
		self.minValue = -1.0
		self.maxValue = 1.0
		self.expanded = False

	def buildDefinition(self, d):
		idx = self.shape.buildDefinition(d)
		return idx, self.value

class Progression(object):
	def __init__(self, name, pairs, interp="spline", falloffs=None):
		self.name = name
		self.pairs = pairs
		self.interp = interp
		self.falloffs = falloffs or []
		self.parent = None
		for pair in self.pairs:
			pair.prog = self
		for falloff in self.falloffs:
			falloff.children.append(self)
		self._buildIdx = None
		self.expanded = False

	def getShapeIndex(self, shape):
		for i, p in enumerate(self.pairs):
			if p.shape == shape:
				return i
		raise ValueError("Provided shape:{0} is not in the list".format(shape.name))

	def getShapes(self):
		return [i.shape for i in self.pairs]

	def buildDefinition(self, d):
		if self._buildIdx is None:
			idxPairs = [pair.buildDefinition(d) for pair in self.pairs]
			idxPairs.sort(key=lambda x: x[1])
			idxs, values = zip(*idxPairs)
			foIdxs = [f.buildDefinition(d) for f in self.falloffs]
			x = [self.name, idxs, values, self.interp, foIdxs]
			d.setdefault("progressions", []).append(x)
			self._buildIdx = len(d["progressions"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None
		for pair in self.pairs:
			pair.shape.clearBuildIndex()
		for fo in self.falloffs:
			fo.clearBuildIndex()

class Slider(object):
	def __init__(self, name, prog, group):
		self.name = name
		self._thing = None
		self._thingRepr = None
		self.prog = prog
		self.group = group
		self.split = False
		self.prog.parent = self
		self.group.sliders.append(self)
		self.simplex = None
		self._buildIdx = None
		self.value = 0.0
		self.minValue = -1.0
		self.maxValue = 1.0
		self.expanded = False

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

	def buildDefinition(self, d):
		if self._buildIdx is None:
			gIdx = self.group.buildDefinition(d)
			pIdx = self.prog.buildDefinition(d)
			d.setdefault("sliders", []).append([self.name, pIdx, gIdx])
			self._buildIdx = len(d["sliders"]) - 1
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

class ComboPair(object):
	def __init__(self, slider, value):
		self.slider = slider
		self.value = float(value)
		self.minValue = -1.0
		self.maxValue = 1.0
		self.combo = None
		self.expanded = False

	def buildDefinition(self, d):
		sIdx = self.slider.buildDefinition(d)
		return sIdx, self.value

class Combo(object):
	def __init__(self, name, pairs, prog, group):
		self.name = name
		self.pairs = pairs
		self.prog = prog
		self.group = group
		self.prog.parent = self
		self.group.combos.append(self)
		self.simplex = None
		self._buildIdx = None
		for p in self.pairs:
			p.combo = self
		self.expanded = False

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

	def buildDefinition(self, d):
		if self._buildIdx is None:
			gIdx = self.group.buildDefinition(d)
			pIdx = self.prog.buildDefinition(d)
			idxPairs = [p.buildDefinition(d) for p in self.pairs]
			x = [self.name, pIdx, idxPairs, gIdx]
			d.setdefault("combos", []).append(x)
			self._buildIdx = len(d["combos"]) - 1
		return self._buildIdx

	def clearBuildIndex(self):
		self._buildIdx = None
		self.prog.clearBuildIndex()
		self.group.clearBuildIndex()

class Simplex(object):
	def __init__(self, name=""):
		self.name = name
		self.sliders = []
		self.combos = []
		self.groups = []
		self.falloffs = []
		# must keep track of shapes for
		# connection order stuff
		self.shapes = []
		self.restShape = None
		self.clusterName = "Shape"
		self.expanded = False
		self.comboExpanded = False
		self.sliderExpanded = False

	def getFloatingShapes(self):
		floaters = [c for c in self.combos if c.isFloating()]
		floatShapes = []
		for f in floaters:
			floatShapes.extend(f.prog.getShapes())
		return floatShapes

	def buildDefinition(self):
		things = [self.sliders, self.combos, self.groups, self.falloffs]
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

		for group in self.groups:
			group.buildDefinition(d)

		for falloff in self.falloffs:
			falloff.buildDefinition(d)

		for slider in self.sliders:
			slider.buildDefinition(d)

		for combo in self.combos:
			combo.buildDefinition(d)

		return d

	def loadDefinition(self, d):
		# Don't set the system name
		# It should be set by here anyway
		self.name = d["systemName"]
		self.clusterName = d["clusterName"]
		self.falloffs = [Falloff(*f) for f in d["falloffs"]]
		self.groups = [Group(g) for g in d["groups"]]
		shapes = [Shape(s, self) for s in d["shapes"]]
		self.restShape = shapes[0]
		self.restShape.isRest = True

		progs = []
		for p in d["progressions"]:
			progShapes = [shapes[i] for i in p[1]]
			progFalloffs = [self.falloffs[i] for i in p[4]]
			progPairs = map(ProgPair, progShapes, p[2])
			progs.append(Progression(p[0], progPairs, p[3], progFalloffs))

		self.sliders = []
		for s in d["sliders"]:
			sliderProg = progs[s[1]]
			sliderGroup = self.groups[s[2]]
			sli = Slider(s[0], sliderProg, sliderGroup)
			sli.simplex = self
			self.sliders.append(sli)

		self.combos = []
		for c in d["combos"]:
			prog = progs[c[1]]
			sliderIdxs, sliderVals = zip(*c[2])
			sliders = [self.sliders[i] for i in sliderIdxs]
			pairs = map(ComboPair, sliders, sliderVals)
			if len(c) >= 4:
				group = self.groups[c[3]]
			else:
				group = self.groups[0] # TEMPORARY
			cmb = Combo(c[0], pairs, prog, group)
			cmb.simplex = self
			self.combos.append(cmb)

		for x in itertools.chain(self.sliders, self.combos):
			x.prog.name = x.name

	def loadJSON(self, jsDefinition):
		self.loadDefinition(json.loads(jsDefinition))

	def getRestName(self):
		return "Rest_{0}".format(self.name)

	def getRestShape(self):
		if self.restShape is None:
			self.restShape = Shape(self.getRestName(), self)
			self.restShape.isRest = True
		return self.restShape

	def dump(self):
		return json.dumps(self.buildDefinition())













# Add these to the objects above
class System(object):



	# Simplex
	def exportABC(self, path, pBar=None):
		self.extractExternal(path, self.DCC.mesh, pBar)

	# Simplex
	def extractExternal(self, path, dccMesh, pBar=None):
		# Extract shapes from an arbitrary mesh based on the current simplex
		defDict = self.simplex.buildDefinition()
		jsString = json.dumps(defDict)

		arch = OArchive(str(path)) # alembic does not like unicode filepaths
		try:
			par = OXform(arch.getTop(), str(self.name))
			props = par.getSchema().getUserProperties()
			prop = OStringProperty(props, "simplex")
			prop.setValue(str(jsString))
			abcMesh = OPolyMesh(par, str(self.name))
			self.DCC.exportABC(dccMesh, abcMesh, defDict, pBar)

		finally:
			del arch

	# Simplex
	def createBlank(self, thing, name):
		simp = Simplex(name)
		self.initSimplex(simp)
		self.DCC.loadNodes(simp, thing, create=True)
		self.buildRest()

	# Simplex
	def loadFromMesh(self, thing, systemName):
		jsDict = json.loads(self.DCC.getSimplexStringOnThing(thing, systemName))
		self.buildFromDict(thing, jsDict, False)

	# Simplex
	def buildFromJson(self, thing, jsonPath):
		""" Create a new system based on a path to a json file
		Build any DCC objects that are missing if create=True """
		with open(jsonPath, 'r') as f:
			js = json.load(f)
		self.buildFromDict(thing, js, True)

	# Simplex
	def buildBaseAbc(self, abcPath):
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

			obj = self.DCC.buildRestABC(abcMesh, js)
		finally:
			del iarch
		return obj

	# Simplex
	def buildFromAbc(self, thing, abcPath, pBar=None):
		""" Load a system from an exported
		abc file onto the current system """
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

			system = self.buildFromDict(thing, js, True, pBar)
			self.DCC.loadABC(abcMesh, js, pBar)
		finally:
			del iarch

		return system

	# Simplex
	def buildFromDict(self, thing, simpDict, create, pBar=None):
		simp = Simplex(simpDict["systemName"])
		simp.loadDefinition(simpDict)
		self.initSimplex(simp)
		self.DCC.loadNodes(simp, thing, create=create)
		self.DCC.loadConnections(simp, create=create)

	# Simplex
	def renameSystem(self, name):
		""" rename a system and all objects in it """
		self.name = name
		self.simplex.name = name
		self.DCC.renameSystem(name)
		restName = self.simplex.buildRestName()
		self.renameShape(self.simplex.restShape, restName)

	# Simplex
	def deleteSystem(self):
		self.DCC.deleteSystem()
		self.name = None
		self.simplex = None
		self.DCC = DCC(self.simplex)

	# Simplex
	def buildRest(self):
		""" create/find the system's rest shape"""
		shape = self.simplex.buildRestShape()
		if not shape.thing:
			pp = ProgPair(shape, 1.0)
			self.DCC.createShape(shape.name, pp)
		return shape

	# Simplex
	def createShape(self, shapeName, prog, tVal):
		""" create a shape and add it to a progression """
		shape = Shape(shapeName, self.simplex)
		pp = ProgPair(shape, tVal)
		pp.prog = prog
		prog.pairs.append(pp)

		self.DCC.createShape(shapeName, pp)
		if isinstance(prog.parent, Slider):
			self.DCC.updateSlidersRange([prog.parent])

		return pp

	# Simplex
	def createGroup(self, name):
		""" Create a new group """
		g = Group(name)
		self.simplex.groups.append(g)
		return g

	# Simplex
	def createFalloff(self, name):
		""" Create a new falloff.  Planar, mid, X axis """
		fo = Falloff(name, 'planar', 'x', 1.0, 0.66, 0.33, -1.0)
		self.simplex.falloffs.append(fo)
		self.DCC.createFalloff(name)
		return fo

	# Simplex
	def createSlider(self, name, group, shape=None, tVal=1.0, multiplier=1):
		"""
		Create a new slider with a name in a group.
		Possibly create a single default shape for this slider
		"""
		pp = [ProgPair(self.getRest(), 0.0)]
		prog = Progression(name, pp)
		if shape is None:
			self.createShape(name, prog, tVal)
		else:
			prog.pairs.append(ProgPair(shape, tVal))

		sli = Slider(name, prog, group)
		self.simplex.sliders.append(sli)

		self.DCC.createSlider(name, sli, multiplier=multiplier)
		return sli

	# Simplex
	def setSlidersWeights(self, sliders, weights):
		""" Set the weight of a slider"""
		for slider, weight in zip(sliders, weights):
			slider.value = weight
		self.DCC.setSlidersWeights(sliders, weights)

	# Simplex
	def comboExists(self, sliders, values):
		checkSet = set([(s.name, v) for s, v in zip(sliders, values)])
		for cmb in self.simplex.combos:
			cmbSet = set([(p.slider.name, p.value) for p in cmb.pairs])
			if checkSet == cmbSet:
				return cmb
		return None

	# Simplex
	def createCombo(self, name, sliders, values, group, shape=None, tVal=1.0):
		""" Create a combo of sliders at values """
		cPairs = [ComboPair(slider, value) for slider, value in zip(sliders, values)]
		pp = [ProgPair(self.getRest(), 0.0)]
		prog = Progression(name, pp)
		if shape:
			prog.pairs.append(ProgPair(shape, tVal))

		cmb = Combo(name, cPairs, prog, group)
		self.simplex.combos.append(cmb)

		if shape is None:
			pp = self.createShape(name, prog, tVal)
			self.zeroShape(pp.shape)

		return cmb

	# Simplex
	def getRest(self):
		""" Return the shape that is the 'rest' shape """
		return self.simplex.buildRestShape()













	# Shape
	def extractShape(self, shape, live=True, offset=10.0):
		""" make a mesh representing a shape. Can be live or not """
		return self.DCC.extractShape(shape, live, offset)

	# Shape
	def connectShape(self, shape, mesh=None, live=False, delete=False):
		""" Force a shape to match a mesh
			The "connect shape" button is:
				mesh=None, delete=True
			The "match shape" button is:
				mesh=someMesh, delete=False
			There is a possibility of a "make live" button:
				live=True, delete=False
		"""
		self.DCC.connectShape(shape, mesh, live, delete)

	# Shape
	def zeroShape(self, shape):
		""" Set the shape to be completely zeroed """
		self.DCC.zeroShape(shape)

	# Shape
	def deleteProgPair(self, pp):
		""" Remove a shape from the system """
		prog = pp.prog
		prog.pairs.remove(pp)
		if not pp.shape.isRest:
			self.simplex.shapes.remove(pp.shape)
			self.DCC.deleteShape(pp.shape)

	# Shape
	def renameShape(self, shape, name):
		""" Change the name of the shape """
		shape.name = name
		self.DCC.renameShape(shape, name)






	# Progression
	def extractProgressive(self, slider, live=True, offset=10.0):
		pairs = {i.value: i.shape for i in slider.prog.pairs}
		pos, neg = [], []
		rest = None
		for pp in slider.prog.pairs:
			if pp.value < 0.0:
				neg.append((pp.value, pp.shape))
			elif pp.value > 0.0:
				pos.append((pp.value, pp.shape))
			elif pp.value == 0.0:
				pos.append((pp.value, pp.shape))
				neg.append((pp.value, pp.shape))
		pos = sorted(pos)
		neg = sorted(neg, reverse=True)
		# rest is the first item, extreme is the last
		for prog in [pos, neg]:
			if len(prog) <= 1:
				continue
			ext, deltaShape = self.DCC.extractWithDeltaShape(prog[-1][1], live, offset)
			extreme = prog[-1][0]
			for p in prog[1:-1]:
				offset += 5
				ext = self.DCC.extractWithDeltaConnection(p[1], deltaShape, p[0]/extreme, live, offset)

	# Progression
	def moveShapeToProgression(self, shapePair, newProg):
		""" Remove the shapePair from its current progression
		and set it in a new progression """
		oldProg = shapePair.prog
		oldProg.pairs.remove(shapePair)
		newProg.pairs.append(shapePair)
		shapePair.prog = newProg

	# Progression
	def setShapesValues(self, progPairs, values):
		""" Set the shape's value in it's progression """
		for pp, val in zip(progPairs, values):
			pp.value = val

		sliders = [i.prog.parent for i in progPairs if isinstance(i.prog.parent, Slider)]
		sliders = list(set(sliders))
		if sliders:
			self.DCC.updateSlidersRange(sliders)

	# Progression
	def addProgFalloff(self, prog, falloff):
		""" Add a falloff to a slider's falloff list """
		prog.falloffs.append(falloff)
		falloff.children.append(prog)
		self.DCC.addProgFalloff(prog, falloff)

	# Progression
	def removeProgFalloff(self, prog, falloff):
		""" Remove a falloff from a slider's falloff list """
		prog.falloffs.remove(falloff)
		falloff.children.remove(prog)
		self.DCC.removeProgFalloff(prog, falloff)






	# Group
	def deleteGroup(self, group):
		""" Delete a group.  Any objects in this group will
		be moved to a single arbitrary other group """
		if len(self.simplex.groups) == 1:
			return
		self.simplex.groups.remove(group)

		for slider in group.sliders:
			self.deleteSlider(slider)

		for combo in group.combos:
			self.deleteCombo(combo)

	# Group
	def renameGroup(self, group, name):
		""" Set the name of a group """
		group.name = name







	# Falloff
	def duplicateFalloff(self, falloff, newName):
		""" duplicate a falloff with a new name """
		nf = copy.copy(falloff)
		nf.name = newName
		nf.data = copy.copy(falloff.data)
		nf.children = []
		self.simplex.falloffs.append(nf)
		self.DCC.duplicateFalloff(falloff, nf, newName)
		return nf

	# Falloff
	def deleteFalloff(self, falloff):
		""" delete a falloff """
		fIdx = self.simplex.falloffs.index(falloff)
		for child in falloff.children:
			child.falloff = None
		self.simplex.falloffs.pop(fIdx)

		self.DCC.deleteFalloff(falloff)

	# Falloff
	def setFalloffData(self, falloff, splitType, axis, minVal, minHandle, maxHandle, maxVal, mapName):
		""" set the type/data for a falloff """
		falloff.splitType = splitType
		falloff.axis = axis
		falloff.minVal = minVal
		falloff.minHandle = minHandle
		falloff.maxHandle = maxHandle
		falloff.maxVal = maxVal
		falloff.mapName = mapName
		self.DCC.setFalloffData(falloff, splitType, axis, minVal, minHandle, maxHandle, maxVal, mapName)





	# Slider
	def renameSlider(self, slider, name, multiplier=1):
		""" Set the name of a slider """
		slider.name = name
		slider.prog.name = name
		self.DCC.renameSlider(slider, name, multiplier=multiplier)

	# Slider
	def setSliderRange(self, slider, multiplier):
		self.DCC.setSliderRange(slider, multiplier)

	# Slider
	def deleteSlider(self, slider):
		""" Delete a slider and any shapes it contains """
		g = slider.group
		g.sliders.remove(slider)
		self.simplex.sliders.remove(slider)
		pairs = slider.prog.pairs[:] #gotta make a copy
		#for pair in slider.prog.pairs:
		for pair in pairs:
			self.deleteProgPair(pair)
		self.DCC.deleteSlider(slider)

	# Slider
	def setSliderGroup(self, slider, group):
		""" Set the group of a slider """
		slider.group.sliders.remove(slider)
		slider.group = group
		group.sliders.append(slider)

	# Slider
	def setSliderInterpolation(self, slider, interp):
		""" Set the interpolation of a slider """
		slider.prog.interp = interp







	# Combo
	def extractComboShape(self, combo, shape, live=True, offset=10.0):
		""" Extract a shape from a combo progression """
		return self.DCC.extractComboShape(combo, shape, live, offset)

	# Combo
	def connectComboShape(self, combo, shape, mesh=None, live=False, delete=False):
		""" Connect a shape into a combo progression"""
		self.DCC.connectComboShape(combo, shape, mesh, live, delete)

	#Combo
	def renameCombo(self, combo, name):
		""" Set the name of a combo """
		combo.name = name
		combo.prog.name = name
		self.DCC.renameCombo(combo, name)

	#Combo
	def deleteCombo(self, combo):
		""" Delete a combo and any shapes it contains """
		g = combo.group
		if combo not in g.combos:
			return # Can happen when deleting multiple groups
		g.combos.remove(combo)
		self.simplex.combos.remove(combo)
		pairs = combo.prog.pairs[:] # gotta make a copy
		for pair in pairs:
			self.deleteProgPair(pair)

	#Combo
	def setComboGroup(self, combo, group):
		""" Set the group of a combo """
		combo.group.combos.remove(combo)
		combo.group = group
		group.combos.append(combo)

	#Combo
	def setComboInterpolation(self, combo, interp):
		""" Set the interpolation of a combo """
		combo.prog.interp = interp

	# Combo
	def setComboValue(self, combo, slider, value):
		""" Set the Slider/value pairs for a combo """
		idx = combo.getSliderIndex(slider)
		combo.pairs[idx].value = value

	# Combo
	def appendComboValue(self, combo, slider, value):
		""" Append a Slider/value pair for a combo """
		cp = ComboPair(slider, value)
		cp.combo = combo
		combo.pairs.append(cp)

	# Combo
	def deleteComboPair(self, cp):
		""" delete a Slider/value pair for a combo """
		combo = cp.combo
		combo.pairs.delete(cp)



















class SimplexModel(QAbstractItemModel):
	def __init__(self, simplex, parent):
		self.simplex = simplex

	def index(self, row, column, parent):
		simpObject = parent.internalPointer()
		# get the child object for the specific row/column
		childObject = None
		self.createIndex(row, column, childObject)

	def parent(self, index):
		simpObject = index.internalPointer()
		parentObject = None
		parentRow = None
		self.createIndex(parentRow, 0, childObject)

	def rowCount(self, parent):
		simpObject = parent.internalPointer()
		return 0 # count of children

	def columnCount(self, parent):
		simpObject = parent.internalPointer()
		pass

	def data(self, index, role):
		if role == Qt.DecorationRole:
			return None
		return None

	def setData(self, index, value, role):
		self.dataChanged(index, index, [role])

	def flags(self, index):
		return None
		
	def headerData(self, section, orientation, role):
		return None

	def insertRows(self, row, count, parent):
		self.beginInsertRows()
		pass
		self.endInsertRows()

	def removeRows(self, row, count, parent):
		self.beginRemoveRows()
		pass
		self.endRemoveRows()

class SliderModel(SimplexModel):
	pass

class ComboModel(SimplexModel):
	pass








