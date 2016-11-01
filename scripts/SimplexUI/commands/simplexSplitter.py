'''
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
'''

#pylint:disable=redefined-outer-name, invalid-name
"""
Sides:
	L = Shows up in left side when splitX
			Shows up in UD when splitV
	R = Shows up in right side when splitX
			Shows up in UD when splitV
	U = Shows up in top when splitV
			Shows up in LR when splitX
	D = Shows up in bottom when splitV
			Shows up in LR when splitX
	M/C = Strictly centered: shows up in both sides when split in X or V

	X = Splittable into L/R
	V = Splittable into U/D

	S = Symmetric: Internal use
"""
import json

LEFTSIDE = "L"
RIGHTSIDE = "R"
TOPSIDE = "U"
BOTTOMSIDE = "D"
CENTERS = "MC"
VERTICALSPLIT = "V"
VERTICALRESULTS = TOPSIDE + BOTTOMSIDE
VERTICALAXIS = "Y"
HORIZONTALSPLIT = "X"
HORIZONTALRESULTS = LEFTSIDE + RIGHTSIDE
HORIZONTALAXIS = "X"
RESTNAME = "Rest"
SEP = "_"
SYMMETRIC = "S"

class Falloff(object):
	def __init__(self, name, search, rep, foType, axis, foValues):
		self.name = name
		self.search = search # 'X'
		self.rep = rep # 'LR'
		self.foType = foType # typeIndex 0=planar 1=map

		self.axis = axis
		self.foValues = foValues

	def __hash__(self):
		return hash(self.name)

	def getSidedName(self, name, sIdx):
		nn = name
		s = "{0}{1}{0}".format(SEP, self.search)
		r = "{0}{1}{0}".format(SEP, self.rep[sIdx])
		nn = nn.replace(s, r)
		s = "{0}{1}".format(SEP, self.search) # handle Postfix
		r = "{0}{1}".format(SEP, self.rep[sIdx])
		nn = nn.replace(s, r)
		s = "{1}{0}".format(SEP, self.search) # handle Prefix
		r = "{1}{0}".format(SEP, self.rep[sIdx])
		nn = nn.replace(s, r)
		return nn

	@classmethod
	def loadJSON(cls, js):
		name = js[0]
		foType = js[1]
		axis = js[2]
		foValues = js[3:]

		search = HORIZONTALSPLIT
		rep = HORIZONTALRESULTS
		if axis == VERTICALAXIS:
			search = VERTICALSPLIT
			rep = VERTICALRESULTS
		return cls(name, search, rep, foType, axis, foValues)

	def toJSON(self):
		out = [self.name, self.foType, self.axis]
		out.extend(self.foValues)
		return out


class Shape(object):
	def __init__(self, name, side, maps=None, mapSides=None, oName=None):
		self.name = name
		self.oName = oName or name
		self.side = side
		self.maps = maps or []
		self.mapSides = mapSides or []

	def canSplit(self, split):
		return split.search in self.side

	def setSide(self, split, sIdx):
		# Rest is unsplittable
		if self.name == RESTNAME:
			return self

		newSide = self.side.replace(split.search, split.rep[sIdx])

		newMaps = self.maps[:]
		newMaps.append(split)

		ms = self.mapSides[:]
		ms.append(split.rep[sIdx])
		nn = split.getSidedName(self.name, sIdx)

		return Shape(nn, newSide, newMaps, ms, self.oName)

	@classmethod
	def loadJSON(cls, js):
		name = js
		# TODO: use a better side metric
		side = name.split(SEP)[0]
		return cls(name, side)

	def toJSON(self):
		return self.name

	def myprint(self, prefix):
		print prefix + self.name
		print prefix + str(self.maps)

	def applyMapToObj(self):
		if not self.mapSides:
			return

		print "Copying", self.oName, "To", self.name
		mapNames = ', '.join([i.name for i in self.maps])
		print "Applying maps:", mapNames
		print "With Sides:", self.mapSides
		print "\n"

	def getPerMap(self, perMap):
		# make a dict keyed on the map and mapsides
		key = (tuple(self.maps), tuple(self.mapSides))
		perMap.setdefault(key, []).append(self)


