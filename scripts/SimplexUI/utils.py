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
import os, sys
from Qt.QtCore import QObject, QTimer

def toPyObject(thing):
	''' Because we could still be in the sip api 1.0 '''
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

def clearPathSymbols(paths, keepers=None):
	""" Removes path symbols from the environment.

	This means I can unload my tools from the current process and re-import them
	rather than dealing with the always finicky reload()

	We use directory paths rather than module names because it gives us more control
	over what is unloaded

	Args:
		paths (list): List of directory paths that will have their modules removed
		keepers (list or None): List of module names that will not be removed
	"""
	keepers = keepers or []
	paths = [os.path.normcase(os.path.normpath(p)) for p in paths]

	for key, value in sys.modules.items():
		protected = False

		# Used by multiprocessing library, don't remove this.
		if key == '__parents_main__':
			protected = True

		# Protect submodules of protected packages
		if key in keepers:
			protected = True

		ckey = key
		while not protected and '.' in ckey:
			ckey = ckey.rsplit('.', 1)[0]
			if ckey in keepers:
				protected = True

		if protected:
			continue

		try:
			packPath = value.__file__
		except AttributeError:
			continue

		packPath = os.path.normcase(os.path.normpath(packPath))

		isEnvPackage = any(packPath.startswith(p) for p in paths)
		if isEnvPackage:
			sys.modules.pop(key)


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


class nested(object):
	"""Combine multiple context managers into a single nested context manager.

	The one advantage of this function over the multiple manager form of the
	with statement is that argument unpacking allows it to be
	used with a variable number of context managers as follows:

	with nested(*managers):
		do_something()

	This has been re-written to properly handle nesting of the contexts.
	So an exception in the definition of a later context will properly
	call the __exit__ methods of all previous contexts
	"""

	def __init__(self, *managers):
		self.managers = managers

	def _nester(self, mIter, prevs):
		try:
			mgr = next(mIter)
		except StopIteration:
			return prevs

		with mgr as a:
			prevs.append(a)
			return self._nester(mIter, prevs)

	def __enter__(self):
		return self._nester(iter(self.managers), [])

	def __exit__(self, excType, exc, trace):
		pass

