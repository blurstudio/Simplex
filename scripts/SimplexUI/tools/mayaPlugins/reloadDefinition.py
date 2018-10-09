import maya.cmds as cmds
from Qt.QtWidgets import QAction

def registerTool(window, menu):
	reloadDefinitionACT = QAction("Reload Definition", window)
	menu.addAction(reloadDefinitionACT)
	kick = lambda: reloadDefinitionInterface(window)
	reloadDefinitionACT.triggered.connect(kick)

def reloadDefinitionInterface(window):
	reloadDefinition(window.simplex)

def reloadDefinition(simplex):
	simplex.DCC.setSimplexString(
		simplex.DCC.op,
		simplex.simplex.dump()
	)

