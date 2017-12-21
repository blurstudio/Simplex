from alembic.Abc import IArchive, OArchive, OStringProperty
from alembic.AbcGeom import IPolyMesh, OPolyMesh, IXform, OXform, OPolyMeshSchemaSample

import numpy as np
from imathnumpy import arrayToNumpy #pylint:disable=no-name-in-module
from imath import V3f, V3fArray, IntArray

def parseAbc(path):
	""" Read an .abc file and produce a Mesh object

	Args:
		path: The path to the .abc formatted file

	Returns:
		A list of vertices and the face connectivity

	Raises:
		IOError: If the file cannot be opened
	"""

	iarch = IArchive(str(path)) # because alembic hates unicode
	top = iarch.getTop()
	ixfo = IXform(top, top.children[0].getName())
	mesh = IPolyMesh(ixfo, ixfo.children[0].getName())

	sch = mesh.getSchema()
	rawVerts = sch.getPositionsProperty().samples[0]
	rawFaces = sch.getFaceIndicesProperty().samples[0]
	rawCounts = sch.getFaceCountsProperty().samples[0]

	faces = []
	faceCounter = 0
	for count in rawCounts:
		f = list(rawFaces[faceCounter: faceCounter+count])
		# Ignoring UV/Normal data for now
		faces.append(f)
		faceCounter += count

	verts = []
	for v in rawVerts:
		verts.append(list(v))

	return verts, faces

def buildEdgeAdjacency(faces):
	''' Build a dictionary with vert indices as keys,
	and a list of edge-adjacent vert indices as the value
	'''
	adj = {}
	for face in faces:
		for i in range(len(face)):
			adj.setdefault(face[i], set()).add(face[i-1])
			adj.setdefault(face[i-1], set()).add(face[i])
	return adj

def buildDiagonalAdjacency(faces):
	''' Build a dictionary with vert indices as keys,
	and a list of quad-diagonal vert indices as the value
	'''
	adj = {}
	for face in faces:
		if len(face) != 4:
			continue
		for i in range(len(face)):
			adj.setdefault(face[i], set()).add(face[i-2])
			adj.setdefault(face[i-2], set()).add(face[i])
	return adj

def growByAdjacency(growSet, exclude, adj):
	''' Grow a set of verts along an adjacency dict
	Args:
		growSet: A set of Vertices to grow.
		exclude: A set of Vertices to exclude from
			the growth

	Returns:
		newGrowSet: the grown verts
		newExclude: the next set of verts to exclude
	'''
	grown = set()
	for vert in growSet:
		grown.update(adj.get(vert, []))
	newgrown = grown - exclude
	newexclude = exclude | growSet
	return newgrown, newexclude

def partitionVerts(hints, adj, diag):
	''' Partition a subdivided mesh's vertices into
	originals , Added edge verts, and added center verts
	'''
	originals = set(hints)
	centers = set()
	exclude = set(hints)

	while True:
		newCorners, exclude = growByAdjacency(originals, exclude, diag)
		if not newCorners:
			break
		centers.update(newCorners)

		newCenters, exclude = growByAdjacency(centers, exclude, diag)
		if not newCenters:
			break
		originals.update(newCenters)

	edges, exc = growByAdjacency(originals, exclude, adj)

	if edges & centers:
		raise ValueError("The input mesh was not a perfect subdivision")

	return originals, edges, centers

def buildNewFaces(faces, centers, diag):
	''' Build a new set of faces by removing
	center verts and the adjacent edgeVerts
	'''
	faceIdxsByVert = {}
	for i, face in enumerate(faces):
		for f in face:
			faceIdxsByVert.setdefault(f, set()).add(i)

	newFaces = []
	for center in centers:
		corners = diag[center]
		centerFaceIdxs = faceIdxsByVert[center]

		newFace = []
		c = corners.pop()
		while c not in newFace:
			newFace.append(c)
			cornerFaceIdxs = faceIdxsByVert[c] & centerFaceIdxs
			cornerFaceIdx = cornerFaceIdxs.pop()
			face = faces[cornerFaceIdx]

			pre = face[face.index(c) - 1]
			edgeFaceIdxs = faceIdxsByVert[pre] & centerFaceIdxs
			edgeFaceIdxs.remove(cornerFaceIdx)
			preFaceIdx = edgeFaceIdxs.pop()
			preFace = faces[preFaceIdx]

			c = preFace[preFace.index(pre) - 1]
		newFace.reverse()
		newFaces.append(newFace)

	return newFaces

def squashFaces(faces):
	''' Take a list of unsubdivided faces and
	squash the indices into a continuous range
	'''
	kept = set()
	for f in faces:
		kept |= set(f)
	kept = sorted(list(kept))

	# build the reverse accessor
	rev = {k: i for i, k in enumerate(kept)}

	newFaces = []
	for face in faces:
		nf = []
		for f in face:
			nf.append(rev[f])
		newFaces.append(nf)

	return newFaces, kept

