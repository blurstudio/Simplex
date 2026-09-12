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
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from .accessor import SimplexTreeAccessor
from .combo import Combo
from .dragItem import Draggable
from .group import Group
from .progression import Progression
from .slider import Slider
from .stack import stackable
from .treeItem import TreeItem

if TYPE_CHECKING:
    from .progression import ProgPair
    from .simplex import DCCObject, Simplex


class TravSide(Enum):
    Start = "START"
    End = "END"


class TravPair(SimplexTreeAccessor, Draggable):
    classDepth: int = 4

    def __init__(self, slider: Slider, value: float) -> None:
        simplex = slider.simplex
        super().__init__(simplex)
        self.slider: Slider = slider
        self._value: float = float(value)
        self.minValue: float = -1.0
        self.maxValue: float = 1.0
        self._tickDelta: float = 0.0
        self.travPoint: TravPoint | None = None

    @property
    def name(self) -> str:
        return self.slider.name

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    @stackable
    def value(self, val: float) -> None:
        self._value = val

    def buildDefinition(
        self, simpDict: dict[str, Any], legacy: bool
    ) -> tuple[int, float]:
        sIdx = self.slider.buildDefinition(simpDict, legacy)
        return sIdx, self.value

    @stackable
    def remove(self) -> None:
        with self.removeItemManager(self):
            if self.travPoint is not None:
                self.travPoint.pairs.remove(self)
            self.travPoint = None

    @stackable
    def delete(self) -> None:
        if self.travPoint is not None:
            if self.travPoint.traversal is not None:
                self.travPoint.traversal.removePairs([self])

    @staticmethod
    def removeAll(pairs: list[TravPair]) -> None:
        points = [i.travPoint for i in pairs if i.travPoint is not None]
        travs = list({pp.traversal for pp in points})
        for trav in travs:
            if trav is not None:
                trav.removePairs(pairs)

    def treeRow(self) -> int:
        if self.travPoint is None:
            raise ValueError(
                "Somehow you're trying to show a TravPair with no TravPoint"
            )
        return self.travPoint.pairs.index(self)

    def treeParent(self) -> TreeItem:
        if self.travPoint is None:
            raise ValueError("")
        return self.travPoint

    def treeData(self, column: int) -> Any | None:
        if column == 0:
            return self.name
        if column == 1:
            return self.value
        return None


class TravPoint(SimplexTreeAccessor):
    classDepth: int = 3

    def __init__(self, pairs: list[TravPair], side: TravSide) -> None:
        if not pairs:
            raise ValueError("Pairs must be provided for a TravPoint")
        simplex = pairs[0].slider.simplex
        super().__init__(simplex)

        self.pairs = pairs
        for pair in pairs:
            pair.travPoint = self
        self.side: TravSide = side
        self.traversal: Traversal | None = None

    def sliders(self) -> list[Slider]:
        return [i.slider for i in self.pairs]

    @staticmethod
    def _wideCeiling(val: float, eps: float = 0.001) -> float:
        if val > eps:
            return 1.0
        elif val < -eps:
            return -1.0
        return 0.0

    @stackable
    def addPair(self, pair: TravPair) -> None:
        with self.insertItemManager(self):
            self.pairs.append(pair)
            pair.travPoint = self

    def removePair(self, pair: TravPair) -> None:
        pair.remove()

    def addSlider(self, slider: Slider, val: float | None = None) -> None:
        val = val if val is not None else slider.value
        val = self._wideCeiling(val)
        sliders = self.sliders()
        try:
            idx = sliders.index(slider)
        except ValueError:
            self.addPair(TravPair(slider, val))
        else:
            self.pairs[idx].value = val

    def addItem(self, item: Slider | Combo) -> None:
        if isinstance(item, Slider):
            self.addSlider(item)
        elif isinstance(item, Combo):
            for cp in item.pairs:
                self.addSlider(cp.slider, cp.value)

    @property
    def name(self) -> str:
        return self.side.value

    def buildDefinition(
        self, simpDict: dict[str, Any], legacy: bool
    ) -> list[tuple[int, float]]:
        return [p.buildDefinition(simpDict, legacy) for p in self.pairs]

    def getInputVector(self) -> list[float]:
        """Get the input to the solver that would fully activate this point of the traversal

        returns
        -------
        : [float, ...]
            the ordered slider values
        """
        invec = [0.0] * len(self.simplex.sliders)
        for cp in self.pairs:
            invec[self.simplex.sliders.index(cp.slider)] = cp.value
        return invec

    def treeData(self, column: int) -> Any | None:
        if column == 0:
            return self.name
        return None

    def treeChild(self, row: int) -> TreeItem:
        return self.pairs[row]

    def treeRow(self) -> int:
        if self.side == TravSide.Start:
            return 0
        return 1

    def treeParent(self) -> TreeItem | None:
        return self.traversal

    def treeChildCount(self) -> int:
        return len(self.pairs)


