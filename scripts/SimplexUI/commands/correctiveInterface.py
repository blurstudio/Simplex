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

import blurdev
from applyCorrectives import loadJSString
from alembic.Abc import IArchive
from Simplex2.interface import Simplex
from SimplexUI.Qt.QtWidgets import QApplication
import numpy as np

try:
	from mayaCorrectiveInterface import setPose, resetPose, getShiftValues
	dcc = 'maya'
except ImportError:
	from xsiCorrectiveInterface import setPose, resetPose, getShiftValues
	dcc = 'xsi'

def getRefForPoses(mesh, poses, multiplier):
	''' Given a set of poses and a multiplier, get the reference '''
	for pose in poses:
		setPose(pose, multiplier)

	ref = getDeformReference(mesh)

	for pose in poses:
		resetPose(pose)
	return ref

def getDeformReference(mesh):
	''' Build the 4x4 deformation reference matrices given a mesh '''
	zero, oneX, oneY, oneZ = getShiftValues(mesh)

	excess = np.ones(len(oneX)).reshape(-1, 1)
	oneX = np.concatenate((np.array(oneX), excess), axis=1)
	oneY = np.concatenate((np.array(oneY), excess), axis=1)
	oneZ = np.concatenate((np.array(oneZ), excess), axis=1)
	zero = np.concatenate((np.array(zero), excess), axis=1)

	dx = oneX - zero
	dy = oneY - zero
	dz = oneZ - zero

	# Maya has numpy 1.09, but np.stack comes from 1.10
	#mats = np.stack((dx, dy, dz, zero), axis=1)

	# Make the new axis to concatenate on
	zero = zero[:, None]
	dx = dx[:, None]
	dy = dy[:, None]
	dz = dz[:, None]
	mats = np.concatenate((dx, dy, dz, zero), axis=1)
	return mats

def buildCorrectiveReferences(mesh, simplex, poses, sliders, pBar=None):
	'''
	Take correlated poses and sliders, and expand down the
	simplex combo tree, building references for each required shape

	Inputs:
		simplex <SimplexSystem> : A simplex system
		solver <PySimplex> : An instantiated simplex value solver
		poses <Prop/Value pair lists> : Different rig poses
		shapes <SimplexShapes> : Shape objects correlated to the poses
	'''
	# cache the pose search

	# Pre-cache the combo search
	allCombosBySliderValue = {}
	for c in simplex.combos:
		for p in c.pairs:
			allCombosBySliderValue.setdefault((p.slider, p.value), []).append(c)

	# This is only my subset set of downstreams
	# Get the downstreams by slider and value
	sliderValuesByCombo = {}
	for slider in sliders:
		for p in slider.prog.pairs:
			combos = allCombosBySliderValue.get((slider, p.value), [])
			for combo in combos:
				sliderValuesByCombo.setdefault(combo, []).append((slider, p.value))

	#out = []
	refCache = {}
	refs, shapes, refIdxs = [], [], []

	# get the slider outputs
	if pBar is not None:
		pBar.setLabelText("Building Shape References")
		pBar.setValue(0)
		mv = 0
		for slider in sliders:
			for p in slider.prog.pairs:
				if not p.shape.isRest:
					mv += 1
		pBar.setMaximum(mv)
		QApplication.processEvents()

	poseBySlider = {}
	for slider, pose in zip(sliders, poses):
		poseBySlider[slider] = pose
		for p in slider.prog.pairs:
			if not p.shape.isRest:
				if pBar is not None:
					pBar.setValue(pBar.value())
					QApplication.processEvents()
				cacheKey = frozenset([(slider, p.value)])
				if cacheKey in refCache:
					idx = refCache[cacheKey]
					refIdxs.append(idx)
				else:
					ref = getRefForPoses(mesh, [pose], p.value)
					refIdxs.append(len(refs))
					refCache[cacheKey] = len(refs)
					refs.append(ref)
				shapes.append(p.shape)

	# Get the combo outputs
	if pBar is not None:
		pBar.setLabelText("Building Combo References")
		pBar.setValue(0)
		mv = 0
		for combo in sliderValuesByCombo.iterkeys():
			for p in combo.prog.pairs:
				if not p.shape.isRest:
					mv += 1
		pBar.setMaximum(mv)
		QApplication.processEvents()

	for combo, sliderVals in sliderValuesByCombo.iteritems():
		#components = frozenset(sliderVals)
		poses = [poseBySlider[s] for s, _ in sliderVals]
		for p in combo.prog.pairs:
			if not p.shape.isRest:
				if pBar is not None:
					pBar.setValue(pBar.value())
					QApplication.processEvents()

				cacheKey = frozenset(sliderVals)
				if cacheKey in refCache:
					idx = refCache[cacheKey]
					refIdxs.append(idx)
				else:
					ref = getRefForPoses(mesh, poses, p.value)
					refIdxs.append(len(refs))
					refCache[cacheKey] = len(refs)
					refs.append(ref)
				shapes.append(p.shape)

	return np.array(refs), shapes, refIdxs

def outputCorrectiveReferences(outNames, outRefs, simplex, mesh, poses, sliders, pBar=None):
	'''
	Output the proper files for an external corrective application

	Arguments:
		outNames: The filepath for the output shape and reference indices
		outRefs: The filepath for the deformation references
		simplex: A simplex system
		mesh: The mesh object to deform
		poses: Lists of parameter/value pairs. Each list corresponds to a slider
		sliders: The simplex sliders that correspond to the poses
	'''
	refs, shapes, refIdxs = buildCorrectiveReferences(mesh, simplex, poses, sliders, pBar)

	if pBar is not None:
		pBar.setLabelText('Writing Names')
		QApplication.processEvents()
	nameWrite = ['{};{}'.format(s.name, r) for s, r, in zip(shapes, refIdxs)]
	with open(outNames, 'w') as f:
		f.write('\n'.join(nameWrite))

	if pBar is not None:
		pBar.setLabelText('Writing References')
		QApplication.processEvents()
	refs.dump(outRefs)


