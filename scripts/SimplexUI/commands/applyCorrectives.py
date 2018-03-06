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

#pylint:disable=unused-variable
import blurdev
import sys, itertools, gc
import numpy as np

from alembic.Abc import IArchive, OArchive, OStringProperty
from alembic.AbcGeom import IXform, IPolyMesh, OPolyMesh, OXform, OPolyMeshSchemaSample
from alembicCommon import mkSampleVertexPoints, getSampleArray

from Simplex2.interface import Simplex, Combo, Slider
from Qt.QtWidgets import QApplication

from pysimplex import PySimplex #pylint:disable=unused-import,wrong-import-position,import-error

def invertAll(matrixArray):
	''' Invert all the square sub-matrices in a numpy array '''
	# Look into numpy to see if there is a way to ignore
	# all the repeated sanity checks, and do them ourselves, once
	return np.array([np.linalg.inv(a) for a in matrixArray])

def applyReference(pts, inv):
	'''
	Given a shape and an array of pre-inverted
	per-point matrices return the deltas
	'''
	preSize = pts.shape[-1]
	if inv.shape[-2] > pts.shape[-1]:
		oneShape = list(pts.shape)
		oneShape[-1] = inv.shape[-2] - pts.shape[-1]
		pts = np.concatenate((pts, np.ones(oneShape)), axis=-1)

	# Return the 3d points
	return np.einsum('ij,ijk->ik', pts, inv)[..., :preSize]

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
	shapes = getSampleArray(abcMesh)

	print "Done Loading"

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

def loadSimplex(shapePath):
	''' Load and parse all the data from a simplex file '''
	iarch = IArchive(str(shapePath))
	print "Opening File:", iarch

	jsString = loadJSString(iarch)
	shapes = loadSmpx(iarch)
	del iarch

	simplex = Simplex()
	simplex.loadJSON(jsString)
	solver = PySimplex(jsString)

	# return as delta shapes
	restIdx = simplex.shapes.index(simplex.restShape)
	restPts = shapes[restIdx]
	shapes = shapes - restPts[None, ...] # reshape for broadcasting

	return jsString, simplex, solver, shapes, restPts

def _writeSimplex(oarch, name, jsString, faces, counts, newShapes, pBar=None):
	''' Separate the writer from oarch creation so garbage
	collection *hopefully* works as expected
	'''
	par = OXform(oarch.getTop(), name)
	props = par.getSchema().getUserProperties()
	prop = OStringProperty(props, "simplex")
	prop.setValue(str(jsString))
	abcMesh = OPolyMesh(par, name)
	schema = abcMesh.getSchema()

	if pBar is not None:
		pBar.setLabelText('Writing Corrected Simplex')
		pBar.setMaximum(len(newShapes))

	for i, newShape in enumerate(newShapes):
		if pBar is not None:
			pBar.setValue(i)
			QApplication.processEvents()
		else:
			print "Writing {0: 3d} of {1}\r".format(i, len(newShapes)),

		verts = mkSampleVertexPoints(newShape)
		abcSample = OPolyMeshSchemaSample(verts, faces, counts)
		schema.set(abcSample)
	if pBar is None:
		print "Writing {0: 3d} of {1}".format(len(newShapes), len(newShapes))

def writeSimplex(inPath, outPath, newShapes, name='Face', pBar=None):
	''' Write a simplex file with new shapes '''
	iarch = IArchive(str(inPath))
	jsString = loadJSString(iarch)
	faces, counts = loadMesh(iarch)
	del iarch

	oarch = OArchive(str(outPath)) # alembic does not like unicode filepaths
	try:
		_writeSimplex(oarch, name, jsString, faces, counts, newShapes, pBar)
	finally:
		del oarch
		gc.collect()

def checkMatch(checkA, checkB, tol=1.0e-4):
	'''
	Debug function to check if two arrays are matching
	If they don't, we print some extra info about where
	'''
	isClose = np.isclose(checkA, checkB, atol=tol)
	ret = np.all(isClose)
	if not ret:
		print np.where(np.invert(isClose))
	return ret


