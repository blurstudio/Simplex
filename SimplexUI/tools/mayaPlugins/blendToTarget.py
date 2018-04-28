import maya.cmds as cmds
from Qt.QtWidgets import QAction

def register(window, menu):
	blendToTargetACT = QAction("Blend To Target", window)
	menu.addAction(blendToTargetACT)
	blendToTargetACT.triggered.connect(blendToTargetInterface)

def blendToTargetInterface(self):
	sel = cmds.ls(sl=True)
	if len(sel) >= 2:
		blendToTarget(sel[0], sel[1])

def blendToTarget(source, target):
	''' Quickly blend one object to another '''
	blendAr = cmds.blendShape(source, target)[0]
	cmds.blendShape(blendAr, edit=True, weight=((0, 1)))

