# Copyright 2016, Blur Studio
#
# This file is part of Simplex.
#
# Simplex is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Simplex is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.

''' Alembic files can be difficult to work with, and can be *very* slow in Python
This is a library of convenience functions with the numpy speed optimizations
'''

from imath import V3fArray, IntArray, V2fArray, V2f, UnsignedIntArray
from alembic.AbcGeom import OV2fGeomParamSample, GeometryScope, IPolyMesh, OPolyMesh, ON3fGeomParamSample, OXform
from alembic.Abc import IArchive, OArchive, OStringProperty

try:
	import numpy as np
except ImportError:
	np = None
	arrayToNumpy = None
else:
	try:
		from imathnumpy import arrayToNumpy #pylint:disable=no-name-in-module
	except ImportError:
		arrayToNumpy = None



def mkArray(aType, iList):
	''' Makes the alembic-usable c++ typed arrays

	Parameters
	----------
	aType : imath type
		The type of the output array
	iList : list or np.array
		The input iterable. 

	Returns
	-------
	aType
		The input list translated into an aType array
	'''
	if isinstance(iList, aType):
		return iList

	if np is None:
		array = aType(len(iList))
		for i in xrange(len(iList)):
			array[i] = tuple(iList[i])
		return array
	elif arrayToNumpy is None:
		array = aType(len(iList))
		for i in xrange(len(iList)):
			array[i] = tuple(iList[i].tolist())
		return array
	else:
		iList = np.array(iList)
		array = aType(len(iList))
		memView = arrayToNumpy(array)
		np.copyto(memView, iList)
		return array

def mkSampleVertexPoints(pts):
	''' Make an imath array of vertices

	Parameters
	----------
	pts : list or np.array
		The input points
		
	Returns
	-------
	V3fArray
		The output list
	'''
	return mkArray(V3fArray, pts)

def mkSampleIntArray(vals):
	''' Make an imath array of integers

	Parameters
	----------
	pts : list or np.array
		The input integers
		
	Returns
	-------
	IntArray
		The output list
	'''
	return mkArray(IntArray, vals)

def mkSampleUIntArray(vals):
	''' Make an imath array of unsigned integers

	Parameters
	----------
	pts : list or np.array
		The input unsigned integers
		
	Returns
	-------
	UnsignedIntArray
		The output list
	'''
	array = UnsignedIntArray(len(vals))
	for i in xrange(len(vals)):
		array[i] = vals[i]
	return array

def mkSampleUvArray(uvs):
	''' Make an imath array of uvs

	Parameters
	----------
	uvs : list or np.array
		The input uvs
		
	Returns
	-------
	V2fArray
		The output list
	'''
	array = V2fArray(len(uvs))
	setter = V2f(0, 0)
	for i in xrange(len(uvs)):
		setter.setValue(uvs[i][0], uvs[i][1])
		array[i] = setter
	return array

def mkUvSample(uvs, indexes=None):
	''' Take an array, and make a poly mesh sample of the uvs

	Parameters
	----------
	uvs : list or np.array
		The input uvs
	indexes : list or np.array or None
		The optional face indices of the uvs

	Returns
	-------
	OV2fGeomParamSample
		The UV sample
	'''
	ary = mkSampleUvArray(uvs)
	if indexes is None:
		return OV2fGeomParamSample(ary, GeometryScope.kFacevaryingScope)
	idxs = mkSampleUIntArray(indexes)
	return OV2fGeomParamSample(ary, idxs, GeometryScope.kFacevaryingScope)

def mkNormalSample(norms, indexes=None):
	""" Take an array, and make a poly mesh sample of the uvs """
	ary = mkSampleNormArray(norms)
	if indexes is None:
		return ON3fGeomParamSample(ary, GeometryScope.kFacevaryingScope)
	idxs = mkSampleUIntArray(indexes)
	return ON3fGeomParamSample(ary, idxs, GeometryScope.kFacevaryingScope)

