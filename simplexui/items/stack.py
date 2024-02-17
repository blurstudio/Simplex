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

# pylint:disable=missing-docstring,unused-argument,no-self-use
from __future__ import absolute_import

import copy
from collections import OrderedDict
from contextlib import contextmanager
from functools import wraps

from ..interface import undoContext


# UNDO STACK SETUP
class Stack(object):
    """Integrate simplex into the DCC undo stack"""

    def __init__(self):
        self._stack = OrderedDict()
        self.depth = 0
        self.currentRevision = 0
        self.enabled = True

    def __setitem__(self, key, value):
        gt = []
        # when setting a new key, remove all keys from
        # the previous branch
        for k in reversed(self._stack):  # pylint: disable=bad-reversed-sequence
            if k > key:
                gt.append(k)
            else:
                # yay ordered dict
                break
        for k in gt:
            del self._stack[k]
        # traceback.print_stack()
        self._stack[key] = value

    def getRevision(self, revision):
        """Every time a change is made to the simplex definition,
        the revision counter is updated, and the revision/definition
        pair is put on the undo stack

        Parameters
        ----------
        revision : int
            The revision number to get

        Returns
        -------
        : Simplex or None
            The stored Simplex system for the given revision
            or None if nothing found

        """
        # This method will ***ONLY*** be called by the undo callback
        # Seriously, don't call this yourself
        if revision != self.currentRevision:
            if revision in self._stack:
                data = self._stack[revision]
                self.currentRevision = revision
                return data
        return None

    def purge(self):
        """Clear the undo stack. This should be done on new-file"""
        self._stack = OrderedDict()
        self.depth = 0
        self.currentRevision = 0

    @contextmanager
    def store(self, wrapObj):
        """A context manager That will store changes to a Simplex system
        Nested calls to this manager will only store the first one

        Parameters
        ----------
        wrapObj : object
            A system object that has a reference to the Simplex

        Returns
        -------

        """
        from .simplex import Simplex

        if self.enabled:
            with undoContext(wrapObj.DCC):
                self.depth += 1
                try:
                    yield
                finally:
                    self.depth -= 1

                if self.depth == 0:
                    # Only store the top Level of the stack
                    srevision = wrapObj.DCC.incrementRevision()
                    if not isinstance(wrapObj, Simplex):
                        wrapObj = wrapObj.simplex
                    self[srevision] = copy.deepcopy(wrapObj)
        else:
            yield


def stackable(method):
    """A Decorator to make a method auto update the stack
        This decorator can only be used on methods of an object
        that has its .simplex value set with a stack. If you need
        to wrap an init method, use the stack.store contextmanager

    Parameters
    ----------
    method :


    Returns
    -------

    """

    @wraps(method)
    def stacked(self, *data, **kwdata):
        """Decorator closure that handles the stack

        Parameters
        ----------
        *data :

        **kwdata :


        Returns
        -------

        """
        ret = None
        with self.stack.store(self):
            ret = method(self, *data, **kwdata)
        return ret

    return stacked
