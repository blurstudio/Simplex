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


from typing import TYPE_CHECKING, Optional
from .treeItem import TreeItem

if TYPE_CHECKING:
    from .simplex import Simplex
    from .stack import Stack


class SimplexAccessor(object):
    """The base object for all Simplex System object types
    This class provides access to the simplex system
    name getters/setters/unifiers, proper deepcopying, and abstract tree lookup
    """

    def __init__(self, simplex: Simplex):
        self.simplex: Simplex = simplex
        self._name: str = ""
        self._splitApplied = set()

    @property
    def name(self) -> str:
        return self._name

    @property
    def DCC(self):
        return self.simplex.DCC

    @property
    def stack(self) -> Stack:
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


class SimplexTreeAccessor(SimplexAccessor, TreeItem):
    def __init__(self, simplex: Simplex):
        # Explicitly 
        SimplexAccessor.__init__(self, simplex)
        TreeItem.__init__(self, simplex)

