import blurdev
print "AE", blurdev.activeEnvironment()

import copy
from SimplexUI.interfaceItems import Simplex, Group, Traversal, Combo, Slider, Shape, Falloff, ProgPair, ComboPair, TravPair, Progression
import numpy as np

class Skip(object): pass # an extra "none-ish" object to signify completely skipping the un-matched shape

def smpxMismatchCheck(simpA, simpB):
	mmDict = {}

	#saShapeNames = {sa.name: sa for sa in simpA.shapes}
	#sbShapeNames = {sb.name: sb for sb in simpB.shapes}
	#saShapeNameUnique = saShapeNames.viewkeys() - sbShapeNames.viewkeys()
	#sbShapeNameUnique = sbShapeNames.viewkeys() - saShapeNames.viewkeys()
	#slnMatch = [(san, None) for san in saShapeNameUnique] + [(None, sbn) for sbn in sbShapeNameUnique]
	#mmDict['shape'] = slnMatch

	saSliderNames = {sa.name: sa for sa in simpA.sliders}
	sbSliderNames = {sb.name: sb for sb in simpB.sliders}
	saSliderNameUnique = saSliderNames.viewkeys() - sbSliderNames.viewkeys()
	sbSliderNameUnique = sbSliderNames.viewkeys() - saSliderNames.viewkeys()
	slnMatch = {}
	for san in saSliderNameUnique:
		slnMatch[san] = (san, None)
	for sbn in sbSliderNameUnique:
		slnMatch[sbn] = (None, sbn)
	mmDict['slider'] = slnMatch

	saComboNames = {sa.name: sa for sa in simpA.combos}
	sbComboNames = {sb.name: sb for sb in simpB.combos}
	saComboNameUnique = saComboNames.viewkeys() - sbComboNames.viewkeys()
	sbComboNameUnique = sbComboNames.viewkeys() - saComboNames.viewkeys()
	# TODO search for combos with mis-ordered inputs
	cnMatch = {}
	for can in saComboNameUnique:
		cnMatch[can] = (can, None)
	for cbn in sbComboNameUnique:
		cnMatch[cbn] = (None, cbn)
	mmDict['combo'] = cnMatch

	saTravNames = {sa.name: sa for sa in simpA.traversals}
	sbTravNames = {sb.name: sb for sb in simpB.traversals}
	saTravNameUnique = saTravNames.viewkeys() - sbTravNames.viewkeys()
	sbTravNameUnique = sbTravNames.viewkeys() - saTravNames.viewkeys()
	# TODO search for travs with mis-ordered inputs
	tnMatch = {}
	for tan in saTravNameUnique:
		tnMatch[tan] = (tan, None)
	for tbn in sbTravNameUnique:
		tnMatch[tbn] = (None, tbn)
	mmDict['traversal'] = tnMatch

	return mmDict
	

def orderedMerge(va, vb):
	# come up with a better way that keeps some of the input structure
	return sorted(set(va) | set(vb))


# Falloffs
def mergeFalloffs(simpA, simpB, outSimp, translation, nameOnly=True):
	if not nameOnly:
		raise ValueError("Not implemented yet")
	aNames = [f.name for f in simpA.falloffs]
	aDict = dict(zip(aNames, simpA.falloffs))
	bNames = [f.name for f in simpB.falloffs]
	bDict = dict(zip(bNames, simpB.falloffs))
	oNames = orderedMerge(aNames, bNames)
	for oName in oNames:
		baseFo = aDict.get(oName, bDict[oName])
		if baseFo.splitType == 'planar':
			data = (
				baseFo.splitType, baseFo.axis, baseFo.maxVal,
				baseFo.maxHandle, baseFo.minHandle, baseFo.minVal
			)
		else:
			data = (baseFo.splitType, baseFo.mapName)
		fo = Falloff(oName, outSimp, *data)
		translation[aDict.get(oName)] = fo
		translation[bDict.get(oName)] = fo