#########################################################################
####                        Deform Reference                         ####
#########################################################################

def _buildSolverInputs(simplex, item, value, indexBySlider):
	'''
	Build an input vector for the solver that will
	produce a required progression value on an item
	'''
	inVec = [0.0] * len(simplex.sliders)
	if isinstance(item, Slider):
		inVec[indexBySlider[item]] = value
		return inVec
	elif isinstance(item, Combo):
		for pair in item.pairs:
			inVec[indexBySlider[pair.slider]] = pair.value * abs(value)
		return inVec
	else:
		raise ValueError("Not a slider or combo. Got type {0}: {1}".format(type(item), item))

def buildFullShapes(simplex, shapes, allPts, solver, restPts, pBar=None):
	'''
	Given shape inputs, build the full output shape from the deltas
	We use shapes here because a shape implies both the progression
	and the value of the inputs (with a little figuring)
	'''
	###########################################
	# Manipulate all the input lists and caches
	indexBySlider = {s: i for i, s in enumerate(simplex.sliders)}
	indexByShape = {s: i for i, s in enumerate(simplex.shapes)}
	floaters = set(simplex.getFloatingShapes())
	floatIdxs = set([indexByShape[s] for s in floaters])

	shapeDict = {}
	for item in itertools.chain(simplex.sliders, simplex.combos):
		for pair in item.prog.pairs:
			if not pair.shape.isRest:
				shapeDict[pair.shape] = (item, pair.value)

	######################
	# Actually do the work
	vecByShape = {} # store this for later use
	ptsByShape = {}

	if pBar is not None:
		pBar.setMaximum(len(shapes))
		pBar.setValue(0)
		QApplication.processEvents()

	for i, shape in enumerate(shapes):
		if pBar is not None:
			pBar.setValue(i)
			QApplication.processEvents()
		else:
			print "Building {0} of {1}\r".format(i+1, len(shapes)),

		item, value = shapeDict[shape]
		inVec = _buildSolverInputs(simplex, item, value, indexBySlider)
		outVec = solver.solve(inVec)
		if shape not in floaters:
			for fi in floatIdxs:
				outVec[fi] = 0.0
		outVec = np.array(outVec)
		outVec[np.where(np.isclose(outVec, 0))] = 0
		outVec[np.where(np.isclose(outVec, 1))] = 1
		vecByShape[shape] = outVec
		pts = np.dot(outVec, allPts.transpose((1, 0, 2)))
		ptsByShape[shape] = pts + restPts
	if pBar is None:
		print

	return ptsByShape, vecByShape

def collapseFullShapes(simplex, allPts, ptsByShape, vecByShape, pBar=None):
	'''
	Given a set of shapes that are full-on shapes (not just deltas)
	Collapse them back into deltas in the simplex shape list
	'''
	#######################
	# Manipulate all the input lists and caches
	#indexBySlider = {s: i for i, s in enumerate(simplex.sliders)}
	indexByShape = {s: i for i, s in enumerate(simplex.shapes)}
	floaters = set(simplex.getFloatingShapes())
	#floatIdxs = set([indexByShape[s] for s in floaters])
	newPts = np.copy(allPts)

	# Order the combos by depth, and split out the floaters
	allDFirst = sorted(simplex.combos[:], key=lambda x: len(x.pairs))
	dFirst, dFloat = [], []
	for c in allDFirst:
		app = dFloat if c.isFloating() else dFirst
		app.append(c)

	# first do the sliders
	for item in simplex.sliders:
		for pair in item.prog.pairs:
			if pair.shape in ptsByShape:
				idx = indexByShape[pair.shape]
				newPts[idx] = ptsByShape[pair.shape]

	# Get the max number of iterations
	mxcount = 0
	for c in itertools.chain(dFirst, dFloat):
		for pair in c.prog.pairs:
			if pair.shape in ptsByShape:
				mxcount += 1

	if pBar is not None:
		pBar.setValue(0)
		pBar.setMaximum(mxcount)
		pBar.setLabelText("Building Corrected Deltas")
		QApplication.processEvents()

	# Then go through all the combos in order
	vcount = 0
	for c in itertools.chain(dFirst, dFloat):

		for pair in c.prog.pairs:
			if pair.shape in ptsByShape:
				if pBar is not None:
					pBar.setValue(vcount)
					QApplication.processEvents()
				else:
					print "Collapsing {0} of {1}\r".format(vcount + 1, mxcount),
				vcount += 1

				idx = indexByShape[pair.shape]
				outVec = vecByShape[pair.shape]
				outVec[idx] = 0.0 # turn off the influence of the current shape
				comboBase = np.dot(outVec, newPts.transpose((1, 0, 2)))
				comboSculpt = ptsByShape[pair.shape]
				newPts[idx] = comboSculpt - comboBase
	if pBar is None:
		print

	return newPts

