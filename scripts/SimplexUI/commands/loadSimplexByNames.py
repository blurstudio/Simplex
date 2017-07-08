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

import maya.cmds as cmds
from Simplex2.interface import (Shape, Group, Falloff, ProgPair, Progression,
								Slider, ComboPair, Combo, Simplex)

def lowerCase(item):
	return item[0].lower() + item[1:]

def getNodes(thing):
	# find/build the shapeNode
	history = cmds.listHistory(thing) or []
	shapeNodes = [h for h in history if cmds.nodeType(h) == "blendShape"]

	if not shapeNodes:
		raise RuntimeError("Couldn't find a blendshape already connected")

	shapeNode = shapeNodes[0]

	# find/build the operator
	ops = cmds.listConnections("{0}.{1}".format(shapeNode, "message"), source=False, destination=True, type="simplex_maya") or []
	if not ops:
		raise RuntimeError("Couldn't find a simplex node already connected")
	op = ops[0]

	# find/build the ctrl object
	ctrlCnx = cmds.listConnections("{0}.{1}".format(op, "ctrlMsg"), source=True, destination=False) or []

	if not ops:
		raise RuntimeError("Couldn't find a control object already connected")
	ctrl = ctrlCnx[0]

	return ctrl, op, shapeNode

def getShapeNames(bs):
	cnx = cmds.listConnections(bs, plugs=True, connections=True, destination=False)
	cnxPairs = zip(cnx[1::2], cnx[::2])
	
	odict = {}
	for weight, shape in cnxPairs:
		sp = weight.split('weights')	
		if len(sp) == 1:
			continue
		key = int(sp[1].strip('[]'))
		name = shape.split('.')[1]
		odict[key] = name
	return [i for _, i in sorted(odict.items())]

def getSliderNames(ctrlObject):
	cnx = cmds.listConnections(ctrlObject, plugs=True, connections=True, source=False)
	cnxPairs = zip(cnx[1::2], cnx[::2])
	
	odict = {}
	for slider, ctrl in cnxPairs:
		sp = slider.split('sliders')	
		if len(sp) == 1:
			continue
		key = int(sp[1].strip('[]'))
		name = ctrl.split('.')[1]
		odict[key] = name
	return [i for _, i in sorted(odict.items())]

def matchShapes(sliderNames, shapeNames):
	# get the direct connections
	sliderNames = set(sliderNames)
	shapeNames = set(shapeNames)

	direct = sliderNames & shapeNames
	sliderNames = sliderNames - direct
	shapeNames = shapeNames - direct

	opposingPairs = [
		('Left', 'Right'),
		('Up', 'Down'),
		('In', 'Out'),
		('Back', 'Fwd'),
		('Wide', 'Narrow'),
		('Suck', 'Flare'),
		('Suck', 'Blow'),
	]
	matches = {}

	for slider in sliderNames:
		for pair in opposingPairs:
			starts = False
			orders = (pair[0] + pair[1], pair[1] + pair[0])
			if orders[0].lower() in slider.lower():
				if slider.lower().startswith(orders[0].lower()):
					starts = True
				order = orders[0]
			elif orders[1].lower() in slider.lower():
				if slider.lower().startswith(orders[1].lower()):
					starts = True
				order = orders[1]
			else:
				continue

			pRep0 = pair[0]
			pRep1 = pair[1]
			if starts:
				order = lowerCase(order)
				pRep0 = lowerCase(pair[0])
				pRep1 = lowerCase(pair[1])

			rep0 = slider.replace(order, pRep0)
			rep1 = slider.replace(order, pRep1)


			if rep0 not in shapeNames:
				print "Oops, {0} not found".format(rep0)
			if rep1 not in shapeNames:
				print "Oops, {0} not found".format(rep1)

			shapeNames.remove(rep0)
			shapeNames.remove(rep1)

			matches[slider] = (rep0, rep1)
			continue

	sliderNames = sliderNames - set(matches.keys())

	rest = None
	if len(shapeNames) == 1:
		rest = shapeNames.pop()

	for d in direct:
		matches[d] = (d,)

	return matches, rest

def buildSimplexByNames():
	sel = cmds.ls(selection=True)
	if not sel:
		return

	ctrl, op, bs = getNodes(sel[0])
	sliderNames = getSliderNames(ctrl)
	shapeNames = getShapeNames(bs)
	matches, restName = matchShapes(sliderNames, shapeNames)

	simp = Simplex(name=op)
	shapeDict = {}

	# build the shape objects
	for shapeName in shapeNames:
		shp = Shape(shapeName, simp)
		shapeDict[shapeName] = shp
		simp.shapes.append(shp)

	# properly set the rest object
	restShape = shapeDict[restName]
	restShape.isRest = True
	simp.restShape = restShape

	g = Group('ALL')
	simp.groups.append(g)
	for sliderName in sliderNames:
		progNames = list(matches[sliderName])
		if len(progNames) == 1:
			progNames.insert(0, restName)
			progValues = (0.0, 1.0)
		elif len(progNames) == 2:
			progNames.insert(1, restName)
			progValues = (-1.0, 0.0, 1.0)
		else:
			continue # Not handling the more complicated cases yet
		
		ppairs = [ProgPair(shapeDict[s], v) for s, v in zip(progNames, progValues)]
		prog = Progression(sliderName, ppairs)

		sld = Slider(sliderName, prog, g)
		simp.sliders.append(sld)

	# set the json value
	val = simp.dump()
	cmds.setAttr(op+".definition", val, type="string")

	# return the simplex structure
	return simp

simp = buildSimplexByNames()


