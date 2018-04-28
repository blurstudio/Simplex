import maya.cmds as cmds
from Qt.QtWidgets import QAction, QInputDialog

def register(window, menu):
	generateShapeIncrementalsACT = QAction("Generate Shape Incrementals", window)
	menu.addAction(generateShapeIncrementalsACT)
	generateShapeIncrementalsACT.triggered.connect(generateShapeIncrementalsInterface)

def generateShapeIncrementalsInterface(self):
	sel = cmds.ls(sl=True)[0]
	if len(sel) >= 2:
		# TODO, build an actual UI for this
		increments = QInputDialog.getInt(self.window, "Increments", "Number of Increments", 4, 1, 100)
		if increments is None:
			return
		generateShapeIncrementals(sel[0], sel[1], increments)

def generateShapeIncrementals(startObj, endObj, increments):
	'''
	Pick a start object, then an end object, and define a number of incremental steps
	'''
	shapeDup = cmds.duplicate(endObj, name="shapeDup")
	bs = cmds.blendShape(startObj, shapeDup)

	for i in range(1, increments):
		val = float(increments - i) / increments
		percent = int(float(i) * 100 /increments)
		cmds.blendShape(bs, edit=True, weight=((0, val)))
		cmds.duplicate(shapeDup, name="{0}_{1}".format(endObj, percent))

	cmds.delete(shapeDup)
	cmds.select(endObj)

