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

This file defines the interface that the simplex UI will communicate with.
This module will detect the DCC we're in and import the proper back-end
The UI should never talk directly to the backend
'''

import os, sys, copy
from collections import OrderedDict
from functools import wraps
try:
	import blurdev #updates our import paths to allow importing of alembic
except ImportError:
	pass

CONTEXT = os.path.basename(sys.executable)
if CONTEXT == "maya.exe":
	from mayaInterface import DISPATCH, rootWindow, ToolActions, undoable, undoContext, customSliderMenu, customComboMenu

elif CONTEXT == "XSI.exe":
	from xsiInterface import DISPATCH, rootWindow, ToolActions, undoable, undoContext, customSliderMenu, customComboMenu

else:
	from dummyInterface import DISPATCH, rootWindow, ToolActions, undoable, undoContext, customSliderMenu, customComboMenu


class Stack(object):
	''' Integrate simplex into the DCC undo stack '''
	def __init__(self):
		self._stack = OrderedDict()
		self._live = True
		self.depth = 0
		self.uiDepth = 0
		self.currentRevision = 0

	def __setitem__(self, key, value):
		gt = []
		# when setting a new key, remove all keys from
		# the previous branch
		for k in reversed(self._stack): #pylint: disable=bad-reversed-sequence
			if k > key:
				gt.append(k)
			else:
				# yay ordered dict
				break
		for k in gt:
			del self._stack[k]
		#traceback.print_stack()
		self._stack[key] = (self._live, value)

	@property
	def live(self):
		return self._live

	@live.setter
	def live(self, value):
		''' The live option allows you to make multiple changes to the
		UI without updating the DCC. This is still very experimental
		'''
		if self._live == value:
			return #short circuit on no-change
		self._live = value
		if self._live: # if we switch from dead to live
			# Get all the things we need to do in this live/dead flip
			doitStack = []
			for k in reversed(self._stack): #pylint: disable=bad-reversed-sequence
				live, data = self._stack[k]
				if not live:
					doitStack.append(data)
				else:
					# get everything from the end until we're back in live action
					break

			# Do the things that were recorded as one big undoable block
			doitStack.reverse() # because I looped over reversed(self._stack)
			with undoContext():
				for simp, inst, name, data, kwdata in doitStack:
					if name is not None: # Name is None if ui-level stack
						getattr(inst, name)(*data, **kwdata)
						inst.simplex = simp

	def getRevision(self, revision):
		''' Every time a change is made to the simplex definition,
		the revision counter is updated, and the revision/definition
		pair is put on the undo stack
		'''
		# This method will ***ONLY*** be called by the undo callback
		if revision != self.currentRevision:
			if revision in self._stack:
				_, data = self._stack[revision]
				self.currentRevision = revision
				return data
		return None

	def purge(self):
		''' Clear the undo stack. This should be done on new-file '''
		self._stack = OrderedDict()
		self._live = True
		self.depth = 0
		self.uiDepth = 0
		self.currentRevision = 0

def stackable(method):
	''' Decorator to make a method auto update the stack '''
	@wraps(method)
	def stacked(self, *data, **kwdata):
		''' Decorator closure that handles the stack '''
		with undoContext():
			ret = None
			self.stack.depth += 1
			ret = method(self, *data, **kwdata)
			self.stack.depth -= 1

			if self.stack.depth == 0:
				# Top Level of the stack
				srevision = self.incrementRevision()
				scopy = copy.deepcopy(self.simplex)
				self.stack[srevision] = (scopy, self, method.__name__, data, kwdata)
			return ret

	return stacked

STACK = Stack()


