import maya.cmds as cmds
from ...Qt.QtWidgets import QAction
from functools import partial

def registerTool(window, menu):
	reloadDefinitionACT = QAction("Reload Definition", window)
	menu.addAction(reloadDefinitionACT)
	reloadDefinitionACT.triggered.connect(partial(reloadDefinitionInterface, window))

def reloadDefinitionInterface(window):
	reloadDefinition(window.simplex)

def reloadDefinition(simplex):
	simplex.DCC.setSimplexString(
		simplex.DCC.op,
		simplex.dump()
	)