def findBoundaryVerts(adj, diag):
	''' Return a list of Vertices along the edge of a mesh '''
	edges = []	
	keys = list(set(adj.keys() + diag.keys()))
	for k in keys:
		if len(adj[k]) == 3 and len(diag[k]) == 2:
			edges.append(k)
		elif len(adj[k]) == 2 and len(diag[k]) == 1:
			edges.append(k)
	return edges

def partitionIslands(adj, numVerts):
	''' Return a list of connected island sets '''
	allVerts = set(range(numVerts))
	islands = []
	while allVerts:
		seed = set([allVerts.pop()])
		island = set()
		while seed:
			seed, island = growByAdjacency(seed, island, adj)
		islands.append(island)
		allVerts.difference_update(island)
	return islands

def buildHints(island, edges, adj):
	''' Find star points that are an even number of grows from an edge '''
	boundaries = island  & set(edges)
	if not boundaries:
		# Well ... we don't have any good way of dealing with this
		# Best thing I can do is search for the highest valence verts
		# and use one of those as the hint.
		d = {}
		for v in island:
			d.setdefault(len(adj[v]), []).append(v)
		mkey = max(d.keys())
		return d[mkey][0]

	exclude = set()
	while boundaries:
		for b in boundaries:
			if len(adj[b]) != 4:
				return b
		boundaries, exclude = growByAdjacency(boundaries, exclude, adj)
		boundaries, exclude = growByAdjacency(boundaries, exclude, adj)
	raise ValueError("Somehow, a mesh has boundaries, but no vert with a non-4 valence")



def getSampleArray(imesh):
	''' The fastest way to read the simplex vertex information '''
	meshSchema = imesh.getSchema()
	posProp = meshSchema.getPositionsProperty()

	shapes = np.empty((len(posProp.samples), len(posProp.samples[0]), 3))
	for i, s in enumerate(posProp.samples):
		shapes[i] = arrayToNumpy(s)
	return shapes

# TODO Make this work with UV's 
def exportUnsub(inPath, outPath, newFaces, kept):
	''' Export the unsubdivided simplex '''
	iarch = IArchive(str(inPath)) # because alembic hates unicode
	top = iarch.getTop()
	ixfo = IXform(top, top.children[0].getName())

	iprops = ixfo.getSchema().getUserProperties()
	iprop = iprops.getProperty("simplex")
	jsString = iprop.getValue()
	imesh = IPolyMesh(ixfo, ixfo.children[0].getName())

	verts = getSampleArray(imesh)
	verts = verts[:, kept]

	indices = []
	counts = []
	for f in newFaces:
		indices.extend(f)
		counts.append(len(f))

	abcCounts = mkSampleFaceArray(counts)
	abcIndices = mkSampleFaceArray(indices)

	# `False` for HDF5 `True` for Ogawa
	oarch = OArchive(str(outPath), False)
	oxfo = OXform(oarch.getTop(), ixfo.getName())
	oprops = oxfo.getSchema().getUserProperties()
	oprop = OStringProperty(oprops, "simplex")
	oprop.setValue(str(jsString))
	omesh = OPolyMesh(oxfo, imesh.getName())
	osch = omesh.getSchema()

	for i, v in enumerate(verts):
		print "Exporting Shape {0: <4}\r".format(i+1),
		sample = OPolyMeshSchemaSample(mkSampleVertexPoints(v), abcIndices, abcCounts)
		osch.set(sample)
	print "Exporting Shape {0: <4}".format(len(verts))



def mkSampleFaceArray(idxs):
	''' Build an output int array '''
	array = IntArray(len(idxs))
	for i in xrange(len(idxs)):
		array[i] = idxs[i]
	return array

def mkSampleVertexPoints(pts):
	''' Build an output vertex array '''
	array = V3fArray(len(pts))
	setter = V3f(0, 0, 0) #speed up object creation
	for i in xrange(len(pts)):
		setter.setValue(pts[i][0], pts[i][1], pts[i][2])
		array[i] = setter
	return array

def unsubdivideSimplex(inPath, outPath):
	''' Unsubdivide a simplex file '''
	print "Loading"
	verts, faces = parseAbc(inPath)

	print "Parsing"
	adj = buildEdgeAdjacency(faces)
	diag = buildDiagonalAdjacency(faces)
	bound = findBoundaryVerts(adj, diag)
	islands = partitionIslands(adj, len(verts))
	hints = [buildHints(isle, bound, adj) for isle in islands]

	print "Unsubdividing"
	originals, edges, centers = partitionVerts(hints, adj, diag)
	delFaces = buildNewFaces(faces, centers, diag)
	newFaces, kept = squashFaces(delFaces)

	print "Exporting"
	exportUnsub(inPath, outPath, newFaces, kept)

	print "Done"

if __name__ == '__main__':
	inPath = r'D:\Users\tyler\Desktop\JawOnly.smpx'
	outPath = r'D:\Users\tyler\Desktop\JawOnlyUnsub.smpx'

	unsubdivideSimplex(inPath, outPath)



