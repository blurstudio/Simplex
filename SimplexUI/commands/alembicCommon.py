import numpy as np
from imathnumpy import arrayToNumpy #pylint:disable=no-name-in-module
from imath import V3fArray, IntArray, V2fArray, V2f

def mkArray(aType, iList):
	''' Makes the alembic-usable c++ typed arrays '''
	iList = np.array(iList)
	array = aType(len(iList))
	memView = arrayToNumpy(array)
	np.copyto(memView, iList)
	return array

def mkSampleVertexPoints(pts):
	pts = np.array(pts)
	pts = pts.reshape((-1, 3)) # handle flattened list
	return mkArray(V3fArray, pts)

def mkSampleIntArray(vals):
	vals = np.array(vals)
	return mkArray(IntArray, vals)

def mkSampleUvArray(uvs):
	""" Makes the alembic-usable c++ typed arrays """
	array = V2fArray(len(uvs))
	setter = V2f(0, 0)
	for i in xrange(len(uvs)):
		setter.setValue(uvs[i][0], uvs[i][1])
		array[i] = setter
	return array  

def getSampleArray(imesh):
	meshSchema = imesh.getSchema()
	posProp = meshSchema.getPositionsProperty()

	shapes = np.empty((len(posProp.samples), len(posProp.samples[0]), 3))
	for i, s in enumerate(posProp.samples):
		shapes[i] = arrayToNumpy(s)
	return shapes

