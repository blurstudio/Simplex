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

"""Utility functions."""
from __future__ import absolute_import

import os
import re
import sys

from .Qt.QtCore import QObject, QTimer, QSettings
from .Qt.QtGui import QIcon

AT_BLUR = os.environ.get("SIMPLEX_AT_BLUR") == "true"


def toPyObject(thing):
    """Because we could still be in the sip api 1.0
        I have to check and convert all Qt returns to python objects

    Parameters
    ----------
    thing : object
        The object, possibly Qt type

    Returns
    -------
    object
        The python object

    """
    try:
        return thing.toPyObject()
    except Exception:
        return thing


def getUiFile(fileVar, subFolder="ui", uiName=None):
    """Get the path to the .ui file

    Parameters
    ----------
    fileVar : str
        The __file__ variable passed from the invocation
    subFolder : str
        The folder to look in for the ui files. Defaults to 'ui'
    uiName : str or None
        The name of the .ui file. Defaults to the basename of
        fileVar with .ui instead of .py

    Returns
    -------
    str
        The path to the .ui file

    """
    uiFolder, filename = os.path.split(fileVar)
    if uiName is None:
        uiName = os.path.splitext(filename)[0]
    if subFolder:
        uiFile = os.path.join(uiFolder, subFolder, uiName + ".ui")
    return uiFile


def getNextName(name, currentNames):
    """Get the next available number-incremented name

    Parameters
    ----------
    name : str
        The name I want to check
    currentNames : list
        The names that currently exist

    Returns
    -------
    str
        The next available number-incremented name

    """
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
    """Removes path symbols from the environment.

    This means I can unload my tools from the current process and re-import them
    rather than dealing with the always finicky reload()

    We use directory paths rather than module names because it gives us more control
    over what is unloaded

    Parameters
    ----------
    paths : list
        List of directory paths that will have their modules removed
    keepers : list or None
        List of module names that will not be removed (Default value = None)
    """
    keepers = keepers or []
    paths = [os.path.normcase(os.path.normpath(p)) for p in paths]

    for key, value in sys.modules.items():
        protected = False

        # Used by multiprocessing library, don't remove this.
        if key == "__parents_main__":
            protected = True

        # Protect submodules of protected packages
        if key in keepers:
            protected = True

        ckey = key
        while not protected and "." in ckey:
            ckey = ckey.rsplit(".", 1)[0]
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


def caseSplit(name):
    """Split CamelCase and dromedaryCase words
    Taken From https://stackoverflow.com/questions/29916065/how-to-do-camelcase-split-in-python

    Parameters
    ----------
    name : str
        The string to split

    Returns
    -------
    list
        The split string
    """
    matches = re.finditer(".+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)", name)
    return [m.group(0) for m in matches]


class singleShot(QObject):
    """Decorator class used to implement a QTimer.singleShot(0, function)

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
            """

            Parameters
            ----------
            inst :

            *args :


            Returns
            -------

            """
            self._args.extend(args)
            if not self._callScheduled:
                self._inst = inst
                self._callScheduled = True
                QTimer.singleShot(0, self.callback)

        newFunction.__name__ = function.__name__
        newFunction.__doc__ = function.__doc__
        return newFunction

    def callback(self):
        """Calls the decorated function and resets singleShot for the next group of calls"""
        self._callScheduled = False
        # self._args needs to be cleared before we call self._function
        args = self._args
        inst = self._inst
        self._inst = None
        self._args = []
        self._function(inst, args)


def makeUnique(seq):
    """Make a sequence unique, keeping the first time each item is seen

    Parameters
    ----------
    seq : list or tuple
        A python sequence

    Returns
    -------
    list
        A list with unique items
    """
    seen = set()
    seen_add = seen.add  # only resolve the method lookup once
    return [x for x in seq if not (x in seen or seen_add(x))]


class nested(object):
    """Combine multiple context managers into a single nested context manager.

    The one advantage of this function over the multiple manager form of the
    with statement is that argument unpacking allows it to be
    used with a variable number of context managers as follows:

    .. code-block:: python

        with nested(*managers):
            do_something()

    This has been re-written to properly handle nesting of the contexts.
    So an exception in the definition of a later context will properly
    call the __exit__ methods of all previous contexts
    """

    def __init__(self, *managers):
        self.managers = managers
        self._managed = []

    def __enter__(self):
        prevs = []
        for m in self.managers:
            self._managed.append(m)
            prevs.append(m.__enter__())
        return prevs

    def __exit__(self, excType, exc, trace):
        while self._managed:
            mgr = self._managed.pop()
            mgr.__exit__(excType, exc, trace)


def naturalSortKey(s, _nsre=re.compile("([0-9]+)")):
    """Get a sort key that puts strings with numbers in numerical order
    This is accomplished by splitting the string into groups of digits, and non-digits,
    then converting the digit groups into integers.

    Parameters
    ----------
    s : str
        The string to get the key for
    _nsre :
        A hack argument to hold the compiled regex

    Returns
    -------
    list
        A list containing both strings and integers.
    """
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


def getIcon(iconName):
    path = os.path.join(os.path.dirname(__file__), "img", iconName)
    return QIcon(path)


class Prefs(object):
    """A wrapper for reading/writing prefs both internal and external to blur"""
    def __init__(self):
        if AT_BLUR:
            import blurdev.prefs
            self._pref = blurdev.prefs.find("tools/simplex3")
        else:
            self._pref = QSettings("Blur", "Simplex3")

    def restoreProperty(self, prop, default=None):
        if AT_BLUR:
            return self._pref.restoreProperty(prop, default)
        else:
            return toPyObject(self._pref.value(prop, default))

    def recordProperty(self, prop, val):
        if AT_BLUR:
            self._pref.recordProperty(prop, val)
        else:
            self._pref.setValue(prop, val)

    def save(self):
        if AT_BLUR:
            self._pref.save()
        else:
            self._pref.sync()