# Groups
def _mergeGroupSubset(aTypedGroups, bTypedGroups, outSimp, gType, translation):
	asG = [g.name for g in aTypedGroups]
	bsG = [g.name for g in bTypedGroups]
	asGDict = dict(zip(asG, aTypedGroups))
	bsGDict = dict(zip(bsG, bTypedGroups))
	osG = orderedMerge(asG, bsG)
	for groupName in osG:
		newGroup = Group(groupName, outSimp, gType)
		translation[asGDict.get(groupName)] = newGroup
		translation[bsGDict.get(groupName)] = newGroup

def mergeGroups(simpA, simpB, outSimp, translation):
	_mergeGroupSubset(simpA.sliderGroups, simpB.sliderGroups, outSimp, Slider, translation) 
	_mergeGroupSubset(simpA.comboGroups, simpB.comboGroups, outSimp, Combo, translation)
	_mergeGroupSubset(simpA.traversalGroups, simpB.traversalGroups, outSimp, Traversal, translation)



# Shapes
def _blendShape(aShape, bShape, outSimp, blendVal, translation):
	if aShape in translation or bShape in translation:
		return translation.get(aShape, translation[bShape])

	newShape = Shape(aShape.name, outSimp, create=True)

	aDeltas = aShape.verts - aShape.simplex.restShape.verts
	bDeltas = bShape.verts - bShape.simplex.restShape.verts
	deltas = aDeltas*(1.0 - blendVal) + bDeltas*blendVal
	newShape.verts = outSimp.restShape.verts + deltas

	translation[aShape] = newShape
	translation[bShape] = newShape
	return newShape

def _copyShape(shape, outSimp, translation, deltaOverride=None):
	if shape in translation:
		return translation[shape]
	newShape = Shape(shape.name, outSimp, create=True)

	if deltaOverride is None:
		deltas = shape.verts - shape.simplex.restShape.verts
		newShape.verts = outSimp.restShape.verts + deltas
	else:
		newShape.verts = deltaOverride

	translation[shape] = newShape
	return newShape




# Progs
def _deltaProg(shape, srcMin, srcMax, tarMin, tarMax, tVal):
	srcExtDelta = tVal * (srcMax.verts - srcMin.verts)
	srcShpDelta = shape.verts - srcMin.verts
	srcOffset = srcShpDelta - srcExtDelta
	ret = tVal*(tarMax.verts - tarMin.verts) + srcOffset
	return ret

def _blendProg(aProg, bProg, outSimp, blendVal, translation):
	''' Progressions don't necessarily have the same number of shapes, or the same ranges
	So we try to be smart here.
	Any shapes with the same value are blended by blendVal
	Any extreme values (-1, or 1) are copied over
	Any progressive values are copied as deltas off the extreme
	'''
	aVals = [float(pp.value) for pp in aProg.pairs]
	bVals = [float(pp.value) for pp in bProg.pairs]
	commonVals = sorted(set(aVals) & set(bVals))
	aUniq = set(aVals) - set(commonVals)
	bUniq = set(bVals) - set(commonVals)
	aValDict = dict(zip(aVals, aProg.pairs))
	bValDict = dict(zip(bVals, bProg.pairs))

	# First handle all the common values
	outValDict = {}
	for c in commonVals:
		newShape = _blendShape(aValDict[c].shape, bValDict[c].shape, outSimp, blendVal, translation)
		outValDict[c] = newShape

	# Then handle any unique extremes
	if 1.0 in aUniq:
		outValDict[1.0] = _copyShape(aValDict[1.0].shape, outSimp, translation)
	if -1.0 in aUniq:
		outValDict[-1.0] = _copyShape(aValDict[-1.0].shape, outSimp, translation)
	if 1.0 in bUniq:
		outValDict[1.0] = _copyShape(bValDict[1.0].shape, outSimp, translation)
	if -1.0 in bUniq:
		outValDict[-1.0] = _copyShape(bValDict[-1.0].shape, outSimp, translation)

	# Finally handle the unique progressions as deltas off the extremes
	outRest = outValDict[0.0]
	aRest = aValDict[0.0].shape
	for c in aUniq:
		aShp = aValDict[c].shape
		mm = 1.0 if c > 0.0 else -1.0
		dd =_deltaProg(aShp, aRest, aValDict[mm].shape, outRest, outValDict[mm], mm * c)
		outValDict[c] = _copyShape(aShp, outSimp, translation, deltaOverride=dd)

	bRest = bValDict[0.0].shape
	for c in bUniq:
		bShp = bValDict[c].shape
		mm = 1.0 if c > 0.0 else -1.0
		dd =_deltaProg(bShp, bRest, bValDict[mm].shape, outRest, outValDict[mm], mm * c)
		outValDict[c] = _copyShape(bShp, outSimp, translation, deltaOverride=dd)

	outPairs = [ProgPair(outSimp, outValDict[val], val) for val in sorted(outValDict.keys())]
	prog = Progression(aProg.name, outSimp, pairs=outPairs, interp=aProg.interp)
	translation[aProg] = prog
	translation[bProg] = prog
	return prog

