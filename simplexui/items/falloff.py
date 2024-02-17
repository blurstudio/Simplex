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
import math

try:
    import numpy as np
except ImportError:
    np = None
from ..Qt.QtGui import QColor
from ..utils import nested
from .accessor import SimplexAccessor
from .stack import stackable


class Falloff(SimplexAccessor):
    """Falloffs define how shapes are split left/right, front/back, top/bottom, or however else

    Falloffs are the core of the splitting algorithm built into Simplex.
    When splitting, they define how shapes are duplicated and renamed, as well as
    how the deltas are multiplied.

    Currently only axis-aligned planar falloffs are fully defined and supported, but there are plans
    for per-point falloffs (weightmap), oriented planes, and other implicit geometric shapes.

    A planar falloff is a worldspace value field where any point past falloff min has the min value,
    any point past the max has the max value, and any point in between is defined by user-controlled curve
    Maya users might think of this as a planar projection of a ramp.

    A group of static variables controls how splits are detected and renamed. Names are split by
    Falloff.SEP and the split chunks are matched to the items below. In some cases, rather than
    lists of characters, I just use a string.

    These define the strings identifying their eponymous sides:
    LEFTSIDE, RIGHTSIDE, TOPSIDE, BOTTOMSIDE, FRONTSIDE, BACKSIDE

    This is a character list definint the single-character values that define centered shapes:
    CENTERS

    These define the strings that are detected to find splits.
    For instance, if HORIZONTAL_SPLIT="X", then cornerPuller_X would split across the X axis,
    and the new items would be given names

    ::
        "cornerPuller_{}".format(LEFTSIDE)
        "cornerPuller_{}".format(RIGHTSIDE)

    VERTICAL_SPLIT, VERTICAL_AXIS, VERTICAL_AXISINDEX
    HORIZONTAL_SPLIT, HORIZONTAL_AXIS, HORIZONTAL_AXISINDEX
    DEPTH_SPLIT, DEPTH_AXIS, DEPTH_AXISINDEX,

    When UNsplitting a simplex system, this value controls the tolerance
    UNSPLIT_GUESS_TOLERANCE

    Parameters
    ----------
    name : str
        The name of the falloff
    simplex : Simplex
        The Simplex system
    *data : list
        The data used to build this falloff.
        You should use one of the classmethod like Falloff.createPlanar or Falloff.createMap instead

    Returns
    -------

    """

    LEFTSIDE = "L"
    RIGHTSIDE = "R"
    TOPSIDE = "U"
    BOTTOMSIDE = "D"
    FRONTSIDE = "F"
    BACKSIDE = "B"
    ALLSIDES = LEFTSIDE + RIGHTSIDE + TOPSIDE + BOTTOMSIDE + FRONTSIDE + BACKSIDE

    CENTERS = "MC"

    VERTICAL_SPLIT = "V"
    VERTICAL_RESULTS = TOPSIDE + BOTTOMSIDE
    VERTICAL_AXIS = "Y"
    VERTICAL_AXISINDEX = 1

    HORIZONTAL_SPLIT = "X"
    HORIZONTAL_RESULTS = LEFTSIDE + RIGHTSIDE
    HORIZONTAL_AXIS = "X"
    HORIZONTAL_AXISINDEX = 0

    DEPTH_SPLIT = "Z"
    DEPTH_RESULTS = FRONTSIDE + BACKSIDE
    DEPTH_AXIS = "Z"
    DEPTH_AXISINDEX = 2

    RESTNAME = "Rest"
    SEP = "_"

    UNSPLIT_GUESS_TOLERANCE = 0.33

    def __init__(self, name, simplex, *data):
        super(Falloff, self).__init__(simplex)
        with self.stack.store(self):
            self._splitType = str(data[0]).lower()
            self._axis = None
            self._maxVal = None
            self._maxHandle = None
            self._minHandle = None
            self._minVal = None
            self._mapName = None

            self._bezier = None
            self._search = None
            self._rep = None
            self._weights = None
            self._verts = None
            self._thing = None
            self._thingRepr = None

            if self._splitType == "planar":
                self._axis = data[1]
                self._maxVal = data[2]
                self._maxHandle = data[3]
                self._minHandle = data[4]
                self._minVal = data[5]
            elif self._splitType == "map":
                self._mapName = data[1]
                self._axis = data[2]

            self._name = name
            self.children = []
            self._buildIdx = None
            self.expanded = {}
            self.color = QColor(128, 128, 128)

            mgrs = [model.insertItemManager(None) for model in self.falloffModels]
            with nested(*mgrs):
                self.simplex.falloffs.append(self)

            # newThing = self.DCC.getFalloffThing(self)
            # if newThing is None:
            # self.thing = self.DCC.createFalloff(self)
            # else:
            # self.thing = newThing

    # @property
    # def thing(self):
    ## if this is a deepcopied object, then self._thing will
    ## be None. Rebuild the thing connection by its representation
    # if self._thing is None and self._thingRepr:
    # self._thing = self.DCC.loadPersistentFalloff(self._thingRepr)
    # return self._thing

    # @thing.setter
    # def thing(self, value):
    # self._thing = value
    # self._thingRepr = self.DCC.getPersistentFalloff(value)

    @property
    def name(self):
        """Get the name of a Falloff"""
        return self._name

    @name.setter
    @stackable
    def name(self, value):
        """Set the name of a Falloff

        Parameters
        ----------
        value :


        Returns
        -------

        """
        self._name = value
        for model in self.falloffModels:
            model.itemDataChanged(self)

    @classmethod
    def createPlanar(cls, name, simplex, axis, maxVal, maxHandle, minHandle, minVal):
        """Create a planar falloff

        Parameters
        ----------
        name : str
            The name to give the falloff
        simplex : Simplex
            The Simplex system
        axis : str
            The axis to align the falloff to. X, Y, or Z
        maxVal : float
            The value past which the falloff is 1.0
        maxHandle : float
            The (0, 1) range of the max cubic falloff handle
        minHandle : float
            The (0, 1) range of the min cubic falloff handle
        minVal : float
            The value past which the falloff is 0.0

        Returns
        -------

        """
        return cls(name, simplex, "planar", axis, maxVal, maxHandle, minHandle, minVal)

    @classmethod
    def createMap(cls, name, simplex, mapName, axis):
        """Create a weightmap falloff

        Parameters
        ----------
        name : str
            The name to give the falloff
        simplex : Simplex
            The Simplex system
        mapName : str
            The name of the weightmap
        axis : str
            The axis to align the falloff to. X, Y, or Z

        Returns
        -------

        """
        return cls(name, simplex, "map", mapName, axis)

    @classmethod
    def loadV2(cls, simplex, data):
        """Load the falloff from the version 2 json specification

        Parameters
        ----------
        simplex : Simplex
            The Simplex system
        data : dict
            The data to load

        Returns
        -------
        : Falloff
            The specified Falloff

        """
        tpe = data["type"]
        name = data["name"]
        axis = data["axis"]
        if tpe == "map":
            return cls.createMap(name, simplex, data["mapName"], axis)
        elif tpe == "planar":
            maxVal = data["maxVal"]
            maxHandle = data["maxHandle"]
            minHandle = data["minHandle"]
            minVal = data["minVal"]
            return cls.createPlanar(
                name, simplex, axis, maxVal, maxHandle, minHandle, minVal
            )

        raise ValueError("Bad data passed to Falloff creation")

    def buildDefinition(self, simpDict, legacy):
        """Output a dictionary definition of this object

        Parameters
        ----------
        simpDict : dict
            The dictionary that is being built
        legacy : bool
            Whether to write out the legacy definition, or the newer one

        Returns
        -------

        """
        if self._buildIdx is None:
            self._buildIdx = len(simpDict["falloffs"])
            if legacy:
                if self.splitType == "planar":
                    line = [
                        "planar",
                        self.axis,
                        self.maxVal,
                        self.maxHandle,
                        self.minHandle,
                        self.minVal,
                    ]
                else:
                    line = ["map", self.mapName]
                simpDict.setdefault("falloffs", []).append([self.name] + line)
            else:
                x = {
                    "name": self.name,
                    "type": self.splitType,
                    "axis": self.axis,
                    "maxVal": self.maxVal,
                    "maxHandle": self.maxHandle,
                    "minHandle": self.minHandle,
                    "minVal": self.minVal,
                    "mapName": self.mapName,
                    "color": self.color.getRgb()[:3],
                }
                simpDict.setdefault("falloffs", []).append(x)
        return self._buildIdx

    def clearBuildIndex(self):
        """Clear the build index of this object

        The buildIndex is stored when building a definition dictionary
        that keeps track of its index for later referencing

        Parameters
        ----------

        Returns
        -------

        """
        self._buildIdx = None

    @stackable
    def duplicate(self, newName):
        """Duplicate a Falloff with a new name

        Parameters
        ----------
        newName : str
            The name to give the new Falloff

        Returns
        -------
        : Falloff
            The newly duplicated Falloff

        """
        nf = copy.copy(self)
        nf.name = newName
        nf.children = []
        nf.clearBuildIndex()
        mgrs = [model.insertItemManager(self) for model in self.falloffModels]
        with nested(*mgrs):
            self.simplex.falloffs.append(nf)
        self.DCC.duplicateFalloff(self, nf)
        return nf

    @stackable
    def delete(self):
        """Delete the Falloff"""
        fIdx = self.simplex.falloffs.index(self)
        for child in self.children:
            child.falloff = None

        mgrs = [model.removeItemManager(self) for model in self.falloffModels]
        with nested(*mgrs):
            self.simplex.falloffs.pop(fIdx)
        self.DCC.deleteFalloff(self)

    @stackable
    def setPlanarData(self, axis, minVal, minHandle, maxHandle, maxVal):
        """Set the type/data for a planar Falloff

        Parameters
        ----------
        axis : str
            The axis to align the falloff to. X, Y, or Z
        maxVal : float
            The value past which the falloff is 1.0
        maxHandle : float
            The (0, 1) range of the max cubic falloff handle
        minHandle : float
            The (0, 1) range of the min cubic falloff handle
        minVal : float
            The value past which the falloff is 0.0

        Returns
        -------

        """
        self.splitType = "planar"
        self.axis = axis
        self.minVal = minVal
        self.minHandle = minHandle
        self.maxHandle = maxHandle
        self.maxVal = maxVal
        self.mapName = None
        self._updateDCC()

    @stackable
    def setMapData(self, mapName):
        """Set the type/data for a map Falloff

        Parameters
        ----------
        mapName : str
            The name of the weightmap

        Returns
        -------

        """
        self.splitType = "map"
        self.axis = None
        self.minVal = None
        self.minHandle = None
        self.maxHandle = None
        self.maxVal = None
        self.mapName = mapName
        self._updateDCC()

    @property
    def splitType(self):
        return self._splitType

    @splitType.setter
    @stackable
    def splitType(self, value):
        self._splitType = str(value).lower()
        for model in self.falloffModels:
            model.itemDataChanged(self)
        self._updateDCC()

    @property
    def axis(self):
        return self._axis

    @axis.setter
    @stackable
    def axis(self, value):
        self._axis = value
        for model in self.falloffModels:
            model.itemDataChanged(self)
        self._updateDCC()

    @property
    def maxVal(self):
        return self._maxVal

    @maxVal.setter
    @stackable
    def maxVal(self, value):
        self._maxVal = value
        for model in self.falloffModels:
            model.itemDataChanged(self)
        self._updateDCC()

    @property
    def maxHandle(self):
        return self._maxHandle

    @maxHandle.setter
    @stackable
    def maxHandle(self, value):
        self._maxHandle = value
        for model in self.falloffModels:
            model.itemDataChanged(self)
        self._updateDCC()

    @property
    def minHandle(self):
        return self._minHandle

    @minHandle.setter
    @stackable
    def minHandle(self, value):
        self._minHandle = value
        for model in self.falloffModels:
            model.itemDataChanged(self)
        self._updateDCC()

    @property
    def minVal(self):
        return self._minVal

    @minVal.setter
    @stackable
    def minVal(self, value):
        self._minVal = value
        for model in self.falloffModels:
            model.itemDataChanged(self)
        self._updateDCC()

    @property
    def mapName(self):
        return self._mapName

    @mapName.setter
    @stackable
    def mapName(self, value):
        self._mapName = value
        for model in self.falloffModels:
            model.itemDataChanged(self)
        self._updateDCC()

    def _updateDCC(self):
        """ """
        self.DCC.setFalloffData(
            self,
            self.splitType,
            self.axis,
            self.minVal,
            self.minHandle,
            self.maxHandle,
            self.maxVal,
            self.mapName,
        )

    # Split code
    @property
    def bezier(self):
        """Pre-build a factorization of the cubic bezier curve that is being used for a falloff
        Based on method described at https://pomax.github.io/bezierinfo/#yforx

        Parameters
        ----------

        Returns
        -------

        """
        if self._bezier is None:
            p0x = 0.0
            p1x = self.minHandle
            p2x = self.maxHandle
            p3x = 1.0

            f = p1x - p0x
            g = p3x - p2x
            d = 3 * f + 3 * g - 2
            n = 2 * f + g - 1
            r = (n * n - f * d) / (d * d)
            qq = (3 * f * d * n - 2 * n * n * n) / (d * d * d)
            self._bezier = (qq, r, d, n)
        return self._bezier

    def getMultiplier(self, xVal):
        """Get the weight value for the given X

        Parameters
        ----------
        xVal : float
            The value to get the weight for

        Returns
        -------
        : float
            The weight

        """
        # Vertices are assumed to be at (0,0) and (1,1)
        if xVal <= self.minVal:
            return 0.0
        if xVal >= self.maxVal:
            return 1.0

        tVal = float(xVal - self.minVal) / float(self.maxVal - self.minVal)
        qq, r, d, n = self.bezier
        q = qq - tVal / d
        discriminant = q * q - 4 * r * r * r
        if discriminant >= 0:
            pm = (discriminant**0.5) / 2
            w = (-q / 2 + pm) ** (1 / 3.0)
            u = w + r / w
        else:
            theta = math.acos(-q / (2 * r ** (3 / 2.0)))
            phi = theta / 3 + 4 * math.pi / 3
            u = 2 * r ** (0.5) * math.cos(phi)
        t = u + n / d
        t1 = 1 - t
        return 3 * t1 * t**2 * 1 + t**3 * 1

    def _setSearchRep(self):
        """ """
        if self.axis.lower() == self.HORIZONTAL_AXIS.lower():
            self._search = self.HORIZONTAL_SPLIT
            self._rep = self.HORIZONTAL_RESULTS
        elif self.axis.lower() == self.VERTICAL_AXIS.lower():
            self._search = self.VERTICAL_SPLIT
            self._rep = self.VERTICAL_RESULTS
        elif self.axis.lower() == self.DEPTH_AXIS.lower():
            self._search = self.DEPTH_SPLIT
            self._rep = self.DEPTH_RESULTS

    @property
    def search(self):
        """The values this fallof searches for"""
        if self._search is None:
            self._setSearchRep()
        return self._search

    @property
    def rep(self):
        """The values this falloff replaces with"""
        if self._rep is None:
            self._setSearchRep()
        return self._rep

    @property
    def verts(self):
        """Get the stored vertex values"""
        return self._verts

    @verts.setter
    def verts(self, vals):
        """Input the vertices into this falloff and compute the weights

        Parameters
        ----------
        vals : np.array
            A (Nx3) numpy array of vertices

        Returns
        -------

        """
        if self.splitType != "map":
            # Clear out any auto-computed weights
            # when setting verts on a non-map falloff
            self._weights = None
        self._verts = vals

    @property
    def weights(self):
        """Get the per-vertex weight values"""

        if self._weights is None:
            if self.splitType == "map":
                raise ValueError(
                    "Attempted to auto-compute weights of a map falloff: {}".format(
                        self.name
                    )
                )

            if self._verts is None:
                raise ValueError(
                    "Attempted to auto-compute weights of a procedural falloff without setting verts: {0}".format(
                        self.name
                    )
                )

            if self.axis.lower() == self.HORIZONTAL_AXIS.lower():
                component = self.HORIZONTAL_AXISINDEX
            elif self.axis.lower() == self.VERTICAL_AXIS.lower():
                component = self.VERTICAL_AXISINDEX
            elif self.axis.lower() == self.DEPTH_AXIS.lower():
                component = self.DEPTH_AXISINDEX
            else:
                raise ValueError("Falloff found with no axis set")

            self._weights = np.array(
                [self.getMultiplier(v[component]) for v in self._verts]
            )

        return self._weights

    @weights.setter
    def weights(self, val):
        """Set the per-vertex weight values

        Parameters
        ----------
        val : A list or numpy array of values between 0 and 1
        """
        self._weights = np.asarray(val)

    def getSidedName(self, name, sIdx):
        """Take name to split along some axis, and replace the fields based on the index
        For instance, this could take cp_X and return cp_L for sIdx=1 and cp_R for sIdx=2

        Parameters
        ----------
        name : str
            The name to "split" with this falloff
        sIdx : int
            The index of the replacement value

        Returns
        -------
        : str
            The newly sided name

        """
        search = self.search
        replace = self.rep[sIdx]

        nn = name
        s = "{0}{1}{0}".format(self.SEP, search)
        r = "{0}{1}{0}".format(self.SEP, replace)
        nn = nn.replace(s, r)

        s = "{0}{1}".format(self.SEP, search)  # handle Postfix
        r = "{0}{1}".format(self.SEP, replace)
        if nn.endswith(s):
            nn = r.join(nn.rsplit(s, 1))

        s = "{1}{0}".format(self.SEP, search)  # handle Prefix
        r = "{1}{0}".format(self.SEP, replace)
        if nn.startswith(s):
            nn = nn.replace(s, r, 1)
        return nn

    def canRename(self, item):
        """Check if the item can be renamed by this Falloff

        Parameters
        ----------
        item : object
            The named simplex object to check

        Returns
        -------
        : bool
            Whether this object can be renamed

        """
        nn = self.getSidedName(item.name, 0)
        return nn != item.name

    def splitRename(self, item, sIdx):
        """Actually run the rename for a particular item

        Parameters
        ----------
        item : object
            The named Simplex Item
        sIdx : int
            The replacement index

        Returns
        -------

        """
        from .combo import Combo
        from .shape import Shape
        from .slider import Slider
        from .traversal import Traversal

        if isinstance(item, (Shape, Slider, Combo, Traversal)):
            item.name = self.getSidedName(item.name, sIdx)

    def applyFalloff(self, shape, sIdx):
        """Apply the falloff to the vertices of a shape

        Parameters
        ----------
        shape : Shape
            The shape to apply to
        sIdx : int
            The replacement index

        Returns
        -------

        """
        rest = self.simplex.restShape
        restVerts = rest.verts

        weights = self.weights
        if sIdx == 1:
            weights = 1 - weights

        weightedDeltas = (shape.verts - restVerts) * weights[:, None]
        shape.verts = weightedDeltas + restVerts
