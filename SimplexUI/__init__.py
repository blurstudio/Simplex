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
_SIMPLEX_UI_ = None
_SIMPLEX_ROOT_ = None
_SIMPLEX_STACK_ = None


def runSimplexUI():
	# Store the Simplex UI object in the global namespace
	# Otherwise, it will get garbage collected
	global _SIMPLEX_UI_
	global _SIMPLEX_ROOT_
	global _SIMPLEX_STACK_
	try:
		_SIMPLEX_STACK_.purge()
		_SIMPLEX_UI_.close()
	except AttributeError:
		from SimplexUI.simplexdialog import STACK, QApplication
		_SIMPLEX_STACK_ = STACK

	# Import/reload the simplex dialog
	import sys
	from SimplexUI.simplexdialog import SimplexDialog, System, DISPATCH

	# make and show the UI
	_SIMPLEX_ROOT_ = System.getRootWindow()
	if _SIMPLEX_ROOT_ is None:
		print "Running standalone"
		app = QApplication.instance()
		if app is None:
			app = QApplication(sys.argv)

	_SIMPLEX_UI_ = SimplexDialog(_SIMPLEX_ROOT_, DISPATCH)
	_SIMPLEX_UI_.show()
	if _SIMPLEX_ROOT_ is None:
		sys.exit(app.exec_())

