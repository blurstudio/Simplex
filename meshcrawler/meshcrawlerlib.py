#pylint:disable=missing-docstring
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

----------------------------------------------------------------------------

Meshcrawler is an awesome library that allows you to build a 1:1 topology match
between two meshes that don't have the same vertex order.

This is done (in most cases) *without* specifying any matching vertex points.
It uses some relatively simple heuristics to accomplish this, and they are
explained in the docstrings below.

The actual matching is done in matchByTopology()
The heuristic pruning is done in findPossiblePairsByValenceSteps()
And the Island/Shell matching is done using the Munkres module
'''

import blurdev
import sys, copy

###################################################
###					Errors						###
###################################################

class Mismatch(Exception):
	''' Base class for my mismatch exceptions '''
	pass

class IslandMismatch(Mismatch):
	''' Raised if there are different numbers of islands '''
	pass

class TopologyMismatch(Mismatch):
	''' Raised if the topology doesn't match for an island '''
	pass


###################################################
###				  Approximation 				###
###################################################

def unscrambleMeshByDistance(clean, dirty):
	cleanVerts = clean.vertArray
	dirtyVerts = dirty.vertArray
	return unscrambleByDistance(cleanVerts, dirtyVerts)

def unscrambleByDistance(cleanVerts, dirtyVerts):
	'''
	Given two meshes whose vertices are generally close to one another,
	find a 1:1 mapping where the distances between the mappings are
	minimized.
	This uses the Munkres (aka Hungarian) algorithm and it will *not* map
	more than one vertex to any other

	This is an O(n**3) algorithm, so this is gonna be SLOW for big meshes

	'''
	from scipy.optimize import linear_sum_assignment
	from scipy.spatial.distance import cdist

	dist = cdist(cleanVerts, dirtyVerts)
	idxs = linear_sum_assignment(dist)
	# The clean index will be sorted
	return sorted(zip(*idxs))

def unscrambleByDistance_Pure(cleanVerts, dirtyVerts):
	# use the pure python implementation
	# because scipy isn't easy to get for Maya :(
	from munkres import Munkres
	m = Munkres()
	costs = buildCosts(cleanVerts, dirtyVerts)
	indexes = m.compute(costs)
	return sorted(indexes)

def buildCosts(orderCenters, shapeCenters):
	# Builds a preference list based on the distance
	# between bounding box centers
	squaredDistances = []
	for oC in orderCenters:
		row = []
		for sC in shapeCenters:
			row.append(sum((i-j)**2 for i, j in zip(oC, sC)))
		squaredDistances.append(row)
	return squaredDistances

###################################################
###				  Match Point Order				###
###################################################

def flipMultiDict(e, f):
	""" Make a dict keyed off the values of two dicts

	Args:
		e,f: Two dictionaries with hashable values

	Returns:
		A dictionary in this form: (eValueSet,fValueSet):key
	"""
	inv = {}
	allkeys = set(e.keys()) | set(f.keys())
	for k in allkeys:
		eVal = frozenset(e.get(k, ()))
		fVal = frozenset(f.get(k, ()))
		inv.setdefault((eVal, fVal), []).append(k)
	return inv

def growTracked(mesh, growSet, allSet):
	""" Grow a set of verts along edges and faces

	This function takes a set of vertices and returns two
	dicts. One that is vert:(edgeAdjVerts..), and another
	that is vert:(faceAdjVerts..)

	While I'm growing a vert, if all vertices adjacent to
	that vert are matched, then I no longer need to grow
	from there.

	Args:
		growSet: A set of Vertex objects to grow. This set
			will have all useless verts removed and will be
			changed in-place.
		allSet: A set of Vertex objects to exclude from
			the growth

	Returns:
		edgeDict: A dictionary with verts as keys and all
			edge adjacent vertices as the value
		faceDict: A dictionary with verts as keys and all
			face adjacent vertices as the value
		newGrowSet: The original growSet with all used-up
			vertices removed
	"""
	edgeDict = {}
	faceDict = {}
	# Verts that are grown, but have no adjacent verts
	# that aren't in the allSet
	rem = []
	for vert in growSet:
		edgeFound = False
		faceFound = False
		for eadj in mesh.adjacentVertsByEdge(vert):
			if eadj not in allSet:
				edgeFound = True
				edgeDict.setdefault(eadj, []).append(vert)

		for fadj in mesh.adjacentVertsByFace(vert):
			if fadj not in allSet:
				faceFound = True
				faceDict.setdefault(fadj, []).append(vert)

		if not edgeFound and not faceFound:
			rem.append(vert)

	newGrowSet = growSet - set(rem)
	return edgeDict, faceDict, newGrowSet

