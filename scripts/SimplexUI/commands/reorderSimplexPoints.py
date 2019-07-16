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

""" Transfer shapes between mismatched models

Given a 1:1 point correspondence, transfer the shapes from one
geometry to another. Figuring out the correspondence is currently
outside the scope of this tool, though I may release one later.

The point correspondence should look like an unordered range, and
will be used as a numpy index to get the output values. It's also
possible to invert the range if you think you've got it backwards
"""
#pylint:disable=wrong-import-position
import gc, os
from alembic.Abc import IArchive, OArchive, OStringProperty
from alembic.AbcGeom import IPolyMesh, OPolyMesh, IXform, OXform, OPolyMeshSchemaSample

from alembicCommon import mkSampleVertexPoints, mkSampleIntArray, getSampleArray


import numpy as np
from imathnumpy import arrayToNumpy #pylint:disable=no-name-in-module
from .. import OGAWA

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

def getShapes(iarch):
	''' Load the animated shape data from an alembic archive '''
	top = iarch.getTop()
	ixfo = IXform(top, top.children[0].getName())
	mesh = IPolyMesh(ixfo, ixfo.children[0].getName())

	shapes = getSampleArray(mesh)
	return shapes

def getMesh(iarch):
	''' Load the static mesh data from an alembic archive '''
	top = iarch.getTop()
	par = top.children[0]
	par = IXform(top, par.getName())

	abcMesh = par.children[0]
	abcMesh = IPolyMesh(par, abcMesh.getName())

	sch = abcMesh.getSchema()
	faces = sch.getFaceIndicesProperty().samples[0]
	counts = sch.getFaceCountsProperty().samples[0]

	return faces, counts


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

		verts = mkSampleVertexPoints(newShape)
		abcSample = OPolyMeshSchemaSample(verts, faces, counts)
		schema.set(abcSample)
	print "Writing {0: 3d} of {1}".format(len(newShapes), len(newShapes))

def reorderSimplexPoints(sourcePath, matchPath, outPath, invertMatch=False):
	''' Transfer shape data from the sourcePath using the numpy int array
	at matchPath to make the final output at outPath
	'''
	print "Loading Simplex"
	if not os.path.isfile(str(sourcePath)):
		raise IOError("File does not exist: " + str(sourcePath))
	sourceArch = IArchive(str(sourcePath)) # because alembic hates unicode
	sourceShapes = getShapes(sourceArch)
	jsString = loadJSString(sourceArch)
	sFaces, counts = getMesh(sourceArch)
	sFaces = np.array(sFaces)

	print "Loading Correspondence"
	c = np.load(matchPath)
	c = c[c[:, 0].argsort()].T[1]
	ci = c.argsort()
	if invertMatch:
		ci, c = c, ci

	print "Reordering"
	targetShapes = sourceShapes[:, c, :]
	faces = mkSampleIntArray(ci[sFaces])

	print "Writing"
	oarch = OArchive(str(outPath), OGAWA) # alembic does not like unicode filepaths
	try:
		_writeSimplex(oarch, 'Face', jsString, faces, counts, targetShapes)
	finally:
		del oarch
		gc.collect()


if __name__ == "__main__":
	import os


	base = r'K:\Departments\CharacterModeling\Library\Head\MaleHead_Standard\005'
	_sourcePath = os.path.join(base,'HeadMaleStandard_High_Split_BadOrder.smpx')
	_matchPath = os.path.join(base, 'Reorder.np')
	_outPath = os.path.join(base,'HeadMaleStandard_High_Split2.smpx')

	reorderSimplexPoints(_sourcePath, _matchPath, _outPath)