class Traversal(SimplexTreeAccessor):
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
    """

    classDepth: int = 2

    def __init__(
        self,
        name: str,
        simplex: Simplex,
        startPoint: TravPoint,
        endPoint: TravPoint,
        prog: Progression,
        group: Group,
    ) -> None:
        super().__init__(simplex)
        with self.stack.store(self):
            if group.groupType is not type(self):
                raise ValueError(
                    "Cannot add this Traversal to a group of a different type"
                )
            self._name: str = name
            self.startPoint: TravPoint = startPoint
            self.endPoint: TravPoint = endPoint
            self.prog: Progression = prog
            self.prog.controller = self
            self._buildIdx: int | None = None
            self._enabled: bool = True
            self.startPoint.traversal = self
            self.endPoint.traversal = self
            self.simplex.traversals.append(self)

            with self.insertItemManager(group):
                self.group: Group = group
                self.group.items.append(self)

    @classmethod
    def createTraversal(
        cls,
        name: str,
        simplex: Simplex,
        startPairs: list[tuple[Slider, float]],
        endPairs: list[tuple[Slider, float]],
        group: Group | None = None,
        count: int = 4,
    ) -> Traversal:
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

        startTPairs = [TravPair(p[0], p[1]) for p in startPairs]
        endTPairs = [TravPair(p[0], p[1]) for p in endPairs]

        startPoint = TravPoint(startTPairs, TravSide.Start)
        endPoint = TravPoint(endTPairs, TravSide.End)

        prog = Progression(name, simplex)
        trav = cls(name, simplex, startPoint, endPoint, prog, group)

        for c in reversed(list(range(count))):
            val = (100 * (c + 1)) // count
            pp = prog.createShape(f"{name}_{val}", val / 100.0)
            simplex.DCC.zeroShape(pp.shape)
        return trav

    @property
    def enabled(self) -> bool:
        """Get whether this Traversal is evaluated in the solver"""
        return self._enabled

    @enabled.setter
    @stackable
    def enabled(self, value: bool) -> None:
        """Set whether this Traversal is evaluated in the solver"""
        self._enabled = value

    @property
    def name(self) -> str:
        """Get the name of a Traversal"""
        return self._name

    @name.setter
    @stackable
    def name(self, value: str) -> None:
        """Set the name of a Traversal"""
        self._name = value
        self.prog.name = value
        # self.DCC.renameTraversal(self, value)

    def allSliders(self) -> list[Slider]:
        """Get the list of all Sliders that control this Traversal
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

    def dynamicSliders(self) -> list[Slider]:
        """Get a list of sliders that have different values at the start and end"""
        return [sli for sli, rng in self.ranges().items() if rng[0] != rng[1]]

    def staticSliders(self) -> list[Slider]:
        """Get a list of sliders that have the same values at the start and end"""
        return [sli for sli, rng in self.ranges().items() if rng[0] == rng[1]]

    def ranges(self) -> dict[Slider, tuple[float, float]]:
        """Get the range per Slider for this Traversal

        Returns
        -------
        : type
            (dict): A {Slider: range} dict
        """
        startDict = {p.slider: p.value for p in self.startPoint.pairs}
        endDict = {p.slider: p.value for p in self.endPoint.pairs}
        allSliders = startDict.keys() | endDict.keys()

        rangeDict = {}
        for sli in allSliders:
            rangeDict[sli] = (startDict.get(sli, 0.0), endDict.get(sli, 0.0))
        return rangeDict

    @stackable
    def setGroup(self, grp: Group) -> None:
        """Set the Group for this Slider

        Parameters
        ----------
        grp : Group
            The Group to put this Slider under
        """
        if grp.groupType is None:
            grp.groupType = type(self)

        if not isinstance(self, grp.groupType):
            raise ValueError(
                f"All items in this group must be of type: {grp.groupType}"
            )

        if self.group:
            self.group.items.remove(self)
        grp.items.append(self)
        self.group = grp

    @staticmethod
    def buildTraversalName(ranges: dict[Slider, tuple[float, float]]) -> str:
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
        for sli, rng in ranges.items():
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

    def controllerNameLinks(self) -> list[bool]:
        surr = f"_{self.name}_"
        return [f"_{sli}_" in surr for sli in self.allSliders()]

    def nameLinks(self) -> list[bool]:
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
    def createShape(
        self, shapeName: str | None = None, tVal: float | None = None
    ) -> ProgPair:
        """Create a shape and add it to a progression

        Parameters
        ----------
        shapeName : str or None
            The name of the shape to create.
            If None, give it a default name
        tVal : float or None
            The progression value to set for the new Shape.
            If None, it gets a "smart" default value
        """
        pp, idx = self.prog.newProgPair(shapeName, tVal)
        with self.insertItemManager(self.prog, row=idx):
            pp.prog = self.prog
            self.prog.pairs.insert(idx, pp)
        return pp

    @classmethod
    def loadV2(
        cls, simplex: Simplex, progs: list[Progression], data: dict[str, Any]
    ) -> Traversal:
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

        ssli = sorted((rangeDict.items()), key=lambda x: x[0].name)
        startPairs, endPairs = [], []
        for slider, (startVal, endVal) in ssli:
            startPairs.append(TravPair(slider, startVal))
            endPairs.append(TravPair(slider, endVal))

        startPoint = TravPoint(startPairs, TravSide.Start)
        endPoint = TravPoint(endPairs, TravSide.End)

        return cls(name, simplex, startPoint, endPoint, prog, group)

    @classmethod
    def loadV3(
        cls, simplex: Simplex, progs: list[Progression], data: dict[str, Any]
    ) -> Traversal:
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

        startDict = dict(data["start"])
        endDict = dict(data["end"])
        sliIdxs = sorted(startDict.keys() | endDict.keys())
        startPairs, endPairs = [], []
        for idx in sliIdxs:
            startPairs.append(TravPair(simplex.sliders[idx], startDict.get(idx, 0.0)))
            endPairs.append(TravPair(simplex.sliders[idx], endDict.get(idx, 0.0)))
        startPoint = TravPoint(startPairs, TravSide.Start)
        endPoint = TravPoint(endPairs, TravSide.End)

        return cls(name, simplex, startPoint, endPoint, prog, group)

    def buildDefinition(self, simpDict: dict[str, Any], legacy: bool) -> int:
        """Output a dictionary definition of this object

        Parameters
        ----------
        simpDict : dict
            The dictionary that is being built
        legacy : bool
            Whether to write out the legacy definition, or the newer one
            This is ignored for Traversals. There is no legacy definition
        """
        if self._buildIdx is None:
            self._buildIdx = len(simpDict["traversals"])
            x = {
                "name": self.name,
                "prog": self.prog.buildDefinition(simpDict, legacy),
                "start": self.startPoint.buildDefinition(simpDict, legacy),
                "end": self.endPoint.buildDefinition(simpDict, legacy),
                "group": self.group.buildDefinition(simpDict, legacy),
                "enabled": self._enabled,
            }
            simpDict.setdefault("traversals", []).append(x)
        return self._buildIdx

    def clearBuildIndex(self) -> None:
        """Clear the build index of this object

        The buildIndex is stored when building a definition dictionary
        that keeps track of its index for later referencing
        """
        self._buildIdx = None
        self.prog.clearBuildIndex()
        self.group.clearBuildIndex()

    @stackable
    def delete(self) -> None:
        """Delete a traversal and any shapes it contains"""
        with self.removeItemManager(self):
            g = self.group
            if self not in g.items:
                return  # Can happen when deleting multiple groups
            g.items.remove(self)
            self.group = None  # type: ignore
            self.simplex.traversals.remove(self)

            pairs = self.prog.pairs[:]  # gotta make a copy
            for pp in pairs:
                if not pp.shape.isRest:
                    self.simplex.shapes.remove(pp.shape)
                    self.DCC.deleteShape(pp.shape)

    def extractShape(self, shape, live: bool = True, offset: float = 10.0) -> DCCObject:
        """Extract a shape from a Traversal progression"""
        return self.DCC.extractTraversalShape(self, shape, live, offset)

    def addSlider(self, slider: Slider) -> None:
        """Add a slider to both the startPoint and endPoint of this Traversal

        Parameters
        ----------
        slider : Slider
            The slider to add
        """
        self.startPoint.addSlider(slider, val=0.0)
        self.endPoint.addSlider(slider)

    def removePairs(self, pairs: list[TravPair]) -> None:
        """Remove the given pairs from both the startPoint and endPoint of this Traversal

        Parameters
        ----------
        pairs : [TravPair
            The pairs to remove
        """
        # Get only the pairs that are a part of this traversal
        sPairs = [i for i in self.startPoint.pairs if i in pairs]
        ePairs = [i for i in self.endPoint.pairs if i in pairs]
        pairs = sPairs + ePairs

        # Get all the pairs that use the selected sliders
        sliders = {p.slider for p in pairs}
        sPairs = [i for i in self.startPoint.pairs if i.slider in sliders]
        ePairs = [i for i in self.endPoint.pairs if i.slider in sliders]

        # do the removal
        for pair in sPairs:
            pair.remove()

        for pair in ePairs:
            pair.remove()

    @staticmethod
    def traversalAlreadyExists(
        simplex: Simplex, sliders: list[Slider], ranges: list[tuple[float, float]]
    ) -> Traversal | None:
        """In a given simplex syste, check if a traversal exists
        with the given sliders and ranges
        """
        chk = dict(zip(sliders, ranges))
        for trav in simplex.traversals:
            if chk == trav.ranges():
                return trav
        return None

    @staticmethod
    def getCount(sliders: list[Slider], ranges: list[tuple[float, float]]) -> int:
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

    def getInputVector(self, value: float) -> list[float]:
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

        def _lerp(s: float, e: float, v: float) -> float:
            return s * (1 - v) + e * v

        return [_lerp(fs, fe, value) for fs, fe in zip(fullStart, fullEnd)]

    def treeChild(self, row: int) -> TreeItem:
        if row == 0:
            return self.startPoint
        elif row == 1:
            return self.endPoint
        elif row == 2:
            return self.prog
        raise ValueError("Somehow have a Traversal item with more than 3 children")

    def treeRow(self) -> int:
        return self.group.items.index(self)

    def treeParent(self) -> TreeItem:
        return self.group

    def treeChildCount(self) -> int:
        return 3

    def treeChecked(self) -> bool:
        return self.enabled
