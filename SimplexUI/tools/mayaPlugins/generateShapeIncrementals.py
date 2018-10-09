import maya.cmds as cmds
from Qt.QtWidgets import QAction, QInputDialog
from SimplexUI.interfaceItems import Slider, Combo
from SimplexUI.interfaceModel import coerceIndexToType

def registerTool(window, menu):
	generateShapeIncrementalsACT = QAction("Generate Incrementals", window)
	menu.addAction(generateShapeIncrementalsACT)
	kick = lambda: generateShapeIncrementalsInterface(window)
	generateShapeIncrementalsACT.triggered.connect(kick)

def registerContext(tree, indexes, menu):
	window = tree.window()
	sliders = coerceIndexToType(indexes, Slider)
	combos = coerceIndexToType(indexes, Combo)
	multis = []
	for grp in [sliders, combos]:
		for idx in grp:
			item = idx.model().itemFromIndex(idx)
			if len(item.prog.pairs) == 2:
				multis.append(idx)

	if not multis:
		return False

	extractACT = menu.addAction('Generate Incrementals')
	kick = lambda: generateShapeIncrementalsContext(multis, window)
	extractACT.triggered.connect(kick)
	return True

def generateShapeIncrementalsContext(indexes, window):
	increments = QInputDialog.getInt(window, "Increments", "Number of Increments", 4, 1, 100)
	if increments is None:
		return

	for idx in indexes:
		slider = idx.model().itemFromIndex(idx)
		rest = None
		target = None
		maxval = -1.0
		for pp in slider.progression.pairs:
			if pp.shape.isRest:
				rest = pp.shape
			elif abs(pp.value) > maxval:
				target = pp.shape
		restObj = slider.extractShape(rest, live=False)
		tarObj = slider.extractShape(target)
		generateShapeIncrementals(restObj, tarObj, increments)

def generateShapeIncrementalsInterface(window):
	sel = cmds.ls(sl=True)[0]
	if len(sel) >= 2:
		increments = QInputDialog.getInt(window, "Increments", "Number of Increments", 4, 1, 100)
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

