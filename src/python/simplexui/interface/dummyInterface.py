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
"""A placeholder interface that takes arguments and does nothing with them"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from functools import wraps

import numpy as np
from alembic.AbcGeom import OPolyMeshSchemaSample
from Qt import QtCore
from Qt.QtCore import Signal
from Qt.QtWidgets import QApplication

from ..commands.alembicCommon import (
    getSampleArray,
    getSampleArrayIndex,
    getStaticMeshData,
    getUvSample,
    mkSampleIntArray,
    mkSampleVertexPoints,
    mkUvSample,
)


# UNDO STACK INTEGRATION
@contextmanager
def undoContext(inst=None):
    """A context that wraps undo chunks

    Parameters
    ----------
    inst : DCC
         An instantiated DCC if available. (Default value = None)
    """
    if inst is None:
        DCC.staticUndoOpen()
    else:
        inst.undoOpen()
    try:
        yield
    finally:
        if inst is None:
            DCC.staticUndoClose()
        else:
            inst.undoClose()


def undoable(f):
    """A decorator that wraps a function in an undoContext"""

    @wraps(f)
    def stacker(self, *args, **kwargs):
        """The wrapper closure"""
        with undoContext():
            return f(self, *args, **kwargs)

    return stacker


class DummyScene:
    """A dcc scene containing existing dummy objects"""

    def __init__(self) -> None:
        self.items = {}

    def get(
        self,
        tpe: type[DummyBlendshape]
        | type[DummyFalloff]
        | type[DummyMesh]
        | type[DummyNode]
        | type[DummySimplex],
        name,
    ):
        return self.items.get(tpe, {}).get(name)

    def add(self, item) -> None:
        typeDict = self.items.setdefault(type(item), {})
        typeDict[item.name] = item

    def remove(self, item) -> None:
        typeDict = self.items.setdefault(type(item), {})
        typeDict.pop(item.name, None)


DB = DummyScene()  # Default module level dummy scene


class DummyAttr:
    """A generic named object attribute"""

    def __init__(self, name, value: float, parent) -> None:
        self.name = name
        self.value = value
        self.parent = parent
        parent.attrs[name] = self


class DummyNode:
    """A generic DCC node"""

    def __init__(self, name: str, db=DB) -> None:
        self.name = name
        self.attrs = {}
        self.ops = []
        if db is not None:
            db.add(self)


class DummySimplex(DummyNode):
    """A generic simplex node"""

    def __init__(self, name, parent, db: DummyScene = DB) -> None:
        super().__init__(name, db)
        self.definition = ""
        parent.ops.append(self)


class DummyFalloff(DummyNode):
    """A generic simplex node"""

    def __init__(self, name, parent: DummyScene, db=DB) -> None:
        super().__init__(name, db)
        self.weightmap = None


class DummyShape:
    """A generic named blendshape shape"""

    def __init__(self, name, shapeNode) -> None:
        self.name = name
        self.value = 0.0
        self.points = None
        self.shapeNode = shapeNode
        shapeNode.shapes[name] = self


class DummyBlendshape(DummyNode):
    """A generic blendshape node"""

    def __init__(self, name, parent, db: DummyScene = DB) -> None:
        # TODO: Just reuse the DummyAttr instead of making an equivalent
        super().__init__(name, db)
        self.shapes = {}
        parent.ops.append(self)


class DummyMesh(DummyNode):
    """A generic mesh"""

    def __init__(self, name, db=DB) -> None:
        super().__init__(name, db)
        self.importPath = ""
        self.faces = None
        self.counts = None
        self.uvs = None
        self.uvFaces = None
        self.verts = None


class DCC:
    program = "dummy"

    def __init__(self, simplex, stack=None) -> None:
        self.simplex = simplex  # the abstract representation of the setup
        self.name = simplex.name

        self.scene = DummyScene()
        self.mesh = None
        self.ctrl = None
        self.shapeNode = None
        self.op = None

        self._live = True
        self._revision = 0
        # self._shapes = {} # hold the shapes from the .smpx file as a dict
        # self._faces = None # Faces for the mesh (Alembic-style)
        # self._counts = None # Face counts for the mesh (Alembic-style)
        # self._uvs = None # UV data for the mesh
        # self._numVerts = None
        self._falloffs = {}  # weightPerVert values
        self.sliderMul = self.simplex.sliderMul

    def dummyLoad(self, other, pBar=None) -> None:
        """Method to copy the information in a DCC to a DummyDCC

        Parameters
        ----------
        other : DCC
            The DCC to load into the dummy
        pBar : QProgressDialog, optional
            An optional progress dialog (Default value = None)

        Returns
        -------
        : DummyDCC :
            The new DummyDCC
        """
        assert self.simplex is not None
        other.getAllShapeVertices(other.simplex.shapes, pBar=pBar)

        # Load all the data onto the new dummy mesh
        points, faces, counts, uvs, uvFaces = other.getMeshTopology(other.mesh)
        dummyMesh = self.buildRawTopology(
            other.name, points, faces, counts, uvs, uvFaces
        )
        self.loadNodes(self.simplex, dummyMesh)

        # Re-create the dummy shapes and sliders
        for shape in self.simplex.shapes:
            shape.thing = DummyShape(shape.name, self.shapeNode)

        for oShape, nShape in zip(other.simplex.shapes, self.simplex.shapes):
            nShape.verts = copy.copy(oShape.verts)

        self.pushAllShapeVertices(self.simplex.shapes)
        restVerts = self.simplex.restShape.verts

        for slider in self.simplex.sliders:
            slider.thing = DummyAttr(slider.name, 0.0, self.ctrl)

        for fo in self.simplex.falloffs:
            fo.thing = DummyFalloff(fo.name, self.scene)
            fo.verts = restVerts

    def preLoad(self, simp, simpDict, create: bool = True, pBar=None) -> None:
        """Code to execute before loading a simplex system into a dcc

        Parameters
        ----------
        simp : Simplex
            The simplex system that will be created
        simpDict : dict
            The dictionary definition of the simplex to be created
        create : bool
            Whether to create the missing objects in the DCC (Default value = True)
        pBar : QProgressDialog, optional
            An optional progress dialog (Default value = None)

        Returns
        -------
        : object :
            A generic python object to be used in the post-load
        """
        return None

    def postLoad(self, simp, preRet) -> None:
        """Code to execute after loading a simplex system into a dcc

        Parameters
        ----------
        simp : Simplex
            The simplex system that was created
        preRet : object
            The object returnd from the preload method
        """
        pass

    def checkForErrors(self, window) -> None:
        """Check for any DCC specific errors

        Parameters
        ----------
        window : QMainWindow
            The simplex window
        """
        pass

    # System IO
    @undoable
    def loadNodes(self, simp, thing, create=True, pBar=None) -> None:
        """Load the nodes from a simplex system onto a thing

        Parameters
        ----------
        simp : Simplex
            The system we're loading for
        thing : object
            The DCC thing we're reading
        create : bool
            Whether to create the missing nodes (Default value = True)
        pBar : QProgressDialog, optional
            An optional progress dialog (Default value = None)
        """
        if thing is None:
            thing = DummyMesh(simp.name)

        self.name = simp.name
        self.mesh = thing
        self.scene.add(self.mesh)

        self.shapeNode = self.scene.get(DummyBlendshape, self.name)

        if self.shapeNode is None:
            if not create:
                raise RuntimeError(
                    f"Blendshape operator not found with creation turned off: {self.name}"
                )
            self.shapeNode = DummyBlendshape(self.name, self.mesh, self.scene)

        self.op = self.scene.get(DummySimplex, self.name)
        if self.op is None:
            if not create:
                raise RuntimeError(
                    "Simplex operator not found with creation turned off"
                )
            self.op = DummySimplex(self.name, self.mesh, self.scene)

        self.ctrl = self.scene.get(DummyNode, self.name)
        if self.ctrl is None:
            if not create:
                raise RuntimeError("Control object not found with creation turned off")
            self.ctrl = DummyNode(self.name, self.scene)

    def loadConnections(self, simp, pBar=None) -> None:
        """Load the connections that exist in a simplex system

        Parameters
        ----------
        simp : Simplex
            The simplex system to load connections for
        pBar : QProgressDialog, optional
            An optional progress dialog (Default value = None)
        """
        pass

    def getShapeThing(self, shapeName):
        """Get the DCC Thing for a given shape name

        Parameters
        ----------
        shapeName : str
            The name of the shape to get

        Returns
        -------
        : object :
            The DCC Thing
        """
        return self.shapeNode.shapes.get(shapeName)

    def getSliderThing(self, sliderName):
        """Get the DCC Thing for a given slider name

        Parameters
        ----------
        sliderName : str
            The name of the slider to get

        Returns
        -------
        : object :
            The DCC Thing
        """
        return self.ctrl.attrs.get(sliderName)

    @staticmethod
    @undoable
    def buildRestAbc(abcMesh, name) -> DummyMesh:
        """Build the rest Alembic node in the dcc

        Parameters
        ----------
        abcMesh : IPolyMesh
            The Alembic mesh object
        name : str
            The name of the object to create
        """
        mesh = DummyMesh(name)  # don't add it to a scene
        mesh.verts = getSampleArrayIndex(abcMesh, index=0)
        faces, counts = getStaticMeshData(abcMesh)
        uvs = getUvSample(abcMesh)

        aryType = list if np is None else np.array
        if uvs is not None:
            mesh.uvs = aryType(uvs.getVals())
            mesh.uvFaces = aryType(uvs.getIndices())
        mesh.faces = aryType(faces)
        mesh.counts = aryType(counts)

        return mesh

    @staticmethod
    @undoable
    def buildRawTopology(
        name, points, faces, counts, uvs=None, uvFaces=None
    ) -> DummyMesh:
        """Build a mesh directly from raw numerical data"""
        # TODO: Move this guy out to the rest of the DCC's
        mesh = DummyMesh(name)  # don't add it to a scene

        aryType = list if np is None else np.array
        mesh.verts = aryType(points)
        mesh.faces = aryType(faces)
        mesh.counts = aryType(counts)
        if uvs is not None and uvFaces is not None:
            mesh.uvs = aryType(uvs)
            mesh.uvFaces = aryType(uvFaces)
        return mesh

    @staticmethod
    def vertCount(mesh) -> int:
        """Get the vert count of the given DCC Object

        Parameters
        ----------
        mesh : object
            The mesh to check

        Returns
        -------
        : int :
            The Number of verts
        """
        return len(mesh.verts)

    @undoable
    def loadAbcPoses(self, abcMesh, js, pBar=None) -> None:
        """Load the joints/skin from an alembic file onto an already-created system

        Parameters
        ----------
        abcMesh : IPolyMesh
            The Alembic mesh to load shapes from
        js : dict
            The simplex definition dictionary
        pBar : QProgressDialog, optional
            An optional progress dialog (Default value = None)
        """
        pass

    @undoable
    def loadAbc(self, abcMesh, js, pBar=None) -> None:
        """Load the shapes from an alembic file onto an already-created system

        Parameters
        ----------
        abcMesh : IPolyMesh
            The Alembic mesh to load shapes from
        js : dict
            The simplex definition dictionary
        pBar : QProgressDialog, optional
            An optional progress dialog (Default value = None)
        """
        shapes = js["shapes"]
        if js["encodingVersion"] > 1:
            shapes = [i["name"] for i in shapes]
        pointPositions = getSampleArray(abcMesh)
        for name, ppos in zip(shapes, pointPositions):
            dummyShape = self.shapeNode.shapes[name]
            dummyShape.points = ppos

    def getAllShapeVertices(self, shapes, pBar=None) -> None:
        """Load all shape vertices into the simplex system for processing

        Parameters
        ----------
        shapes : [Shape, ...]
            A list of simplex Shape objects to get positions for

        pBar : QProgressDialog, optional
            An optional progress dialog (Default value = None)
        """
        for shape in shapes:
            verts = self.getShapeVertices(shape)
            shape.verts = verts

    def getShapeVertices(self, shape):
        """Get the point positions of a shape

        Parameters
        ----------
        shape : Shape
            A simplex Shape object to get the vertices for

        Returns
        -------
        : np.array :
            A numpy array of the point positions
        """
        return shape.thing.points

    def pushAllShapeVertices(self, shapes, pBar=None) -> None:
        """Push the computed vertex positions for the given shapes back to the DCC

        Parameters
        ----------
        shapes : [Shape, ...]
            A list of simplex Shape objects

        pBar : QProgressDialog, optional
            An optional progress dialog (Default value = None)
        """
        for shape in shapes:
            self.pushShapeVertices(shape)

    def pushShapeVertices(self, shape) -> None:
        """Push the computed vertex positions for the given shape back to the DCC
        Parameters
        ----------
        shape : Shape
            The Simplex Shape object to update
        """
        shape.thing.points = shape.verts

    def loadMeshTopology(self) -> None:
        """Load the mesh topology from the DCC into the simplex interface"""
        # Here in Dummy I either have the data already or I don't, So nothing to do
        pass

    @staticmethod
    def getMeshTopology(mesh, uvName=None):
        """Get the topology of a mesh

        Parameters
        ----------
        mesh : object
            The DCC Mesh to read
        uvName : str, optional
            The name of the uv set to read

        Returns
        -------
        : np.array :
            The vertex array
        : np.array :
            The "faces" array
        : np.array :
            The "counts" array
        : np.array :
            The uv positions
        : np.array :
            The "uvFaces" array
        """
        return mesh.verts, mesh.faces, mesh.counts, mesh.uvs, mesh.uvFaces

    def exportAbc(
        self, dccMesh, abcMesh, js, world=False, ensureCorrect=False, pBar=None
    ) -> None:
        """Export a .smpx file

        Parameters
        ----------
        dccMesh : object
            The DCC Mesh to export
        abcMesh : OPolyMesh
            The Alembic output mesh
        js : dict
            The definition dictionary
        world : bool
            Do the export in worldspace (Default value = False)
        pBar : QProgressDialog, optional
            An optional progress dialog (Default value = None)
        """
        # export the data to alembic
        if dccMesh is None:
            dccMesh = self.mesh

        shapeDict = {i.name: i for i in self.simplex.shapes}

        shapeNames = js["shapes"]
        if js["encodingVersion"] > 1:
            shapeNames = [i["name"] for i in shapeNames]
        shapes = [shapeDict[i] for i in shapeNames]
        schema = abcMesh.getSchema()

        if pBar is not None:
            pBar.show()
            pBar.setMaximum(len(shapes))
            spacerName = "_" * max(list(map(len, shapeNames)))
            pBar.setLabelText(f"Exporting:\n{spacerName}")
            QApplication.processEvents()

        faces = mkSampleIntArray(self.mesh.faces)
        counts = mkSampleIntArray(self.mesh.counts)
        uvs = None
        if self.mesh.uvs is not None and self.mesh.uvFaces is not None:
            uvs = mkUvSample(self.mesh.uvs, self.mesh.uvFaces)

        for i, shape in enumerate(shapes):
            if pBar is not None:
                pBar.setLabelText(f"Exporting:\n{shape.name}")
                pBar.setValue(i)
                pBar.repaint()  # Required to properly show the percentage. Don't know why
                QApplication.processEvents()
                if pBar.wasCanceled():
                    return
            verts = mkSampleVertexPoints(shape.thing.points)
            if uvs is not None:
                # Alembic doesn't allow for uvs=None for some reason
                abcSample = OPolyMeshSchemaSample(verts, faces, counts, uvs)
            else:
                abcSample = OPolyMeshSchemaSample(verts, faces, counts)
            schema.set(abcSample)

    def exportOtherAbc(
        self, dccMesh, abcMesh, js, world: bool = False, pBar=None
    ) -> None:
        """Export a .smpx file of a mesh other than self.mesh

        Parameters
        ----------
        dccMesh : object
            The DCC Mesh to export
        abcMesh : OPolyMesh
            The Alembic output mesh
        js : dict
            The definition dictionary
        world : bool
            Do the export in worldspace (Default value = False)
        pBar : QProgressDialog, optional
            An optional progress dialog (Default value = None)
        """
        if dccMesh is None:
            raise ValueError(
                "Export Other requires an explicitly defined mesh to export"
            )
        self.exportAbc(
            dccMesh, abcMesh, js, world=world, ensureCorrect=False, pBar=pBar
        )

    def deleteObj(self, dccMesh, path) -> None:
        """Export a mesh to the given path"""
        pass

    def exportMesh(self, dccMesh, path) -> None:
        """Export a mesh to the given path"""
        pass

    # Revision tracking
    def getRevision(self) -> int:
        """Get the simplex revision number"""
        return self._revision

    def incrementRevision(self) -> int:
        """Increment the revision number"""
        self._revision += 1
        return self._revision

    def setRevision(self, val) -> None:
        """Manually set the revision numer

        Parameters
        ----------
        val : int
            The value to set
        """
        self._revision = val

    # System level
    @undoable
    def renameSystem(self, name) -> None:
        """Rename a simplex system

        Parameters
        ----------
        name : str
            The new name
        """
        # TODO
        # oldName = self.name
        self.name = name
        # for dd in (DB.nodes, DB.ops, DB.bss, DB.meshes):
        # oo = dd.get(oldName)
        # if oo is not None:
        # oo.name = self.name
        # dd[self.name] = oo
        # dd.pop(oldName, None)

    @undoable
    def deleteSystem(self) -> None:
        """Delete the current system"""
        # for dd in (DB.nodes, DB.ops, DB.bss, DB.meshes):
        # if self.name in dd:
        # dd.pop(self.name, None)
        # TODO
        self.name = None
        self.simplex = None

    # Shapes
    @undoable
    def createShape(self, shape, live: bool = False, offset: int = 10) -> DummyShape:
        """Create a dcc shape

        Parameters
        ----------
        shape : Shape
            A simplex shape object
        live : bool
            Whether this shape is live-connected (Default value = False)
        offset : float
            The offset of the created shape (Default value = 10)
        """
        newShape = DummyShape(shape.name, self.shapeNode)
        newShape.points = copy.copy(self.mesh.verts)
        return newShape

    @undoable
    def extractWithDeltaShape(
        self, shape, live: bool = True, offset: float = 10.0
    ) -> None:
        """Make a mesh representing a shape. Can be live or not.
        Also, make a shapenode that is the delta of the change being made
        """
        pass

    @undoable
    def extractWithDeltaConnection(
        self, shape, delta, value, live: bool = True, offset: float = 10.0
    ) -> None:
        """Extract a shape with a live partial delta added in.
        Useful for updating progressive shapes
        """
        pass

    @undoable
    def extractShape(self, shape, live: bool = True, offset: float = 10.0) -> None:
        """Make a mesh representing a shape. Can be live or not.
        Can also store its starting shape and delta data
        """
        pass

    @undoable
    def connectShape(
        self, shape, mesh=None, live: bool = False, delete: bool = False
    ) -> None:
        """Force a shape to match a mesh
        The "connect shape" button is:
            mesh=None, delete=True
        The "match shape" button is:
            mesh=someMesh, delete=False
        There is a possibility of a "make live" button:
            live=True, delete=False
        """
        pass

    @undoable
    def extractPosedShape(self, shape) -> None:
        pass

    @undoable
    def zeroShape(self, shape) -> None:
        """Set a shape back to rest

        Parameters
        ----------
        shape : Shape
            The simplex shpae to zero out
        """
        shape.thing.points = self.getShapeVertices(self.simplex.restShape)

    @undoable
    def deleteShape(self, toDelShape) -> None:
        """Delete a shape from the system

        Parameters
        ----------
        toDelShape :
        """
        self.shapeNode.shapes.pop(toDelShape.name, None)

    @undoable
    def renameShape(self, shape, name) -> None:
        """Rename a shape

        Parameters
        ----------
        shape : Shape
            The simplex Shape object to rename
        name : str
            The new name
        """
        self.shapeNode.shapes.pop(shape.thing.name, None)
        shape.thing.name = name
        self.shapeNode.shapes[name] = shape.thing

    @undoable
    def convertShapeToCorrective(self, shape) -> None:
        pass

    # Falloffs
    def createFalloff(self, falloff) -> None:
        """Create a per-vert falloff weightmap

        Parameters
        ----------
        falloff : Falloff
            The simplex Falloff object to create
        """
        fo = DummyFalloff(falloff.name, self.scene)
        fo.weights = np.zeros(len(self.mesh.verts))

    def duplicateFalloff(self, falloff, newFalloff) -> None:
        """Create a new falloff from an already existing one

        Parameters
        ----------
        falloff : Falloff
            The already existing falloff
        newFalloff : Falloff
            The newly created falloff to store the newly duplicated data
        """
        fo = DummyFalloff(newFalloff.name, self.scene)
        fo.weights = copy.copy(falloff.thing.weights)

    def deleteFalloff(self, falloff) -> None:
        """Delete a falloff object

        Parameters
        ----------
        falloff : Falloff
            The Falloff object to delete
        """
        self.scene.remove(falloff.thing)

    def setFalloffData(
        self, falloff, splitType, axis, minVal, minHandle, maxHandle, maxVal, mapName
    ) -> None:
        """Set the data of a falloff object"""
        # TODO: set the per-vert falloffs
        pass  # for eventual live splits

    def getFalloffThing(self, falloff):
        """Get the thing for a given falloff

        Parameters
        ----------
        falloff : Falloff
            The simplex falloff object to get
        """
        return self.scene.get(DummyFalloff, falloff.name)

    # Sliders
    @undoable
    def createSlider(self, slider) -> DummyAttr:
        """Create a slider object

        Parameters
        ----------
        slider : Slider
            The simplex slider object to create
        """
        return DummyAttr(slider.name, 0.0, self.ctrl)

    @undoable
    def renameSlider(self, slider, name) -> None:
        """Rename a slider

        Parameters
        ----------
        slider : Slider
            The slider to rename
        name : str
            The new name
        """
        self.ctrl.attrs.pop(slider.thing.name, None)
        self.ctrl.attrs[name] = slider.thing
        slider.thing.name = name

    @undoable
    def setSliderRange(self, slider) -> None:
        """Set the min and max of a slider

        Parameters
        ----------
        slider : Slider
            The slider to set
        """
        pass

    @undoable
    def deleteSlider(self, toDelSlider) -> None:
        """Delete a slider

        Parameters
        ----------
        toDelSlider : Slider
            The slider to delete
        """
        self.ctrl.attrs.pop(toDelSlider.name, None)

    @undoable
    def addProgFalloff(self, prog, falloff) -> None:
        pass  # for eventual live splits

    @undoable
    def removeProgFalloff(self, prog, falloff) -> None:
        pass  # for eventual live splits

    @undoable
    def setSlidersWeights(self, sliders, weights) -> None:
        """Set the values for the given sliders

        Parameters
        ----------
        sliders : [Slider, ...]
            The sliders to set values for
        weights : [float, ...]
            The values to set
        """
        for slider, val in zip(sliders, weights):
            slider.thing.value = val

    @undoable
    def setSliderWeight(self, slider, weight) -> None:
        """Set the value for a given slider

        Parameters
        ----------
        slider : Slider
            The slider
        weight : float
            The value
        """
        slider.thing.value = weight

    @undoable
    def updateSlidersRange(self, sliders) -> None:
        """Update the range of the given sliders"""
        pass

    @undoable
    def extractTraversalShape(
        self, trav, shape, live: bool = True, offset: float = 10.0
    ) -> None:
        """Extract a shape from a traversal progression"""
        pass

    @undoable
    def connectTraversalShape(
        self, trav, shape, mesh=None, live: bool = True, delete: bool = False
    ) -> None:
        """Connect a shape to a traversal progression"""
        pass

    # Combos
    @undoable
    def extractComboShape(
        self, combo, shape, live: bool = True, offset: float = 10.0
    ) -> None:
        """Extract a shape from a combo progression"""
        pass

    @undoable
    def connectComboShape(
        self, combo, shape, mesh=None, live: bool = True, delete: bool = False
    ) -> None:
        """Connect a shape to a combo progression"""
        pass

    @staticmethod
    def setDisabled(op) -> None:
        """Disable the output of any simplex systems

        Parameters
        ----------
        op : The operator to disable

        Returns
        -------
        : object :
            Some object that will allow us to re-enable the system
        """
        return None

    @staticmethod
    def reEnable(helpers) -> None:
        """Re-enable a simplex system

        Parameters
        ----------
        helpers : object
            The helper object returned from setDisabled
        """
        pass

    @undoable
    def renameCombo(self, combo, name) -> None:
        """Set the name of a Combo

        Parameters
        ----------
        combo : Combo
            The combo to rename
        name : str
            The new name
        """
        pass

    # Data Access
    @staticmethod
    def getSimplexOperators():
        """Get all simplex operators in the DCC"""
        return list(DB.ops.values())

    @staticmethod
    def getSimplexOperatorsByName(name):
        """Get a simplex operator

        Parameters
        ----------
        name : str
            The name to search for

        Returns
        -------
        : object :
            The simplex operator for the DCC
        """
        return DB.ops.get(name)

    @staticmethod
    def getSimplexOperatorsOnObject(thing) -> list[DummySimplex]:
        """Get all simplex operators controlling an object

        Parameters
        ----------
        thing : object
            A dcc object to check for simplex operators

        Returns
        -------
        : [object, ...] :
            A list of simplex operators
        """
        return [o for o in thing.ops if isinstance(o, DummySimplex)]

    @staticmethod
    def getSimplexString(op):
        """Get the simplex string from the given operator

        Parameters
        ----------
        op : object
            The Simplex operator to get the definition from

        Returns
        -------
        : str :
            The simplex definition
        """
        return op.definition

    @staticmethod
    def getSimplexStringOnThing(thing, systemName):
        """Get the definition on an object by name

        Parameters
        ----------
        thing : object
            The DCC object to check for a simplex operator
        systemName : str
            The system name to check for

        Returns
        -------
        : str :
            The simplex definition
        """
        for op in thing.ops:
            if op.name == systemName:
                return op.definition
        return None

    @staticmethod
    def setSimplexString(op, val) -> None:
        """Set the definition string on an object

        Parameters
        ----------
        op : object
            The operator to set the definition on
        val : str
            The definition to set
        """
        op.definition = val

    @staticmethod
    def selectObject(thing) -> None:
        """Select an object in the DCC"""
        pass

    def selectCtrl(self) -> None:
        """Select the system's control object"""
        pass

    @staticmethod
    def getObjectByName(name):
        """Get an object by name

        Parameters
        ----------
        name : str
            The name to search for

        Returns
        -------
        : object :
            The found object
        """
        # TODO: maybe also filter by type??
        # return DB.meshes.get(name)
        return DB.get(DummyMesh, name)

    @staticmethod
    def getObjectName(thing):
        """Get the name of an object

        Parameters
        ----------
        thing : object
            The dcc object to get the name for

        Returns
        -------
        : str :
            The Object Name
        """
        return thing.name

    @staticmethod
    def staticUndoOpen() -> None:
        """Open an undo chunk without knowledge of Simplex"""
        pass

    @staticmethod
    def staticUndoClose() -> None:
        """Close an undo chunk without knowledge of Simplex"""
        pass

    def undoOpen(self) -> None:
        """Open an undo chunk with knowledge of Simplex"""
        pass

    def undoClose(self) -> None:
        """Close an undo chunk with knowledge of Simplex"""
        pass

    @classmethod
    def getPersistentFalloff(cls, thing):
        """Get a representation of the given object that won't get deleted or garbage collected

        Parameters
        ----------
        thing : object
            The thing to get a persistent representation of

        Returns
        -------
        : object :
            The requested persistent object
        """
        return cls.getObjectName(thing)

    @classmethod
    def loadPersistentFalloff(cls, thing):
        """Get the usable representation of the given persistent thing

        Parameters
        ----------
        thing : object
            A persistent representation

        Returns
        -------
        : object :
            The requested volatile object
        """
        return cls.getObjectByName(thing)

    @classmethod
    def getPersistentShape(cls, thing):
        """Get a representation of the given object that won't get deleted or garbage collected

        Parameters
        ----------
        thing : object
            The thing to get a persistent representation of

        Returns
        -------
        : object :
            The requested persistent object
        """
        return cls.getObjectName(thing)

    @classmethod
    def loadPersistentShape(cls, thing):
        """Get the usable representation of the given persistent thing

        Parameters
        ----------
        thing : object
            A persistent representation

        Returns
        -------
        : object :
            The requested volatile object
        """
        return cls.getObjectByName(thing)

    @classmethod
    def getPersistentSlider(cls, thing):
        """Get a representation of the given object that won't get deleted or garbage collected

        Parameters
        ----------
        thing : object
            The thing to get a persistent representation of

        Returns
        -------
        : object :
            The requested persistent object
        """
        return cls.getObjectName(thing)

    @classmethod
    def loadPersistentSlider(cls, thing):
        """Get the usable representation of the given persistent thing

        Parameters
        ----------
        thing : object
            A persistent representation

        Returns
        -------
        : object :
            The requested volatile object
        """
        return cls.getObjectByName(thing)

    @staticmethod
    def getSelectedObjects() -> list[DummyNode]:
        """Get the selected objects"""
        # Here in the dummy interface, we short-circuit this
        # And return a default selected object called "thing"
        return [DummyNode("thing")]

    def getFreezeThing(self, combo):
        return []


class SliderDispatch(QtCore.QObject):
    valueChanged = Signal()

    def __init__(self, node, parent=None) -> None:
        super().__init__(parent)

    def emitValueChanged(self, *args, **kwargs) -> None:
        self.valueChanged.emit()


class Dispatch(QtCore.QObject):
    beforeNew = Signal()
    afterNew = Signal()
    beforeOpen = Signal()
    afterOpen = Signal()
    undo = Signal()
    redo = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    def connectCallbacks(self) -> None:
        pass

    def disconnectCallbacks(self) -> None:
        pass

    def emitBeforeNew(self, *args, **kwargs) -> None:
        self.beforeNew.emit()

    def emitAfterNew(self, *args, **kwargs) -> None:
        self.afterNew.emit()

    def emitBeforeOpen(self, *args, **kwargs) -> None:
        self.beforeOpen.emit()

    def emitAfterOpen(self, *args, **kwargs) -> None:
        self.afterOpen.emit()

    def emitUndo(self, *args, **kwargs) -> None:
        self.undo.emit()

    def emitRedo(self, *args, **kwargs) -> None:
        self.redo.emit()


DISPATCH = Dispatch()


def rootWindow() -> None:
    return None
