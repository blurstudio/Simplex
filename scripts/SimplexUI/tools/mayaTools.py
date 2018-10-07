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

#pylint: disable=no-self-use, fixme, missing-docstring
import os, textwrap
import mayaPlugins

# Registration class
class ToolActions(object):
	def __init__(self, window, system=None):
		self.system = system
		self.window = window
		menu = self.window.menuBar.addMenu('Tools')
		for mp in mayaPlugins.__all__:
			module = mayaPlugins.__dict__[mp]
			try:
				reg = module.register
			except AttributeError:
				print "Plugin {} is missing the registration function".format(mp)
			else:
				module.register(window, menu)

def customSliderMenu(menu):
	pass

def customComboMenu(menu):
	pass