def matchByTopology(lhsMesh, rhsMesh, vertexPairs, vertNum=None, symmetry=False, pBar=None):
	""" Match the topology of two meshes with different vert orders

	Provide a 1:1 vertex index match between two meshes that don't
	necessarily have the same vertex order.
	At minimum, 3 vertex pairs around a single poly are required.

	The algorithm simultaneously performs two different types of
	"grow verts" operations on each mesh and each vertex keeps track
	of where it was grown from, and how.
	New matching verts will be grown from known matching verts in the
	same way.

	Example:
	Starting with two meshes and a "matched" vertex selection on two meshes
	I'm calling M1 and M2

	Say:
	v6 on M1 is an edge away from (v3 ,v5) and a face away from (v3 ,v5,v4)
	v9 on M2 is an edge away from (v13,v2) and a face away from (v13,v2,v6)
	And we know going in that: M1.v3=M2.v13, M1.v5=M2.v2, M1.v4=M2.v6

	Then we can say M1.v6=M2.v9 becaue if we substitute all of our known
	matches, we can see that the two vertices are equivalent

	Args:
		M1: A Mesh object
		M2: A second Mesh object
		vertPairs: A List of 2-Tuples of vertex indices
			that are known matches
		vertNum: The total number of vertices in the mesh, for
			percentageDone purposes. Default: None
		symmetry: Boolean value indicating whether the vertPairs
			are mirrored indices on the same mesh. Default: False

	Returns:
		A list of (Vertex,Vertex) pairs that define 1:1 matches

	"""
	# The meshes are generally specified as "lefthandSide"(lhs)
	# and "righthandSide"(rhs) through this code
	lhsVerts, rhsVerts = zip(*vertexPairs)
	lhsVertsGrow = set(lhsVerts)
	rhsVertsGrow = set(rhsVerts)
	lhsVerts = set(lhsVerts)
	rhsVerts = set(rhsVerts)
	centerVerts = set()

	lhsTorhs = {s:t for s, t in vertexPairs}

	if vertNum is not None:
		vertNum = float(vertNum) #just for percentage reporting
		if symmetry:
			vertNum /= 2

	updated = True
	#counter = 0
	while updated:
		updated = False
		if vertNum is not None:
			percent = len(lhsVerts) / vertNum * 100
			if pBar is None:
				print "Percentage processed: {0:.2f}%\r".format(percent),
			else:
				pBar.setValue(int(percent))
		# Grow the vert selection along edges and save as a set
		# Grow the vert selection along faces and save as another set
		# Remove already selected verts from both lists
		#
		# The dicts are structured like this:
		#	 {vertex: (lhsVertTuple), ...}

		if symmetry:
			# A fun little hack that allows me to treat the left and
			# right hand sides of a model with symmetrical topology as
			# two different meshes to match
			allSet = lhsVerts|rhsVerts|centerVerts
			lAllSet = allSet
			rAllSet = allSet
		else:
			lAllSet = lhsVerts
			rAllSet = rhsVerts

		lhsEdgeDict, lhsFaceDict, lhsVertsGrow = growTracked(lhsMesh, lhsVertsGrow, lAllSet)
		rhsEdgeDict, rhsFaceDict, rhsVertsGrow = growTracked(rhsMesh, rhsVertsGrow, rAllSet)

		# if a key has a *unique* (face & edge) value
		# we can match it to the rhs
		#
		# so flip the dicts and key off of *BOTH* values
		# simultaneously
		lhsEFDict = flipMultiDict(lhsEdgeDict, lhsFaceDict)
		rhsEFDict = flipMultiDict(rhsEdgeDict, rhsFaceDict)

		# Then, if the swapped dict's value only has 1 item
		# it is a uniquely identified vertex and can be matched
		for lhsKey, lhsValue in lhsEFDict.iteritems():
			if len(lhsValue) == 1:
				edgeKey = frozenset(lhsTorhs[i] for i in lhsKey[0])
				faceKey = frozenset(lhsTorhs[i] for i in lhsKey[1])

				try:
					rhsValue = rhsEFDict[(edgeKey, faceKey)]
				except KeyError:
					area = list(edgeKey) + list(faceKey)
					area = [i.index for i in area]
					area = list(set(area))
					vp = [(i.index, j.index) for i, j in vertexPairs]
					iidx, jidx = zip(*vp)
					m = 'Order {0} to Shape {1}: Match produced no results: Check this order area {2}'.format(iidx, jidx, area)
					print m
					raise TopologyMismatch(m)

				if len(rhsValue) != 1:
					raise TopologyMismatch('Match produced multiple results')

				lhsVert = lhsValue[0]
				rhsVert = rhsValue[0]
				if (rhsVert == lhsVert) and symmetry:
					centerVerts.add(rhsVert)
				else:
					lhsTorhs[lhsVert] = rhsVert
					lhsVerts.add(lhsVert)
					lhsVertsGrow.add(lhsVert)
					rhsVerts.add(rhsVert)
					rhsVertsGrow.add(rhsVert)

				#pair = (lhsVert, rhsVert)
				updated = True

	if vertNum is not None:
		if pBar is None:
			print #clear the percentage value

	#if vertNum is not None:
		#print "\n"
	return [(k, v) for k, v in lhsTorhs.iteritems()]

