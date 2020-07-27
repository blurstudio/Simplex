# Copyright 2016, Blur Studio
#
# This file is part of Simplex.
#
# Simplex is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Simplex is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.

try:
	# Check to see if we're at blur b/c we're still stuck on HDF5
	import blurdev
except ImportError:
	OGAWA = True
else:
	OGAWA = False

SIMPLEX_UI = None
SIMPLEX_UI_ROOT = None
def runSimplexUI():
	from .interface import rootWindow, DISPATCH
	from .simplexDialog import SimplexDialog
	global SIMPLEX_UI
	global SIMPLEX_UI_ROOT

	# make and show the UI
	SIMPLEX_UI_ROOT = rootWindow()
	# Keep a global reference around, otherwise it gets GC'd
	SIMPLEX_UI = SimplexDialog(parent=SIMPLEX_UI_ROOT, dispatch=DISPATCH)
	SIMPLEX_UI.show()

def tool_paths():
	import os
	path = os.path.dirname(__file__)
	pathPar = os.path.dirname(path)
	return [path], [pathPar]


if __name__ == "__main__":
	import os
	import sys
	folder = os.path.dirname(os.path.dirname(__file__))
	if folder not in sys.path:
		sys.path.insert(0, folder)
	runSimplexUI()

