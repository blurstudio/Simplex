"""
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

"""
# This file will serve as the only place where the choice of DCC will be chosen
import os, sys

CONTEXT = os.path.basename(sys.executable)
if CONTEXT == "maya.exe":
	from mayaInterface import customSliderMenu, customComboMenu, ToolActions, undoContext, DCC, rootWindow
elif CONTEXT == "XSI.exe":
	from xsiInterface import customSliderMenu, customComboMenu, ToolActions, undoContext, DCC, rootWindow
else:
	from dummyInterface import customSliderMenu, customComboMenu, ToolActions, undoContext, DCC, rootWindow

