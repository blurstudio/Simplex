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

from maya import cmds
from maya import OpenMaya as om
import numpy as np
from ctypes import c_float

def setPose(pvp, multiplier):
	'''Set a percentage of a pose

	Parameters
	----------
	pvp :
		
	multiplier :
		

	Returns
	-------

	'''
	for prop, val in pvp:
		cmds.setAttr(prop, val*multiplier)

def resetPose(pvp):
	'''rest everything back to rest

	Parameters
	----------
	pvp :
		

	Returns
	-------

	'''
	for prop, val in pvp:
		cmds.setAttr(prop, 0)

def _getDagPath(mesh):
	'''

	Parameters
	----------
	mesh :
		

	Returns
	-------

	'''
	sl = om.MSelectionList()
	sl.add(mesh)
	dagPath = om.MDagPath()
	sl.getDagPath(0, dagPath)
	return dagPath

def _getMayaPoints(meshFn):
	'''

	Parameters
	----------
	meshFn :
		

	Returns
	-------

	'''
	rawPts = meshFn.getRawPoints()
	ptCount = meshFn.numVertices()
	cta = (c_float * 3 * ptCount).from_address(int(rawPts))
	out = np.ctypeslib.as_array(cta)
	out = np.copy(out)
	out = out.reshape((-1, 3))
	return out

def getShiftValues(thing):
	'''Get the rest and 1-move arrays from a thing

	Parameters
	----------
	thing :
		

	Returns
	-------

	'''
	dp = _getDagPath(thing)
	meshFn = om.MFnMesh(dp)
	allVerts = '{0}.vtx[*]'.format(thing)

	zero = _getMayaPoints(meshFn)
	cmds.move(1, 0, 0, allVerts, relative=1, objectSpace=1)
	oneX = _getMayaPoints(meshFn)
	cmds.move(-1, 1, 0, allVerts, relative=1, objectSpace=1)
	oneY = _getMayaPoints(meshFn)
	cmds.move(0, -1, 1, allVerts, relative=1, objectSpace=1)
	oneZ = _getMayaPoints(meshFn)
	cmds.move(0, 0, -1, allVerts, relative=1, objectSpace=1)

	return zero, oneX, oneY, oneZ


