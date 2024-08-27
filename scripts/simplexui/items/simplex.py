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
from __future__ import absolute_import, print_function

import copy
import itertools
import json

import six
from six.moves import map, zip

try:
    import numpy as np
except ImportError:
    np = None

from ..commands.alembicCommon import (
    buildAlembicArchiveData,
    getPointCount,
    getSmpxArchiveData,
    readFalloffData,
)
from ..interface import DCC, undoContext
from ..interface.dummyInterface import DCC as DummyDCC
from ..Qt.QtGui import QColor
from ..Qt.QtWidgets import QApplication
from ..utils import nested
from .combo import Combo, ComboPair
from .falloff import Falloff
from .group import Group
from .progression import ProgPair, Progression
from .shape import Shape
from .slider import Slider
from .stack import Stack, stackable
from .traversal import Traversal, TravPair


class Simplex(object):
    """The main Top-level abstract object that controls an entire setup

    Simplex objects contain and manage the entire hierarchy. They have methods
    to import from and export to disk. Simplex objects also mange the connections
    to the DCC and the UI, setting up connections with the undo stack, the dispatcher,
    and all of the ui TreeModels.

    Finally Simplex systems handle splitting, which will be covered more in depth
    in the documentation for the split method.

    """

    classDepth = 0

    def __init__(
        self, name="", models=None, falloffModels=None, forceDummy=False, sliderMul=1.0
    ):
        """Constructor

        Parameters
        ----------
        name : str, optional
            The name of the new system. Defaults to ""
        models : [QAbstractItemModel, ....], optional
            The ui models that read this system. Defaults to []
        falloffModels : [QAbstractItemModel, ....], optional
            The ui models for managing Falloffs.
            Defaults to []
        forceDummy : bool, optional
            When loading, don't make a connection to the actual DCC. Instead use the
            "dummy" DCC. Defaults False
        sliderMul : float, optional
            A multiplier for the range of sliders. Simplex will only define values
            between -1 and 1. This multiplier will let the attribute range in the DCC be larger so
            animators can push the extremes

        Returns
        -------
        """
        self._name = name  # The name of the system
        self.sliders = []  # List of contained sliders
        self.combos = []  # List of contained combos
        self.traversals = []  # list of contained traversals
        self.sliderGroups = []  # List of groups containing sliders
        self.comboGroups = []  # List of groups containing combos
        self.traversalGroups = []  # List of groups containing traversals
        self.falloffs = []  # List of contained falloff objects
        self.shapes = []  # List of contained shape objects
        self.models = models or []  # connected Qt Item Models
        self.falloffModels = falloffModels or []  # connected Qt Falloff Models
        self.restShape = None  # Name of the rest shape
        self.clusterName = "Shape"  # Name of the cluster (XSI use only)
        self.expanded = {}  # Am I expanded by model
        self.comboExpanded = False  # Am I expanded in the combo tree
        self.sliderExpanded = False  # Am I expanded in the slider tree
        self.sliderMul = sliderMul
        self.DCC = DummyDCC(self) if forceDummy else DCC(self)  # Interface to the DCC
        self.stack = Stack()  # Reference to the Undo stack
        self._extras = {}  # Any extra key data to store in the output json
        self._legacy = False  # whether to write the legacy types

    def __deepcopy__(self, memo):
        """Gotta be really picky about what gets deepcopied.
        Especially since I pretty much abuse the deepcopy mechanism to do splitting
        Deep-copied systems have no reference to a UI, or a DCC
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in six.iteritems(self.__dict__):
            if k == "models":
                # do not make a copy of the connected models
                # a deepcopied simplex won't be connected to a UI
                setattr(result, k, [])
            elif k == "falloffModels":
                # do not make a copy of the connected models
                # a deepcopied simplex won't be connected to a UI
                setattr(result, k, [])
            elif k == "stack":
                # Make a disabled stack for new simplex
                s = Stack()
                s.enabled = False
                setattr(result, k, s)
            elif k == "DCC":
                # do not connect the deepcopied simplex to the DCC
                # we will want to change it without affecting the current scene
                # Requires the name be copied already
                setattr(result, "_name", copy.deepcopy(self._name, memo))
                if v.program == "dummy":
                    # If it's already a dummy, go ahead and just deepcopy
                    setattr(result, k, copy.deepcopy(v, memo))
                else:
                    setattr(result, k, DummyDCC(result))
            elif k == "expanded":
                # do not make a copy of the expansion
                # because it's keyed off the un-copied models
                setattr(result, k, {})
            else:
                setattr(result, k, copy.deepcopy(v, memo))
        return result

    def _initValues(self):
        """Re-initialize the variables to that of an empy system"""
        self._name = ""  # The name of the system
        self.sliders = []  # List of contained sliders
        self.combos = []  # List of contained combos
        self.sliderGroups = []  # List of groups containing sliders
        self.comboGroups = []  # List of groups containing combos
        self.traversalGroups = []  # List of groups containing combos
        self.falloffs = []  # List of contained falloff objects
        self.shapes = []  # List of contained shape objects
        self.restShape = None  # Name of the rest shape
        self.clusterName = "Shape"  # Name of the cluster (XSI use only)
        self.expanded = {}  # Am I expanded? (Keep around for consistent interface)
        self.color = QColor(128, 128, 128)
        self.comboExpanded = False  # Am I expanded in the combo tree
        self.sliderExpanded = False  # Am I expanded in the slider tree

    # Alternate Constructors
    @classmethod
    def buildBaseObject(cls, smpxPath, name=None, forceDummy=False):
        """Build the rest object from a .smpx file

        Parameters
        ----------
        smpxPath : str
            The path to the .smpx file
        name : str, optional
            The Name of the object to create. Defaults to the name of the simplex system

        Returns
        -------
        : object
            A reference to the DCC mesh

        """
        iarch, abcMesh, jsString = getSmpxArchiveData(smpxPath)
        try:
            if name is None:
                js = json.loads(jsString)
                name = js["systemName"]
            if forceDummy:
                return DummyDCC.buildRestAbc(abcMesh, name)
            else:
                return DCC.buildRestAbc(abcMesh, name)
        finally:
            del iarch

    @classmethod
    def buildEmptySystem(cls, thing, name, sliderMul=1.0, forceDummy=False):
        """Create a new, empty system on a given mesh

        Parameters
        ----------
        thing : object
            The DCC mesh to build the system on
        name : str
            The name of the new Simplex system
        sliderMul : float, optional
            A multiplier for the range of sliders. Simplex will only define values
            between -1 and 1. This multiplier will let the attribute range in the DCC be larger so
            animators can push the extremes (Default value = 1.0)
        forceDummy : bool, optional
            When loading, don't make a connection to the actual DCC. Instead use the
            "dummy" DCC. Defaults False

        Returns
        -------
        : Simplex
            A newly created Simplex system

        """
        self = cls(name, forceDummy=forceDummy, sliderMul=sliderMul)
        self.DCC.loadNodes(self, thing, create=True)
        self.restShape = Shape.buildRest(self)
        return self

    @classmethod
    def buildSystemFromJsonString(
        cls, jsString, thing=None, name=None, forceDummy=False, sliderMul=1.0, pBar=None
    ):
        """Build a system from a json encoded string

        Parameters
        ----------
        jsString : str
            The json encoded simplex definition
        thing : object
            The DCC mesh to build the system on (Default value = None)
        name : str
            The name of the new Simplex system (Default value = None)
        forceDummy : bool
            When loading, don't make a connection to the actual DCC. Instead use the
            "dummy" DCC. Defaults False
        sliderMul : float
            A multiplier for the range of sliders. Simplex will only define values
            between -1 and 1. This multiplier will let the attribute range in the DCC be larger so
            animators can push the extremes (Default value = 1.0)
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------
        : Simplex
            A newly created Simplex system

        """
        js = json.loads(jsString)
        if name is None:
            name = js["systemName"]
        return cls.buildSystemFromDict(
            js, thing, name=name, forceDummy=forceDummy, sliderMul=sliderMul, pBar=pBar
        )

    @classmethod
    def buildSystemFromJson(
        cls, jsPath, thing=None, name=None, forceDummy=False, sliderMul=1.0, pBar=None
    ):
        """Build a system from .json file

        Parameters
        ----------
        jsPath : str
            The .json file to load
        thing : object
            The DCC mesh to build the system on (Default value = None)
        name : str
            The name of the new Simplex system (Default value = None)
        forceDummy : bool
            When loading, don't make a connection to the actual DCC. Instead use the
            "dummy" DCC. Defaults False
        sliderMul : float
            A multiplier for the range of sliders. Simplex will only define values
            between -1 and 1. This multiplier will let the attribute range in the DCC be larger so
            animators can push the extremes (Default value = 1.0)
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------
        : Simplex
            A newly created Simplex system

        """
        with open(jsPath, "r") as f:
            jsString = f.read()
        return cls.buildSystemFromJsonString(
            jsString,
            thing,
            name=name,
            forceDummy=forceDummy,
            sliderMul=sliderMul,
            pBar=pBar,
        )

    @classmethod
    def buildSystemFromSmpx(
        cls, smpxPath, thing=None, name=None, forceDummy=False, sliderMul=1.0, pBar=None
    ):
        """Build a system from a .smpx file
        SMPX files are (under-the-hood) alembic caches with each shape delta stored as a frame of animation,
        and the json string stored in a property on the mesh.

        Parameters
        ----------
        smxpPath : str
            The .smpx file to load
        thing : object
            The DCC mesh to build the system on (Default value = None)
        name : str
            The name of the new Simplex system (Default value = None)
        forceDummy : bool
            When loading, don't make a connection to the actual DCC. Instead use the
            "dummy" DCC. Defaults False
        sliderMul : float
            A multiplier for the range of sliders. Simplex will only define values
            between -1 and 1. This multiplier will let the attribute range in the DCC be larger so
            animators can push the extremes (Default value = 1.0)
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------
        : Simplex
            A newly created Simplex system

        """
        if thing is None:
            thing = cls.buildBaseObject(smpxPath, forceDummy=forceDummy)
        iarch, abcMesh, jsString = getSmpxArchiveData(smpxPath)
        js = json.loads(jsString)

        if not forceDummy:
            smpxCount = getPointCount(abcMesh)
            dccCount = DCC.vertCount(thing)
            if smpxCount != dccCount:
                raise RuntimeError(
                    "Point Count Mismatch. Smpx File:{0} DCC:{1}".format(
                        smpxCount, dccCount
                    )
                )

        del iarch, abcMesh  # release the files
        if name is None:
            name = js["systemName"]
        self = cls.buildSystemFromDict(
            js, thing, name=name, forceDummy=forceDummy, sliderMul=sliderMul, pBar=pBar
        )
        self.loadSmpxShapes(smpxPath, pBar=pBar)
        self.loadSmpxFalloffs(smpxPath, pBar=pBar)
        return self

    @classmethod
    def buildSystemFromFile(
        cls, path, thing=None, name=None, forceDummy=False, sliderMul=1.0, pBar=None
    ):
        """Build a system from a file

        Parameters
        ----------
        path : str
            The file to load. Either .json or .smpx
        thing : object
            The DCC mesh to build the system on (Default value = None)
        name : str
            The name of the new Simplex system (Default value = None)
        forceDummy : bool
            When loading, don't make a connection to the actual DCC. Instead use the
            "dummy" DCC. Defaults False
        sliderMul : float
            A multiplier for the range of sliders. Simplex will only define values
            between -1 and 1. This multiplier will let the attribute range in the DCC be larger so
            animators can push the extremes (Default value = 1.0)
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------
        : Simplex
            A newly created Simplex system

        """
        if path.endswith(".json"):
            return cls.buildSystemFromJson(
                path,
                thing=thing,
                name=name,
                forceDummy=forceDummy,
                sliderMul=sliderMul,
                pBar=pBar,
            )
        elif path.endswith(".smpx"):
            return cls.buildSystemFromSmpx(
                path,
                thing=thing,
                name=name,
                forceDummy=forceDummy,
                sliderMul=sliderMul,
                pBar=pBar,
            )
        else:
            raise ValueError(
                "The filepath provided is not a .json or .smpx: {0}".format(path)
            )

    @classmethod
    def buildSystemFromMesh(
        cls, thing, name, forceDummy=False, sliderMul=1.0, pBar=None
    ):
        """Build a system from the data already built in the DCC

        Parameters
        ----------
        thing : object
            The DCC mesh to load the system from
        name : str
            The name of the new Simplex system
        forceDummy : bool
            When loading, don't make a connection to the actual DCC. Instead use the
            "dummy" DCC. Defaults False
        sliderMul : float
            A multiplier for the range of sliders. Simplex will only define values
            between -1 and 1. This multiplier will let the attribute range in the DCC be larger so
            animators can push the extremes (Default value = 1.0)
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------
        : Simplex
            A newly created Simplex system

        """
        jsDict = json.loads(DCC.getSimplexStringOnThing(thing, name))
        return cls.buildSystemFromDict(
            jsDict,
            thing,
            name=name,
            create=False,
            forceDummy=forceDummy,
            sliderMul=sliderMul,
            pBar=pBar,
        )

    @classmethod
    def buildSystemFromDict(
        cls,
        jsDict,
        thing,
        name=None,
        create=True,
        forceDummy=False,
        sliderMul=1.0,
        pBar=None,
    ):
        """Utility for building a cleared system from a dictionary

        Parameters
        ----------
        jsDict : dict
            The definition dictonary (parsed from a json string)
        thing : object
            The DCC mesh to load the system on
        name : str, optional
            The name of the new Simplex system. If None, default to the system name
        create : bool, optional
            Create any missing blendshapes as the system is loaded. If False, error on missing.
            Defaults to True
        forceDummy : bool, optional
            When loading, don't make a connection to the actual DCC. Instead use the
            "dummy" DCC. Defaults to False
        sliderMul : float, optional
            A multiplier for the range of sliders. Simplex will only define values
            between -1 and 1. This multiplier will let the attribute range in the DCC be larger so
            animators can push the extremes (Default value = 1.0)
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------
        : Simplex
            A newly created Simplex system

        """
        if name is None:
            name = jsDict["systemName"]
        self = cls(name, forceDummy=forceDummy, sliderMul=sliderMul)
        self.DCC.loadNodes(self, thing, create=create)
        self.loadDefinition(jsDict, create=create, pBar=pBar)
        return self

    def loadSmpxShapes(self, smpxPath, pBar=None):
        """Load the Shapes from a .smpx file onto an already loaded system
        This is the "We got updated shapes from the modelers" method

        Parameters
        ----------
        smpxPath : str
            The path to the .smpx file
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------

        """
        iarch, abcMesh, jsString = getSmpxArchiveData(smpxPath)
        js = json.loads(jsString)

        try:
            self.DCC.loadAbc(abcMesh, js, pBar=pBar)
        finally:
            del abcMesh, iarch

    def loadSmpxFalloffs(self, abcPath, pBar=None):
        """Load the relevant data from a simplex alembic

        Parameters
        ----------
        abcPath : str
            Path to the .smpx file
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------

        """
        foDict = readFalloffData(abcPath)

        for fo in self.falloffs:
            foData = foDict.get(fo.name, None)
            if foData is not None:
                fo.weights = foData

    # Properties
    @property
    def name(self):
        """Get the system name"""
        return self._name

    @name.setter
    @stackable
    def name(self, value):
        """Set the system name"""
        if value == self._name:
            return

        self._name = value
        self.DCC.renameSystem(value)  # ??? probably needs work
        if self.restShape is not None:
            self.restShape.name = self.getRestName()

        for model in self.models:
            model.itemDataChanged(self)

    @property
    def progs(self):
        """Get all Progressions defined in the system"""
        out = []
        for slider in self.sliders:
            out.append(slider.prog)
        for combo in self.combos:
            out.append(combo.prog)
        for trav in self.traversals:
            out.append(trav.prog)
        return out

    @property
    def groups(self):
        """Get all Groups defined in the system"""
        return self.sliderGroups + self.comboGroups + self.traversalGroups

    def treeChild(self, row):
        """ """
        return self.groups[row]

    def treeRow(self):
        """ """
        return 0

    def treeParent(self):
        """ """
        return None

    def treeChildCount(self):
        """ """
        return len(self.groups)

    def treeData(self, column):
        """ """
        if column == 0:
            return self.name
        return None

    def treeChecked(self):
        """ """
        return None

    def icon(self):
        return None

    # HELPER
    def comboExists(self, sliders, values):
        """Check if a combo exists with these specific sliders and values
        Because combo names aren't necessarily always in the same order

        Parameters
        ----------
        sliders : [Slider, ....]
            The sliders to check
        values : [float, ....]
            The values to check

        Returns
        -------
        : Combo or None
            The Combo with those sliders and values, or None if none found

        """
        checkSet = set([(s.name, v) for s, v in zip(sliders, values)])
        for cmb in self.combos:
            cmbSet = set([(p.slider.name, p.value) for p in cmb.pairs])
            if checkSet == cmbSet:
                return cmb
        return None

    # DESTRUCTOR
    def deleteSystem(self):
        """Delete an existing system from the DCC"""
        # Store the models as temp so the model doesn't go crazy with the signals
        models, self.models = self.models, None
        mgrs = [model.resetModelManager() for model in models]
        with nested(*mgrs):
            self.DCC.deleteSystem()
            self._initValues()
            self.DCC = DCC(self)
        self.models = models

    def getComboUpstreams(self, combo):
        """Get a list of only combos that are upstream to the given combo
        In this case, "upstream" means that when the given combo is active,
        then any returned combos are also active.

        I am currently ignoring floating combos in this function
        The upstream sliders are available trivially through combo.pairs

        Parameters
        ----------
        combo : Combo
            The given combo

        Returns
        -------
        : [Combo, ....]
            The list of upstream combos

        """
        pairDict = {p.slider: p.value for p in combo.pairs}

        upstreams = []
        for c in self.combos:
            if c.isFloating():
                continue

            if len(c.pairs) >= len(pairDict):
                continue

            if not all(p.slider in pairDict for p in c.pairs):
                continue

            fail = False
            for p in c.pairs:
                if p.slider not in pairDict:
                    fail = True
                    break
                if pairDict[p.slider] * p.value < 0.0:
                    # opposite Signs
                    fail = True
                    break

            if not fail:
                upstreams.append(c)

        return upstreams

    def getDownstreamTraversals(self, slider):
        """Get a list of any traversals that depend on the given slider

        Parameters
        ----------
        slider : Slider
            The system slider to check

        Returns
        -------
        : [Traversal, ....]
            The list of dependent Traversals

        """
        downstream = []
        for t in self.traversals:
            for pair in t.startPoint.pairs + t.endPoint.pairs:
                if slider == pair.slider:
                    downstream.append(t)
                    break
        downstream = list(set(downstream))
        return downstream

    def getDownstreamCombos(self, slider):
        """Get a list of any Combos that depend on the given slider

        Parameters
        ----------
        slider : Slider
            The Slider item to check

        Returns
        -------
        : [Combo, ....]
            The list of dependent Combos

        """
        downstream = []
        if not isinstance(slider, Slider):
            return downstream
        for c in self.combos:
            for pair in c.pairs:
                if pair.slider == slider:
                    downstream.append(c)
                    break
        downstream = list(set(downstream))
        return downstream

    def deleteDownstream(self, item):
        """Delete all items from the system that depend on the given item

        Parameters
        ----------
        item : object
            The system item to check

        Returns
        -------

        """
        todel = []
        todel.extend(self.getDownstreamCombos(item))
        todel.extend(self.getDownstreamTraversals(item))
        for c in todel:
            c.delete()

    # USER METHODS
    def setLegacy(self, legacy):
        """Set whether to use the legacy .json format

        Parameters
        ----------
        legacy : bool
            Whether to use the legacy .json format

        Returns
        -------

        """
        self._legacy = legacy

    def getFloatingShapes(self):
        """Find Combos with values other than -1 and 1

        Parameters
        ----------

        Returns
        -------
        : [Combo, ....]
            Combos that don't have fully extreme activations

        """
        floaters = [c for c in self.combos if c.isFloating()]
        floatShapes = []
        for f in floaters:
            floatShapes.extend(f.prog.getShapes())
        return floatShapes

    def buildDefinition(self):
        """Create a simplex definition dictionary
        Loop through all the objects managed by this simplex system, and build a dictionary that defines it

        Parameters
        ----------

        Returns
        -------
        : dict
            The simplex definition dictionary

        """
        things = [
            self.shapes,
            self.sliders,
            self.combos,
            self.traversals,
            self.groups,
            self.falloffs,
        ]
        for thing in things:
            for i in thing:
                i.clearBuildIndex()

        # Make sure we start with the extras in
        # case we're overwriting with new data
        d = copy.deepcopy(self._extras)

        # Then set all the top-level system keys
        d["encodingVersion"] = 1 if self._legacy else 3
        d["systemName"] = self.name
        d["clusterName"] = self.clusterName
        d.setdefault("falloffs", [])
        d.setdefault("combos", [])
        d.setdefault("shapes", [])
        d.setdefault("sliders", [])
        d.setdefault("groups", [])
        d.setdefault("progressions", [])
        d.setdefault("traversals", [])

        # rest shape should *ALWAYS* be index 0
        for shape in self.shapes:
            shape.buildDefinition(d, self._legacy)

        for group in self.groups:
            group.buildDefinition(d, self._legacy)

        for falloff in self.falloffs:
            falloff.buildDefinition(d, self._legacy)

        for slider in self.sliders:
            slider.buildDefinition(d, self._legacy)

        for combo in self.combos:
            combo.buildDefinition(d, self._legacy)

        for trav in self.traversals:
            trav.buildDefinition(d, self._legacy)

        return d

    @stackable
    def loadDefinition(self, simpDict, create=True, pBar=None):
        """Build the structure of objects in this system
        based on a provided dictionary

        Parameters
        ----------
        simpDict : dict
            The dictionary to load
        create : bool, optional
            Create any missing blendshapes as the system is loaded. If False, error on missing.
            Defaults to True
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------

        """

        self.name = simpDict["systemName"]
        self.clusterName = simpDict["clusterName"]  # for XSI
        if simpDict["encodingVersion"] == 1:
            self.loadV1(simpDict, create=create, pBar=pBar)
        elif simpDict["encodingVersion"] == 2:
            self.loadV2(simpDict, create=create, pBar=pBar)
        elif simpDict["encodingVersion"] == 3:
            self.loadV3(simpDict, create=create, pBar=pBar)
        self.storeExtras(simpDict)

    def _incPBar(self, pBar, txt, inc=1):
        """Increment the progress bar and return False if the user cancelled

        Parameters
        ----------
        pBar :

        txt :

        inc :
             (Default value = 1)

        Returns
        -------

        """
        if pBar is not None:
            pBar.setValue(pBar.value() + inc)
            pBar.setLabelText("Building:\n" + txt)
            QApplication.processEvents()
            return not pBar.wasCanceled()
        return True

    def loadV3(self, simpDict, create=True, pBar=None):
        """Load the version 3 simplex definition
        V3 is just the same as V2, except for an update Traversal definition

        Parameters
        ----------
        simpDict : dict
            The simplex definition dictionary
        create : bool, optional
            Create any missing blendshapes as the system is loaded. If False, error on missing.
            Defaults to True
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------

        """
        preRet = self.DCC.preLoad(self, simpDict, create=create, pBar=pBar)
        try:
            fos = simpDict.get("falloffs", [])
            gs = simpDict.get("groups", [])
            for f in fos:
                Falloff.loadV2(self, f)
            if gs:
                for g in gs:
                    Group.loadV2(self, g)
            else:
                Group("Group_0", self, Slider)
                Group("Group_1", self, Combo)
                Group("Group_2", self, Traversal)

            if pBar is not None:
                maxLen = max(len(i["name"]) for i in simpDict["shapes"])
                pBar.setLabelText("_" * maxLen)
                pBar.setValue(0)
                pBar.setMaximum(len(simpDict["shapes"]) + 1)
            self.shapes = []
            for s in simpDict["shapes"]:
                if not self._incPBar(pBar, s["name"]):
                    return
                Shape.loadV2(self, s, create)

            self.restShape = self.shapes[0]
            self.restShape.isRest = True

            progs = [Progression.loadV2(self, p) for p in simpDict["progressions"]]

            for s in simpDict["sliders"]:
                Slider.loadV2(self, progs, s, create)
            for c in simpDict["combos"]:
                Combo.loadV2(self, progs, c)
            for t in simpDict["traversals"]:
                Traversal.loadV3(self, progs, t)

            for x in itertools.chain(self.sliders, self.combos, self.traversals):
                x.prog.name = x.name
        finally:
            self.DCC.postLoad(self, preRet)

    def loadV2(self, simpDict, create=True, pBar=None):
        """Load the version 2 simplex definition

        Parameters
        ----------
        simpDict : dict
            The simplex definition dictionary
        create : bool, optional
            Create any missing blendshapes as the system is loaded. If False, error on missing.
            Defaults to True
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------

        """
        preRet = self.DCC.preLoad(self, simpDict, create=create, pBar=pBar)
        try:
            fos = simpDict.get("falloffs", [])
            gs = simpDict.get("groups", [])
            for f in fos:
                Falloff.loadV2(self, f)
            if gs:
                for g in gs:
                    Group.loadV2(self, g)
            else:
                Group("Group_0", self, Slider)
                Group("Group_1", self, Combo)
                Group("Group_2", self, Traversal)

            if pBar is not None:
                maxLen = max(len(i["name"]) for i in simpDict["shapes"])
                pBar.setLabelText("_" * maxLen)
                pBar.setValue(0)
                pBar.setMaximum(len(simpDict["shapes"]) + 1)
            self.shapes = []
            for s in simpDict["shapes"]:
                if not self._incPBar(pBar, s["name"]):
                    return
                Shape.loadV2(self, s, create)

            self.restShape = self.shapes[0]
            self.restShape.isRest = True

            progs = [Progression.loadV2(self, p) for p in simpDict["progressions"]]

            for s in simpDict["sliders"]:
                Slider.loadV2(self, progs, s, create)
            for c in simpDict["combos"]:
                Combo.loadV2(self, progs, c)
            for t in simpDict["traversals"]:
                Traversal.loadV2(self, progs, t)

            for x in itertools.chain(self.sliders, self.combos, self.traversals):
                x.prog.name = x.name
        finally:
            self.DCC.postLoad(self, preRet)

    def loadV1(self, simpDict, create=True, pBar=None):
        """Load the version 1 simplex definition

        Parameters
        ----------
        simpDict : dict
            The simplex definition dictionary
        create : bool, optional
            Create any missing blendshapes as the system is loaded. If False, error on missing.
            Defaults to True
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------

        """
        preRet = self.DCC.preLoad(self, simpDict, create=create, pBar=pBar)
        try:
            self.falloffs = [Falloff(f[0], self, *f[1:]) for f in simpDict["falloffs"]]
            groupNames = simpDict["groups"]

            if pBar is not None:
                maxLen = max(list(map(len, simpDict["shapes"])))
                pBar.setLabelText("_" * maxLen)
                pBar.setValue(0)
                pBar.setMaximum(len(simpDict["shapes"]) + 1)

            shapes = []
            for s in simpDict["shapes"]:
                if not self._incPBar(pBar, s):
                    return
                shapes.append(Shape(s, self))

            self.restShape = shapes[0]
            self.restShape.isRest = True

            progs = []
            for p in simpDict["progressions"]:
                progShapes = [shapes[i] for i in p[1]]
                progFalloffs = [self.falloffs[i] for i in p[4]]
                progPairs = [ProgPair(self, s, pv) for s, pv in zip(progShapes, p[2])]
                progs.append(Progression(p[0], self, progPairs, p[3], progFalloffs))

            self.sliders = []
            self.sliderGroups = []
            createdSlidergroups = {}
            for s in simpDict["sliders"]:
                sliderProg = progs[s[1]]

                gn = groupNames[s[2]]
                if gn in createdSlidergroups:
                    sliderGroup = createdSlidergroups[gn]
                else:
                    sliderGroup = Group(gn, self, Slider)
                    createdSlidergroups[gn] = sliderGroup

                Slider(s[0], self, sliderProg, sliderGroup)

            self.combos = []
            self.comboGroups = []
            createdComboGroups = {}
            for c in simpDict["combos"]:
                prog = progs[c[1]]
                sliderIdxs, sliderVals = list(zip(*c[2]))
                sliders = [self.sliders[i] for i in sliderIdxs]
                pairs = list(map(ComboPair, sliders, sliderVals))
                if len(c) >= 4:
                    gn = groupNames[c[3]]
                else:
                    gn = "DEPTH_0"

                if gn in createdComboGroups:
                    comboGroup = createdComboGroups[gn]
                else:
                    comboGroup = Group(gn, self, Combo)
                    createdComboGroups[gn] = comboGroup

                cmb = Combo(c[0], self, pairs, prog, comboGroup, None)
                cmb.simplex = self

            self.traversals = []
            self.traversalGroups = []
            createdTraversalGroups = {}
            if "traversals" in simpDict:
                for t in simpDict["traversals"]:
                    name = t["name"]
                    prog = progs[t["prog"]]

                    pcIdx = t["progressControl"]
                    pcSearch = (
                        self.sliders
                        if t["progressType"].lower() == "slider"
                        else self.combos
                    )
                    pc = pcSearch[pcIdx]
                    pFlip = t["progressFlip"]
                    pp = TravPair(pc, -1 if pFlip else 1, "progress")

                    mcIdx = t["multiplierControl"]
                    mcSearch = (
                        self.sliders
                        if t["multiplierType"].lower() == "slider"
                        else self.combos
                    )
                    mc = mcSearch[mcIdx]
                    mFlip = t["multiplierFlip"]
                    mm = TravPair(mc, -1 if mFlip else 1, "multiplier")

                    gn = groupNames[t.get("group", 2)]
                    if gn in createdTraversalGroups:
                        travGroup = createdTraversalGroups[gn]
                    else:
                        travGroup = Group(gn, self, Traversal)
                        createdTraversalGroups[gn] = travGroup

                    color = QColor(*t.get("color", (0, 0, 0)))

                    trav = Traversal(name, self, mm, pp, prog, travGroup, color)
                    trav.simplex = self

            for x in itertools.chain(self.sliders, self.combos, self.traversals):
                x.prog.name = x.name
        finally:
            self.DCC.postLoad(self, preRet)

    def storeExtras(self, simpDict):
        """Store any unknown keys when dumping, just in case they're important elsewhere

        Parameters
        ----------
        simpDict : dict
            The simplex definition dictionary

        Returns
        -------

        """
        sd = copy.deepcopy(simpDict)
        knownTopLevel = [
            "encodingVersion",
            "systemName",
            "clusterName",
            "falloffs",
            "combos",
            "shapes",
            "sliders",
            "groups",
            "traversals",
            "progressions",
        ]

        for ktn in knownTopLevel:
            if ktn in sd:
                del sd[ktn]
        self._extras = sd

    def loadJSON(self, jsString):
        """Convenience method to load a JSON string definition

        Parameters
        ----------
        jsString : str
            The json formatted definition string

        Returns
        -------

        """
        self.loadDefinition(json.loads(jsString))

    def getRestName(self):
        """Get the default rest shape name

        Parameters
        ----------

        Returns
        -------
        : str
            The default rest shape name

        """
        return "Rest_{0}".format(self.name)

    def dump(self):
        """Dump the definition dictionary to a json string

        Parameters
        ----------

        Returns
        -------
        : str
            The json formatted definition string

        """
        return json.dumps(self.buildDefinition())

    def exportAbc(self, path, pBar=None):
        """Export the current mesh to a .smpx formatted file

        Parameters
        ----------
        path : str
            The path to export to
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------

        """
        defDict = self.buildDefinition()
        jsString = json.dumps(defDict)

        arch, abcMesh = buildAlembicArchiveData(path, self.name, jsString, True)
        try:
            self.DCC.exportAbc(
                self.DCC.mesh,
                abcMesh,
                defDict,
                world=False,
                ensureCorrect=True,
                pBar=pBar,
            )
        finally:
            del arch, abcMesh

    def exportOther(self, path, dccMesh, world=False, ensureCorrect=False, pBar=None):
        """Export shapes from a mesh that isn't part of the current system

        The export process for shapes differs from DCC to DCC.
        In Maya, every blendshape is activated, one by one and the point posisitions
        are read from the target mesh. This allows exportOther to work

        In XSI, the blendshape properties are read directly, so there's no chance
        to process the new shapes (which means this won't work in XSI)

        Parameters
        ----------
        path : str
            The output path for the .smpx file
        dccMesh : object
            The system-external DCC mesh to export
        world : bool, optional
            Whether to do the export in worldspace. Defaults to False
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        """
        defDict = self.buildDefinition()
        jsString = json.dumps(defDict)

        arch, abcMesh = buildAlembicArchiveData(path, self.name, jsString, True)
        try:
            self.DCC.exportOtherAbc(dccMesh, abcMesh, defDict, world=world, pBar=pBar)
        finally:
            del arch, abcMesh

    def setSlidersWeights(self, sliders, weights):
        """Set the weights of multiple sliders as one method

        Parameters
        ----------
        sliders : [Slider, ....]
            The list of Sliders to set weights for
        weights : [float, ....]
            The weights to set

        Returns
        -------

        """
        with undoContext(self.DCC):
            for slider, weight in zip(sliders, weights):
                slider.value = weight
            self.DCC.setSlidersWeights(sliders, weights)
            for model in self.models:
                for slider in sliders:
                    model.itemDataChanged(slider)

    def extractRestShape(self, offset=0):
        """Extract the rest shape to a mesh in the DCC

        Parameters
        ----------
        offset : float
            The offset value given to the extracted mesh (Default value = 0)

        Returns
        -------

        """
        if self.restShape is None:
            return None
        return self.DCC.extractShape(self.restShape, live=False, offset=offset)

    def buildRestShape(self):
        """Build and store a rest shape for this system"""
        self.restShape = Shape.buildRest(self)
        return self.restShape

    def buildInputVectors(
        self,
        keepSliders=None,
        ignoreSliders=None,
        depthCutoff=None,
        ignoreFloaters=False,
        ignoreTraversals=False,
        extremes=False,
    ):
        """This is kind of a specialized function. Often, I have to sum combo deltas
        into the full sculpted shape. But to do that, I have to build the inputs to the
        solver that enable each shape, and I need a name for each shape.
        This function gives me both.

        Parameters
        ----------
        keepSliders : set([str, ....]), optional
            The returned sliders will have names that are part of this list
        ignoreSliders : set([str, ....]), optional
            A set of Slider names to ignore as part of this process
        depthCutoff : int, optional
            The maximum number of Sliders allowed per Combo
            (Defaults to None which allows all Combos)
        ignoreFloaters : bool, optional
            Ignore Combos with values other than -1 and 1
        extremes : bool, optional
            Only build activations for sliders and combos at -1 and 1

        Returns
        -------
        : [str, ...]
            The names of the shapes that are activated in each list
        : [[float, ...], ...]
            A list of activation values for the entire system

        """
        # InputVector comes from the c++ std::vector
        # Get all endpoint shapes from the progressions
        shapeNames = []
        inVecs = []
        keyIdxs = []
        ignoreSliders = ignoreSliders or set()
        ignoreSliders = set(ignoreSliders)
        indexByShape = {shape: idx for idx, shape in enumerate(self.shapes)}

        for slIdx, slider in enumerate(self.sliders):
            if slider.name in ignoreSliders:
                continue
            if keepSliders is not None and slider.name not in keepSliders:
                continue

            pairs = [p for p in slider.prog.pairs if not p.shape.isRest]
            if extremes:
                pairs = [p for p in pairs if abs(p.value) == 1.0]

            for pp in pairs:
                inVec = [0.0] * len(self.sliders)
                inVec[slIdx] = pp.value
                shapeNames.append(pp.shape.name)
                inVecs.append(inVec)
                keyIdxs.append(indexByShape[pp.shape])

        for combo in self.combos:
            if ignoreFloaters and combo.isFloating():
                continue
            if depthCutoff is not None and len(combo.pairs) > depthCutoff:
                continue
            if ignoreSliders & set([i.name for i in combo.getSliders()]):
                # if the combo's sliders are in ignoreSliders
                continue

            pairs = [p for p in combo.prog.pairs if not p.shape.isRest]
            if extremes:
                pairs = [p for p in pairs if abs(p.value) == 1.0]

            iv = combo.getInputVector()
            for pp in pairs:
                inVecs.append([x * pp.value for x in iv])
                shapeNames.append(pp.shape.name)
                keyIdxs.append(indexByShape[pp.shape])

        for trav in self.traversals:
            # Extremes doesn't make sense at all for traversals
            if ignoreTraversals:
                continue
            pairs = [p for p in trav.prog.pairs if not p.shape.isRest]
            if extremes:
                pairs = [p for p in pairs if abs(p.value) == 1.0]

            for pp in pairs:
                inVecs.append(trav.getInputVector(pp.value))
                shapeNames.append(pp.shape.name)
                keyIdxs.append(indexByShape[pp.shape])

        return shapeNames, inVecs, keyIdxs

    def evaluateInputs(self, inVecs):
        """Get the shape activation vectors that are paired with the given input vectors
        It will probably be useful to pass the returned inVecs from `buildInputVectors`

        This will use the compiled python solver, and may not be available

        Parameters
        ----------
        inVecs : [[SliderVal, ...], ...]
            A list of lists of sliderValues. Each sub-list has to have the same number of
            items as there are sliders in the current simplex system

        Returns
        -------
        : [[ShapeVal, ...], ...]
            A list of lists of shapeValues resulting from the given inVecs. This returns
            the activations of all the shape values. Each sub-list will have the same
            number of items as there are shapes in the current system.
        """
        from pysimplex import PySimplex

        solver = PySimplex(self.dump())
        return [solver.solve(iv) for iv in inVecs]

    def controllersByDepth(self):
        """Get the shapes ordered by the depth of their controllers
        in the simplex hierarchy
        This is often useful when doing vertex position computations

        Returns
        -------
        : [Shape, ...]
            A list of all shapes in the depth order
        """
        ctrlOrder = self.sliders[:]
        combosByDepth = {}
        for c in self.combos:
            combosByDepth.setdefault(len(c.pairs), []).append(c)

        for depth in sorted(combosByDepth.keys()):
            combos = combosByDepth[depth]
            regular, floating = [], []
            for c in combos:
                lst = floating if c.isFloating() else regular
                lst.append(c)
            ctrlOrder.extend(regular + floating)

        travByDepth = {}
        for t in self.traversals:
            travByDepth.setdefault(len(t.startPoint.pairs), []).append(t)

        for depth in sorted(travByDepth.keys()):
            ctrlOrder.extend(travByDepth[depth])

        return ctrlOrder

    # SPLIT CODE
    def buildSplitterList(self, foList):
        """The way deepcopy works is that every object visited is added to the 'memo' dictionary,
        keyed by its id(). This way, you don't have to re-copy an object if you've already seen
        it. This means that if I make a memo that already contains objects that I don't want copied,
        then I should just be able to use deepcopy, and that will handle keeping references to the
        un-copied objects.

        For example: If X references A, and I want to split X into L and R, then I would still want
        L to reference A *and* R to reference A. This process just auto-handles that
        I think that's is kinda neat.

        Parameters
        ----------
        foList : [Falloff, ....]
            A list of Falloff objects *that all share the same split axis*

        Returns
        -------
        : [object, ....]
            A list of objects to be split
        : dict
            A dict of {object: Falloff} saying what falloff should be used to split each objct
        : dict
            The memo to start the deepcopy with

        """
        # Add all items to the memo.
        memo = {}
        memo[id(self)] = self
        stack = Stack()
        stack.enabled = False
        memo[id(self.stack)] = stack
        memo[id(self.DCC)] = self.DCC

        memList = [
            self.groups,
            self.sliders,
            self.combos,
            self.traversals,
            self.falloffs,
            self.shapes,
            self.progs,
        ]

        for lst in memList:
            for item in lst:
                memo[id(item)] = item
                # splitApplied needs to be part of the item so it persists
                # through the copy. Otherwise I'd have to keep track of it
                item._splitApplied = set()

        # Using the memo from here would mean that nothing got copied
        # because all items are in it

        toSplit = []  # A list of objects to be split along the shared foList axis

        # A dictionary of {object: set(falloff)}. When recursing down the hierarchy,
        # some objects may be split by many falloffs. Keep track of that in this dict
        splitBySet = {}

        for prog in self.progs:
            # I take pains to this with lists (rather than sets) so it keeps order
            sect = [i for i in foList if i in prog.falloffs]
            if sect:
                # Because I can only split an item once on an axis
                # Assume that the foList is in priority order
                # ... So I can just grab the first (highest priority)
                # falloff affecting this item
                splitFalloff = sect[0]
                ctrl = prog.controller

                toSplit.append(prog)
                toSplit.append(ctrl)
                splitBySet.setdefault(prog, set()).add(splitFalloff)
                splitBySet.setdefault(ctrl, set()).add(splitFalloff)
                for pair in prog.pairs:
                    toSplit.append(pair.shape)
                    splitBySet.setdefault(pair.shape, set()).add(splitFalloff)

                # Also add the downstream combos, and their progs
                dss = []
                if isinstance(ctrl, Slider):
                    dss.extend(self.getDownstreamCombos(ctrl))
                    dss.extend(self.getDownstreamTraversals(ctrl))

                for ds in dss:
                    toSplit.append(ds)
                    toSplit.append(ds.prog)
                    splitBySet.setdefault(ds, set()).add(splitFalloff)
                    splitBySet.setdefault(ds.prog, set()).add(splitFalloff)
                    for pair in ds.prog.pairs:
                        toSplit.append(pair.shape)
                        splitBySet.setdefault(pair.shape, set()).add(splitFalloff)

        # Dict of {item : falloff}
        splitBy = {}
        for item, foSet in six.iteritems(splitBySet):
            # Because I can only split an item once on an axis
            # Assume that the foList is in priority order
            # So get the min-indexed falloff in the set
            idx = min([foList.index(f) for f in foSet])
            splitBy[item] = foList[idx]

        toSplit = set(toSplit)
        toSplit.discard(self.restShape)
        # Get the items to split that haven't already had a split applied along this axis
        toSplit = [i for i in toSplit if foList[0].axis not in i._splitApplied]
        # If I can't apply a sided name ot this item, then it can't be split
        toSplit = [i for i in toSplit if foList[0].canRename(i)]

        # Remove the splitter items from the memo, ensuring they actually get copied
        for sp in toSplit:
            try:
                del memo[id(sp)]
            except KeyError:
                print("SP", sp, sp.name)
                raise
            sp._splitApplied.add(foList[0].axis.lower())

        return toSplit, splitBy, memo

    def split(self, pBar=None):
        """Return a split deepcopy of the system.
        The new system will be a dummy system containing all the shapes as numpy arrays which can be
        exported to a .smpx file

        Parameters
        ----------
        pBar : QProgressDialog, optional
            If provided, display progress in this dialog

        Returns
        -------
        : Simplex :
            A newly split system

        """
        if np is None:
            raise RuntimeError("Numpy is not available, and splitting requires it")

        if pBar is not None:
            pBar.setValue(0)
            pBar.setLabelText("Building Split System")

        # Very first thing: Ensure that every object with a falloff is fully splittable
        # Meaning that splittable progs only contain splittable shapes. And splittable progs
        # are only controlled by splittable controllers
        for fo in self.falloffs:

            controllers = self.sliders + self.combos + self.traversals
            for ctrl in controllers:
                prog = ctrl.prog

                pSplit = fo.canRename(prog)
                cSplit = fo.canRename(ctrl)
                sSplit = [s for s in prog.getShapes() if not s.isRest]
                sSplit = [fo.canRename(shape) for shape in sSplit]
                sSplitSame = all([i == sSplit[0] for i in sSplit])
                sSplit = sSplit[0]
                if not sSplitSame:
                    shapes = [i.name for i in prog.getShapes()]
                    msg = "Bad shapes: {0}".format(", ".join(shapes))
                    raise ValueError(
                        "Mix of splittable and un-splittable shapes in a progression\n"
                        + msg
                    )

                if pSplit != sSplit:
                    msg = "Bad Prog: {0}".format(prog.name)
                    raise ValueError("A progression is not fully splittable\n" + msg)

                if pSplit != cSplit:
                    msg = "Bad prog: {0}\nBad Controller:{1}".format(
                        prog.name, ctrl.name
                    )
                    raise ValueError("A controller is not fully splittable\n" + msg)

        # Create the initial deepcopy
        splitSmpx = copy.deepcopy(self)
        splitSmpx.DCC.dummyLoad(self.DCC, pBar=pBar)

        # Sort the falloffs by which axis the split on
        foByAxis = {}
        for fo in splitSmpx.falloffs:
            foByAxis.setdefault(fo.axis.lower(), []).append(fo)

        for axis, foList in six.iteritems(foByAxis):
            if pBar is not None:
                pBar.setLabelText("Splitting On {0} axis".format(axis))
                QApplication.processEvents()
            else:
                print("Splitting On {0} axis".format(axis))

            # Get the items to split, and the memo that ensures *only* those items will be copied
            toSplit, splitBy, memo = splitSmpx.buildSplitterList(foList)

            # DeepCopy the items twice. Once for each side of the split
            lSideSplitList = copy.deepcopy(toSplit, memo=copy.copy(memo))
            rSideSplitList = copy.deepcopy(toSplit, memo=copy.copy(memo))

            if pBar is not None:
                pBar.setMaximum(len(toSplit))
                QApplication.processEvents()

            # Loop through the copied items and make the replacements
            for i, (oldItem, lItem, rItem) in enumerate(
                zip(toSplit, lSideSplitList, rSideSplitList)
            ):
                if pBar is not None:
                    pBar.setValue(i + 1)
                    QApplication.processEvents()

                # Get thefalloff that will split oldItem into lItem and rItem
                fo = splitBy[oldItem]

                # Rename the newly split items
                fo.splitRename(lItem, 0)
                fo.splitRename(rItem, 1)

                # Apply the falloff weights to any shapes
                if isinstance(oldItem, Shape):
                    fo.applyFalloff(lItem, 0)
                    fo.applyFalloff(rItem, 1)

                # Maybe for all this, get the index of the oldItem in the group
                # and insert rather than append??

                # Remove the oldItem from any groups and add the newItems
                if hasattr(oldItem, "group"):
                    oldItem.group.items.remove(oldItem)
                    oldItem.group = None
                    lItem.group.items.append(lItem)
                    rItem.group.items.append(rItem)

                # Remove the oldItem from the simplex storage, and add the newItems
                if isinstance(oldItem, Slider):
                    splitSmpx.sliders.remove(oldItem)
                    splitSmpx.sliders.append(lItem)
                    splitSmpx.sliders.append(rItem)
                elif isinstance(oldItem, Combo):
                    splitSmpx.combos.remove(oldItem)
                    splitSmpx.combos.append(lItem)
                    splitSmpx.combos.append(rItem)
                elif isinstance(oldItem, Traversal):
                    splitSmpx.traversals.remove(oldItem)
                    splitSmpx.traversals.append(lItem)
                    splitSmpx.traversals.append(rItem)
                elif isinstance(oldItem, Shape):
                    splitSmpx.shapes.remove(oldItem)
                    # Part of deepCopy ensures the new system uses the DummyDCC
                    # So this just removes the shape verts from the DummyDCC dictionary
                    # and doesn't actually delete the shape from anywhere important
                    splitSmpx.DCC.deleteShape(oldItem)
                    splitSmpx.shapes.append(lItem)
                    splitSmpx.shapes.append(rItem)

        splitSmpx.DCC.pushAllShapeVertices(splitSmpx.shapes)
        return splitSmpx
