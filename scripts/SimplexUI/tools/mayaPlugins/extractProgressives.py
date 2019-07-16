import maya.cmds as cmds
from ...Qt.QtWidgets import QAction
from ...interfaceItems import Slider
from ...interfaceModel import coerceIndexToType
from functools import partial

def registerTool(window, menu):
	extractProgressivesACT = QAction("Extract Progressive", window)
	menu.addAction(extractProgressivesACT)
	extractProgressivesACT.triggered.connect(partial(extractProgressivesInterface, window))

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
		extractACT.triggered.connect(partial(extractProgressivesContext, multis, live))
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