def _copyProg(prog, outSimp, translation):
	pairs = []
	for pp in prog.pairs:
		newShape = _copyShape(pp.shape, outSimp, translation)
		pair = ProgPair(outSimp, newShape, pp.value)
		pairs.append(pair)
	outProg = Progression(prog.name, outSimp, pairs=pairs, interp=prog.interp)
	translation[prog] = outProg
	return outProg



# Sliders
def _blendSliders(aSlider, bSlider, outSimp, blendVal, translation):
	if aSlider in translation or bSlider in translation:
		return translation.get(aSlider, translation[bSlider])
		
	group = translation.get(aSlider.group, translation[bSlider.group])
	prog = _blendProg(aSlider.prog, bSlider.prog, outSimp, blendVal, translation)
	outSlider = Slider(aSlider.name, outSimp, prog, group)
	translation[aSlider] = outSlider
	translation[bSlider] = outSlider
	return outSlider

def _copySlider(slider, outSimp, translation):
	if slider in translation:
		return translation[slider]

	group = translation[slider.group]
	prog = _copyProg(slider.prog, outSimp, translation)
	outSlider = Slider(slider.name, outSimp, prog, group)
	translation[slider] = outSlider
	return outSlider
	
def sliderBlend(simpA, simpB, outSimp, blendVal, translation, mismatch):
	aNames = [s.name for s in simpA.sliders]
	aDict = dict(zip(aNames, simpA.sliders))
	bNames = [s.name for s in simpB.sliders]
	bDict = dict(zip(bNames, simpB.sliders))
	oNames = orderedMerge(aNames, bNames)

	for oIdx, oName in enumerate(oNames):
		print "Copying Slider {0} of {1}: {2}".format(oIdx, len(oNames), oName)
		aName, bName = mismatch['slider'].get(oName, (oName, oName))
		if aName is Skip or bName is Skip:
			continue
		elif aName is None:
			_copySlider(bDict[bName], outSimp, translation)
		elif bName is None:
			_copySlider(aDict[aName], outSimp, translation)
		else:
			_blendSliders(aDict[aName], bDict[bName], outSimp, blendVal, translation)



# Combos
def _blendCombos(aCombo, bCombo, outSimp, blendVal, translation):
	if aCombo in translation or bCombo in translation:
		return translation.get(aCombo, translation[bCombo])

	group = translation.get(aCombo.group, translation[bCombo.group])

	cPairs = []
	for aPair, bPair in zip(aCombo.pairs, bCombo.pairs):
		slider = _blendSliders(aPair.slider, bPair.slider, outSimp, blendVal, translation)
		cPairs.append(ComboPair(slider, aPair.value))
	
	prog = _blendProg(aCombo.prog, bCombo.prog, outSimp, blendVal, translation)
	outCombo = Combo(aCombo.name, outSimp, cPairs, prog, group, aCombo.solveType)
	translation[aCombo] = outCombo
	translation[bCombo] = outCombo
	return outCombo

