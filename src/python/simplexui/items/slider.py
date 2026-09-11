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

import itertools
from typing import TYPE_CHECKING, Any

from ..interface import undoContext
from ..utils import caseSplit, getNextName, makeUnique, singleShot
from .accessor import SimplexTreeAccessor
from .dragItem import Draggable
from .group import Group
from .progression import ProgPair, Progression
from .shape import Shape
from .stack import stackable
from .treeItem import TreeItem

if TYPE_CHECKING:
    from .simplex import DCCObject, Simplex


class Slider(SimplexTreeAccessor, Draggable):
    """A user-input to the simplex system that directly controls a Progression

    Parameters
    ----------
    name : str
        The name of this Slider
    simplex : Simplex
        The parent Simplex system
    prog : Progression
        The Progression that this Slider controls
    group : Group
        The Group to create this Slider in
    color : QColor
        The color of this item in the UI
    create : bool
        Whether to create a DCC Shape, or look for it already in-scene
    """

    classDepth: int = 7

    def __init__(
        self,
        name: str,
        simplex: Simplex,
        prog: Progression,
        group: Group,
        create: bool = True,
    ):
        if group.groupType is not type(self):
            raise ValueError("Cannot add this slider to a combo group")

        super().__init__(simplex)

        with self.stack.store(self):
            self._name: str = name
            self._thing: DCCObject | None = None
            self._thingRepr: str | None = None
            self.prog: Progression = prog
            self.prog.controller = self
            self.split: bool = False
            self._buildIdx: int | None = None
            self._value: float = 0.0
            self._enabled: bool = True

            mn, mx = self.prog.getRange()
            self.minValue: float = mn
            self.maxValue: float = mx
            self.simplex.sliders.append(self)

            with self.insertItemManager(group):
                self.group: Group = group
                self.group.items.append(self)

            newThing = self.DCC.getSliderThing(self._name)
            if newThing is None:
                if create:
                    self.thing = simplex.DCC.createSlider(self)
                else:
                    raise RuntimeError(f"Unable to find existing shape: {self.name}")
            else:
                self.thing = newThing

    @property
    def enabled(self) -> bool:
        """Get whether this Slider is evaluated in the solver"""
        return self._enabled

    @enabled.setter
    @stackable
    def enabled(self, value: bool):
        """Get whether this Slider is evaluated in the solver"""
        self._enabled = value

    @classmethod
    def createSlider(
        cls,
        name: str,
        simplex: Simplex,
        group: Group | None = None,
        shape: Shape | None = None,
        tVal: float = 1.0,
    ) -> Slider:
        """Create a new slider with a name in a group.
        Possibly create a single default shape for this slider

        Parameters
        ----------
        name : str
            The name of this Slider
        simplex : Simplex
            The parent Simplex system
        group : Group or None
            The group to add the Slider to.
            If None, create a default group. Defaults to None
        shape : Shape or None
            What shape to add to the new Slider's Progression at the given tVal
            if None, create a default shape. Defaults to None
        tVal : float
            The value for the new shape in the Slider's Progression. Defaults to 1.0

        Returns
        -------
        Slider
            The newly created Slider
        """
        if simplex.restShape is None:
            raise RuntimeError("Simplex system is missing rest shape")

        if group is None:
            if simplex.sliderGroups:
                group = simplex.sliderGroups[0]
            else:
                group = Group(f"{name}_GROUP", simplex, Slider)

        currentNames = [s.name for s in simplex.sliders]
        name = getNextName(name, currentNames)

        prog = Progression(name, simplex)
        if shape is None:
            prog.createShape(name, tVal)
        else:
            prog.pairs.append(ProgPair(simplex, shape, tVal))

        sli = cls(name, simplex, prog, group)
        return sli

    @classmethod
    def createMultiSlider(
        cls,
        name: str,
        simplex: Simplex,
        shapes: list[Shape],
        tVals: list[float],
        group: Group | None = None,
    ) -> Slider:
        """Create a new slider with a name (possibly in a custom group) with the
        provided shapes and t-values.

        Parameters
        ----------
        name : str
            The name of this Slider
        simplex : Simplex
            The parent Simplex system
        shape : list of Shape
            What shape s to add to the new Slider's Progression at the given tVals
        tVal : list of float
            The values for the new shapes in the Slider's Progression
        group : Group or None
            The group to add the Slider to.
            If None, create a default group. Defaults to None
        Returns
        -------
        Slider
            The newly created Slider
        """
        if simplex.restShape is None:
            raise RuntimeError("Simplex system is missing rest shape")

        if group is None:
            if simplex.sliderGroups:
                group = simplex.sliderGroups[0]
            else:
                group = Group(f"{name}_GROUP", simplex, Slider)

        currentNames = [s.name for s in simplex.sliders]
        name = getNextName(name, currentNames)

        prog = Progression(name, simplex)
        for shape, tVal in zip(shapes, tVals):
            prog.pairs.append(ProgPair(simplex, shape, tVal))

        sli = cls(name, simplex, prog, group)
        return sli

    @property
    def name(self) -> str:
        """Get the name of a Slider"""
        return self._name

    @name.setter
    @stackable
    def name(self, value: str):
        """Set the name of a Slider"""
        self._name = value
        self.prog.name = value
        self.DCC.renameSlider(self, value)
        # TODO Also rename the combos

    def nameLinks(self) -> list[bool]:
        sp = self._name.split("_")
        sliderPoss = []
        for orig in sp:
            s = caseSplit(orig)
            if len(s) > 1:
                s = [orig] + s
            sliderPoss.append(s)

        # remove numbered chunks from the end
        shapeNames = []
        shapes = [p.shape for p in self.prog.pairs]
        for s in shapes:
            x = s.name.rsplit("_", 1)
            if len(x) == 2:
                base, sfx = x
                if sfx[0].lower() == "n":
                    sfx = sfx[1:]
                x = base if sfx.isdigit() else s.name
            shapeNames.append(x)

        out = [False] * len(shapeNames)
        for poss in itertools.product(*sliderPoss):
            check = "".join(poss)
            for i, s in enumerate(shapeNames):
                if check == s:
                    out[i] = True
            if all(out):
                break
        return out

    @classmethod
    def buildSliderName(cls, pairs: list[tuple[str, float]]) -> str:
        """Figure out then name for a slider with given shapes

        This will mostly be used to figure out what the new name
        for a slider will be if its shapes are renamed

        Parameters
        ----------
        pairs : [(str, float)]
            A list of (name, value) pairs

        Returns
        -------
        : str
            A newly created name
        """
        # In this case, pairs is *not* a list of ProgPairs
        # but a list of (name, value) tuples

        # First, I'm just going to ignore anything with values that aren't 1.0
        # This simplifies the logic greatly
        extPairs = [p for p in pairs if abs(p[1]) == 1.0]
        if len(extPairs) == 1:
            return extPairs[0][0]
        if extPairs[0] == 1:
            extPairs = extPairs[::-1]

        names = []
        for ep in extPairs:
            sp = ep[0].split("_")
            if Shape.isNumberField(sp[-1]):
                sp = sp[:-1]
            names.append(sp)

        return "_".join(["".join(makeUnique(n)) for n in names])

    @property
    def thing(self) -> DCCObject:
        """Get the stored reference to the DCC attribute"""
        # if this is a deepcopied object, then self._thing will
        # be None. Rebuild the thing connection by its representation
        if self._thing is None and self._thingRepr:
            self._thing = self.DCC.loadPersistentSlider(self._thingRepr)
        return self._thing

    @thing.setter
    def thing(self, value: DCCObject):
        self._thing = value
        self._thingRepr = self.DCC.getPersistentSlider(value)

    @property
    def value(self) -> float:
        """Get the current value for this Slider"""
        return self._value

    @value.setter
    def value(self, val: float):
        """Set the current value for this Slider"""
        self._value = val
        # singleShot consolidates all
        self._setAllSliders(self)  # type: ignore

    @singleShot()
    def _setAllSliders(self, *sliders: Slider):
        with undoContext(self.DCC):
            for slider in sliders:
                self.DCC.setSliderWeight(slider, slider.value)

    def updateValue(self):
        pass

    @classmethod
    def loadV2(
        cls,
        simplex: Simplex,
        progs: list[Progression],
        data: dict[str, Any],
        create: bool,
    ) -> Slider:
        """Load the data from a version2 formatted json dictionary

        Parameters
        ----------
        simplex : Simplex
            The Simplex system that's being built
        progs : [Progression
            The progressions that have already been built
        data : dict
            The chunk of the json dict used to build this object
        create : bool
            Whether to create the DCC Shape, or look for it already in-scene

        Returns
        -------
        : Slider
            The specified Slider
        """
        name = data["name"]
        prog = progs[data["prog"]]
        group = simplex.groups[data.get("group", 0)]
        return cls(name, simplex, prog, group, create=create)

    def buildDefinition(self, simpDict: dict[str, Any], legacy: bool) -> int:
        """Output a dictionary definition of this object

        Parameters
        ----------
        simpDict : dict
            The dictionary that is being built
        legacy : bool
            Whether to write out the legacy definition, or the newer one

        Returns
        -------
        : int
            The build index
        """
        if self._buildIdx is None:
            self._buildIdx = len(simpDict["sliders"])
            if legacy:
                gIdx = self.group.buildDefinition(simpDict, legacy)
                pIdx = self.prog.buildDefinition(simpDict, legacy)
                simpDict.setdefault("sliders", []).append([self.name, pIdx, gIdx])
            else:
                x = {
                    "name": self.name,
                    "prog": self.prog.buildDefinition(simpDict, legacy),
                    "group": self.group.buildDefinition(simpDict, legacy),
                    "enabled": self._enabled,
                }
                simpDict.setdefault("sliders", []).append(x)
        return self._buildIdx

    def clearBuildIndex(self):
        """Clear the build index of this object

        The buildIndex is stored when building a definition dictionary
        that keeps track of its index for later referencing
        """
        self._buildIdx = None
        self.prog.clearBuildIndex()
        self.group.clearBuildIndex()

    def setRange(self):
        """Set the range of this Slider based on the progPair values"""
        values = [i.value for i in self.prog.pairs]
        self.minValue = min(values)
        self.maxValue = max(values)
        self.DCC.setSliderRange(self)

    @stackable
    def delete(self):
        """Delete a slider, any shapes it contains, and all downstream Combos and Traversals"""
        self.simplex.deleteDownstream(self)
        with self.removeItemManager(self):
            g = self.group
            g.items.remove(self)
            self.group = None  # type: ignore
            self.simplex.sliders.remove(self)

            pairs = self.prog.pairs[:]  # gotta make a copy
            for pp in pairs:
                if not pp.shape.isRest:
                    self.simplex.shapes.remove(pp.shape)
                    self.DCC.deleteShape(pp.shape)

            self.DCC.deleteSlider(self)

    @stackable
    def setInterpolation(self, interp: str):
        """Set the interpolation of a single Slider

        Parameters
        ----------
        interp : str
            The interpolation for this Slider's Progression
        """
        self.prog.interp = interp

    @stackable
    def setInterps(self, sliders: list[Slider], interp: str):
        """Set the interpolation of multiple Sliders

        Parameters
        ----------
        sliders : [Slider
            List of sliders to set interpolations on
        interp : str
            The interpolation to set on the list of Sliders
        """
        # This uses an instantiated slider to set the values
        # of multiple sliders. This is so we don't update the
        # DCC over and over again
        if not sliders:
            return
        with undoContext(self.DCC):
            for slider in sliders:
                slider.prog.interp = interp

    @stackable
    def createShape(
        self, shapeName: str | None = None, tVal: float | None = None
    ) -> ProgPair:
        """Create a shape and add it to a progression

        Parameters
        ----------
        shapeName : str or None
            The new Shape name in this Slider's Progression.
            If None, give it a default name. Defaults to None
        tVal : float or None
            The value to give the shape in this Slider's Progression.
            If None, give it a "smart" default. Defaults to None

        Returns
        -------
        : ProgPair
            The newly created Shape in a ProgPair already added to the Progression
        """
        pp, idx = self.prog.newProgPair(shapeName, tVal)
        with self.insertItemManager(self, row=idx):
            pp.prog = self.prog
            self.prog.pairs.insert(idx, pp)
        self.updateRange()
        return pp

    def extractProgressive(
        self, live: bool = True, offset: float = 10.0, separation: float = 5.0
    ):
        """Extract all of the Shapes in this Slider's Progression

        Parameters
        ----------
        live : bool
            Whether to maintain a live connection in the DCC for the extracted meshes
            Defaults to True
        offset : float
            The offset value for the first extracted mesh in the DCC (Default value = 10.0)
        separation : float
            The offset to add between any two extracted meshes (Default value = 5.0)
        """
        with undoContext(self.DCC):
            pos, neg = [], []
            for pp in sorted(self.prog.pairs):
                if pp.value < 0.0:
                    neg.append((pp.value, pp.shape, offset))
                    offset += separation
                elif pp.value > 0.0:
                    pos.append((pp.value, pp.shape, offset))
                    offset += separation
                # skip the rest value at == 0.0
            neg = list(reversed(neg))

            for prog in [pos, neg]:
                if not prog:
                    continue
                xtVal, shape, shift = prog[-1]
                ret = self.DCC.extractWithDeltaShape(shape, live, shift)
                if ret is not None:
                    ext, deltaShape = ret
                    for value, shape, shift in prog[:-1]:
                        self.DCC.extractWithDeltaConnection(
                            shape, deltaShape, value / xtVal, live, shift
                        )

    def extractShape(
        self, shape: Shape, live: bool = True, offset: float = 10.0
    ) -> DCCObject:
        """Extract a Shape that is controlled by a Slider to a DCC mesh

        This is on Slider (vs being on Shape) because live connections are handled
        differently based on the different Progression controllers

        Parameters
        ----------
        shape : Shape
            The shape to extract
        live :
             (Default value = True)
        offset : float
            The offset value for the first extracted mesh in the DCC (Default value = 10.0)
        """
        return self.DCC.extractShape(shape, live, offset)

    def connectShape(
        self,
        shape: Shape,
        mesh: DCCObject | None = None,
        live: bool = False,
        delete: bool = False,
    ):
        """Connect a Shape that is controlled by a Slider to a DCC mesh

        This is on Slider (vs being on Shape) because live connections are handled
        differently based on the different Progression controllers

        Parameters
        ----------
        shape : Shape
            The shape to connect
        mesh : object or None
            The DCC mesh to connect to the shape.
            If None, search the DCC by name. Defaults to None
        live : bool
            Whether to maintain a live connection in the DCC for the extracted meshes
            Defaults to True
        delete : bool
            Whether to delete the DCC mesh after it was connected (Default value = False)
        """
        self.DCC.connectShape(shape, mesh, live, delete)

    def updateRange(self):
        """Update the range in the DCC for this Slider"""
        self.DCC.updateSlidersRange([self])

    @stackable
    def setGroup(self, grp: Group):
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

        with self.moveItemManager(self, grp):
            if self.group:
                self.group.items.remove(self)
            grp.items.append(self)
            self.group = grp

    def getInputVectors(self) -> list[list[float]]:
        """Get the ordered values for input to the solver that activate this Slider
        Multiple outputs are possible if the slider has -1 to 1 range

        Returns
        -------
        : [[float, ....], ....]
            The ordered slider values
        """
        inVecs = []
        for pp in self.prog.getExtremePairs():
            inVec = [0.0] * len(self.simplex.sliders)
            inVec[self.simplex.sliders.index(self)] = pp.value
            inVecs.append(inVec)
        return inVecs

    def treeChild(self, row: int) -> TreeItem:
        return self.prog.pairs[row]

    def treeRow(self) -> int:
        return self.group.items.index(self)

    def treeParent(self) -> TreeItem:
        return self.group

    def treeChildCount(self) -> int:
        return len(self.prog.pairs)

    def treeData(self, column: int) -> Any | None:
        if column == 0:
            return self.name
        if column == 1:
            return self.value
        return None

    def treeChecked(self) -> bool:
        return self.enabled
