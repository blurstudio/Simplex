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

import six
from six.moves import range, zip

# pylint:disable=missing-docstring,unused-argument,no-self-use
from ..Qt.QtGui import QColor
from ..utils import nested
from .accessor import SimplexAccessor
from .combo import Combo
from .group import Group
from .progression import Progression
from .slider import Slider
from .stack import stackable


class TravPair(SimplexAccessor):
    """ """

    classDepth = 4

    def __init__(self, slider, value):
        simplex = slider.simplex
        super(TravPair, self).__init__(simplex)
        self.slider = slider
        self._value = float(value)
        self.minValue = -1.0
        self.maxValue = 1.0
        self._tickDelta = 0.0
        self.travPoint = None
        self.expanded = {}

    def valueTick(self, ticks, mul):
        """ """
        self._tickDelta += self.dragStep * ticks * mul
        if (self._tickDelta + self.value) <= self.slider.minValue:
            self._tickDelta = self.slider.minValue - self.value
            if self.value != self.slider.minValue:
                self.value = self.slider.minValue
                self._tickDelta = 0.0
        elif (self._tickDelta + self.value) >= self.slider.maxValue:
            self._tickDelta = self.slider.maxValue - self.value
            if self.value != self.slider.maxValue:
                self._tickDelta = 0.0
                self.value = self.slider.maxValue
        elif abs(self._tickDelta + self.value) <= 1.0e-5:
            if self.value != 0.0:
                self._tickDelta = 0.0
                self.value = 0.0

    @property
    def models(self):
        """ """
        return self.simplex.models

    @property
    def name(self):
        """ """
        return self.slider.name

    @property
    def value(self):
        """ """
        return self._value

    @value.setter
    @stackable
    def value(self, val):
        """ """
        self._value = val
        for model in self.models:
            model.itemDataChanged(self)

    def buildDefinition(self, simpDict, legacy):
        """ """
        sIdx = self.slider.buildDefinition(simpDict, legacy)
        return sIdx, self.value

    def treeRow(self):
        """ """
        return self.travPoint.pairs.index(self)

    def treeParent(self):
        """ """
        return self.travPoint

    def treeData(self, column):
        """ """
        if column == 0:
            return self.name
        if column == 1:
            return self.value
        return None

    @stackable
    def remove(self):
        """ """
        mgrs = [model.removeItemManager(self) for model in self.models]
        with nested(*mgrs):
            self.travPoint.pairs.remove(self)
            self.travPoint = None

    @stackable
    def delete(self):
        """ """
        self.travPoint.traversal.removePairs([self])

    @staticmethod
    def removeAll(pairs):
        """ """
        travs = list(set([p.travPoint.traversal for p in pairs]))
        for trav in travs:
            trav.removePairs(pairs)


class TravPoint(SimplexAccessor):
    """ """

    classDepth = 3

    def __init__(self, pairs, row):
        if not pairs:
            raise ValueError("Pairs must be provided for a TravPoint")
        simplex = pairs[0].slider.simplex
        super(TravPoint, self).__init__(simplex)

        self.pairs = pairs
        for pair in pairs:
            pair.travPoint = self
        self.row = row
        self.traversal = None
        self.expanded = {}

    def sliders(self):
        """ """
        return [i.slider for i in self.pairs]

    @staticmethod
    def _wideCeiling(val, eps=0.001):
        """ """
        if val > eps:
            return 1.0
        elif val < -eps:
            return -1.0
        return 0.0

    @stackable
    def addPair(self, pair):
        """

        Parameters
        ----------
        pair :


        Returns
        -------

        """
        mgrs = [model.insertItemManager(self) for model in self.models]
        with nested(*mgrs):
            self.pairs.append(pair)
            pair.travPoint = self

    def removePair(self, pair):
        """

        Parameters
        ----------
        pair :


        Returns
        -------

        """
        pair.remove()

    def addSlider(self, slider, val=None):
        """

        Parameters
        ----------
        slider :

        val :
             (Default value = None)

        Returns
        -------

        """
        val = val if val is not None else slider.value
        val = self._wideCeiling(val)
        sliders = self.sliders()
        try:
            idx = sliders.index(slider)
        except ValueError:
            self.addPair(TravPair(slider, val))
        else:
            self.pairs[idx].value = val

    def addItem(self, item):
        """

        Parameters
        ----------
        item :


        Returns
        -------

        """
        if isinstance(item, Slider):
            self.addSlider(item)
        elif isinstance(item, Combo):
            for cp in item.pairs:
                self.addSlider(cp.slider, cp.value)

    @property
    def name(self):
        """ """
        return "START" if self.row == 0 else "END"

    def treeData(self, column):
        """

        Parameters
        ----------
        column :


        Returns
        -------

        """
        if column == 0:
            return self.name
        return None

    def treeChild(self, row):
        """

        Parameters
        ----------
        row :


        Returns
        -------

        """
        return self.pairs[row]

    def treeRow(self):
        """ """
        return self.row

    def treeParent(self):
        """ """
        return self.traversal

    def treeChildCount(self):
        """ """
        return len(self.pairs)

    def buildDefinition(self, simpDict, legacy):
        """

        Parameters
        ----------
        simpDict :

        legacy :


        Returns
        -------

        """
        return [p.buildDefinition(simpDict, legacy) for p in self.pairs]

    def getInputVector(self):
        """get the input to the solver that would fully activate this point of the traversal

        parameters
        ----------

        returns
        -------
        : [float, ...]
            the ordered slider values

        """
        invec = [0.0] * len(self.simplex.sliders)
        for cp in self.pairs:
            invec[self.simplex.sliders.index(cp.slider)] = cp.value
        return invec