class Progression(object):
	def __init__(self, name, shapes, times, interp, falloffs, forceSide=None):
		self.name = name
		self.shapes = shapes
		self.times = map(float, times)
		self.interp = interp
		self.falloffs = falloffs
		self.sided = None
		self.forceSide = forceSide

	def canSplit(self, split):
		return split in self.falloffs

	def isSided(self, side):
		if self.forceSide is not None:
			return side in self.forceSide

		sp = self.name.split(SEP)
		sp = [i for i in sp if len(i) < 3]
		sp = [i for i in sp if i.isupper()]
		found = set(sp)

		# remove all centered shapes
		found -= set(HORIZONTALSPLIT + VERTICALSPLIT + CENTERS)
		if len(found) == 1 and side in found:
			return True
		return False

	def setSide(self, split, sIdx):
		if not self.canSplit(split):
			return self

		splits = [i.setSide(split, sIdx) for i in self.shapes]
		forceSide = split.rep[sIdx]
		if self.forceSide is not None:
			forceSide += self.forceSide

		falloffs = self.falloffs[:]
		falloffs.remove(split)

		nn = split.getSidedName(self.name, sIdx)
		return Progression(nn, splits, self.times, self.interp, falloffs, forceSide)

	@classmethod
	def loadJSON(cls, js, allShapes, allFalloffs):
		name = js[0]
		shapeIdxs = js[1]
		times = js[2]
		interp = js[3]
		falloffIdxs = js[4]
		shapes = [allShapes[i] for i in shapeIdxs]
		falloffs = [allFalloffs[i] for i in falloffIdxs]
		return cls(name, shapes, times, interp, falloffs)

	def toJSON(self, newShapes, falloffList):
		name = self.name
		shapeIdxs = [newShapes.index(shape) for shape in self.shapes]
		times = self.times
		interp = self.interp
		falloffs = [falloffList.index(fo) for fo in self.falloffs]
		return [name, shapeIdxs, times, interp, falloffs]

	def myprint(self, prefix=""):
		print prefix + self.name
		for shape in self.shapes:
			shape.myprint(prefix + "  ")


class Slider(object):
	def __init__(self, name, progression, groupIdx):
		self.name = name
		self.prog = progression
		self.groupIdx = groupIdx
		# progression defines the side

	def isSided(self, side):
		return self.prog.isSided(side)

	def canSplit(self, split):
		return self.prog.canSplit(split)

	def split(self, split):
		if not self.canSplit(split):
			return None

		nn0 = split.getSidedName(self.name, 0)
		nn1 = split.getSidedName(self.name, 1)
		return [Slider(nn0, self.prog.setSide(split, 0), self.groupIdx),
				Slider(nn1, self.prog.setSide(split, 1), self.groupIdx)]

	@classmethod
	def loadJSON(cls, js, allProgs):
		name = js[0]
		progIdx = js[1]
		groupIdx = js[2]
		return cls(name, allProgs[progIdx], groupIdx)

	def toJSON(self, allProgs):
		name = self.name
		progIdx = allProgs.index(self.prog)
		groupIdx = self.groupIdx
		return [name, progIdx, groupIdx]

	def myprint(self, prefix=""):
		print prefix + self.name
		self.prog.myprint(prefix + "  ")


class Combo(object):
	def __init__(self, name, progression, sliders, values, groupIdx):
		self.name = name
		self.prog = progression
		self.sliders = sliders
		self.values = values
		self.groupIdx = groupIdx

	def split(self, splitMap, splitList):
		toSplit = []
		for sp in splitList:
			if sp[0] in self.sliders:
				toSplit.append(sp)

		if toSplit == []:
			return [self]

		# check each input slider to see what side of the split this combo is on
		# If everything is either center or one side of the split, then the
		# resulting combo will be only that side
		# eg.  furrow_C*sneer_L*smile_L should only return: furrow_L*sneer_L*smile_L

		cursides = set()
		for state in self.sliders:
			for i in splitMap.rep:
				if state.isSided(i):
					cursides.add(i)

		if len(cursides) == 0:
			curside = None
		elif len(cursides) == 1:
			curside = cursides.pop()
		else:
			curside = SYMMETRIC

		#inputPoint
		lState = self.sliders[:]
		rState = self.sliders[:]

		for slider, newsliders in toSplit:
			lSlider, rSlider = newsliders
			idx = self.sliders.index(slider)
			lState[idx] = lSlider
			rState[idx] = rSlider

		lProg = self.prog.setSide(splitMap, 0)
		rProg = self.prog.setSide(splitMap, 1)

		if curside == SYMMETRIC:
			symState = dict(zip(lState, self.values) + zip(rState, self.values))
			symSliders, symValues = zip(*symState)
			symCombo = Combo(self.name, self.prog, symSliders, symValues)
			return [symCombo]

		nnL = splitMap.getSidedName(self.name, 0)
		nnR = splitMap.getSidedName(self.name, 1)

		comboL = Combo(nnL, lProg, lState, self.values, self.groupIdx)
		comboR = Combo(nnR, rProg, rState, self.values, self.groupIdx)
		combos = [comboL, comboR]

		if curside is None:
			return combos

		sideIdx = splitMap.rep.index(curside)
		return [combos[sideIdx]]

	@classmethod
	def loadJSON(cls, js, allProgs, allSliders):
		name = js[0]
		progIdx = js[1]
		sliderTimes = js[2]
		group = js[3]
		sliderIdxs, times = zip(*sliderTimes)
		sliders = [allSliders[i] for i in sliderIdxs]
		return cls(name, allProgs[progIdx], sliders, times, group)

	def toJSON(self, allProgs, allSliders):
		name = self.name
		progIdx = allProgs.index(self.prog)
		sliders = [allSliders.index(sli) for sli in self.sliders]
		times = self.values
		groupIdx = self.groupIdx
		sliderTimes = zip(sliders, times)
		return [name, progIdx, sliderTimes, groupIdx]


