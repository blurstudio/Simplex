import maya.cmds as cmds
from Qt.QtWidgets import QAction

def register(window, menu):
	extractDeltasACT = QAction("Extract Deltas", window)
	menu.addAction(extractDeltasACT)
	extractDeltasACT.triggered.connect(extractDeltasInterface)

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

