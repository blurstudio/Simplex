
from Qt.QtCore import QAbstractItemModel, QModelIndex, Qt


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

	def buildRestName(self):
		return "Rest_{0}".format(self.name)

	def buildRestShape(self):
		if self.restShape is None:
			self.restShape = Shape(self.buildRestName(), self)
			self.restShape.isRest = True
		return self.restShape

	def dump(self):
		return json.dumps(self.buildDefinition())





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








