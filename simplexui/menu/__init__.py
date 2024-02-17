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

from __future__ import absolute_import

import importlib
import os
import pkgutil
import sys

from ..Qt.QtWidgets import QMenu
from . import genericPlugins

CONTEXT = os.path.basename(sys.executable)
if CONTEXT == "maya.exe":
    from . import mayaPlugins as plugins
elif CONTEXT == "XSI.exe":
    from . import xsiPlugins as plugins
else:
    from . import dummyPlugins as plugins


def _iter_namespace(ns_pkg):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")


# Registration class
def loadPlugins():
    toolModules = []
    contextModules = []
    imod = sorted([i[1] for i in _iter_namespace(genericPlugins)])
    imod += sorted([i[1] for i in _iter_namespace(plugins)])

    plugs = [importlib.import_module(name) for name in imod]
    for module in plugs:
        if hasattr(module, "registerTool"):
            toolModules.append(module)
        if hasattr(module, "registerContext"):
            contextModules.append(module)

    return toolModules, contextModules


def buildToolMenu(window, modules):
    menu = window.menuBar.addMenu("Tools")
    for m in modules:
        m.registerTool(window, menu)
    return menu


def buildRightClickMenu(tree, indexes, modules):
    menu = QMenu()
    for m in modules:
        m.registerContext(tree, indexes, menu)
    return menu
