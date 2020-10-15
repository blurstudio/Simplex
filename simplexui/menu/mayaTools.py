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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.

#pylint: disable=no-self-use, fixme, missing-docstring
import mayaPlugins as plugins
import genericPlugins
from ..Qt.QtWidgets import QMenu

# Registration class
def loadPlugins():
	toolModules = []
	contextModules = []
	for plugger in [genericPlugins, plugins]:
		for mp in plugger.__all__:
			module = plugger.__dict__[mp]
			if hasattr(module, 'registerTool'):
				toolModules.append(module)
			if hasattr(module, 'registerContext'):
				contextModules.append(module)
	return toolModules, contextModules

def buildToolMenu(window, modules):
	menu = window.menuBar().addMenu('Tools')
	for m in modules:
		m.registerTool(window, menu)
	return menu

def buildRightClickMenu(tree, indexes, modules):
	menu = QMenu()
	for m in modules:
		m.registerContext(tree, indexes, menu)
	return menu

