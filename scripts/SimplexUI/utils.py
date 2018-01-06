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

"""Utility functions."""
import os

def toPyObject(thing):
  try:
	  return thing.toPyObject()
  except:
	  return thing


def getUiFile(fileVar, subFolder="ui", uiName=None):
	"""Get the path to the .ui file"""
	uiFolder, filename = os.path.split(fileVar)
	if uiName is None:
		uiName = os.path.splitext(filename)[0]
	if subFolder:
		uiFile = os.path.join(uiFolder, subFolder, uiName+".ui")
	return uiFile
