'''
Copyright 2016, Blur Studio

This file is part of Simplex.

Simplex is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Simplex is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with Simplex.  If not, see <http://www.gnu.org/licenses/>.
'''

SIMPLEX_UI = None
SIMPLEX_UI_ROOT = None
def runSimplexUI():
	import os, sys
	import SimplexUI.interface
	import SimplexUI.simplexInterfaceDialog

	global SIMPLEX_UI
	global SIMPLEX_UI_ROOT

	# make and show the UI
	SIMPLEX_UI_ROOT = SimplexUI.interface.rootWindow()
	# Keep a global reference around, otherwise it gets GC'd
	SIMPLEX_UI = SimplexUI.simplexInterfaceDialog.SimplexDialog(parent=SIMPLEX_UI_ROOT)
	SIMPLEX_UI.show()