def getSampleArray(imesh):
	''' Get the per-frame vertex positions for a mesh

	Parameters
	----------
	imesh : IPolyMesh
		The input alembic mesh object

	Returns
	-------
	np.array or list
		The per-frame vertex positions
	'''
	meshSchema = imesh.getSchema()
	posProp = meshSchema.getPositionsProperty()
	if arrayToNumpy is not None:
		shapes = np.empty((len(posProp.samples), len(posProp.samples[0]), 3))
		for i, s in enumerate(posProp.samples):
			shapes[i] = arrayToNumpy(s)
		return shapes
	elif np is not None:
		shapes = []
		for i, s in enumerate(posProp.samples):
			shapes.append(s)
		return np.array(shapes)
	else:
		shapes = []
		for i, s in enumerate(posProp.samples):
			shapes.append(s)
		return shapes

def getStaticMeshData(imesh):
	''' Get all the generally non-changing data for a mesh

	Parameters
	----------
	imesh : IPolyMesh
		The input alembic mesh object
		
	Returns
	-------
	IntArray
		A flat alembic array of vertex indices for the faces
	IntArray
		The number of vertices per face
	'''
	sch = imesh.getSchema()
	faces = sch.getFaceIndicesProperty().samples[0]
	counts = sch.getFaceCountsProperty().samples[0]
	return faces, counts

def getUvSample(imesh):
	''' Get the UV's for a mesh

	Parameters
	----------
	imesh : IPolyMesh
		The input alembic mesh object

	Returns
	-------
	OV2fGeomParamSample
		The UV Sample
	'''
	imeshsch = imesh.getSchema()
	uvParam = imeshsch.getUVsParam()

	if not uvParam.valid():
		return None

	uvValue = uvParam.getValueProperty().getValue()
	if uvParam.isIndexed():
		idxValue = uvParam.getIndexProperty().getValue()
		uv = OV2fGeomParamSample(uvValue, idxValue, GeometryScope.kFacevaryingScope)
	else:
		uv = OV2fGeomParamSample(uvValue, GeometryScope.kFacevaryingScope)
	return uv

def getUvArray(imesh):
	''' Get the uv positions for a mesh

	Parameters
	----------
	imesh : IPolyMesh
		The input alembic mesh object
		
	Returns
	-------
	list or np.array or None
		The UVs if they exist
	'''
	imeshsch = imesh.getSchema()
	uvParam = imeshsch.getUVsParam()
	if uvParam.valid():
		uvProp = uvParam.getValueProperty()
		uvVals = uvProp.getValue()
		uv = zip(uvVals.x, uvVals.y)
		if np is not None:
			uv = np.array(uv)
	else:
		uv = None
	return uv

def getUvFaces(imesh):
	''' Get the UV structure for a mesh if it's indexed. If un-indexed, return None
		This means that if we have valid UVs, but invalid uvFaces, then we're un-indexed
		and can handle the data appropriately for export without keeping track of index-ness

	Parameters
	----------
	imesh : IPolyMesh
		The input alembic mesh object

	Returns
	-------
	[[int, ...], ...]
		The UVFace structure
	'''
	sch = imesh.getSchema()
	rawCounts = sch.getFaceCountsProperty().samples[0]
	iuvs = sch.getUVsParam()
	uvFaces = None
	if iuvs.valid():
		uvFaces = []
		uvCounter = 0
		if iuvs.isIndexed():
			idxs = list(iuvs.getIndexProperty().getValue())
			for count in rawCounts:
				uvFaces.append(list(idxs[uvCounter: uvCounter+count]))
				uvCounter += count
	return uvFaces

def getMeshFaces(imesh):
	''' Get The vertex indices used per face
	
	Parameters
	----------
	imesh : IPolyMesh
		The input alembic mesh object

	Returns
	-------
	[[int, ...], ...]
		The UVFace structure
	'''
	rawFaces, rawCounts = getStaticMeshData(imesh)
	faces = []
	ptr = 0
	for count in rawCounts:
		faces.append(list(rawFaces[ptr: ptr+count]))
		ptr += count
	return faces

