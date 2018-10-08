import maya.cmds as cmds
from Qt.QtWidgets import QAction
from SimplexUI.constants import THING_ROLE, C_SHAPE_TYPE, S_SLIDER_TYPE
from SimplexUI.mayaInterface import disconnected
from SimplexUI.utils import toPyObject

def registerTool(window, menu):
	tweakMixACT = QAction("Tweak Mix", window)
	menu.addAction(tweakMixACT)
	tweakMixACT.triggered.connect(tweakMixInterface)

def tweakMixInterface(self):
	if not self.system:
		return
	live = self.window.uiLiveShapeConnectionACT.isChecked()

	comboIndexes = self.window.getFilteredChildSelection(self.window.uiComboTREE, C_SHAPE_TYPE)
	comboShapes = []
	for i in comboIndexes:
		if not i.isValid():
			continue
		progPair = toPyObject(i.model().data(i, THING_ROLE))
		combo = progPair.prog.parent
		if not progPair.shape.isRest:
			comboShapes.append((combo, progPair.shape))

	tweakMix(self.system, comboShapes, live)


def tweakMix(system, comboShapes, live):
	# first extract the rest shape non-live
	restGeo = system.extractShape(system.simplex.restShape, live=False, offset=0)

	floatShapes = system.simplex.getFloatingShapes()
	floatShapes = [i.thing for i in floatShapes]

	offset = 5
	for combo, shape in comboShapes:
		offset += 5
		geo = system.extractComboShape(combo, shape, live=live, offset=offset)
		# disconnect the controller from the operator
		tweakShapes = []
		with disconnected(system.DCC.op) as sliderCnx:
			# disconnect any float shapes
			with disconnected(floatShapes):
				# zero all slider vals on the op
				for a in sliderCnx.itervalues():
					cmds.setAttr(a, 0.0)

				# set the combo values
				sliderVals = []
				for pair in combo.pairs:
					cmds.setAttr(sliderCnx[pair.slider.thing], pair.value)

				for shape in system.simplex.shapes[1:]: #skip the restShape
					shapeVal = cmds.getAttr(shape.thing)
					if shapeVal != 0.0: # maybe handle floating point errors
						tweakShapes.append((shape, shapeVal))

		tweakMeshes = []
		with disconnected(system.DCC.shapeNode) as shapeCnx:
			for a in shapeCnx.itervalues():
				cmds.setAttr(a, 0.0)
			for tshape, shapeVal in tweakShapes:
				cmds.setAttr(tshape.thing, shapeVal)
				#print "setAttr", tshape.thing, shapeVal
				tweakMesh = cmds.duplicate(system.DCC.mesh, name='{0}_Tweak'.format(tshape.name))[0]
				tweakMeshes.append(tweakMesh)
				cmds.setAttr(tshape.thing, 0.0)

		# Yeah, yeah, this is REALLY ugly, but it's quick and it works
		tempBS = cmds.blendShape(geo, name='Temp_BS')
		cmds.blendShape(tempBS, edit=True, target=(geo, 0, restGeo, 1.0))
		cmds.blendShape(tempBS, edit=True, weight=[(0, 1.0)])
		cmds.delete(geo, constructionHistory=True)

		# build the actual blendshape
		tweakBS = cmds.blendShape(geo, name="Tweak_BS")
		for i, tm in enumerate(tweakMeshes):
			cmds.blendShape(tweakBS, edit=True, target=(geo, i, tm, 1.0))
		tmLen = len(tweakMeshes)
		cmds.blendShape(tweakBS, edit=True, weight=zip(range(tmLen), [1.0]*tmLen))

		cmds.delete(tweakMeshes)
		cmds.delete(restGeo)

