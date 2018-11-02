from Qt.QtWidgets import QAction

def registerTool(window, menu):
	showTraversalsACT = QAction("Show Traversals", window)
	menu.addAction(showTraversalsACT)
	showTraversalsACT.triggered.connect(window.showTraversalDialog)

