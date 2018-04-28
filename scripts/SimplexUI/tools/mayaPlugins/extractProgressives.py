import maya.cmds as cmds
from Qt.QtWidgets import QAction
from ..constants import THING_ROLE, C_SHAPE_TYPE, S_SLIDER_TYPE
from ..utils import toPyObject

def register(window, menu):
	extractProgressivesACT = QAction("Extract Progressive", window)
	menu.addAction(extractProgressivesACT)
	extractProgressivesACT.triggered.connect(extractProgressivesInterface)

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

