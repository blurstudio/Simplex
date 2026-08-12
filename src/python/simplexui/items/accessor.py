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
import copy


from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from .simplex import Simplex
    from .stack import Stack


class SimplexAccessor(object):
    """The base object for all Simplex System object types
        This class provides access to the simplex system, draggability,
        name getters/setters/unifiers, proper deepcopying, and abstract tree lookup

    Parameters
    ----------

    Returns
    -------

    """

    def __init__(self, simplex: Simplex):
        self.simplex: Simplex = simplex
        self._name: str = ""
        self._splitApplied = set()

    @property
    def name(self) -> str:
        """ """
        return self._name

    @name.setter
    def name(self, val: str):
        """The name of the current object"""
        self._name = val

    @property
    def models(self) -> list:
        """ """
        return self.simplex.models

    @property
    def falloffModels(self) -> list:
        """ """
        return self.simplex.falloffModels

    @property
    def DCC(self):
        """ """
        return self.simplex.DCC

    @property
    def stack(self) -> Stack:
        """ """
        return self.simplex.stack

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "_thing" and self.DCC.program != "dummy":
                # DO NOT make a copy of the DCC thing (unless its a dummy dcc)
                # as it may or may not be a persistent object
                # setattr(result, k, self._thing)
                setattr(result, k, None)
            elif k == "expanded":
                # Skip the expanded dict because it deals with the Qt models
                setattr(result, k, {})
            else:
                setattr(result, k, copy.deepcopy(v, memo))
        return result

    def _buildLinkedRename(
        self,
        newName: str,
        maxDepth: int,
        currentLinks: dict[type, dict[str, tuple[SimplexAccessor, int]]],
    ):
        """Build the proposed set of renames specifically for this object
        This allows sub-classes to override the linked name behavior

        Parameters
        ----------
        newName :

        maxDepth :

        currentLinks :


        Returns
        -------

        """
        return currentLinks

    def buildLinkedRename(
        self,
        newName: str,
        maxDepth: int = 5,
        currentLinks: Optional[
            dict[type, dict[str, tuple[SimplexAccessor, int]]]
        ] = None,
    ) -> dict[type, dict[str, tuple[SimplexAccessor, int]]]:
        """For the Shape, Slider, Combo, and Traversal items, build a linked rename
        dictionary like {itemType: {newName: (item, maxDepth)}} recursively up to a
        maximum given depth

        The dictionary is structured like that to easily check for name clashes

        Parameters
        ----------
        newName : str
            The new suggested name for this object
        maxDepth : int
            The maximum depth of recursion when resolving names (Default value = 5)
        currentLinks : dict
            The current set of proposed renames. (Default value = None)

        Returns
        -------
        dict :
            A new set of propsed renames

        """
        # Build the output dict if not done already
        if currentLinks is None:
            currentLinks = {}

        # return at depth
        if maxDepth <= 0:
            return currentLinks

        # If this doesn't need renamed, then we can prune this branch
        if self.name == newName:
            return currentLinks

        # Check for conflicts, or other short circuits
        typeLinks = currentLinks.setdefault(type(self), {})
        if newName in typeLinks:
            tlPair = typeLinks[newName]
            if tlPair[0] is not self:
                # Error out if a name conflict is found.
                msg = "Linked rename produced a conflict: Trying to rename {0} {1} and {2} to {3}"
                msg = msg.format(
                    type(self), typeLinks[newName][0].name, self.name, newName
                )
                raise ValueError(msg)
            elif tlPair[1] >= maxDepth:
                # If we've been here before with more available depth
                # then we can just return because we've done this before
                return currentLinks

        # Finally add myself to the rename
        typeLinks[newName] = (self, maxDepth)

        # And now handle the type-specific stuff
        return self._buildLinkedRename(newName, maxDepth, currentLinks)

    def treeChild(self, row):
        """ """
        return None

    def treeRow(self):
        """ """
        return None

    def treeParent(self):
        """ """
        return None

    def treeChildCount(self) -> int:
        """ """
        return 0

    def treeData(self, column) -> Any:
        """ """
        if column == 0:
            return self.name
        return None

    def treeChecked(self):
        """ """
        return None

    def icon(self):
        return None


class SimplexTickAccessor(SimplexAccessor):
    value: float

    def __init__(self, simplex):
        super().__init__(simplex)
        self.dragStep: float = 0.05
        self.maxValue: float = 1.0
        self.minValue: float = 0.0

    def valueTick(self, ticks: int, mul: float):
        """Change the value of the current object by some number of ticks
        with some given multiplier. This is the interface for the MMB drag

        Parameters
        ----------
        ticks : int
            The number of dragStep ticks to apply
        mul : float
            An overall multiplier
        """
        val = self.value + (self.dragStep * ticks * mul)
        val = 0.0 if abs(val) < 1e-5 else val
        val = max(min(val, self.maxValue), self.minValue)
        self.value = val
