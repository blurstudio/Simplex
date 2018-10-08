import maya.cmds as cmds
from Qt.QtWidgets import QAction
from SimplexUI.constants import THING_ROLE, C_SHAPE_TYPE, S_SLIDER_TYPE
from SimplexUI.utils import toPyObject

def registerTool(window, menu):
	extractProgressivesACT = QAction("Extract", window)
	menu.addAction(extractProgressivesACT)
	extractProgressivesACT.triggered.connect(extractProgressivesInterface)

'''
def menuFilter(window, menu, indexes):
	extractACT = QAction("Extract", window)
	menu.addAction(extractACT)
	extractACT.triggered.connect(window)

	if not isinstance(item, (Slider, Combo)):
		return
	live = window.uiLiveShapeConnectionACT.isChecked()
	item.extractProgressive()


	sliders = self.uiSliderTREE.getSelectedItems(Slider)
	combos = self.uiSliderTREE.getSelectedItems(Combo)
	
	for slider in sliders:
		slider.extractProgressive()
'''






def extractProgressivesInterface(self):
	if not self.system:
		return
	live = self.window.uiLiveShapeConnectionACT.isChecked()

	sliderIndexes = self.window.getFilteredChildSelection(self.window.uiSliderTREE, S_SLIDER_TYPE)
	sliders = []
	for i in sliderIndexes:
		if not i.isValid():
			continue
		slider = toPyObject(i.model().data(i, THING_ROLE))
		sliders.append(slider)
	extractProgressives(self.system, sliders, live)

def extractProgressives(system, sliders, live):
	for slider in sliders:
		system.extractProgressive(slider, live, 10.0)