class Simplex(object):
	def __init__(self, name, groups, encodingVersion, clusterName, falloffs, shapes, progs, sliders, combos):
		self.name = name
		self.groups = groups
		self.encodingVersion = encodingVersion
		self.clusterName = clusterName
		self.falloffs = falloffs
		self.shapes = shapes
		self.progs = progs
		self.sliders = sliders
		self.combos = combos
		self.restShape = shapes[0]
		self._split = False

	def split(self):
		for falloff in self.falloffs:
			newsliders = []
			newcombos = []
			splitList = []
			for slider in self.sliders:
				sp = slider.split(falloff)
				if sp is None:
					newsliders.append(slider)
				else:
					newsliders.extend(sp)
					splitList.append((slider, sp))

			for combo in self.combos:
				newcombos.extend(combo.split(falloff, splitList))

			self.sliders = newsliders[:]
			self.combos = newcombos[:]

		# Dig through sliders and combos to find the freshly split shapes and progressions
		progs = []

		for slider in self.sliders:
			progs.append(slider.prog)

		for combo in self.combos:
			progs.append(combo.prog)

		progs = list(set(progs))
		progs.sort(key=lambda x: x.name)
		self.progs = progs

		shapes = []
		for prog in self.progs:
			shapes.extend(prog.shapes)

		shapes = set(shapes)
		shapes.remove(self.restShape)
		shapes = list(shapes)
		shapes.sort(key=lambda x: x.name)
		self.shapes = [self.restShape] + shapes
		self._split = True

	def applyMaps(self):
		if self._split:
			for shape in self.shapes:
				shape.applyMapToObj()
		else:
			raise RuntimeError("Please call the .split() method first")

	def getPerMap(self):
		perMap = {}
		if self._split:
			for shape in self.shapes:
				shape.getPerMap(perMap)
		else:
			raise RuntimeError("Please call the .split() method first")

		return perMap

	@classmethod
	def loadJSON(cls, js):
		name = js["systemName"]
		groups = js["groups"]

		encodingVersion = js["encodingVersion"]
		clusterName = js["clusterName"]

		jfalloffs = js["falloffs"]
		jshapes = js["shapes"]
		jprogressions = js["progressions"]
		jsliders = js["sliders"]
		jcombos = js["combos"]

		falloffs = [Falloff.loadJSON(i) for i in jfalloffs]
		shapes = [Shape.loadJSON(i) for i in jshapes]
		progs = [Progression.loadJSON(i, shapes, falloffs) for i in jprogressions]
		sliders = [Slider.loadJSON(i, progs) for i in jsliders]
		combos = [Combo.loadJSON(i, progs, sliders) for i in jcombos]
		return cls(name, groups, encodingVersion, clusterName, falloffs, shapes, progs, sliders, combos)

	def toJSON(self):
		name = self.name
		groups = self.groups
		encodingVersion = self.encodingVersion
		clusterName = self.clusterName
		falloffs = [i.toJSON() for i in self.falloffs]
		shapes = [i.toJSON() for i in self.shapes]
		progs = [i.toJSON(self.shapes, self.falloffs) for i in self.progs]
		sliders = [i.toJSON(self.progs) for i in self.sliders]
		combos = [i.toJSON(self.progs, self.sliders) for i in self.combos]

		js = {}
		js["systemName"] = name
		js["groups"] = groups
		js["encodingVersion"] = encodingVersion
		js["clusterName"] = clusterName

		js["falloffs"] = falloffs
		js["shapes"] = shapes
		js["progressions"] = progs
		js["sliders"] = sliders
		js["combos"] = combos

		return js


# I'm not using these b/c they're slower than just using json.dumps
# Though when debugging, they're kinda nice to have
import pprint
def pprintFormatter(thing, context, maxlevels, level):
	typ = pprint._type(thing)
	if typ is unicode:
		thing = str(thing)
	return pprint._safe_repr(thing, context, maxlevels, level)

def makeHumanReadableDump(nestedDict):
	pp = pprint.PrettyPrinter(indent=2, width=300)
	pp.format = pprintFormatter
	dump = pp.pformat(nestedDict)
	dump = dump.replace("'", '"')
	return dump

if __name__ == "__main__":
	jpath = 'C:\Users\tyler\Desktop\Simplex2\commands\test.json'
	opath = 'C:\Users\tyler\Desktop\Simplex2\commands\test_Split.json'

	with open(jpath) as f:
		j = json.loads(f.read())
	system = Simplex.loadJSON(j)
	system.split()
	js = system.toJSON()
	#hr = makeHumanReadableDump(js)
	#system.applyMaps()
	jsOut = json.dumps(js, sort_keys=True, indent=2, separators=(',', ':'))

	with open(opath, 'w') as f:
		f.write(jsOut)







