#pylint: disable=missing-docstring

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

--------------------------------------------------------------------------------------

This is the Blur Abstract Geometry Library (bagel)

This library will try to provide mesh conversion to and from every DCC and file format
we use here at Blur

The Mesh object itself will try to provide an efficient way to run algorithms on
3d mesh data

There are also convenience classes that act as function sets for mesh object components
Verts and Faces are the most common convenience classes and give access to adjacency
data (for backwards compatibility)

VertSet and FaceSet classes behave similarly to the python built-in set:
	Only one of each object is allowed in the set
	The sets allow for element-wise boolean operators, addition, and subtraction
'''

class Mesh(object):
	def __init__(self, verts, faces, uvs=None, normals=None, ensureWinding=True):
		"""
		The inputs to this mesh object are inspired by the .obj file format

		Arguments:
			verts: list of 3d vectors ((x,y,z), ...)
			faces: list of lists of vertex/uv/normal indices
				[[T1, T2, T3], [T4, T5, T6, T7] ...]
				Where each Tn above is a tuple containing (vertIdx, uvIdx, normalIdx) data
				Any items except the vertIdx can be None, and any trailing None's can be
				omitted
			uvs (default:None): list of 2d vectors ((u, v), ...)
			normals (default:None): list of 3d vectors ((x,y,z), ...)
			ensureWinding (default:True): Ensure that neighbor operations return items in order

		Faces are ccw wound
		The main uv set is named 'default'

		The idea for this data structure is to keep all the data in one place and have the
		individual convenience objects reference back to it
		Storing in one place means I can store it efficiently

		This doesn't really handle non-manifold geometry, nor do I want it to.
		I should probably make it error when loading non-manifold.

		The only strange one is "Edge Adjacency", and this borrows some data from
		the winged edge structure. Given two neighboring vertices, return the bordering
		faces. The first face contains the vertices wound backwards (counter clockwise),
		the second face contains the vertices wound forwards (clockwise)
		For instance, we could pass the vert indices (0, 1), and get back (10, 13) where
		faces[10].verts is (1, 0, 2) and faces[13].verts is (0, 1, 3).

		Float Data:
			vertArray			: array of 3d floats
			normalArray			: array of 3d floats
			uvMap				: map of d[name] => array of 2d floats

		Face Data:
			faceVertArray		: 2d array of vertex indices per face
			faceNormalArray		: 2d array of normal indices per face
			faceUVMap			: map of d[name] => 2d array of UV indices per face

		Vert Data:
			vertToFaces			: 2d array of face indices per vert
			vertNeighbors		: 2d array of vert indices per vert

		Edge Adjacency:
			faceEdgeAdjacency	: map of d[(vert1, vert2)] => (order, reverse) face indices
									where `order` contains (vert1, vert2) in the winding order
									and `reverse` contains (vert2, vert1) in the winding order
		"""
		self.children = []
		# load the float data
		self.vertArray = verts
		self.normalArray = normals
		self.uvMap = {}
		self.uvMap['default'] = uvs

		# build the empty face data
		self.faceVertArray = []
		self.faceNormalArray = []
		self.faceUVArray = {}
		self.faceUVArray['default'] = []

		vertToFaces = {}
		defaultUvArray = self.faceUVArray['default']
		for i, face in enumerate(faces):
			# handle missing uv/normal data
			tFace = zip(*face) + [[], []]
			vfl, uvfl, nfl = tFace[:3]

			self.faceVertArray.append(vfl)
			if uvs and uvfl:
				defaultUvArray.append(uvfl)
			if normals and nfl:
				self.faceNormalArray.append(nfl)

			for v in vfl:
				vertToFaces.setdefault(v, []).append(i)
		self.vertToFaces = [vertToFaces[i] for i in xrange(len(verts))]

		# build the neighbor dictionaries
		neighborDict = {}
		hedgeCCWDict = {}
		hedgeCWDict = {}

		for i, vIdxs in enumerate(self.faceVertArray):
			for j in xrange(len(vIdxs)):
				neighborDict.setdefault(vIdxs[j-1], []).append(vIdxs[j])
				hedgeCCWDict[(vIdxs[j-1], vIdxs[j])] = i
				hedgeCWDict[(vIdxs[j], vIdxs[j-1])] = i
		self.vertNeighbors = [neighborDict[i] for i in xrange(len(self.vertArray))]

		if ensureWinding:
			for vert in xrange(len(self.vertArray)):
				faces = self.vertToFaces[vert]
				neighbors = self.vertNeighbors[vert]

				# find the face to the cw and ccw of each edge
				# around a single vertex
				wingPairs = []
				for n in neighbors:
					incoming = hedgeCWDict.get((vert, n), None)
					outgoing = hedgeCCWDict.get((vert, n), None)
					wingPairs.append((incoming, outgoing))

				# make sure all face neighbors are returned in ccw order
				idxs = self._linkPairs(wingPairs)
				newFaceIdxs = []
				for fan in idxs:
					v = [wingPairs[i][0] for i in fan]
					wrap = wingPairs[fan[-1]][1]
					if wrap != v[0]:
						v.append(wrap)
					v = [i for i in v if i is not None]
					newFaceIdxs.extend(v)
				self.vertToFaces[vert] = newFaceIdxs

				try:
					# make sure all vert neighbors are in ccw order
					newNeighborIdxs = []
					for f in self.vertToFaces[vert]:
						verts = self.faceVertArray[f]
						i = verts.index(vert)
						newNeighborIdxs.append(verts[i-1])
					self.vertNeighbors[vert] = newNeighborIdxs
				except TypeError:
					print "V2F", self.vertToFaces[vert]
					raise

		self.faceEdgeAdjacency = {}
		for i in xrange(len(self.vertArray)):
			for j in self.vertNeighbors[i]:
				pair = (i, j)
				ccw = hedgeCCWDict.get(pair, None)
				cw = hedgeCWDict.get(pair, None)
				self.faceEdgeAdjacency[pair] = (ccw, cw)

	@classmethod
	def loadObj(cls, path, ensureWinding=True):
		""" Read a .obj file and produce a Mesh object

		Args:
			path: The path to the .obj formatted file

		Returns:
			A Mesh() object containing lists of linked
			vertices, edges, and faces

		Raises:
			IOError: If the file cannot be opened
		"""
		vertices = []
		faces = []
		uvs = []
		normals = []

		with open(path, 'r') as inFile:
			lines = inFile.readlines()

		for line in lines:
			sp = line.split()
			if sp == []:
				pass
			elif sp[0] == "v":
				v = [float(i) for i in sp[1:4]]
				vertices.append(v)

			elif sp[0] == 'vt':
				uv = [float(i) for i in sp[1:3]]
				uvs.append(uv)

			elif sp[0] == 'vn':
				norm = [float(i) for i in sp[1:4]]
				normals.append(norm)

			elif sp[0] == "f":
				# Make sure to pad out the face vert/uv/normal triples
				#print "LINE", line
				face = []
				for s in sp[1:]:
					vt = [int(i)-1 if i else None for i in s.split('/')]
					face.append(vt + [None]*3)
				face = [i[:3] for i in face]
				faces.append(face)

		return cls(vertices, faces, uvs, normals, ensureWinding)

	@classmethod
	def loadAbc(cls, path, meshName=None, ensureWinding=True):
		""" Read a .abc file and produce a Mesh object

		Args:
			path: The path to the .abc formatted file

		Returns:
			A Mesh() object containing lists of linked
			vertices, edges, and faces

		Raises:
			IOError: If the file cannot be opened
		"""
		from alembic.Abc import IArchive
		from alembic.AbcGeom import IPolyMesh
		from blur3d.lib.alembiclib import findAlembicObject

		iarch = IArchive(str(path)) # because alembic hates unicode
		mesh = findAlembicObject(iarch.getTop(), abcType=IPolyMesh, name=meshName)
		sch = mesh.getSchema()
		rawVerts = sch.getPositionsProperty().samples[0]
		rawFaces = sch.getFaceIndicesProperty().samples[0]
		rawCounts = sch.getFaceCountsProperty().samples[0]

		faces = []
		faceCounter = 0
		for count in rawCounts:
			f = list(rawFaces[faceCounter: faceCounter+count])
			# Ignoring UV/Normal data for now
			f = [[i, None, None] for i in f]
			faces.append(f)
			faceCounter += count

		verts = []
		for v in rawVerts:
			verts.append(list(v))

		return cls(verts, faces, ensureWinding=ensureWinding)

	@staticmethod
	def _linkPairs(pairs):
		'''
		Take a list of paired items, and order them so the
		second item of a pair matches the first of the next pair
		Then return the first item of each pair
		'''
		prevIdxs = [None] * len(pairs)
		postIdxs = [None] * len(pairs)
		lhsList, rhsList = zip(*pairs)
		for i, pair in enumerate(pairs):
			if pair[1] is not None:
				try:
					postIdxs[i] = lhsList.index(pair[1])
				except ValueError:
					pass
			if pair[0] is not None:
				try:
					prevIdxs[i] = rhsList.index(pair[0])
				except ValueError:
					pass

		starts = [i for i, v in enumerate(prevIdxs) if v is None]
		if not starts:
			starts = [0]
		outs = []
		for start in starts:
			idx = start
			out = []
			while idx is not None and idx not in out:
				out.append(idx)
				idx = postIdxs[out[-1]]
			outs.append(out)
		return outs

	def adjacentFacesByEdge(self, faceIdx):
		''' Get all faces that share an edge with the given face
		Winding Guaranteed Counterclockwise
		'''
		verts = self.faceVertArray[faceIdx]
		out = []
		for i in xrange(verts):
			edge = (verts[i-1], verts[i])
			_, rev = self.faceEdgeAdjacency.get(edge, (None, None))
			out.append(rev)
		return out

	def adjacentFacesByVert(self, faceIdx):
		''' Get all faces that share a vert with the given face
		Winding Not Guaranteed
		'''
		out = set()
		verts = self.faceVertArray[faceIdx]
		for v in verts:
			out.update(self.vertToFaces[v])
		return list(out)

	def adjacentVertsByFace(self, vertIdx):
		''' Get all verts that share a face with the given vert
		Winding Not Guaranteed
		'''
		faces = self.vertToFaces[vertIdx]
		out = set()
		for f in faces:
			out.update(self.faceVertArray[f])
		return list(out)

	def adjacentVertsByEdge(self, vertIdx):
		''' Get all verts that share an edge with the given vert
		Winding Guaranteed Counterclockwise
		'''
		return self.vertNeighbors[vertIdx]

	def verts(self):
		return [Vert(self, i) for i in xrange(len(self.vertArray))]

	def faces(self):
		return [Face(self, i) for i in xrange(len(self.faceVertArray))]

	def uvs(self):
		return [UV(self, i) for i in xrange(len(self.uvArray))]

	def normals(self):
		return [Normal(self, i) for i in xrange(len(self.normalArray))]

	def __del__(self):
		for child in self.children:
			child.clear()


class MeshComponent(object):
	__slot__ = 'mesh', 'index'
	def __init__(self, mesh, index):
		self.mesh = mesh
		self.index = index
		self.mesh.children.append(self)

	def clear(self):
		self.mesh = None
		self.mesh.children.remove(self)


class Vert(MeshComponent):
	def adjacentVertsByEdge(self):
		return self.mesh.adjacentVertsByEdge(self.index)

	def adjacentVertsByFace(self):
		return self.mesh.adjacentVertsByFace(self.index)

	def value(self):
		return self.mesh.vertArray[self.index]

	def setValue(self, tup):
		t = tuple(tup)
		assert len(t) == 3
		self.mesh.vertArray[self.index] = t

	def __eq__(self, other):
		if isinstance(other, Vert):
			if self.mesh is other.mesh:
				return self.index == other.index
			# Not worrying about floating point equality
			return self.value() == other.value()
		return NotImplemented

	def __hash__(self):
		return self.index


class Face(MeshComponent):
	def adjacentFacesByEdge(self):
		return self.mesh.adjacentFacesByEdge(self.index)

	def adjacentFacesByVert(self):
		return self.mesh.adjacentFacesByVert(self.index)

	def __eq__(self, other):
		if isinstance(other, Face):
			return set(self.verts()) == set(other.verts())
		return NotImplemented

	def __hash__(self):
		return hash(self.verts())

	def verts(self):
		return self.mesh.faceVertArray[self.index]

	def uvs(self, name='default'):
		return self.mesh.faceUVArray[name][self.index]

	def normals(self):
		return self.mesh.faceNormalArray[self.index]


class UV(MeshComponent):
	__slot__ = 'mesh', 'index', 'name'
	def __init__(self, mesh, name, index):
		self.name = name
		super(UV, self).__init__(mesh, index)

	def value(self):
		return self.mesh.uvArray[self.name][self.index]

	def setValue(self, tup):
		t = tuple(tup)
		assert len(t) == 2
		self.mesh.uvArray[self.name][self.index] = t

	def __eq__(self, other):
		if isinstance(other, UV):
			if self.name == other.name:
				if self.mesh is other.mesh:
					return self.index == other.index
			# Not worrying about floating point equality
			return self.value() == other.value()
		return NotImplemented

	def __hash__(self):
		return hash(self.name, self.index)


class Normal(MeshComponent):
	def value(self):
		return self.mesh.normalArray[self.index]

	def setValue(self, tup):
		t = tuple(tup)
		assert len(t) == 3
		self.mesh.normalArray[self.index] = t

	def __eq__(self, other):
		if isinstance(other, Normal):
			if self.mesh is other.mesh:
				return self.index == other.index
			# Not worrying about floating point equality
			return self.value() == other.value()
		return NotImplemented

	def __hash__(self):
		return self.index


class MeshSet(object):
	def __init__(self, mesh, indices):
		self.mesh = mesh
		self.indices = set(indices)
		self.mesh.children.append(self)

	def clear(self):
		self.mesh = None
		self.mesh.children.remove(self)

	def __sub__(self, other):
		if isinstance(other, type(self)):
			newset = self.indices - other.indices
			return type(self)(self.mesh, newset)
		return NotImplemented

	def __add__(self, other):
		if isinstance(other, type(self)):
			newset = self.indices | other.indices
			return type(self)(self.mesh, newset)
		return NotImplemented

	def __or__(self, other):
		if isinstance(other, type(self)):
			newset = self.indices | other.indices
			return type(self)(self.mesh, newset)
		return NotImplemented

	def __xor__(self, other):
		if isinstance(other, type(self)):
			newset = self.indices ^ other.indices
			return type(self)(self.mesh, newset)
		return NotImplemented

	def __and__(self, other):
		if isinstance(other, type(self)):
			newset = self.indices & other.indices
			return type(self)(self.mesh, newset)
		return NotImplemented

	@classmethod
	def fromVerts(cls, mesh, indices):
		idxs = [i.index for i in indices]
		return cls(mesh, idxs)


class VertSet(MeshSet):
	def growByEdge(self):
		out = set()
		v = Vert(self.mesh, 0)
		for index in self.indices:
			v.index = index
			out.update(v.adjacentVertsByEdge())
		return VertSet(self.mesh, out)

	def growByFace(self):
		out = set()
		v = Vert(self.mesh, 0)
		for index in self.indices:
			v.index = index
			out.update(v.adjacentVertsByFace())
		return VertSet(self.mesh, out)


class FaceSet(MeshSet):
	def growByEdge(self):
		out = set()
		f = Face(self.mesh, 0)
		for index in self.indices:
			f.index = index
			out.update(f.adjacentFacesByEdge())
		return out

	def growByVert(self):
		out = set()
		f = Face(self.mesh, 0)
		for index in self.indices:
			f.index = index
			out.update(f.adjacentFacesByVert())
		return out


