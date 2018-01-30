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


def getNextName(name, currentNames):
	''' Get the next available name '''
	i = 0
	s = set(currentNames)
	while True:
		if not i:
			nn = name
		else:
			nn = name + str(i)
		if nn not in s:
			return nn
		i += 1
	return name




from Qt.QtCore import QObject, QTimer


class singleShot(QObject):
	""" Decorator class used to implement a QTimer.singleShot(0, function)

	This is useful so your refresh function only gets called once even if
	its connected to a signal that gets emitted several times at once.

	Note:
		The values passed to the decorated method will be accumulated
		and run all at once, then reset for the next go-round

	From the Qt Docs:
		As a special case, a QTimer with a timeout of 0 will time out as
		soon as all the events in the window system's event queue have
		been processed. This can be used to do heavy work while providing
		a snappy user interface
	"""
	def __init__(self):
		super(singleShot, self).__init__()
		self._function = None
		self._callScheduled = False
		self._args = []
		self._inst = None

	def __call__(self, function):
		self._function = function
		def newFunction(inst, *args):
			self._args.extend(args)
			if not self._callScheduled:
				self._inst = inst
				self._callScheduled = True
				QTimer.singleShot(0, self.callback)
		newFunction.__name__ = function.__name__
		newFunction.__doc__ = function.__doc__
		return newFunction

	def callback(self):
		""" Calls the decorated function and resets singleShot for the next group of calls
		"""
		self._callScheduled = False
		# self._args needs to be cleared before we call self._function
		args = self._args
		inst = self._inst
		self._inst = None
		self._args = []
		self._function(inst, args)