###################################################
###			 Find pairs from positions			###
###################################################

def _getMinListSizeKey(d):
	lenDict = {}
	for k, v in d.iteritems():
		lenDict.setdefault(len(v), set()).add(k)
	minLen = min(lenDict.iterkeys())
	return lenDict[minLen]

def _getValenceDict(mesh):
	meshValence = {}
	for vert in xrange(len(mesh.vertArray)):
		valence = len(mesh.vertNeighbors[vert])
		meshValence.setdefault(valence, []).append(vert)
	return meshValence

def _getMinValencePoints(order, shape, orderVerts, shapeVerts):
	# get the smallest group of common valence points
	orderValence = _getValenceDict(order)
	shapeValence = _getValenceDict(shape)

	if len(orderValence) != len(shapeValence):
		ovk = set(orderValence.keys())
		svk = set(shapeValence.keys())
		oCheck = []
		sCheck = []
		for key in ovk - svk:
			oCheck.extend(orderValence[key])
		for key in svk - ovk:
			sCheck.extend(shapeValence[key])

		print "Raising Topo Mismatch", oCheck, sCheck
		raise TopologyMismatch("Valence Points Mismatch. Check Order Here {0}, and Shape Here {1}".format(oCheck, sCheck))
	else:
		for key in orderValence:
			if len(orderValence[key]) != len(shapeValence[key]):
				if len(orderValence[key]) < 10 and len(shapeValence[key]) < 10:
					oCheck = [i.index for i in orderValence[key]]
					sCheck = [i.index for i in shapeValence[key]]
					raise TopologyMismatch("Valence Points Mismatch. Check Order Here {0}, and Shape Here {1}".format(oCheck, sCheck))
				else:
					raise TopologyMismatch("Valence Points Mismatch. Too many to be useful")

	minValence = _getMinListSizeKey(orderValence)
	minValence = minValence.pop()

	orderPoints = orderValence[minValence]
	shapePoints = shapeValence[minValence]

	return minValence, orderPoints, shapePoints

def _getNearestGrow(mesh, points, valence):
	# make sure only to run this if there's more than 1 point
	growLength = {} # steps:[vertList]
	for point in points:
		grown = set([point])
		exclude = set()
		steps = 0
		found = False
		while not found and len(grown) > 0:
			grown, exclude = _growByEdge(mesh, grown, exclude)
			steps += 1
			for g in grown:
				if len(mesh.adjacentVertsByEdge(g)) == valence:
					growLength.setdefault(steps, []).append(point)
					found = True
					break
		if not found:
			raise TopologyMismatch("Could not find any other valence points")
	return growLength

def _growByEdge(mesh, growSet, exclude):
	""" Grow a set of verts along edges without any fanciness
	Args:
		mesh: The mesh object for the growth
		growSet: A set of Vertex objects to grow.
		exclude: A set of Vertex objects to exclude from
			the growth

	Returns:
		newGrowSet: the grown verts
		newExclude: the next set of verts to exclude
	"""
	grown = set()
	for vert in growSet:
		grown.update(mesh.adjacentVertsByEdge(vert))

	newgrown = grown - exclude
	newexclude = exclude | growSet

	return newgrown, newexclude

def _growByFace(mesh, growSet, exclude):
	""" Grow a set of verts along edges without any fanciness
	Args:
		mesh: The mesh object for the growth
		growSet: A set of Vertex objects to grow.
		exclude: A set of Vertex objects to exclude from
			the growth

	Returns:
		newGrowSet: the grown verts
		newExclude: the next set of verts to exclude
	"""

	grown = set()
	for vert in growSet:
		grown.update(mesh.adjacentVertsByFace(vert))

	newgrown = grown - exclude
	newexclude = exclude | growSet

	return newgrown, newexclude

