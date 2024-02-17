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
from ..Qt.QtGui import QColor
from ..utils import nested
from .accessor import SimplexAccessor
from .stack import stackable


class Group(SimplexAccessor):
    """Groups organize Simplex items

        Groups have no purpose in the solver. They don't do anything other than organize
        the items in a system.

        Each group can hold only one type of item (Slider, Combo, or Traversal)

    Parameters
    ----------
    name : str
        The name of the group
    simplex : Simplex
        The Simplex system
    groupType : type
        The type that this group can hold
    color : QColor
        The color of this item in the Ui

    Returns
    -------

    """

    classDepth = 1

    def __init__(self, name, simplex, groupType, color=QColor(128, 128, 128)):
        super(Group, self).__init__(simplex)
        from .combo import Combo
        from .slider import Slider
        from .traversal import Traversal

        with self.stack.store(self):
            self._name = name
            self.items = []
            self._buildIdx = None
            self.expanded = {}
            self.color = color
            self.groupType = groupType

            mgrs = [
                model.insertItemManager(simplex, row=self._getInsertionRow())
                for model in self.models
            ]
            with nested(*mgrs):
                if self.groupType is Slider:
                    self.simplex.sliderGroups.append(self)
                elif self.groupType is Combo:
                    self.simplex.comboGroups.append(self)
                elif self.groupType is Traversal:
                    self.simplex.traversalGroups.append(self)

    def _getInsertionRow(self):
        """ """
        from .combo import Combo
        from .slider import Slider
        from .traversal import Traversal

        c = len(self.simplex.sliderGroups)
        if self.groupType is Slider:
            return c
        c += len(self.simplex.comboGroups)
        if self.groupType is Combo:
            return c
        c += len(self.simplex.traversalGroups)
        if self.groupType is Traversal:
            return c

    @property
    def name(self):
        """Get the name of the Group"""
        return self._name

    @name.setter
    @stackable
    def name(self, value):
        """Set the name of the Group

        Parameters
        ----------
        value :


        Returns
        -------

        """
        self._name = value
        for model in self.models:
            model.itemDataChanged(self)

    def treeChild(self, row):
        """

        Parameters
        ----------
        row :


        Returns
        -------

        """
        return self.items[row]

    def treeRow(self):
        """ """
        return self.simplex.groups.index(self)

    def treeParent(self):
        """ """
        return self.simplex

    def treeChildCount(self):
        """ """
        return len(self.items)

    @classmethod
    def createGroup(cls, name, simplex, things=None, groupType=None):
        """Convenience method for creating a group

        Parameters
        ----------
        name : str
            The name to give the new Group
        simpelx : Simplex
            The Simplex system
        things : [object
            The things to add to this Group (Default value = None)
        groupType : type
            The type that the new Group can hold (Default value = None)
        simplex :


        Returns
        -------

        """
        g = cls(name, simplex, groupType)
        if things is not None:
            g.take(things)
        return g

    @classmethod
    def loadV2(cls, simplex, data):
        """Load the data from a version2 formatted json dictionary

        Parameters
        ----------
        simplex : Simplex
            The Simplex system that's being built
        data : dict
            The chunk of the json dict used to build this object

        Returns
        -------
        : Group
            The specified Group

        """
        from .combo import Combo
        from .slider import Slider
        from .traversal import Traversal

        name = data["name"]
        color = data.get("color", (0, 0, 0))
        typeName = data["type"]
        if typeName == "Slider":
            groupType = Slider
        elif typeName == "Combo":
            groupType = Combo
        elif typeName == "Traversal":
            groupType = Traversal
        else:
            raise RuntimeError("Malformed simplex json string: Improper group type")
        return cls(name, simplex, groupType, QColor(*color))

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
            self._buildIdx = len(simpDict["groups"])
            if legacy:
                simpDict.setdefault("groups", []).append(self.name)
            else:
                x = {
                    "name": self.name,
                    "color": self.color.getRgb()[:3],
                    "type": self.groupType.__name__,
                }
                simpDict.setdefault("groups", []).append(x)
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
    def delete(self):
        """Delete a group. Any objects in this group will be deleted"""
        from .combo import Combo
        from .slider import Slider

        if self.groupType is Slider:
            if len(self.simplex.sliderGroups) == 1:
                return
            gList = self.simplex.sliderGroups
        elif self.groupType is Combo:
            if len(self.simplex.comboGroups) == 1:
                return
            gList = self.simplex.comboGroups
        else:
            raise RuntimeError("Somehow this group has no type")

        mgrs = [model.removeItemManager(self) for model in self.models]
        with nested(*mgrs):
            gList.remove(self)
            # Gotta iterate over copies of the lists
            # as .delete removes the items from the list
            for item in self.items[:]:
                item.delete()

    @stackable
    def take(self, things):
        """Remove some items from their current groups and put them in this one

        Parameters
        ----------
        things : [object
            A list of things to put in this group

        Returns
        -------

        """
        if self.groupType is None:
            self.groupType = type(things[0])

        if not all([isinstance(i, self.groupType) for i in things]):
            raise ValueError(
                "All items in this group must be of type: {}".format(self.groupType)
            )

        # do it this way instead of using set() to keep order
        for thing in things:
            if thing not in self.items:
                thing.setGroup(self)
