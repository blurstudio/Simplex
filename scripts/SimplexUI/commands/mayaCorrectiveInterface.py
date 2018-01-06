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

from maya import cmds #pylint:disable=import-error,wrong-import-position
import numpy as np

def setPose(pvp, multiplier):
	''' Set a percentage of a pose '''
	for prop, val in pvp:
		cmds.setAttr(prop, val*multiplier)

def resetPose(pvp):
	''' rest everything back to rest '''
	for prop, val in pvp:
		cmds.setAttr(prop, 0)

def getShiftValues(thing):
	''' Get the rest and 1-move arrays from a thing '''
	allVerts = '{0}.vtx[*]'.format(thing)

	zero = np.array(cmds.xform(allVerts, translation=1, query=1)).reshape((-1, 3))
	cmds.move(1, 0, 0, allVerts, relative=1, objectSpace=1)
	oneX = np.array(cmds.xform(allVerts, translation=1, query=1)).reshape((-1, 3))
	cmds.move(-1, 1, 0, allVerts, relative=1, objectSpace=1)
	oneY = np.array(cmds.xform(allVerts, translation=1, query=1)).reshape((-1, 3))
	cmds.move(0, -1, 1, allVerts, relative=1, objectSpace=1)
	oneZ = np.array(cmds.xform(allVerts, translation=1, query=1)).reshape((-1, 3))
	cmds.move(0, 0, -1, allVerts, relative=1, objectSpace=1)

	return zero, oneX, oneY, oneZ

