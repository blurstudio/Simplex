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


from six.moves import zip

from ..interface import DCC, undoContext

# pylint:disable=missing-docstring,unused-argument,no-self-use
from ..Qt.QtGui import QColor
from .accessor import SimplexAccessor
from .stack import stackable


class Shape(SimplexAccessor):
    """A representation of a single blendshape

    For every Shape object in a system, there will be one blendshape.
    The Simplex solver takes an ordered list of Slider values, and outputs
    an ordered list of shape values.

    Shapes hold references to their DCC objects, and can also hold
    the vertex positions in certain cases

    Parameters
    ----------
    name : str
        The name for the new Shape
    simplex : Simplex
        The Simplex system
    create : bool
        Whether to create the DCC Shape, or look for it already in-scene
    color : QColor
        The color of this item in the Ui

    Returns
    -------

    """

    classDepth = 10

    def __init__(self, name, simplex, create=True, color=QColor(128, 128, 128)):
        super(Shape, self).__init__(simplex)
        with self.stack.store(self):
            self._thing = None
            self._verts = None
            self._thingRepr = None
            self._name = name
            self._buildIdx = None
            simplex.shapes.append(self)
            self.isRest = False
            self.expanded = {}
            self.color = color
            self.progPairs = []

            newThing = self.DCC.getShapeThing(self._name)
            if newThing is None:
                if create:
                    self.thing = self.DCC.createShape(self)
                else:
                    raise RuntimeError(
                        "Unable to find existing shape: {0}".format(self.name)
                    )
            else:
                self.thing = newThing

    @classmethod
    def createShape(cls, name, simplex, slider=None):
        """Convenience method for creating a new shape
        This will create all required parent objects to have a new shape

        Parameters
        ----------
        name : str
            The name for the new Shape
        simplex : Simplex
            The Simplex system
        slider : Slider or None
            The slider to add this shape to.
            If None, A new Slider will be created (Default value = None)

        Returns
        -------
        : Shape
            The new Shape

        """
        if simplex.restShape is None:
            raise RuntimeError("Simplex system is missing rest shape")

        if slider is None:
            # Implicitly creates a shape
            from .slider import Slider

            slider = Slider.createSlider(name, simplex)
            for p in slider.prog.pairs:
                if p.shape.name == name:
                    return p.shape
            raise RuntimeError("Problem creating shape with proper name")
        else:
            if slider.simplex != simplex:
                raise RuntimeError("Slider does not belong to the provided Simplex")
            tVal = slider.prog.guessNextTVal()
            pp = slider.prog.createShape(name, tVal)
            return pp.shape

    @classmethod
    def buildRest(cls, simplex):
        """Create/find the system's rest shape

        Parameters
        ----------
        simplex : Simplex
            The Simplex system

        Returns
        -------
        : Shape
            The system's rest Shape

        """
        rest = cls(simplex.getRestName(), simplex, create=True)
        rest.isRest = True
        return rest

    @property
    def name(self):
        """Get the Shape's name"""
        return self._name

    @name.setter
    @stackable
    def name(self, value):
        """Set the Shape's name

        Parameters
        ----------
        value :


        Returns
        -------

        """
        if value == self._name:
            return
        self.DCC.renameShape(self, value)
        self._name = value
        for model in self.models:
            model.itemDataChanged(self)

    def strippedName(self):
        """Get the name of this shape with any progressive numbers stripped from the end"""
        sp = self.name.split("_")
        if self.isNumberField(sp[-1]):
            sp = sp[:-1]
        return "_".join(sp)

    def _buildLinkedRename(self, newName, maxDepth, currentLinks):
        """

        Parameters
        ----------
        newName :

        maxDepth :

        currentLinks :


        Returns
        -------

        """
        # Now that all the bookkeeping has been handled by the main method
        # I can handle recursing for the object specific stuff here
        shape = None  # TEMP

        from .combo import Combo
        from .slider import Slider
        from .traversal import Traversal

        for pp in self.progPairs:
            currentLinks = pp.prog.siblingRename(shape, newName, currentLinks)

            ctrl = pp.prog.controller
            if isinstance(ctrl, Slider):
                nn = None
                currentLinks = ctrl.buildLinkedRename(
                    nn, maxDepth=maxDepth - 1, currentLinks=currentLinks
                )
            elif isinstance(ctrl, Combo):
                nn = None
                currentLinks = ctrl.buildLinkedRename(
                    nn, maxDepth=maxDepth - 1, currentLinks=currentLinks
                )
            elif isinstance(ctrl, Traversal):
                nn = None
                currentLinks = ctrl.buildLinkedRename(
                    nn, maxDepth=maxDepth - 1, currentLinks=currentLinks
                )

        return currentLinks

        # First, check for a slider rename,
        # if so, recurse into that slider
        # Check for combo renames (because combos use the shape names)

        # if isinstance(item, Shape):
        # Check if the parent is a slider
        # Check if the slider needs renamed
        # Check if the item's siblings need renamed
        # Check if there are any combos that depend on this shape name
        # If so, rename *both* the combo and its linked children
        # Check if the parent is a combo
        # Check if the combo needs renamed
        # If so, check if the item's siblings need renamed too
        # Check if the parent is a traversal
        # Check if the traversal needs renamed
        # If so, check if the item's siblings need renamed too
        # elif isinstance(item, Slider):
        # Check if the name change is linked to any of my shapes
        # Go through the shape linked rename for one of those instead, maybe?
        # There are possible ambiguities if you do a *full* slider rename
        # with both positive and negatively named shapes.
        # Otherwise
        # Check for linked combos, and rename down that branch
        # Check for linked traversals, and rename down that branch
        # elif isinstance(item, Combo):
        # pass
        # elif isinstance(item, Traversal):
        # pass

    @property
    def thing(self):
        """Get the stored reference to the DCC object"""
        # if this is a deepcopied object, then self._thing will
        # be None. Rebuild the thing connection by its representation
        if self._thing is None and self._thingRepr:
            self._thing = DCC.loadPersistentShape(self._thingRepr)
        return self._thing

    @thing.setter
    def thing(self, value):
        """Set the stored reference to the DCC object

        Parameters
        ----------
        value :


        Returns
        -------

        """
        self._thing = value
        self._thingRepr = self.DCC.getPersistentShape(value)

    @classmethod
    def loadV2(cls, simplex, data, create):
        """Load the data from a version2 formatted json dictionary

        Parameters
        ----------
        simplex : Simplex
            The Simplex system that's being built
        data : dict
            The chunk of the json dict used to build this object
        create : bool
            Whether to create the DCC Shape, or look for it already in-scene

        Returns
        -------
        : Shape
            The specified Shape

        """
        return cls(data["name"], simplex, create, QColor(*data.get("color", (0, 0, 0))))

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
            self._buildIdx = len(simpDict["shapes"])
            if legacy:
                simpDict.setdefault("shapes", []).append(self.name)
            else:
                x = {
                    "name": self.name,
                    "color": self.color.getRgb()[:3],
                }
                simpDict.setdefault("shapes", []).append(x)
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

    def zeroShape(self):
        """Set the shape to be equal to the rest shape"""
        self.DCC.zeroShape(self)

    @staticmethod
    def zeroShapes(shapes):
        """Set the shapes to be equal to the rest shape

        Parameters
        ----------
        shapes : [Shape
            Shapes to be zeroed

        Returns
        -------

        """
        for shape in shapes:
            if not shape.isRest:
                shape.zeroShape()

    def connectShape(self, mesh=None, live=False, delete=False):
        """Force a shape to match a mesh
            The "connect shape" button is: mesh=None, delete=True
            The "match shape" button is: mesh=someMesh, delete=False
            There is a possibility of a "make live" button: live=True, delete=False

        Parameters
        ----------
        mesh : object or None
            The DCC Mesh object. If None, it's searched for by name in scene (Default value = None)
        live : bool
            Whether or not to create a live connection in the DCC. Defaults False
        delete : bool
            Whether to delete the DCC Mesh after its connection. Defaults False

        Returns
        -------

        """
        self.DCC.connectShape(self, mesh, live, delete)

    @staticmethod
    def connectShapes(shapes, meshes, live=False, delete=False):
        """Connect multiple meshes to multiple Shapes

        Parameters
        ----------
        shapes : [Shape
            The shapes to connect to
        meshes : [object
            The DCC Meshes
        live : bool
            Whether or not to create a live connection in the DCC. Defaults False
        delete : bool
            Whether to delete the DCC Mesh after its connection. Defaults False

        Returns
        -------

        """
        with undoContext():
            for shape, mesh in zip(shapes, meshes):
                shape.connectShape(mesh, live, delete)

    @staticmethod
    def isNumberField(val):
        """A utility function to check if a field is numeric
        Also, this allows for the "n" prefix for negative numbers because
        many DCC's don't allow "-" in an object name

        Parameters
        ----------
        val : str
            The string to check

        Returns
        -------
        : bool
            Whether the field is numeric

        """
        if not val:
            return False
        if val[0].lower() == "n":
            val = val[1:]
        return val.isdigit()

    @property
    def verts(self):
        """Get the stored vertices"""
        if self._verts is None:
            self._verts = self.DCC.getShapeVertices(self)
        return self._verts

    @verts.setter
    def verts(self, value):
        """Set the stored vertices

        Parameters
        ----------
        value :


        Returns
        -------

        """
        self._verts = value
