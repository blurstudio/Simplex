import os
import maya.cmds as cmds
from ...Qt.QtWidgets import QAction


dn = os.path.dirname
SHELF_DEV_BUTTON = """ 
import os, sys

path = r'{0}'
path = os.path.normcase(os.path.normpath(path))
if sys.path[0] != path:
	sys.path.insert(0, path)

import SimplexUI
if SimplexUI.SIMPLEX_UI is not None:
	try:
		SimplexUI.SIMPLEX_UI.close()
	except RuntimeError:
		# In case I closed it myself
		pass
del SimplexUI

for key, value in sys.modules.items():
	try:
		packPath = value.__file__
	except AttributeError:
		continue

	packPath = os.path.normcase(os.path.normpath(packPath))
	if packPath.startswith(path):
		sys.modules.pop(key)

import SimplexUI
SimplexUI.runSimplexUI()

sys.path.pop(0)
""".format(dn(dn(dn(dn(__file__)))))

def registerTool(window, menu):
	makeShelfBtnACT = QAction("Make Shelf Button", window)
	menu.addAction(makeShelfBtnACT)
	makeShelfBtnACT.triggered.connect(makeShelfButton)


def makeShelfButton():
	pass
	# TODO: Actually, ya know, Add the button to the shelf