def matchPossiblePairs(order, shape, orderMatches, shapeMatches, status=None, pBar=None):
	vertNum = min(len(order.vertArray), len(shape.vertArray))

	# There should be an equal number of order and shape matches
	# Build a distance-weighted pairing to minimize
	# the chance of flipping symmetrical meshes

	if len(shapeMatches) < 30:
		orderPoints = [order.vertArray[i] for i in orderMatches]
		shapePoints = [shape.vertArray[i] for i in shapeMatches]
		pairs = unscrambleByDistance_Pure(orderPoints, shapePoints)
		orderIdxs, shapeIdxs = zip(*pairs)
	else:
		orderIdxs = range(len(orderMatches))
		shapeIdxs = range(len(shapeMatches))

	for orderIdx in orderIdxs:
		orderPoint = orderMatches[orderIdx]
		orderVerts = order.adjacentVertsByEdge(orderPoint) + [orderPoint]

		for shapeIdx in shapeIdxs:
			shapePoint = shapeMatches[shapeIdx]
			shapeStar = shape.adjacentVertsByEdge(shapePoint)
			for i in range(len(shapeStar)):
				shapeVerts = shapeStar[i:] + shapeStar[:i] + [shapePoint]

				try:
					match = matchByTopology(order, shape,
								zip(orderVerts, shapeVerts),
								vertNum=vertNum, pBar=pBar)
				except TopologyMismatch:
					continue
				else:
					return match

	return []

def findPossiblePairsByValenceSteps(order, shape, orderVerts, shapeVerts):
	"""
	Makes a list of the vertices that have a specific valence
		(specifically, the valence with the lowest number of verts)
	Then matches the vertices by finding the "grow distance" to the
	closest vertex of the same valence.
	Example:
		There are 54 valence 3 vertices
		There are 13112 valence 4 vertices
		There are 28 valence 5 vertices
		So we use valence 5 vertices

		On the orderMesh, loop through the valence 5 vertices
		Pt 324 is 6 growIterations away from another valence 5 vertex
		Pt 10545 is 6 growIterations away from another valence 5 vertex
		Pt 1484 is 5 growIterations away from another valence 5 vertex
		... and so on

		On the shapeMesh, loop through the valence 5 vertices
		Pt 575 is 6 growIterations away from another valence 5 vertex
		Pt 12245 is 6 growIterations away from another valence 5 vertex
		Pt 3177 is 5 growIterations away from another valence 5 vertex
		... and so on

		There is only one that has a minimum of 5 grows to another
		valence 5 vertex, therefore
		orderMesh.vertices[1484] pairs with shapeMesh.vertices[3177]
		I should be OK if I find a group of 5 or fewer
	"""
	try:
		valence, orderPoints, shapePoints = _getMinValencePoints(order, shape, orderVerts, shapeVerts)
	except KeyError:
		return [], []

	if len(orderPoints) == 1:
		return orderPoints, shapePoints

	orderSteps = _getNearestGrow(order, orderPoints, valence)
	shapeSteps = _getNearestGrow(shape, shapePoints, valence)

	orderMinKey = _getMinListSizeKey(orderSteps)
	shapeMinKey = _getMinListSizeKey(shapeSteps)

	common = orderMinKey & shapeMinKey
	if not common:
		return [], []
	minKey = common.pop()

	orderMatches = orderSteps[minKey]
	shapeMatches = shapeSteps[minKey]

	return orderMatches, shapeMatches

def _buildIslandVertSets(mesh):
	allverts = set(xrange(len(mesh.vertArray)))
	islands = []
	while allverts:
		seed = set([allverts.pop()])
		island = set()
		while seed:
			seed, island = _growByFace(mesh, seed, island)
		islands.append(island)
		allverts.difference_update(island)
	return islands

def matchIsland(orderMesh, shapeMesh, orderIsland, shapeIsland, status=None, pBar=None):
	orderPossible, shapePossible = findPossiblePairsByValenceSteps(orderMesh, shapeMesh, orderIsland, shapeIsland)

	if not orderPossible:
		print "Valence Steps Failed"
		return []
	match = matchPossiblePairs(orderMesh, shapeMesh, orderPossible, shapePossible, status, pBar)
	return match

