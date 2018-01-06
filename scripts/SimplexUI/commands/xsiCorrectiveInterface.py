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

from dcc.xsi import xsi, constants
from dcc.xsi.ice import ICETree #pylint:disable=import-error

def setPose(pvp, multiplier):
	''' Set a percentage of a pose '''
	for prop, val in pvp:
		xsi.setValue(prop, val * multiplier)

def resetPose(pvp):
	''' reset everything back to rest '''
	for prop, val in pvp:
		xsi.setValue(prop, 0)

def getMeshVerts(mesh):
	vts = mesh.ActivePrimitive.Geometry.Points.PositionArray
	return zip(*vts)

def buildTree(mesh):
	iceTree = ICETree(None, mesh, 'Test', constants.siConstructionModePrimaryShape)

	getter = iceTree.addGetDataNode("Self.PointPosition")
	adder = iceTree.addNode('Add')
	vector = iceTree.addNode('ScalarTo3DVector')
	setter = iceTree.addSetDataNode("Self.PointPosition")

	getter.value.connect(adder.value1)
	vector.vector.connect(adder.value2)
	adder.result.connect(setter.Value)
	iceTree.connect(setter.Execute, 2)

	return iceTree, vector

def getShiftValues(mesh):
	tree, vector = buildTree(mesh)
	zero = getMeshVerts(mesh)

	vector.x.value = 1.0
	oneX = getMeshVerts(mesh)
	vector.x.value = 0.0

	vector.y.value = 1.0
	oneY = getMeshVerts(mesh)
	vector.y.value = 0.0

	vector.z.value = 1.0
	oneZ = getMeshVerts(mesh)
	vector.z.value = 0.0

	tree.delete()
	return zero, oneX, oneY, oneZ



