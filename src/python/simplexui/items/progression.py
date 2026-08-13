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
from __future__ import annotations
from ..utils import getNextName
from .accessor import SimplexAccessor
from .stack import stackable


from typing import Optional, Union, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .simplex import Simplex
    from .shape import Shape
    from .falloff import Falloff
    from .slider import Slider
    from .combo import Combo
    from .traversal import Traversal


class ProgPair(SimplexAccessor):
    classDepth: int = 9

    def __init__(self, simplex: Simplex, shape: Shape, value: float):
        super(ProgPair, self).__init__(simplex)
        self.shape: Shape = shape
        self._value: float = value
        self.prog: Optional[Progression] = None
        self.minValue: float = -1.0
        self.maxValue: float = 1.0
        if not shape.isRest and self not in self.shape.progPairs:
            self.shape.progPairs.append(self)

    @property
    def name(self) -> str:
        return self.shape.name

    @name.setter
    def name(self, value: str):
        self.shape.name = value

    def buildDefinition(
        self, simpDict: dict[str, Any], legacy: bool
    ) -> tuple[int, float]:
        idx = self.shape.buildDefinition(simpDict, legacy)
        return idx, self.value

    def __lt__(self, other: Any) -> bool:
        return self.value < other.value

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    @stackable
    def value(self, val: float):
        from .slider import Slider

        self._value = val
        if self.prog is None:
            raise ValueError(
                "Can't set the value of a progPair that doesn't have a controller"
            )

        if isinstance(self.prog.controller, Slider):
            self.prog.controller.setRange()

    @stackable
    def delete(self):
        if self.prog is None:
            return

        ppairs = self.prog.pairs
        ridx = ppairs.index(self)
        pp = ppairs.pop(ridx)
        if not pp.shape.isRest:
            pp.shape.progPairs.remove(pp)
            if not pp.shape.progPairs:
                self.simplex.shapes.remove(pp.shape)
                self.DCC.deleteShape(pp.shape)


