from imath import V3fArray, IntArray, V2fArray, V2f, UnsignedIntArray
from alembic.AbcGeom import OV2fGeomParamSample, GeometryScope

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
	''' Makes the alembic-usable c++ typed arrays '''
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
	return mkArray(V3fArray, pts)

def mkSampleIntArray(vals):
	return mkArray(IntArray, vals)

def mkSampleUIntArray(vals):
	array = UnsignedIntArray(len(vals))
	for i in xrange(len(vals)):
		array[i] = vals[i]
	return array

def mkSampleUvArray(uvs):
	""" Makes the alembic-usable c++ typed arrays """
	array = V2fArray(len(uvs))
	setter = V2f(0, 0)
	for i in xrange(len(uvs)):
		setter.setValue(uvs[i][0], uvs[i][1])
		array[i] = setter
	return array

def mkUvSample(uvs, indexes=None):
	""" Take an array, and make a poly mesh sample of the uvs """
	ary = mkSampleUvArray(uvs)
	if indexes is None:
		return OV2fGeomParamSample(ary, GeometryScope.kFacevaryingScope)
	idxs = mkSampleUIntArray(indexes)
	return OV2fGeomParamSample(ary, idxs, GeometryScope.kFacevaryingScope)

def getSampleArray(imesh):
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
	sch = imesh.getSchema()
	faces = sch.getFaceIndicesProperty().samples[0]
	counts = sch.getFaceCountsProperty().samples[0]
	return faces, counts

def getUvSample(imesh):
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
	imeshsch = imesh.getSchema()
	uvParam = imeshsch.getUVsParam()
	if uvParam.valid():
		uvProp = uvParam.getValueProperty()
		uvValue = uvProp.getValue()
		uv = OV2fGeomParamSample(uvValue, GeometryScope.kFacevaryingScope)
	else:
		uv = None
	return uv

