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

import blurdev
import gc, os

from alembic.Abc import IArchive, OArchive, OStringProperty
from alembic.AbcGeom import IXform, IPolyMesh, OPolyMesh, OXform, OPolyMeshSchemaSample

def _writeSimplex(oarch, name, jsString, faces, counts, newShapes):
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
	top = iarch.getTop()
	par = top.children[0]
	par = IXform(top, par.getName())

	systemSchema = par.getSchema()
	props = systemSchema.getUserProperties()
	prop = props.getProperty("simplex")
	jsString = prop.getValue()
	return jsString

def loadSmpx(iarch):
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
	top = iarch.getTop()
	par = top.children[0]
	par = IXform(top, par.getName())

	abcMesh = par.children[0]
	abcMesh = IPolyMesh(par, abcMesh.getName())

	sch = abcMesh.getSchema()
	faces = sch.getFaceIndicesProperty().samples[0]
	counts = sch.getFaceCountsProperty().samples[0]

	return faces, counts

def hdf5Convert(inPath, outPath, ogawa=False):
	'''Load and parse all the data from a simplex file

	Parameters
	----------
	inPath : str
		The input .smpx file path
	outPath : str
		The output .smpx file path
	ogawa : bool
		Whether to write out in Ogawa format. Defaults False

	Returns
	-------

	'''
	if not os.path.isfile(str(inPath)):
		raise IOError("File does not exist: " + str(inPath))
	iarch = IArchive(str(inPath))
	jsString = loadJSString(iarch)
	shapes = loadSmpx(iarch)
	faces, counts = loadMesh(iarch)
	del iarch

	oarch = OArchive(str(outPath), ogawa) # alembic does not like unicode filepaths
	try:
		_writeSimplex(oarch, 'Face', jsString, faces, counts, shapes)
	finally:
		del oarch
		gc.collect()

if __name__ == '__main__':
	inPath = r'D:\Users\tyler\Desktop\Head_Morphs_Main_Head-Face_v0010.smpx'
	outPath = r'D:\Users\tyler\Desktop\Head_ogawa.smpx'
	hdf5Convert(inPath, outPath, ogawa=True)

