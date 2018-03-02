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

--------------------------------------------------------------------------------------

This is the Blur Abstract Geometry Library (bagel)

This library will try to provide mesh conversion to and from every DCC and file format
we use here at Blur

The Mesh object itself will try to provide an efficient way to run algorithms on
3d mesh data

There are also convenience classes that act as function sets for mesh object components
Verts and Faces are the most common convenience classes and give access to adjacency
data (for backwards compatibility)

VertSet and FaceSet classes are just sets that also contain references back to the mesh
"""

class Mesh(object):
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
	def __init__(self, verts, faces, uvs=None, normals=None, ensureWinding=True):
		self._verts = None
		self._faces = None
		self._uvs = {}
		self._normals = None

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
			self._ensureWinding(hedgeCWDict, hedgeCCWDict)

		self.faceEdgeAdjacency = {}
		for i in xrange(len(self.vertArray)):
			for j in self.vertNeighbors[i]:
				pair = (i, j)
				ccw = hedgeCCWDict.get(pair, None)
				cw = hedgeCWDict.get(pair, None)
				self.faceEdgeAdjacency[pair] = (ccw, cw)

	def _ensureWinding(self, hedgeCWDict, hedgeCCWDict):
		"""
		Ensure that all neighbor queries return objects in a counter-clockwise order
		"""
		for vert in xrange(len(self.vertArray)):
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
		"""
		Take a list of paired items, and order them so the
		second item of a pair matches the first of the next pair
		Then return the first item of each pair. For instance:
			input:   [(2, 3), (1, 2), (3, 4), (0, 1), (4, 0)]
			reorder: [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]
			output   [0, 1, 2, 3, 4]
		"""
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
		""" Get all faces that share an edge with the given face
		Winding Guaranteed Counterclockwise
		
		Args:
			faceIdx (int): Face Index

		Returns:
			list: List of faces indices that share an edge with the input

		Raises:
			IndexError: The input is out of range
		"""
		verts = self.faceVertArray[faceIdx]
		out = []
		for i in xrange(verts):
			edge = (verts[i-1], verts[i])
			_, rev = self.faceEdgeAdjacency.get(edge, (None, None))
			out.append(rev)
		return out

	def adjacentFacesByVert(self, faceIdx):
		""" Get all faces that share a vert with the given face
		Winding Not Guaranteed

		Args:
			faceIdx (int): Face Index

		Returns:
			list: List of faces indices that share a vert with the input

		Raises:
			IndexError: The input is out of range
		"""
		out = set()
		verts = self.faceVertArray[faceIdx]
		for v in verts:
			out.update(self.vertToFaces[v])
		return list(out)

	def adjacentVertsByFace(self, vertIdx):
		""" Get all verts that share a face with the given vert
		Winding Not Guaranteed

		Args:
			vertIdx (int): Vertex Index

		Returns:
			list: List of vertex indices that share a face with the input

		Raises:
			IndexError: The input is out of range
		"""
		faces = self.vertToFaces[vertIdx]
		out = set()
		for f in faces:
			out.update(self.faceVertArray[f])
		return list(out)

	def adjacentVertsByEdge(self, vertIdx):
		""" Get all verts that share an edge with the given vert
		Winding Guaranteed Counterclockwise

		Args:
			vertIdx (int): Vertex Index

		Returns:
			list: List of vertex indices that share an edge with the input

		Raises:
			IndexError: The input is out of range
		"""
		return self.vertNeighbors[vertIdx]

	def verts(self):
		""" Get all vertex convenience objects

		Returns:
			list: List of vertex objects
		"""
		if self._verts is None:
			self._verts = [Vert(self, i) for i in xrange(len(self.vertArray))]
		return self._verts

	def faces(self):
		""" Get all face convenience objects

		Returns:
			list: List of face objects
		"""
		if self._faces is None:
			self._faces = [Face(self, i) for i in xrange(len(self.faceVertArray))]
		return self._faces

	def uvs(self, channelName):
		""" Get all UV convenience objects

		Returns:
			list: List of UV objects
		"""
		if channelName not in self._uvs:
			self._uvs[channelName] = [UV(self, channelName, i) for i in xrange(len(self.faceUVArray[channelName]))]
		return self._uvs[channelName]

	def normals(self):
		""" Get all normal convenience objects

		Returns:
			list: List of normal objects
		"""
		if self._normals is None:
			self._normals = [Normal(self, i) for i in xrange(len(self.normalArray))]
		return self._normals

	def clear(self):
		""" Remove all cached convenience classes """
		self._verts = None
		self._faces = None
		self._uvs = {}
		self._normals = None



	def __del__(self):
		for child in self.children:
			child.clear()


class MeshComponent(object):
	""" Base class for all mesh components
	Handles keeping track of the mesh and index
	"""
	__slot__ = 'mesh', 'index'
	def __init__(self, mesh, index):
		self.mesh = mesh
		self.index = index
		self.mesh.children.append(self)

	def __int__(self):
		return self.index

	def clear(self):
		""" Remove all reference data from this object """
		self.mesh = None
		self.mesh.children.remove(self)

	def __eq__(self, other):
		if isinstance(other, type(self)):
			if self.mesh is other.mesh:
				return self.index == other.index
			# Not worrying about floating point equality
			return self.value() == other.value()
		return NotImplemented

	def __hash__(self):
		return self.index


class Vert(MeshComponent):
	''' A convenience class for accessing and manipulating vertices '''
	def adjacentVertsByEdge(self):
		""" Get all verts that share an edge with the given vert

		Returns:
			list: List of verts that share an edge with the input
		"""
		idxs = self.mesh.adjacentVertsByEdge(self.index)
		verts = self.mesh.verts()
		return [verts[i] for i in idxs]

	def adjacentVertsByFace(self):
		""" Get all verts that share a face with the given vert

		Returns:
			list: List of verts that share a face with the input
		"""
		idxs = self.mesh.adjacentVertsByFace(self.index)
		verts = self.mesh.verts()
		return [verts[i] for i in idxs]

	def adjacentFaces(self):
		""" Get all faces that use this vertex

		Returns:
			list: List of faces that use this vertex
		"""
		idxs = self.mesh.vertToFaces[self.index]
		faces = self.mesh.faces()
		return [faces[i] for i in idxs]

	def value(self):
		""" Get the vertex's position

		Returns:
			tuple: (x, y, z) vertex position
		"""
		return self.mesh.vertArray[self.index]

	def setValue(self, pos):
		""" Set the vertex position

		Args:
			pos (tuple): (x, y, z) vertex position
		"""
		t = tuple(pos)
		assert len(t) == 3
		self.mesh.vertArray[self.index] = t


class Face(MeshComponent):
	''' A convenience class for accessing and manipulating faces '''
	def adjacentFacesByEdge(self):
		""" Get all faces that share an edge with the given face

		Returns:
			list: List of faces that share an edge with the input
		"""
		idxs = self.mesh.adjacentFacesByEdge(self.index)
		faces = self.mesh.faces()
		return [faces[i] for i in idxs]

	def adjacentFacesByVert(self):
		""" Get all faces that share a vert with the given face

		Returns:
			list: List of faces that share a vert with the input
		"""
		idxs = self.mesh.adjacentFacesByVert(self.index)
		faces = self.mesh.faces()
		return [faces[i] for i in idxs]

	def __eq__(self, other):
		if isinstance(other, Face):
			return set(self.verts()) == set(other.verts())
		return NotImplemented

	def __hash__(self):
		return hash(self.verts())

	def verts(self):
		""" Get all verts that make up this face

		Returns:
			list: List of vertexes that make up this face
		"""
		idxs = self.mesh.faceVertArray[self.index]
		verts = self.mesh.verts()
		return [verts[i] for i in idxs]

	def uvs(self, name='default'):
		""" Get all uvs that make up this face

		Returns:
			list: List of uvs that make up this face
		"""
		idxs = self.mesh.faceUVArray[name][self.index]
		uvs = self.mesh.uvs(name)
		return [uvs[i] for i in idxs]

	def normals(self):
		""" Get all normals that make up this face

		Returns:
			list: List of normals that make up this face
		"""
		idxs = self.mesh.faceNormalArray[self.index]
		normals = self.mesh.normals()
		return [normals[i] for i in idxs]


class UV(MeshComponent):
	''' A convenience class for accessing and manipulating uvs '''
	__slot__ = 'mesh', 'index', 'name'
	def __init__(self, mesh, name, index):
		self.name = name
		super(UV, self).__init__(mesh, index)

	def value(self):
		""" Get the uv's position

		Returns:
			tuple: (u, v) position
		"""
		return self.mesh.uvArray[self.name][self.index]

	def setValue(self, pos):
		""" Set the uv's position

		Args:
			pos (tuple): (u, v) position
		"""
		t = tuple(pos)
		assert len(t) == 2
		self.mesh.uvArray[self.name][self.index] = t

	def __hash__(self):
		return hash(self.name, self.index)


class Normal(MeshComponent):
	''' A convenience class for accessing and manipulating normals '''
	def value(self):
		""" Get the normal's vector

		Returns:
			tuple: (x, y, z) vector
		"""
		return self.mesh.normalArray[self.index]

	def setValue(self, norm):
		""" Set the normal's vector

		Args:
			norm (tuple): (x, y, z) vector
		"""
		t = tuple(norm)
		assert len(t) == 3
		self.mesh.normalArray[self.index] = t


class MeshSet(set):
	""" An set-like object that deals with geometry """
	def __init__(self, mesh, indices):
		idxs = [int(i) for i in indices]
		super(MeshSet, self).__init__(idxs)
		self.mesh = mesh
		self.mesh.children.append(self)


class VertSet(MeshSet):
	""" An set-like object that deals with vertices """
	def growByEdge(self, exclude=None):
		""" Add verts that share edges with the current set
		Args:
			exclude (VertSet): A set of vertices to exclude from growth

		Returns:
			VertSet: An updated vertex set
		"""
		exclude = exclude or set()
		out = VertSet(self.mesh, [])
		verts = self.mesh.verts()
		for index in self:
			if index in exclude:
				continue
			v = verts[index]
			out.update(map(int, v.adjacentVertsByEdge()))
		return out - exclude

	def growByFace(self, exclude=None):
		""" Add verts that share faces with the current set
		Args:
			exclude (VertSet): A set of vertices to exclude from growth

		Returns:
			VertSet: An updated vertex set
		"""
		exclude = exclude or set()
		out = VertSet(self.mesh, [])
		verts = self.mesh.verts()
		for index in self:
			if index in exclude:
				continue
			v = verts[index]
			out.update(map(int, v.adjacentVertsByFace()))
		return out - exclude


class FaceSet(MeshSet):
	""" An set-like object that deals with faces """
	def growByEdge(self, exclude=None):
		""" Add faces that share edges with the current set
		Args:
			exclude (FaceSet): A set of faces to exclude from growth

		Returns:
			FaceSet: An updated face set
		"""
		exclude = exclude or set()
		out = FaceSet(self.mesh, [])
		faces = self.mesh.faces()
		for index in self:
			if index in exclude:
				continue
			f = faces[index]
			out.update(map(int, f.adjacentFacesByEdge()))
		return out - exclude

	def growByVert(self, exclude=None):
		""" Add faces that share verts with the current set
		Args:
			exclude (FaceSet): A set of faces to exclude from growth

		Returns:
			FaceSet: An updated face set
		"""
		exclude = exclude or set()
		out = FaceSet(self.mesh, [])
		faces = self.mesh.faces()
		for index in self:
			if index in exclude:
				continue
			f = faces[index]
			out.update(map(int, f.adjacentFacesByVert()))
		return out - exclude

