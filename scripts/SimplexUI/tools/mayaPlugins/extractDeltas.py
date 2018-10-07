import maya.cmds as cmds
from Qt.QtWidgets import QAction

def register(window, menu):
	extractDeltasACT = QAction("Extract Deltas", window)
	menu.addAction(extractDeltasACT)
	extractDeltasACT.triggered.connect(extractDeltasInterface)

	applyDeltasACT = QAction("Apply Deltas", window)
	menu.addAction(applyDeltasACT)
	applyDeltasACT.triggered.connect(applyDeltasInterface)


def extractDeltasInterface(self):
	if not self.system:
		return
	sel = cmds.ls(sl=True)
	restShape = self.system.simplex.buildRestShape()
	rest = self.system.extractShape(restShape, live=False, offset=0.0)
	if len(sel) >= 2:
		extractDeltas(sel[0], sel[1], rest)
	cmds.delete(rest)

def extractDeltas(original, sculpted, rest):
	'''
	Get the difference between the original and the sculpted meshes
	Then apply that difference to the rest
	'''
	extractedDeltas = cmds.duplicate(rest, name="extractedDeltas")[0]
	deltaBlends = cmds.blendShape(sculpted, original, extractedDeltas)
	cmds.blendShape(deltaBlends, edit=True, weight=((0, 1), (1, -1)))

def applyDeltasInterface(self):
	if not self.system:
		return
	sel = cmds.ls(sl=True)
	restShape = self.system.simplex.buildRestShape()
	rest = self.system.extractShape(restShape, live=False, offset=0.0)
	if len(sel) >= 2:
		applyDeltas(sel[0], sel[1], rest)
	cmds.delete(rest)

def applyDeltas(deltaMesh, targetMesh, rest):
	'''
	Apply the extracted deltas from `extractDeltas` to another object
	'''
	# Create a temporary mesh to hold the sum of the delta and our target
	outputMesh = cmds.duplicate(rest, name='deltaMesh')

	# create that 'sum', and delete the history
	blendNode = cmds.blendShape(deltaMesh, targetMesh, outputMesh)[0]
	cmds.blendShape(blendNode, edit=True, weight=((0, 1), (1, 1)))
	cmds.delete(outputMesh, constructionHistory=True)

	# Connect that 'sum' back into our target, and delete the temp mesh
	cmds.blendShape(outputMesh, targetMesh)
	cmds.delete(outputMesh)