def _copyCombo(combo, outSimp, translation):
	if combo in translation:
		return translation[combo]
	group = translation[combo.group]

	cPairs = []
	for pair in combo.pairs:
		slider = _copySlider(pair.slider, outSimp, translation)
		cPairs.append(ComboPair(slider, pair.value))
	prog = _copyProg(combo.prog, outSimp, translation)
	
	outCombo = Combo(combo.name, outSimp, cPairs, prog, group, combo.solveType)
	translation[combo] = outCombo
	return outCombo

def comboBlend(simpA, simpB, outSimp, blendVal, translation, mismatch):
	aNames = [s.name for s in simpA.combos]
	aDict = dict(zip(aNames, simpA.combos))
	bNames = [s.name for s in simpB.combos]
	bDict = dict(zip(bNames, simpB.combos))
	oNames = orderedMerge(aNames, bNames)

	for oIdx, oName in enumerate(oNames):
		print "Copying Combo {0} of {1}: {2}".format(oIdx, len(oNames), oName)
		aName, bName = mismatch['combo'].get(oName, (oName, oName))

		if oName in mismatch:
			print "Getting", oName
			print "Mismatch Get", oName in mismatch, aName, bName

		if aName is Skip or bName is Skip:
			continue
		elif aName is None:
			_copyCombo(bDict[bName], outSimp, translation)
		elif bName is None:
			_copyCombo(aDict[aName], outSimp, translation)
		else:
			_blendCombos(aDict[aName], bDict[bName], outSimp, blendVal, translation)



# Traversals
def _blendController(aItem, bItem, outSimp, blendVal, translation):
	aCtrl = aItem.controller
	bCtrl = bItem.controller

	if isinstance(aCtrl, Slider):
		ctrl = _blendSliders(aCtrl, bCtrl, outSimp, blendVal, translation)
	elif isinstance(aCtrl, Combo):
		ctrl = _blendCombos(aCtrl, bCtrl, outSimp, blendVal, translation)
	else:
		raise ValueError("Bad object type: {0} {1}".format(aCtrl, type(aCtrl)))
	return TravPair(ctrl, aItem.value, aItem.usage)

def _copyController(item, outSimp, translation):
	iCtrl = item.controller
	if isinstance(iCtrl, Slider):
		ctrl = _copySlider(iCtrl, outSimp, translation)
	elif isinstance(iCtrl, Combo):
		ctrl = _copyCombo(iCtrl, outSimp, translation)
	else:
		raise ValueError("Bad object type: {0} {1}".format(iCtrl, type(iCtrl)))
	return TravPair(ctrl, item.value, item.usage)


def _blendTraversals(aTrav, bTrav, outSimp, blendVal, translation):
	group = translation.get(aTrav.group, translation[bTrav.group])
	multCtrl = _blendController(aTrav.multiplierCtrl, bTrav.multiplierCtrl, outSimp, blendVal, translation)
	progCtrl = _blendController(aTrav.progressCtrl, bTrav.progressCtrl, outSimp, blendVal, translation)
	prog = _blendProg(aTrav.prog, bTrav.prog, outSimp, blendVal, translation)
	outTrav = Traversal(aTrav.name, outSimp, multCtrl, progCtrl, prog, group)
	translation[aTrav] = outTrav
	translation[bTrav] = outTrav
	return outTrav

def _copyTraversal(traversal, outSimp, translation):
	group = translation[traversal.group]
	multCtrl = _copyController(traversal.multiplierCtrl, outSimp, translation)
	progCtrl = _copyController(traversal.progressCtrl, outSimp, translation)
	prog = _copyProg(traversal.prog, outSimp, translation)
	outTrav = Traversal(traversal.name, outSimp, multCtrl, progCtrl, prog, group)
	translation[traversal] = outTrav
	return outTrav

