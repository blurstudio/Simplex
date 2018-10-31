import maya.cmds as cmds
from SimplexUI.Qt.QtWidgets import QAction
from SimplexUI.interfaceItems import Slider
from SimplexUI.interfaceModel import coerceIndexToType

def registerTool(window, menu):
	extractProgressivesACT = QAction("Extract Progressive", window)
	menu.addAction(extractProgressivesACT)
	kick = lambda: extractProgressivesInterface(window)
	extractProgressivesACT.triggered.connect(kick)

def registerContext(tree, clickIdx, indexes, menu):
	window = tree.window()
	live = window.uiLiveShapeConnectionACT.isChecked()
	sliders = coerceIndexToType(indexes, Slider)

	multis = []
	for slidx in sliders:
		slider = slidx.model().itemFromIndex(slidx)
		if len(slider.prog.pairs) > 2:
			multis.append(slidx)

	if multis:
		extractACT = menu.addAction('Extract Progressive')
		kick = lambda: extractProgressivesContext(multis, live)
		extractACT.triggered.connect(kick)
		return True
	return False

def extractProgressivesContext(indexes, live):
	sliders = [idx.model().itemFromIndex(idx) for idx in indexes]
	sliders = list(set(sliders))
	for sli in sliders:
		sli.extractProgressive(live=live)

def extractProgressivesInterface(window):
	live = window.uiLiveShapeConnectionACT.isChecked()
	indexes = window.uiSliderTREE.getSelectedIndexes()
	indexes = coerceIndexToType(indexes, Slider)
	sliders = [idx.model().itemFromIndex(idx) for idx in indexes]
	sliders = list(set(sliders))
	for sli in sliders:
		sli.extractProgressive(live=live)