class Progression(SimplexAccessor):
    """A set of shapes to interpolate between

    A Progression is a collection of shape/value pairs, and an interpolation type.
    Progressions don't exist on their own, they are always part of a higher-level object
    like a Combo, Slider, or Traversal. The ProgPairs are always sorted by value

    Progressions should always have a shape at 0 (which is almost always the rest shape)
    and a shape at either -1 or 1.
    They can also have other shapes at any value between 0 and the extremes.

    Sliders give users direct control over the value that is passed to the progression.
    Combos and Traversals use input values to control their progressions.

    Progressions can use different interpolations.
    The simplest is 'linear', which blends in a straight line between shapes.
    The 'spline' interp uses Catmull-Rom spline values.
    The 'splitspline' builds separate Catmull-Rom splines for positive and negative values

    Parameters
    ----------
    name : str
        The name for the Progression. Usually just copies the name of its controller
    simplex : Simplex
        The Simplex system
    pairs : [ProgPair
        The ProgPairs that will make up this Progression.
        If None, the a default Rest at 0.0 pair will be created.
    interp : str
        The interpolation for this Progression. Defaults to 'spline'
    falloffs : [Falloff
        A list of Fallofs to apply to the progression
        Defaults to None

    Returns
    -------

    """

    classDepth: int = 8
    interpTypes: tuple[tuple[str, str], ...] = (
        ("Linear", "linear"),
        ("Spline", "spline"),
        ("Split Spline", "splitspline"),
    )

    def __init__(
        self,
        name: str,
        simplex: Simplex,
        pairs: Optional[list[ProgPair]] = None,
        interp: str = "spline",
        falloffs: Optional[list[Falloff]] = None,
    ):
        super(Progression, self).__init__(simplex)

        if self.simplex.restShape is None:
            raise RuntimeError("Simplex is not initialized with a rest shape")

        with self.stack.store(self):
            self._name: str = name
            self._interp: str = interp
            self.falloffs: list[Falloff] = falloffs or []
            self.controller: Optional[Union[Slider, Combo, Traversal]] = None

            self.pairs: list[ProgPair]
            if pairs is None:
                self.pairs = [ProgPair(self.simplex, self.simplex.restShape, 0.0)]
            else:
                self.pairs = pairs

            for pair in self.pairs:
                pair.prog = self

            for falloff in self.falloffs:
                falloff.children.append(self)
            self._buildIdx: Optional[int] = None

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def interp(self) -> str:
        """Get the interp for this Progression"""
        return self._interp

    @interp.setter
    @stackable
    def interp(self, value: str):
        """Set the interp for this Progression"""
        self._interp = value

    def getShapeIndex(self, shape: Shape) -> int:
        """Get the index of the given shape in this progression

        Parameters
        ----------
        shape : Shape
            The shape to get the index of

        Returns
        -------
        : int
            The index of the ProgPair that contains the given shape

        """
        for i, p in enumerate(self.pairs):
            if p.shape == shape:
                return i
        raise ValueError("Provided shape:{0} is not in the list".format(shape.name))

    def getShapes(self) -> list[Shape]:
        """Return the Shapes in this Progression

        Returns
        -------
        : type
            ([Shape, ....]): The shapes in the Progression

        """
        return [i.shape for i in self.pairs]

    def getValues(self) -> list[float]:
        """Return the values in this Progression

        Returns
        -------
        : type
            ([float, ....]): The values in the Progression

        """
        return [i.value for i in self.pairs]

    def getInsertIndex(self, tVal: float) -> int:
        """Get the index to insert a pair with value tVal

        Parameters
        ----------
        tVal : float
            The value to get the insertion index for

        Returns
        -------
        : int
            The insertion index

        """
        values = self.getValues()
        if not values:
            return 0
        elif tVal <= values[0]:
            return 0
        elif tVal >= values[-1]:
            return len(self.pairs)
        else:
            for i in range(1, len(values)):
                if values[i - 1] <= tVal < values[i]:
                    return i
        return 0

    def getShapeAtValue(self, val: float, tol=0.0001) -> Optional[Shape]:
        """Return the shape at the given value

        Parameters
        ----------
        val :
            float
        tol :
            float (Default value = 0.0001)

        Returns
        -------
        : type
            (Shape or None): The shape found with the given value, or None if nothing was found

        """
        for pp in self.pairs:
            if abs(pp.value - val) < tol:
                return pp.shape
        return None

    @classmethod
    def loadV2(cls, simplex: Simplex, data: dict[str, Any]) -> Progression:
        """Load the data from a version2 formatted json dictionary

        Parameters
        ----------
        simplex : Simplex
            The Simplex system that's being built
        data : dict
            The chunk of the json dict used to build this object

        Returns
        -------
        : Progression
            The specified Progression

        """
        name = data["name"]
        pairs = data["pairs"]
        interp = data.get("interp", "spline")
        foIdxs = data.get("falloffs", [])
        pairs = [ProgPair(simplex, simplex.shapes[s], v) for s, v in pairs]
        fos = [simplex.falloffs[i] for i in foIdxs]
        return cls(name, simplex, pairs=pairs, interp=interp, falloffs=fos)

    def buildDefinition(self, simpDict: dict[str, Any], legacy: bool) -> int:
        """Output a dictionary definition of this object

        Parameters
        ----------
        simpDict : dict
            The dictionary that is being built
        legacy : bool
            Whether to write out the legacy definition, or the newer one
        """
        if self._buildIdx is None:
            idxPairs = [pair.buildDefinition(simpDict, legacy) for pair in self.pairs]
            idxPairs.sort(key=lambda x: x[1])
            idxs, values = list(zip(*idxPairs))
            foIdxs = [f.buildDefinition(simpDict, legacy) for f in self.falloffs]
            self._buildIdx = len(simpDict["progressions"])
            if legacy:
                x = [self.name, idxs, values, self.interp, foIdxs]
                simpDict.setdefault("progressions", []).append(x)
            else:
                x = {
                    "name": self.name,
                    "pairs": idxPairs,
                    "interp": self.interp,
                    "falloffs": foIdxs,
                }
                simpDict.setdefault("progressions", []).append(x)
        return self._buildIdx

    def clearBuildIndex(self):
        """Clear the build index of this object

        The buildIndex is stored when building a definition dictionary
        that keeps track of its index for later referencin
        """
        self._buildIdx = None
        for pair in self.pairs:
            pair.shape.clearBuildIndex()
        for fo in self.falloffs:
            fo.clearBuildIndex()

    @stackable
    def moveShapeToProgression(self, shapePair: ProgPair):
        """Remove the shapePair from its current progression and set it in a new progression

        Parameters
        ----------
        shapePair : progPair
            The ProgPair to take
        """
        oldProg = shapePair.prog
        if oldProg is not None:
            oldProg.pairs.remove(shapePair)
        self.pairs.append(shapePair)
        shapePair.prog = self

    @stackable
    def setShapesValues(self, values: list[float]):
        """Set all the Shape's values

        Parameters
        ----------
        values : [float
            The values to set
        """
        from .slider import Slider

        for pp, val in zip(self.pairs, values):
            pp.value = val

        if isinstance(self.controller, Slider):
            self.controller.updateRange()

    def siblingRename(
        self, shape: Shape, newName: str, currentLinks: dict
    ) -> dict[type, dict[str, tuple[SimplexAccessor, int]]]:
        # This is part of the in-progress linked naming system
        # get name change
        return {}

    @stackable
    def addFalloff(self, falloff: Falloff):
        """Add a falloff to a slider's falloff list

        Parameters
        ----------
        falloff : Falloff
            The falloff to add

        Returns
        -------

        """
        if falloff not in self.falloffs:
            self.falloffs.append(falloff)
            falloff.children.append(self)
            self.DCC.addProgFalloff(self, falloff)

    @stackable
    def removeFalloff(self, falloff: Falloff):
        """Remove a falloff from a slider's falloff list

        Parameters
        ----------
        falloff : Falloff
            The falloff to remove

        Returns
        -------

        """
        if falloff in self.falloffs:
            self.falloffs.remove(falloff)
            falloff.children.remove(self)
            self.DCC.removeProgFalloff(self, falloff)

    @stackable
    def createShape(
        self, shapeName: Optional[str] = None, tVal: Optional[float] = None
    ) -> ProgPair:
        """Create a shape and add it to a progression

        Parameters
        ----------
        shapeName : str or None
            The name to give the shape
            If None, give it a default value
        tVal : float or None
            The value to give the new ProgPair
            if None, give it a "smart" default

        Returns
        -------
        : ProgPair
            The newly created ProgPair

        """
        from .slider import Slider

        pp, idx = self.newProgPair(shapeName, tVal)
        pp.prog = self
        self.pairs.insert(idx, pp)

        if isinstance(self.controller, Slider):
            self.controller.updateRange()

        return pp

    def newProgPair(
        self, shapeName: Optional[str] = None, tVal: Optional[float] = None
    ) -> tuple[ProgPair, int]:
        """Create a shape and DO NOT add it to a progression

        Parameters
        ----------
        shapeName : str or None
            The name to give the shape
            If None, give it a default value
        tVal : float or None
            The value to give the new ProgPair
            if None, give it a "smart" default

        Returns
        -------
        : ProgPair
            The newly created ProgPair
        : int
            The insertion index for this ProgPair into this Progression

        """
        from .shape import Shape

        if tVal is None:
            tVal = self.guessNextTVal()

        if shapeName is None:
            if self.controller is not None:
                if abs(tVal) == 1.0:
                    shapeName = self.controller.name
                else:
                    neg = "n" if tVal < 0.0 else ""
                    shapeName = "{0}_{1}{2}".format(
                        self.controller.name, neg, int(abs(tVal) * 100)
                    )

            currentNames = [i.name for i in self.simplex.shapes]
            shapeName = getNextName(shapeName, currentNames)

        idx = self.getInsertIndex(tVal)
        shape = Shape(shapeName, self.simplex)
        pp = ProgPair(self.simplex, shape, tVal)
        return pp, idx

    def guessNextTVal(self) -> float:
        """Given the current progression values, make an educated guess what's next.

        Returns
        -------
        : float
            The "smart" guess for the next tVal

        """
        # The question remains if negative or
        # intermediate values are more important
        # I think intermediate
        vals = [i.value for i in self.pairs]
        mnv = min(vals)
        mxv = max(vals)
        if mnv == 0.0 and mxv == 1.0:
            for c in [0.5, 0.25, 0.75, -1.0]:
                if c not in vals:
                    return c
        if mnv == -1.0 and mxv == 1.0:
            for c in [0.5, -0.5, 0.25, -0.25, 0.75, -0.75]:
                if c not in vals:
                    return c
        return 1.0

    @stackable
    def deleteShape(self, shape: Shape):
        """Delete a shape from the system and the DCC

        Parameters
        ----------
        shape : Shape
            The shape to delete
        """
        ridx = None
        for i, pp in enumerate(self.pairs):
            if pp.shape == shape:
                ridx = i
        if ridx is None:
            raise RuntimeError("Shape does not exist to remove")

        pp = self.pairs[ridx]
        self.pairs.pop(ridx)
        if not shape.isRest:
            self.simplex.shapes.remove(shape)
            self.DCC.deleteShape(shape)

    @stackable
    def delete(self):
        """Delete the Progression and all its Shapes"""
        for pp in self.pairs[:]:
            if pp.shape.isRest:
                continue
            self.simplex.shapes.remove(pp.shape)
            self.DCC.deleteShape(pp.shape)

    def getRange(self) -> tuple[float, float]:
        """Get the range for this Progression
        Returns
        -------
        : float
            The minimum value
        : float
            The maximum value

        """
        vals = [i.value for i in self.pairs]
        return min(vals), max(vals)

    def getExtremePairs(self) -> list[ProgPair]:
        """Get the ProgPairs where the value is -1 or 1

        Returns
        -------
        : [ProgPair, ...]
            ProgPairs whose values are -1 or 1
        """
        ret = []
        for pp in self.pairs:
            if abs(pp.value) != 1.0:
                continue
            ret.append(pp)
        return ret