def traversalBlend(simpA, simpB, outSimp, blendVal, translation, mismatch):
	aNames = [s.name for s in simpA.traversals]
	aDict = dict(zip(aNames, simpA.traversals))
	bNames = [s.name for s in simpB.traversals]
	bDict = dict(zip(bNames, simpB.traversals))
	oNames = orderedMerge(aNames, bNames)

	for oIdx, oName in enumerate(oNames):
		print "Copying Traversal {0} of {1}: {2}".format(oIdx, len(oNames), oName)
		aName, bName = mismatch['traversal'].get(oName, (oName, oName))
		if aName is Skip or bName is Skip:
			continue
		elif aName is None:
			_copyTraversal(bDict[bName], outSimp, translation)
		elif bName is None:
			_copyTraversal(aDict[aName], outSimp, translation)
		else:
			_blendTraversals(aDict[aName], bDict[bName], outSimp, blendVal, translation)



# Simplex
def smpxBlend(simpA, simpB, blendVal=0.50, mismatchDict=None, name='Face'):
	'''
	Blend the deltas from simplexA and simplexB. Apply the output to simplexA
	Equal falloffs will be combined. Others will be given suffixes
	'''
	mismatchDict = mismatchDict or {}
	simpA.stack.enabled = False
	simpB.stack.enabled = False

	outSimp = Simplex(name=name, forceDummy=True)
	outSimp.stack.enabled = False

	dcc = outSimp.DCC
	dcc._faces = simpA.DCC._faces
	dcc._counts = simpA.DCC._counts
	dcc._uvs = simpA.DCC._uvs
	dcc._falloffs = simpA.DCC._falloffs
	dcc._numVerts = simpA.DCC._numVerts

	rest = Shape.buildRest(outSimp)
	rest.verts = simpA.restShape.verts*(1-blendVal) + simpB.restShape.verts*blendVal

	outSimp.restShape = rest

	# When walking through this smpx file, keep a "translation" dictionary 
	# where translation[InputObjectID] = OutputObject
	translation = {}
	translation[simpA.restShape] = rest
	translation[simpB.restShape] = rest

	# Merge the groups. This one is easy. Merge by name
	mergeGroups(simpA, simpB, outSimp, translation)
	
	# Merge the falloffs. We can either require them to have equal values to "merge"
	# Or we can just merge by name. The nameOnly kwarg handles this. True for now
	mergeFalloffs(simpA, simpB, outSimp, translation, nameOnly=True)

	# Copying one of the "big" object types should create and blend its child prog and shapes
	print "Copying Sliders"
	sliderBlend(simpA, simpB, outSimp, blendVal, translation, mismatchDict)
	print "Copying Combos"
	comboBlend(simpA, simpB, outSimp, blendVal, translation, mismatchDict)
	print "Copying Traversals"
	traversalBlend(simpA, simpB, outSimp, blendVal, translation, mismatchDict)

	# push the verts to the dummy dcc for later export
	dcc.pushAllShapeVertices(outSimp.shapes)
	return outSimp


if __name__ == "__main__":
	pathA = r'D:\Users\tyler\Desktop\TEST\GumboA.smpx'
	pathB = r'D:\Users\tyler\Desktop\TEST\GumboB.smpx'
	outPath = r'D:\Users\tyler\Desktop\TEST\hoping2.smpx'

	print "Loading SimpA"
	simpA = Simplex.buildSystemFromSmpx(pathA, forceDummy=True)
	print "Loading SimpB"
	simpB = Simplex.buildSystemFromSmpx(pathB, forceDummy=True)

	print "Matching A:B"
	mismatch = smpxMismatchCheck(simpA, simpB)
	outSmpx = smpxBlend(simpA, simpB, blendVal=0.5, mismatchDict=mismatch)
	
	print "Exporting"
	print "OUT SMPX", outSmpx
	outSmpx.exportAbc(outPath)


	print "DONE"