def applyCorrectives(simplex, allShapePts, restPts, solver, shapes, refIdxs, references, pBar=None):
	'''
	Loop over the shapes and references, apply them, and return a new np.array
	of shape points

	simplex: Simplex system
	allShapePts: deltas per shape
	restPts: The rest point positions
	solver: The Python Simplex solver object
	shapes: The simplex shape objects we care about
	refIdxs: The reference index per shape
	references: A list of matrix-per-points
	'''
	# The rule of thumb is "THE SHAPE IS ALWAYS A DELTA"

	if pBar is not None:
		pBar.setLabelText("Inverting References")
		pBar.setValue(0)
		pBar.setMaximum(len(references))
		QApplication.processEvents()
	else:
		print "Inverting References"

	inverses = []
	for i, r in enumerate(references):
		if pBar is not None:
			pBar.setValue(i)
			QApplication.processEvents()
		inverses.append(invertAll(r))

	if pBar is not None:
		pBar.setLabelText("Extracting Uncorrected Shapes")
		QApplication.processEvents()
	else:
		print "Building Full Shapes"
	ptsByShape, vecByShape = buildFullShapes(simplex, shapes, allShapePts, solver, restPts, pBar)

	if pBar is not None:
		pBar.setLabelText("Correcting")
		QApplication.processEvents()
	else:
		print "Correcting"
	newPtsByShape = {}
	for shape, refIdx in zip(shapes, refIdxs):
		inv = inverses[refIdx]
		pts = ptsByShape[shape]
		newPts = applyReference(pts, inv)
		newPtsByShape[shape] = newPts

	newShapePts = collapseFullShapes(simplex, allShapePts, newPtsByShape, vecByShape, pBar)
	newShapePts = newShapePts + restPts[None, ...]

	return newShapePts

def readAndApplyCorrectives(inPath, namePath, refPath, outPath, pBar=None):
	'''
	Read the provided files, apply the correctives, then output a new file

	Arguments:
		inPath: The input .smpx file
		namePath: A file correlating the shape names, and the reference
			indices. Separated by ; with one entry per line
		refPath: The reference matrices per point of deformation.
			Created by npArray.dump(refPath)
		outPath: The output .smpx filepath
	'''

	if pBar is not None:
		pBar.setLabelText("Reading reference data")
		QApplication.processEvents()

	jsString, simplex, solver, allShapePts, restPts = loadSimplex(inPath)
	with open(namePath, 'r') as f:
		nr = f.read()
	nr = [i.split(';') for i in nr.split('\n') if i]
	names, refIdxs = zip(*nr)
	refIdxs = map(int, refIdxs)
	refs = np.load(refPath)
	simplex = Simplex()
	simplex.loadJSON(jsString)

	shapeByName = {i.name: i for i in simplex.shapes}
	shapes = [shapeByName[n] for n in names]
	newPts = applyCorrectives(simplex, allShapePts, restPts, solver, shapes, refIdxs, refs, pBar)
	writeSimplex(inPath, outPath, newPts, pBar=pBar)
	print "DONE"