def getPointCount(imesh):
	''' Get the number of vertices in a mesh

	Parameters
	----------
	imesh : IPolyMesh
		The input alembic mesh object

	Returns
	-------
	int
		The number of vertices in the mesh
	'''
	meshSchema = imesh.getSchema()
	posProp = meshSchema.getPositionsProperty()
	return len(posProp.samples[0])

def findAlembicObject(obj, abcType=None, name=None):
	"""
		Finds a single object in an alembic archive by name and/or type
		If only type is specified, then the first object of that type
		encountered will be returned
	"""
	md = obj.getMetaData()
	if abcType is None:
		if name is None or obj.getName() == name:
			return obj
	elif abcType.matches(md):
		if name is None or obj.getName() == name:
			return abcType(obj.getParent(), obj.getName())
	for child in obj.children:
		out = findAlembicObject(child, abcType, name)
		if out is not None:
			return out
	return None

def getMesh(infile):
	''' Get the first found mesh object from the alembic filepath '''
	iarch = IArchive(infile)
	ipolymsh = findAlembicObject(iarch.getTop(), abcType=IPolyMesh)
	return ipolymsh

def buildAbc(outPath, points, faces, faceCounts=None,
	uvs=None, uvFaces=None, normals=None, normFaces=None,
	name='polymsh', shapeSuffix='Shape', transformSuffix='',
	propDict=None):
	'''
	Build a single-mesh alembic file from all of the non-alembic raw data

	Parameters
	----------
	outPath: str or OArchive
		The output path for the alembic file
	points: list or ndarray
		The list or array of points. Single multiple frames supported
	faces: list
		A list of lists of face indices, or a flattened list of indices.
		If flat, then faceCounts must be provided
	faceCounts: list
		A list of the number of vertices per face. Defaults to None
	uvs: list or ndarray
		The Uvs for this mesh. Defaults to None
	uvFaces: list
		A list of lists of face indices, or a flattened list of indices.
		If flat, then faceCounts must be provided. Defaults to None
	normals: list or ndarray
		The Normals for this mesh. Defaults to None
	normFaces: list
		A list of lists of face indices, or a flattened list of indices.
		If flat, then faceCounts must be provided. Defaults to None
	name: str
		The name to give this mesh. Defaults to "polymsh"
	shapeSuffix: str
		The suffix to add to the shape of this mesh. Defaults to "Shape"
	transformSuffix: str
		The suffix to add to the transform of this mesh. Defaults to ""
	propDict: dict
		A dictionary of properties to add to the xform object
	'''
	if faceCounts is None:
		# All the faces are in list-of-list format
		# put them in index-count format
		faceCounts, faces = _flattenFaces(faces)
		if uvFaces is not None:
			_, uvFaces = _flattenFaces(uvFaces)
		if normFaces is not None:
			_, normFaces = _flattenFaces(normFaces)

	faceCounts = mkSampleIntArray(faceCounts)
	faces = mkSampleIntArray(faces)

	if uvFaces is not None and uvs is not None:
		uvs = mkUvSample(uvs, indexes=uvFaces)
	if normFaces is not None and normals is not None:
		normals = mkNormalSample(normals, indexes=normFaces)

	if isinstance(outPath, basestring):
		oarch = OArchive(str(outPath), False) #False for HDF5
	else:
		oarch = outPath

	parent = oarch.getTop()
	opar = OXform(parent, name+transformSuffix)
	if propDict:
		props = opar.getSchema().getUserProperties()
		for k, v in propDict.iteritems():
			prop = OStringProperty(props, str(k))
			prop.setValue(str(v))
	omesh = OPolyMesh(opar, name+shapeSuffix)
	
	if np is not None:
		points = np.array(points)
		if len(points.shape) == 2:
			points = points[None, ...]
	else:
		if not isinstance(points[0][0], (list, tuple)):
			points = [points]

	sch = omesh.getSchema()
	for frame in points:
		abcFrame = mkSampleVertexPoints(frame)
		setAlembicSample(sch, abcFrame, faces, faceCounts, uvs=uvs, normals=normals)
	return oarch

