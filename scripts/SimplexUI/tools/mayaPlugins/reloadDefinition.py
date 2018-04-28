import maya.cmds as cmds
from Qt.QtWidgets import QAction

def register(window, menu):
	reloadDefinitionACT = QAction("Reload Definition", window)
	menu.addAction(reloadDefinitionACT)
	reloadDefinitionACT.triggered.connect(reloadDefinitionInterface)

def reloadDefinitionInterface(self):
	reloadDefinition(self.system)

def reloadDefinition(system):
	system.DCC.setSimplexString(
		system.DCC.op,
		system.simplex.dump()
	)

