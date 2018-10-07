import blurdev
import gc

from alembic.Abc import IArchive, OArchive, OStringProperty
from alembic.AbcGeom import IXform, IPolyMesh, OPolyMesh, OXform, OPolyMeshSchemaSample

def _writeSimplex(oarch, name, jsString, faces, counts, newShapes):
	''' Separate the writer from oarch creation so garbage
	collection *hopefully* works as expected
	'''
	par = OXform(oarch.getTop(), name)
	props = par.getSchema().getUserProperties()
	prop = OStringProperty(props, "simplex")
	prop.setValue(str(jsString))
	abcMesh = OPolyMesh(par, name)
	schema = abcMesh.getSchema()

	for i, newShape in enumerate(newShapes):
		print "Writing {0: 3d} of {1}\r".format(i, len(newShapes)),
		abcSample = OPolyMeshSchemaSample(newShape, faces, counts)
		schema.set(abcSample)
	print "Writing {0: 3d} of {1}".format(len(newShapes), len(newShapes))

def loadJSString(iarch):
	''' Get the json string out of a .smpx file '''
	top = iarch.getTop()
	par = top.children[0]
	par = IXform(top, par.getName())

	systemSchema = par.getSchema()
	props = systemSchema.getUserProperties()
	prop = props.getProperty("simplex")
	jsString = prop.getValue()
	return jsString

def loadSmpx(iarch):
	''' Load the json and shape data from a .smpx file '''
	top = iarch.getTop()
	par = top.children[0]
	par = IXform(top, par.getName())

	abcMesh = par.children[0]
	abcMesh = IPolyMesh(par, abcMesh.getName())

	meshSchema = abcMesh.getSchema()
	posProp = meshSchema.getPositionsProperty()

	shapes = []
	lpps = len(posProp.samples)
	for i, s in enumerate(posProp.samples):
		print "Reading {0: 3d} of {1}\r".format(i, lpps),
		shapes.append(s)
	print "Reading {0: 3d} of {1}".format(lpps, lpps)
	return shapes

def loadMesh(iarch):
	''' Load the static mesh data from a .smpx file'''
	top = iarch.getTop()
	par = top.children[0]
	par = IXform(top, par.getName())

	abcMesh = par.children[0]
	abcMesh = IPolyMesh(par, abcMesh.getName())

	sch = abcMesh.getSchema()
	faces = sch.getFaceIndicesProperty().samples[0]
	counts = sch.getFaceCountsProperty().samples[0]

	return faces, counts

def hdf5Convert(inPath, outPath):
	''' Load and parse all the data from a simplex file '''
	iarch = IArchive(str(inPath))
	jsString = loadJSString(iarch)
	shapes = loadSmpx(iarch)
	faces, counts = loadMesh(iarch)
	del iarch

	oarch = OArchive(str(outPath), False) # alembic does not like unicode filepaths
	try:
		_writeSimplex(oarch, 'Face', jsString, faces, counts, shapes)
	finally:
		del oarch
		gc.collect()

if __name__ == '__main__':
	inPath = r'D:\Users\tyler\Desktop\highresSimplex_BadOrder_Ogawa.smpx'
	outPath = r'D:\Users\tyler\Desktop\highresSimplex_BadOrder_hdf5.smpx'
	hdf5Convert(inPath, outPath)