def bbCenter(mesh, island):
	verts = [mesh.vertArray[i] for i in island]
	xAxis, yAxis, zAxis = zip(*verts)
	lC = (min(xAxis), min(yAxis), min(zAxis)) # lowerCorner
	uC = (max(xAxis), max(yAxis), max(zAxis)) # upperCorner
	center = [(i+j)/2.0 for i, j in zip(lC, uC)]
	return center

def makeIslandMarriages(orderMesh, shapeMesh, orderIslands, shapeIslands):
	if len(orderIslands) == 1:
		return [0]

	orderCenters = [bbCenter(orderMesh, i) for i in orderIslands]
	shapeCenters = [bbCenter(shapeMesh, i) for i in shapeIslands]
	unscrambled = unscrambleByDistance_Pure(orderCenters, shapeCenters)
	return [i[1] for i in unscrambled]

def getIslandFaceCount(mesh, island):
	faceSet = set()
	for v in island:
		faceSet.update(mesh.vertToFaces[v])
	return len(faceSet)

def matchIslands(orderMesh, shapeMesh, skipMismatchedIslands=True, status=None, pBar=None):
	if status is not None:
		status.setStatus("Partitioning Islands")
	orderIslandSets = _buildIslandVertSets(orderMesh)
	shapeIslandSets = _buildIslandVertSets(shapeMesh)

	orderIslandDict = {}
	for oi in orderIslandSets:
		pointCount = len(oi)
		faceCount = getIslandFaceCount(orderMesh, oi)
		orderIslandDict.setdefault((pointCount, faceCount), []).append(oi)

	shapeIslandDict = {}
	for si in shapeIslandSets:
		pointCount = len(si)
		faceCount = getIslandFaceCount(shapeMesh, si)
		shapeIslandDict.setdefault((pointCount, faceCount), []).append(si)

	allKeys = set(orderIslandDict.keys() + shapeIslandDict.keys())
	matches = []

	if (len(shapeIslandDict) == 1 and len(orderIslandDict) == 1 and
			len(shapeIslandDict.values()[0]) == 1 and len(orderIslandDict.values()[0]) == 1):

		oi = orderIslandDict.values()[0][0]
		si = shapeIslandDict.values()[0][0]
		match = matchIsland(orderMesh, shapeMesh, oi, si, status, pBar)
		if match:
			matches.append(match)
	else:
		islandIdx = 1
		for key in allKeys:
			try:
				oIslands = orderIslandDict[key]
			except KeyError:
				if skipMismatchedIslands:
					continue
				raise IslandMismatch('There are no islands on the order object with {0} vertices and {1} faces'.format(*key))

			try:
				sIslands = shapeIslandDict[key]
			except KeyError:
				if skipMismatchedIslands:
					continue
				raise IslandMismatch('There are no islands on the shape object with {0} vertices and {1} faces'.format(*key))

			shapeOrder = makeIslandMarriages(orderMesh, shapeMesh, oIslands, sIslands)
			used = [False] * len(shapeOrder)
			for oi in oIslands:
				if status is not None:
					status.setStatus("Matching Island {0}".format(islandIdx))
				islandIdx += 1
				for sIdx in shapeOrder:
					if used[sIdx]:
						continue
					si = sIslands[sIdx]

					match = matchIsland(orderMesh, shapeMesh, oi, si, status, pBar)
					if match:
						matches.append(match)
						used[sIdx] = True
						break
				else:
					raise TopologyMismatch("Unable to find Island match")

	out = sum(matches, [])
	return out

def test():
	from bagel import Mesh
	orderPath = r'H:\public\tyler\bagel\head.obj'
	shapePath = r'H:\public\tyler\bagel\head2.obj'
	outPath = r'H:\public\tyler\bagel\crawl.obj'

	print "Loading Order Mesh"
	headOrder = Mesh.loadObj(orderPath)
	print "Loading Shape Mesh"
	headShape = Mesh.loadObj(shapePath)
	print "Done Loading"
	matchIslands(headOrder, headShape)
	print "Matched"

	#orderPossible, shapePossible = findPossiblePairsByValenceSteps(headOrder.vertices, headShape.vertices)
	#print "POSSIBLE PAIRS:", orderPossible, shapePossible

	#minValence, orderPossible, shapePossible = _getMinValencePoints(headOrder, headShape)
	#match = matchPossiblePairs(headOrder, headShape, orderPossible, shapePossible)
	#print "Match Found!!!"
	#match = matchByTopology(headOrder, headShape, vertPairs, len(headOrder.vertices))

	#updateVertPairs(headOrder, match)
	#UpdateMesh()(headOrder, outPath)


if __name__ == "__main__":
	test()


