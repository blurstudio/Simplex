from SimplexUI.Qt.QtWidgets import QAction

def registerTool(window, menu):
	editFalloffsACT = QAction("Edit Falloffs", window)
	menu.addAction(editFalloffsACT)
	editFalloffsACT.triggered.connect(window.showFalloffDialog)