class Traversal(SimplexAccessor):
    """Traversals control a Progression based on any 2 points in the Solver space.

    Traversals only make sense with intermediate shapes in the progression of the sliders
    that control it.

    Traversals should never have a shape at 100%. That shape should be handled by a Combo

    First: A "point in solver space" just means a list of slider/value pairs.
    The Slider/Value pairs that make a up a Combo are just a "Point in solver space" as well.
    So technically Combos could be thought of as a special-case of Traversals. Combos control
    a progression between the "Rest Point" where all sliders are at 0, and the Combo point

    Outside of the context of Traversals, I just call solver space points "Combos", because
    I don't need to be crazy specific like I do here.

    The initial use-case for Traversals was dealing with eye combo shapes with incremental
    Progressions. The eyeLookDown and the eyeClosed shapes both pull the upper lid down a great
    deal, and the eyeClosed was a 4-shape progression. So, when transitioning from eyeLookDown
    to eyeLookDown+eyeClosed, the deltas for all the progressive shapes were being triggered as
    the combo was coming on, causing major wobbles in the eyelid. So we needed shapes that
    countered those incrementals, but *only* on the transition from eyeLookDown to
    eyeLookDown+eyeClosed (NOT on the transition from eyeClosed to eyeLookDown+eyeClosed)

    Early setups used floating Combos, but those have linearinterpolation, and I wanted a
    cleaner solution. That solution is the Traversal

    Parameters
    ----------
    name : str
        The name of this Combo
    simplex : Simplex
        The parent Simplex system
    startPoint : TravPoint
        A set of Slider/Value pairs where the Traversal solves to 0
    endPoint : TravPoint
        A set of Slider/Value pairs where the Traversal solves to 1
    prog : Progression
        The Progression that this Combo controls
    group : Group
        The Group to create this combo in
    color : QColor
        The color of this item in the UI

    Returns
    -------

    """

    classDepth = 2

    def __init__(
        self,
        name,
        simplex,
        startPoint,
        endPoint,
        prog,
        group,
        color=QColor(128, 128, 128),
    ):

        super(Traversal, self).__init__(simplex)
        with self.stack.store(self):
            if group.groupType != type(self):
                raise ValueError(
                    "Cannot add this Traversal to a group of a different type"
                )
            self._name = name
            self.startPoint = startPoint
            self.endPoint = endPoint
            self.prog = prog
            self._buildIdx = None
            self.expanded = {}
            self._enabled = True
            self.color = color

            mgrs = [model.insertItemManager(group) for model in self.models]
            with nested(*mgrs):
                self.group = group
                self.startPoint.traversal = self
                self.endPoint.traversal = self
                self.prog.controller = self
                self.group.items.append(self)
                self.simplex.traversals.append(self)

    @classmethod
    def createTraversal(cls, name, simplex, startPairs, endPairs, group=None, count=4):
        """Create a Traversal between two lists of pairs

        Parameters
        ----------
        name : str
            The name of this Combo
        simplex : Simplex
            The parent Simplex system
        startPairs : [(Slider
            A list of Slider/Value pairs to make the startPoint
        endPairs : [(Slider
            A list of Slider/Value pairs to make the endPoint
        group : Group
            The Group to create this combo in (Default value = None)
        count : int
            The number of incrementals to create (including the 100%) (Default value = 4)

        Returns
        -------

        """
        if simplex.restShape is None:
            raise RuntimeError("Simplex system is missing rest shape")

        if group is None:
            gname = "TRAVERSALS"
            matches = [i for i in simplex.traversalGroups if i.name == gname]
            if matches:
                group = matches[0]
            else:
                group = Group(gname, simplex, Traversal)

        startPairs = [TravPair(p[0], p[1]) for p in startPairs]
        endPairs = [TravPair(p[0], p[1]) for p in endPairs]

        startPoint = TravPoint(startPairs, 0)
        endPoint = TravPoint(endPairs, 1)

        prog = Progression(name, simplex)
        trav = cls(name, simplex, startPoint, endPoint, prog, group)

        for c in reversed(list(range(count))):
            val = (100 * (c + 1)) // count
            pp = prog.createShape("{0}_{1}".format(name, val), val / 100.0)
            simplex.DCC.zeroShape(pp.shape)
        return trav

    @property
    def enabled(self):
        """Get whether this Traversal is evaluated in the solver"""
        return self._enabled

    @enabled.setter
    @stackable
    def enabled(self, value):
        """Set whether this Traversal is evaluated in the solver

        Parameters
        ----------
        value :


        Returns
        -------

        """
        self._enabled = value
        for model in self.models:
            model.itemDataChanged(self)

    @property
    def name(self):
        """Get the name of a Traversal"""
        return self._name

    @name.setter
    @stackable
    def name(self, value):
        """Set the name of a Traversal

        Parameters
        ----------
        value :


        Returns
        -------

        """
        self._name = value
        self.prog.name = value
        # self.DCC.renameTraversal(self, value)
        # for model in self.models:
        # model.itemDataChanged(self)

    def treeChild(self, row):
        """

        Parameters
        ----------
        row :


        Returns
        -------

        """
        if row == 0:
            return self.startPoint
        elif row == 1:
            return self.endPoint
        elif row == 2:
            return self.prog
        return None

    def treeRow(self):
        """ """
        return self.group.items.index(self)

    def treeParent(self):
        """ """
        return self.group

    def treeChildCount(self):
        """ """
        return 3

    def treeChecked(self):
        """ """
        return self.enabled

    def allSliders(self):
        """Get the list of all Sliders that control this Traversal

        Parameters
        ----------

        Returns
        -------
        : [Slider, ...]
            The list of all Sliders that control this Traversal

        """
        startSliders = [p.slider for p in self.startPoint.pairs]
        endSliders = [
            p.slider for p in self.endPoint.pairs if p.slider not in startSliders
        ]
        return startSliders + endSliders

    def dynamicSliders(self):
        """Get a list of sliders that have different values at the start and end"""
        return [sli for sli, rng in self.ranges() if rng[0] != rng[1]]

    def staticSliders(self):
        """Get a list of sliders that have the same values at the start and end"""
        return [sli for sli, rng in self.ranges() if rng[0] == rng[1]]

    def ranges(self):
        """Get the range per Slider for this Traversal

        Parameters
        ----------

        Returns
        -------
        : type
            (dict): A {Slider: range} dict

        """
        startDict = {p.slider: p.value for p in self.startPoint.pairs}
        endDict = {p.slider: p.value for p in self.endPoint.pairs}
        allSliders = six.viewkeys(startDict) | six.viewkeys(endDict)

        rangeDict = {}
        for sli in allSliders:
            rangeDict[sli] = (startDict.get(sli, 0.0), endDict.get(sli, 0.0))
        return rangeDict

    @staticmethod
    def buildTraversalName(ranges):
        """Given the range dict (like from Traversal.ranges()) come up with a name

        Parameters
        ----------
        ranges : dict
            A {Slider: range} dict

        Returns
        -------
        : str
            The suggested Traversal name

        """
        static, dynamic = [], []
        for sli, rng in six.iteritems(ranges):
            if rng[0] == rng[1]:
                static.append(sli)
            else:
                dynamic.append(sli)

        parts = []
        for grp in static, dynamic:
            for slider in sorted(grp, key=lambda x: x.name):
                prefix = None
                start, end = ranges[slider]
                if start == end:
                    # prefix = 'St' # St for Static
                    if start == 0:
                        continue
                    shp = slider.prog.getShapeAtValue(start)
                    if shp is None:
                        continue
                    name = shp.strippedName()
                else:
                    prefix = "Dy"  # Dy for Dynamic
                    if start == 0:
                        shp = slider.prog.getShapeAtValue(end)
                        if shp is None:
                            continue
                        name = shp.strippedName()
                    elif end == 0:
                        shp = slider.prog.getShapeAtValue(start)
                        if shp is None:
                            continue
                        name = shp.strippedName()
                    else:
                        name = slider.name

                if prefix is not None:
                    parts.append(prefix)
                parts.append(name)

        return "Tv_" + "_".join(parts)

    def controllerNameLinks(self):
        """ """
        surr = "_{0}_".format(self.name)
        return ["_{0}_".format(sli) in surr for sli in self.allSliders()]

    def nameLinks(self):
        """

        Parameters
        ----------

        Returns
        -------
        : type
            progression depends on this traversal's name

        """
        # In this case, these names will *NOT* have the possibility of
        # a pos/neg name. Only the traversal name, and possibly a percentage
        shapeNames = []
        shapes = [i.shape for i in self.prog.pairs]
        for s in shapes:
            x = s.name.rsplit("_", 1)
            if len(x) == 2:
                base, sfx = x
                x = base if sfx.isdigit() else s.name
            shapeNames.append(x)
        return [i == self.name for i in shapeNames]

    @stackable
    def createShape(self, shapeName=None, tVal=None):
        """Create a shape and add it to a progression

        Parameters
        ----------
        shapeName : str or None
            The name of the shape to create.
            If None, give it a default name
        tVal : float or None
            The progression value to set for the new Shape.
            If None, it gets a "smart" default value

        Returns
        -------

        """
        pp, idx = self.prog.newProgPair(shapeName, tVal)
        mgrs = [model.insertItemManager(self.prog, idx) for model in self.models]
        with nested(*mgrs):
            pp.prog = self.prog
            self.prog.pairs.insert(idx, pp)
        return pp

    @classmethod
    def loadV2(cls, simplex, progs, data):
        """Load the data from a version2 formatted json dictionary

        Parameters
        ----------
        simplex : Simplex
            The Simplex system that's being built
        progs : [Progression
            The progressions that have already been built
        data : dict
            The chunk of the json dict used to build this object

        Returns
        -------
        : Traversal
            The specified Traversal

        """
        name = data["name"]
        prog = progs[data["prog"]]
        group = simplex.groups[data.get("group", 2)]
        color = QColor(*data.get("color", (0, 0, 0)))

        rangeDict = {}  # slider: [startVal, endVal]

        pFlip = -1.0 if data["progressFlip"] else 1.0
        pcIdx = data["progressControl"]
        if data["progressType"].lower() == "slider":
            sli = simplex.sliders[pcIdx]
            rangeDict[sli] = (0.0, pFlip)
        else:
            cmb = simplex.combos[pcIdx]
            for cp in cmb.pairs:
                rangeDict[cp.slider] = (0.0, cp.value)

        mFlip = -1.0 if data["multiplierFlip"] else 1.0
        mcIdx = data["multiplierControl"]
        if data["multiplierType"].lower() == "slider":
            sli = simplex.sliders[mcIdx]
            rangeDict[sli] = (mFlip, mFlip)
        else:
            cmb = simplex.combos[mcIdx]
            for cp in cmb.pairs:
                rangeDict[cp.slider] = (cp.value, cp.value)

        ssli = sorted(list(rangeDict.items()), key=lambda x: x[0].name)
        startPairs, endPairs = [], []
        for slider, (startVal, endVal) in ssli:
            startPairs.append(TravPair(slider, startVal))
            endPairs.append(TravPair(slider, endVal))

        startPoint = TravPoint(startPairs, 0)
        endPoint = TravPoint(endPairs, 1)

        return cls(name, simplex, startPoint, endPoint, prog, group, color)

    @classmethod
    def loadV3(cls, simplex, progs, data):
        """Load the data from a version3 formatted json dictionary

        Parameters
        ----------
        simplex : Simplex
            The Simplex system that's being built
        progs : [Progression
            The progressions that have already been built
        data : dict
            The chunk of the json dict used to build this object

        Returns
        -------
        : Traversal
            The specified Traversal

        """
        name = data["name"]
        prog = progs[data["prog"]]
        group = simplex.groups[data.get("group", 2)]
        color = QColor(*data.get("color", (0, 0, 0)))

        startDict = dict(data["start"])
        endDict = dict(data["end"])
        sliIdxs = sorted(six.viewkeys(startDict) | six.viewkeys(endDict))
        startPairs, endPairs = [], []
        for idx in sliIdxs:
            startPairs.append(TravPair(simplex.sliders[idx], startDict.get(idx, 0.0)))
            endPairs.append(TravPair(simplex.sliders[idx], endDict.get(idx, 0.0)))
        startPoint = TravPoint(startPairs, 0)
        endPoint = TravPoint(endPairs, 1)

        return cls(name, simplex, startPoint, endPoint, prog, group, color)

    def buildDefinition(self, simpDict, legacy):
        """Output a dictionary definition of this object

        Parameters
        ----------
        simpDict : dict
            The dictionary that is being built
        legacy : bool
            Whether to write out the legacy definition, or the newer one
            This is ignored for Traversals. There is no legacy definition

        Returns
        -------

        """
        if self._buildIdx is None:
            self._buildIdx = len(simpDict["traversals"])
            x = {
                "name": self.name,
                "prog": self.prog.buildDefinition(simpDict, legacy),
                "start": self.startPoint.buildDefinition(simpDict, legacy),
                "end": self.endPoint.buildDefinition(simpDict, legacy),
                "group": self.group.buildDefinition(simpDict, legacy),
                "color": self.color.getRgb()[:3],
                "enabled": self._enabled,
            }
            simpDict.setdefault("traversals", []).append(x)
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
        self.prog.clearBuildIndex()
        self.group.clearBuildIndex()

    @stackable
    def delete(self):
        """Delete a traversal and any shapes it contains"""
        mgrs = [model.removeItemManager(self) for model in self.models]
        with nested(*mgrs):
            g = self.group
            if self not in g.items:
                return  # Can happen when deleting multiple groups
            g.items.remove(self)
            self.group = None
            self.simplex.traversals.remove(self)

            pairs = self.prog.pairs[:]  # gotta make a copy
            for pp in pairs:
                if not pp.shape.isRest:
                    self.simplex.shapes.remove(pp.shape)
                    self.DCC.deleteShape(pp.shape)

    def extractShape(self, shape, live=True, offset=10.0):
        """Extract a shape from a Traversal progression

        Parameters
        ----------
        shape :

        live :
             (Default value = True)
        offset :
             (Default value = 10.0)

        Returns
        -------

        """
        return self.DCC.extractTraversalShape(self, shape, live, offset)

    def addSlider(self, slider):
        """Add a slider to both the startPoint and endPoint of this Traversal

        Parameters
        ----------
        slider : Slider
            The slider to add

        Returns
        -------

        """
        self.startPoint.addSlider(slider, val=0.0)
        self.endPoint.addSlider(slider)

    def removePairs(self, pairs):
        """Remove the given pairs from both the startPoint and endPoint of this Traversal

        Parameters
        ----------
        pairs : [TravPair
            The pairs to remove

        Returns
        -------

        """
        # Get only the pairs that are a part of this traversal
        sPairs = [i for i in self.startPoint.pairs if i in pairs]
        ePairs = [i for i in self.endPoint.pairs if i in pairs]
        pairs = sPairs + ePairs

        # Get all the pairs that use the selected sliders
        sliders = set([p.slider for p in pairs])
        sPairs = [i for i in self.startPoint.pairs if i.slider in sliders]
        ePairs = [i for i in self.endPoint.pairs if i.slider in sliders]

        # do the removal
        for pair in sPairs:
            pair.remove()

        for pair in ePairs:
            pair.remove()

    @staticmethod
    def traversalAlreadyExists(simplex, sliders, ranges):
        """In a given simplex syste, check if a traversal exists
        with the given sliders and ranges
        """
        chk = dict(zip(sliders, ranges))
        for trav in simplex.traversals:
            if chk == trav.ranges():
                return trav
        return None

    @staticmethod
    def getCount(sliders, ranges):
        """Get the count of shapes to create for a traversal with the given
        sliders and ranges. It's the max number of shapes on a given side of 0
        """
        counts = []
        for sli, rng in zip(sliders, ranges):
            if rng[0] == rng[1]:
                continue
            vals = sli.prog.getValues()
            if max(rng) == 0:
                count = len([v for v in vals if v < 0])
            else:
                count = len([v for v in vals if v > 0])
            counts.append(count)
        if not counts:
            return 0
        return max(counts)

    def getInputVector(self, value):
        """Get the input to the Solver that would set this traversal to
        the given value

        Parameters
        ----------
        value : float
            The value to set the traversal to

        Returns
        -------
        : [float, ...]
            The ordered slider values

        """
        indexBySlider = {slider: idx for idx, slider in enumerate(self.simplex.sliders)}

        fullStart = [0.0] * len(self.simplex.sliders)
        for pair in self.startPoint.pairs:
            fullStart[indexBySlider[pair.slider]] = pair.value

        fullEnd = [0.0] * len(self.simplex.sliders)
        for pair in self.endPoint.pairs:
            fullEnd[indexBySlider[pair.slider]] = pair.value

        def _lerp(s, e, v):
            return s * (1 - v) + e * v

        return [_lerp(fs, fe, value) for fs, fe in zip(fullStart, fullEnd)]
