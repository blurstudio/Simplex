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


# pylint: disable=invalid-name
from __future__ import absolute_import, print_function

import json
import os
import tempfile
from contextlib import contextmanager
from functools import wraps
from itertools import repeat

import dcc.xsi as dcc
import numpy as np
import six
from alembic.AbcGeom import OPolyMeshSchemaSample
from imath import IntArray, V3f, V3fArray
from six.moves import range, zip

from ..commands.alembicCommon import mkUvSample
from ..commands.buildIceXML import buildIceXML, buildLoaderXML, buildSliderIceXML
from ..Qt import QtCore
from ..Qt.QtCore import Signal
from ..Qt.QtWidgets import QApplication, QDialog, QMainWindow, QSplashScreen


# UNDO STACK INTEGRATION
@contextmanager
def undoContext(inst=None):
    """

    Parameters
    ----------
    inst :
         (Default value = None)

    Returns
    -------

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
    """

    Parameters
    ----------
    f :


    Returns
    -------

    """

    @wraps(f)
    def stacker(*args, **kwargs):
        """

        Parameters
        ----------
        *args :

        **kwargs :


        Returns
        -------

        """
        with undoContext():
            return f(*args, **kwargs)

    return stacker


# temporarily disconnect inputs from the slider list
@contextmanager
def disconnected(sliders, prop):
    """

    Parameters
    ----------
    sliders :

    prop :


    Returns
    -------

    """
    params = [slider.thing for slider in sliders]
    pairs = []
    toRemove = []
    for param in params:
        if param.IsAnimated(dcc.constants.siExpressionSource):
            pairs.append((param.Name, param.Source.Definition.Value))

            toRemove.append(param)
    dcc.xsi.RemoveAnimation(toRemove)
    dcc.xsi.SetValue(params, 0.0)

    try:
        yield pairs
    finally:
        for paramName, exp in pairs:
            param = prop.Parameters(paramName)
            if param is not None:
                param.AddExpression(exp)


class DCC(object):
    """ """

    program = "xsi"
    shapeNamePrefix = ""
    texName = "Texture_Projection"

    def __init__(self, simplex, stack=None):
        self.name = None  # the name of the system
        self.mesh = None  # the mesh object with the system
        self.inProp = None  # the control property on the object
        self.shapeCluster = None  # the cluster containing the shapes
        self.shapeTree = None  # the ICETree driving the shapes
        self.shapeNode = None  # the shape compound node in the IceTree
        self.sliderNode = None  # the slider compound node in the IceTree
        self.op = None  # the simplex node in the IceTree
        self.simplex = simplex  # the abstract representation of the setup
        self.undoDepth = 0
        self._live = True
        self.sliderMul = self.simplex.sliderMul

        cls = type(self)
        self.shapeNamePrefix = cls.shapeNamePrefix
        # Reset the prefix because othewise, someone will forget
        cls.shapeNamePrefix = ""

    def getShapeThing(self, shapeName):
        """

        Parameters
        ----------
        shapeName :


        Returns
        -------

        """
        for prop in self.shapeCluster.Properties:
            if prop.Name == self.shapeNamePrefix + shapeName:
                return [prop, None, None, None]
        return None

    def getSliderThing(self, sliderName):
        """

        Parameters
        ----------
        sliderName :


        Returns
        -------

        """
        return self.inProp.Parameters(sliderName)

    def preLoad(self, simp, simpDict, create=True, pBar=None):
        """

        Parameters
        ----------
        simp :

        simpDict :

        create :
             (Default value = True)
        pBar :
             (Default value = None)

        Returns
        -------

        """
        # Pre-build all the nodes and parameters quickly
        if pBar is not None:
            pBar.setLabelText("Loading Connections")
            QApplication.processEvents()
        ev = simpDict["encodingVersion"]

        shapeNames = simpDict.get("shapes")
        if not shapeNames:
            return

        if ev > 1:
            shapeNames = [i["name"] for i in shapeNames]

        # Gather all the missing shapes to create in one go
        if pBar is not None:
            pBar.setMaximum(len(shapeNames))
            pBar.setLabelText("Checking for missing shapes")
            pBar.setValue(0)
            QApplication.processEvents()

        toMake = self._checkAllShapeValidity(shapeNames, pBar=pBar)

        if toMake:
            # Make 1 master duplicate and store it as a shapekey
            # This ensures that all the shapes are created on the correct cluster
            dupName = "__Simplex_Master_Dup"
            tempVertArray, tempFaceArray = self.mesh.ActivePrimitive.Geometry.Get2()
            dup = self.mesh.parent.AddPolygonMesh(tempVertArray, tempFaceArray, dupName)
            dup.Properties("Visibility").viewvis = False

            newShape = dcc.xsi.StoreShapeKey(
                self.shapeCluster,
                dup.Name,
                dcc.constants.siShapeObjectReferenceMode,
                1,
                0,
                0,
                dcc.constants.siShapeContentPrimaryShape,
                False,
            )
            dcc.xsi.FreezeObj(newShape)
            dcc.xsi.DeleteObj(dup)
            sks = [newShape]

            if len(toMake) > 1:
                # If there are more shapes to make, then we make them by
                # duplicating the shapes from the mixer. This is easily
                # 50x faster than creating shapes via any other method
                if pBar is not None:
                    pBar.setMaximum(len(toMake))
                    pBar.setValue(0)
                    pBar.setLabelText("Creating Empty Shapes")
                    QApplication.processEvents()

                mixShape = "{0}.{1}".format(
                    newShape.model.mixer.FullName, newShape.Name
                )
                # This may fail on stupid-dense meshes.
                # Maybe add a pointCount vs. chunk size heuristic?
                chunk = 20
                for i in range(0, len(toMake[1:]), chunk):
                    if pBar is not None:
                        pBar.setValue(i)
                        QApplication.processEvents()

                    curSize = min(len(toMake) - 1, i + chunk) - i
                    # Can't duplicate more than 1 at a time, otherwise we get memory issues
                    dupShapes = dcc.xsi.Duplicate(
                        mixShape,
                        curSize,
                        dcc.constants.siCurrentHistory,
                        dcc.constants.siSharedParent,
                        dcc.constants.siShareGrouping,
                        dcc.constants.siNoProperties,
                        dcc.constants.siDuplicateAnimation,
                        dcc.constants.siShareConstraints,
                        dcc.constants.siNoSelection,
                    )
                    for dd in dupShapes:
                        cs = dcc.xsi.GetValue(
                            "{0}.{1}".format(self.shapeCluster.FullName, dd.Name)
                        )
                        sks.append(cs)

            if pBar is not None:
                pBar.setLabelText("Naming Shapes")
                pBar.setValue(0)
                pBar.setMaximum(len(sks))
                QApplication.processEvents()

            with self.noShapeNode():
                chunk = 20
                pfxToMake = [self.shapeNamePrefix + i for i in toMake]
                for idx in range(0, len(sks), chunk):
                    if pBar is not None:
                        pBar.setValue(idx)
                    pns = ",".join(
                        [p.fullname + ".Name" for p in sks[idx : idx + chunk]]
                    )
                    dcc.xsi.SetValue(pns, pfxToMake[idx : idx + chunk])

        dcc.xsi.FreezeObj(
            [i for i in self.shapeCluster.Properties if len(i.NestedObjects) > 2]
        )

        clsCombiner = dcc.operator.getOperatorFromStack(
            self.mesh, "clustershapecombiner"
        )
        if clsCombiner:
            dcc.xsi.DeleteObj(clsCombiner)

        sliderNames = simpDict.get("sliders")
        if not sliderNames:
            return
        if ev > 1:
            sliderNames = [i["name"] for i in sliderNames]
        else:
            sliderNames = [i[0] for i in sliderNames]

        for sliderName in sliderNames:
            sliderParam = self.inProp.Parameters(sliderName)
            if not sliderParam:
                if not create:
                    raise RuntimeError(
                        "Slider {0} not found with creation turned off".format(
                            sliderName
                        )
                    )
                self.inProp.AddParameter3(
                    sliderName, dcc.constants.siFloat, 0, -2.0, 2.0
                )
        return None

    def postLoad(self, simp, preRet):
        """

        Parameters
        ----------
        simp :

        preRet :


        Returns
        -------

        """
        self.rebuildSliderNode()
        self.resetShapeIndexes()
        self.recreateShapeNode()
        self.updateSlidersRange(simp.sliders)

    def checkForErrors(self, window):
        """ Check for any DCC specific errors

        Parameters
        ----------
        window : QMainWindow
            The simplex window
        """
        pass

    # System IO
    @undoable
    def loadNodes(self, simp, thing, create=True, pBar=None):
        """Create a new system based on the simplex tree
        Build any DCC objects that are missing if create=True
        Raises a runtime error if missing objects are found and
        create=False

        Parameters
        ----------
        simp :

        thing :

        create :
             (Default value = True)
        pBar :
             (Default value = None)

        Returns
        -------

        """
        self.name = simp.name
        self.mesh = thing

        # find/build the shapeCluster
        if pBar is not None:
            pBar.setLabelText("Loading Nodes")
            QApplication.processEvents()

        shapeCluster = thing.ActivePrimitive.Geometry.Clusters("Shape")
        if not shapeCluster:
            shapeCluster = thing.ActivePrimitive.Geometry.Clusters(
                "%s_Shapes" % self.name
            )
        if not shapeCluster:
            if not create:
                raise RuntimeError("Shape cluster not found with creation turned off")
            self.shapeCluster = dcc.xsi.CreateCluster("%s.pnt[*]" % thing.FullName)[0]
            self.shapeCluster.Name = "%s_Shapes" % self.name
            dcc.xsi.SelectObj(thing)
        else:
            self.shapeCluster = shapeCluster

        # find/build the Icetree
        shapeTree = thing.ActivePrimitive.ICETrees("%s_IceTree" % self.name)
        if not shapeTree:
            if not create:
                raise RuntimeError(
                    "Simplex shape ICETree not found with creation turned off"
                )
            self.shapeTree = dcc.ice.ICETree(
                None,
                self.mesh,
                "%s_IceTree" % self.name,
                dcc.constants.siConstructionModePrimaryShape,
            )
        else:
            self.shapeTree = dcc.ice.ICETree(shapeTree)

        # find/build the Slider compound in the Icetree
        sliderComp = None
        for node in self.shapeTree.compoundNodes:
            if node.name == "SliderArray":
                sliderComp = node
                break
        if not sliderComp:
            if not create:
                raise RuntimeError(
                    "Slider array compound not found in ICETree with creation turned off"
                )
            sliderArray = self.shapeTree.addNode("BuildArray")
            sliderComp = self.shapeTree.createCompound([sliderArray])
            sliderComp.rename("SliderArray")
            sliderComp.exposePort(sliderArray.outputPorts["array"])
        self.sliderNode = sliderComp

        # find/build the simplex node in the Icetree
        ops = DCC.getSimplexOperatorsOnObjectByName(thing, self.name)
        if not ops:
            if not create:
                raise RuntimeError("Simplex Operator not found with create turned off")
            op = dcc.ice.ICENode(
                dcc.xsi.AddICENode("SimplexNode", self.shapeTree.fullName)
            )
            op.inputPorts["Sliders"].connect(self.sliderNode.outputPorts["Array"])
            setter = self.shapeTree.addSetDataNode("Self._%s_SimplexVector" % self.name)
            setter.Value.connect(op.outputPorts["Weights"])
            self.shapeTree.connect(setter.Execute, 1)
            self.op = op
        else:
            self.op = ops

        # find/build the shape compound in the Icetree
        shapeNode = None
        for node in self.shapeTree.compoundNodes:
            if node.name == "ShapeCompound":
                shapeNode = node
                break
        if not shapeNode:
            if not create:
                raise RuntimeError(
                    "Shape compound not found in ICETree with creation turned off"
                )
            setter = self.shapeTree.addSetDataNode("Self.PointPosition")
            self.shapeTree.connect(setter.Execute)
            shapeCompound = self.rebuildShapeNode(simp)
            getter = self.shapeTree.addGetDataNode("Self._%s_SimplexVector" % self.name)
            getter.value.connect(shapeCompound.inputPorts["In"])
            setter.Value.connect(shapeCompound.Result)
            self.shapeNode = shapeCompound
        else:
            self.shapeNode = shapeNode

        # find/build the input and output properties
        inProp = thing.Properties("%s_inProperty" % self.name)
        if not inProp:
            if not create:
                raise RuntimeError(
                    "Control parameters not found with creation turned off"
                )
            self.inProp = self.mesh.AddProperty(
                "CustomProperty", False, "%s_inProperty" % self.name
            )
        else:
            self.inProp = inProp

    def _checkAllShapeValidity(self, shapeNames, errorOnMissing=False, pBar=None):
        """Check shapes to see if they exist, and either gather the missing files, or
        Load the proper data onto the shapes

        Parameters
        ----------
        shapeNames :

        errorOnMissing :
             (Default value = False)
        pBar :
             (Default value = None)

        Returns
        -------

        """
        propByName = {i.Name: i for i in list(self.shapeCluster.Properties)}

        if pBar is not None:
            pBar.setMaximum(len(shapeNames))
            if errorOnMissing:
                pBar.setLabelText("Checking Validity")
            else:
                pBar.setLabelText("Checking For Missing Shapes")
            pBar.setValue(0)
            QApplication.processEvents()

        # Keep the set ordered, but make a set for quick checking
        missingNameSet = set()
        missingNames = []
        seen = set()

        for i, shapeName in enumerate(shapeNames):
            if shapeName in seen:
                continue
            seen.add(shapeName)

            if pBar is not None:
                pBar.setValue(i)
                QApplication.processEvents()

            if self.shapeNamePrefix + shapeName not in propByName:
                if errorOnMissing:
                    raise RuntimeError("Missing shape: {}".format(shapeName))
                else:
                    if shapeName not in missingNameSet:
                        missingNameSet.add(shapeName)
                        missingNames.append(shapeName)
        return missingNames

    def _loadShapeIceNodes(self, simp):
        """load the ICE nodes related to the given shapeKey

        Parameters
        ----------
        simp :


        Returns
        -------

        """
        # Ice nodes are created in-order by the buildIceXML function
        # so we can take advantage of that to properly connect the shapes
        simpNode = self.shapeNode
        children = simpNode.nodes
        # addNode, passNode, getSelfPos = children[:3]
        shapeNodes = children[3:]
        propByName = {i.Name: i for i in list(self.shapeCluster.Properties)}

        for i, shape in enumerate(simp.shapes):
            selector = shapeNodes[(3 * i) + 0]._nativePointer
            getData = shapeNodes[(3 * i) + 1]._nativePointer
            multiplier = shapeNodes[(3 * i) + 2]._nativePointer
            shape.thing = [
                propByName[self.shapeNamePrefix + shape.name],
                getData,
                selector,
                multiplier,
            ]

    @contextmanager
    def noShapeNode(self):
        """ """
        # Clear the shape node so we don't take the renaming speed hit
        if self.shapeNode:
            vectorGetter = list(
                self.shapeNode.inputPortList[0].connectedNodes.values()
            )[0]
            pointSetter = list(
                self.shapeNode.outputPortList[0].connectedNodes.values()
            )[0]
            # Also disconnect the pointSetter so we don't get the null deformation
            self.shapeTree.disconnect(2)
            self.shapeNode.delete()
        else:
            vectorGetter, pointSetter = None, None
        yield

        if vectorGetter is None and pointSetter is None:
            self.shapeNode = self.rebuildShapeNode(self.simplex)
        else:
            # Rebuild the shape and slider nodes
            self.shapeTree.connect(pointSetter.Execute, 2)
            shapeCompound = self.rebuildShapeNode(self.simplex)
            pointSetter.Value.connect(shapeCompound.Result)
            vectorGetter.value.connect(shapeCompound.inputPorts["In"])
            self.shapeNode = shapeCompound
            self._loadShapeIceNodes(self.simplex)
            self.rebuildSliderNode()

    @staticmethod
    def _getTextureProp(mesh, texName):
        """

        Parameters
        ----------
        mesh :

        texName :


        Returns
        -------

        """
        import pywintypes

        textureCls = [
            cluster
            for cluster in mesh.ActivePrimitive.Geometry.Clusters
            if cluster.Type == "sample"
        ]
        try:
            for cluster in textureCls:
                prop = cluster.Properties(texName)
                if prop:
                    return prop
        except pywintypes.com_error:
            pass
        return None

    @classmethod
    def buildRestAbc(cls, abcMesh, name):
        """

        Parameters
        ----------
        abcMesh :

        name :


        Returns
        -------

        """
        with undoContext():
            meshSchema = abcMesh.getSchema()
            rawFaces = meshSchema.getFaceIndicesProperty().samples[0]
            rawCounts = meshSchema.getFaceCountsProperty().samples[0]
            rawPos = meshSchema.getPositionsProperty().samples[0]
            iuvs = meshSchema.getUVsParam()

            uvws = None
            if iuvs.valid():
                uvValue = iuvs.getValueProperty().getValue()
                uvs = list(zip(uvValue.x, uvValue.y, repeat(0.0)))
                if iuvs.isIndexed():
                    idxs = list(iuvs.getIndexProperty().getValue())
                    uvs = [uvs[i] for i in idxs]
                uvws = []
                ptr = 0
                for i in rawCounts:
                    uvws.extend(reversed(uvs[ptr : ptr + i]))
                    ptr += i

            faces = []
            ptr = 0
            for i in rawCounts:
                faces.append(i)
                faces.extend(reversed(rawFaces[ptr : ptr + i]))
                ptr += i

            vertexArray = [list(rawPos.x), list(rawPos.y), list(rawPos.z)]

            cName = "{0}_SIMPLEX".format(name)
            model = dcc.xsi.ActiveSceneRoot.AddModel(
                None, "{0}_SIMPLEXModel".format(name)
            )
            mesh = model.AddPolygonMesh(vertexArray, faces, cName)

            if uvws is not None:
                dcc.xsi.CreateProjection(mesh, "", "", "", cls.texName, True, "", "")
                texProp = cls._getTextureProp(mesh, cls.texName)

                if texProp is not None:
                    dcc.xsi.FreezeObj(texProp)
                    if len(uvws) == texProp.Elements.Count:
                        texProp.Elements.Array = list(zip(*uvws))
                    dcc.xsi.FreezeObj(texProp)

        return mesh

    @staticmethod
    def vertCount(mesh):
        geo = mesh.ActivePrimitive.Geometry
        vertArray, faceArray = geo.Get2()
        return len(vertArray[0])

    @undoable
    def loadAbc(self, abcMesh, js, pBar=False):
        """

        Parameters
        ----------
        abcMesh :

        js :

        pBar :
             (Default value = False)

        Returns
        -------

        """
        shapes = js["shapes"]
        if js["encodingVersion"] > 1:
            shapes = [i["name"] for i in shapes]

        if pBar is not None:
            pBar.show()
            pBar.setMaximum(len(shapes))
            longName = max(shapes, key=len)
            pBar.setValue(1)
            pBar.setLabelText("Loading:\n{0}".format("_" * len(longName)))
            QApplication.processEvents()

        # Load the alembic via geometry
        preAtc = self.mesh.model.Properties("alembic_timecontrol")
        loader = dcc.io.abcImport(
            abcMesh.getArchive().getName(), parentNode=self.mesh.parent()
        )
        postAtc = self.mesh.model.Properties("alembic_timecontrol")
        loader = loader[0]
        loader.name = "Loader"
        loader.Properties("Visibility").viewvis = False
        dcc.xsi.FreezeModeling(loader)
        dcc.xsi.DeleteObj(
            "{0}.polymsh.alembic_polymesh.Expression".format(loader.FullName)
        )

        tVal = "{0}.polymsh.alembic_polymesh.time".format(loader.FullName)
        dcc.xsi.SetValue(tVal, 0)

        # rester = dcc.xsi.Duplicate(loader, 1,
        # dcc.constants.siCurrentHistory, dcc.constants.siSharedParent,
        # dcc.constants.siNoGrouping, dcc.constants.siNoProperties,
        # dcc.constants.siNoAnimation, dcc.constants.siNoConstraints,
        # dcc.constants.siNoSelection)

        tempVertArray, tempFaceArray = loader.ActivePrimitive.Geometry.Get2()
        rester = loader.parent.AddPolygonMesh(tempVertArray, tempFaceArray, "Rester")
        rester.Properties("Visibility").viewvis = False

        matcher = self._matchDelta(loader, rester)

        cluster = self.shapeCluster.FullName
        # "{0}.polymsh.cls.Face_Shapes".format(self.mesh.FullName)

        with self.noShapeNode():

            for i, shapeName in enumerate(shapes):
                if pBar is not None:
                    pBar.setValue(i)
                    pBar.setLabelText("Loading:\n{0}".format(shapeName))
                    QApplication.processEvents()
                    if pBar.wasCanceled():
                        return
                dcc.xsi.SetValue(tVal, i)
                dcc.xsi.ReplaceShapeKey(
                    "{0}.{1}".format(cluster, self.shapeNamePrefix + shapeName)
                )

        matcher.delete()
        dcc.xsi.DeleteObj(loader)
        dcc.xsi.DeleteObj(rester)
        self.deleteShapeCombiner()
        if preAtc is None:
            if postAtc is not None:
                # Clear the alembic time control
                dcc.xsi.DeleteObj(postAtc)

        # Force a rebuild of the Icetree
        self.recreateShapeNode()

        if pBar is not None:
            pBar.setValue(len(shapes))

    def _matchDelta(self, loader, rester):
        """

        Parameters
        ----------
        loader :

        rester :


        Returns
        -------

        """
        xmlString = buildLoaderXML(loader, rester)
        fHandle, compoundPath = tempfile.mkstemp(".xsicompound", text=True)
        f = os.fdopen(fHandle, "w")
        f.write(xmlString)
        f.close()
        tree = dcc.ice.ICETree(
            None,
            self.mesh,
            "SimplexDeltaMatch",
            dcc.constants.siConstructionModePrimaryShape,
        )
        compound = dcc.ice.ICECompoundNode(
            dcc.xsi.AddICECompoundNode(compoundPath, tree._nativePointer)
        )
        tree.connect(compound.Value)
        os.remove(compoundPath)
        return tree

    def getShapeVertices(self, shape):
        """

        Parameters
        ----------
        shape :


        Returns
        -------

        """
        dcc.xsi.DeactivateAbove("%s.modelingmarker" % self.mesh.ActivePrimitive, True)
        restVerts = self.mesh.ActivePrimitive.Geometry.Points.PositionArray
        restVerts = np.array(list(zip(*restVerts)))
        shapeDeltas = np.array(shape.thing[0].Elements.Array).T
        dcc.xsi.DeactivateAbove("%s.modelingmarker" % self.mesh.ActivePrimitive, "")
        return restVerts + shapeDeltas

    def getAllShapeVertices(self, shapes, pBar=None):
        """

        Parameters
        ----------
        shapes :

        pBar :
             (Default value = None)

        Returns
        -------

        """
        for shape in shapes:
            shape.verts = self.getShapeVertices(shape)

    def pushAllShapeVertices(self, shapes, pBar=None):
        """

        Parameters
        ----------
        shapes :

        pBar :
             (Default value = None)

        Returns
        -------

        """
        # take all the verts stored on the shapes
        # and push them back to the DCC
        for shape in shapes:
            self.pushShapeVertices(shape)

    def pushShapeVertices(self, shape):
        """

        Parameters
        ----------
        shape :


        Returns
        -------

        """
        # Push the vertices for a specific shape back to the DCC
        pass

    def _getMeshVertices(self, mesh, world=False):
        """

        Parameters
        ----------
        mesh :

        world :
             (Default value = False)

        Returns
        -------

        """
        # We're ignoring world in XSI because we don't use it for that
        vts = mesh.ActivePrimitive.Geometry.Points.PositionArray
        vts = list(zip(*vts))
        return vts

    def _exportAbcVertices(self, mesh, shape, world=False):
        """

        Parameters
        ----------
        mesh :

        shape :

        world :
             (Default value = False)

        Returns
        -------

        """
        vts = np.array(self._getMeshVertices(mesh, world=world))
        shapeVts = np.array(shape.thing[0].Elements.Array)
        outVerts = vts + shapeVts.T

        vertices = V3fArray(len(vts))
        setter = V3f(0, 0, 0)
        for i in range(len(outVerts)):
            setter.setValue(outVerts[i, 0], outVerts[i, 1], outVerts[i, 2])
            vertices[i] = setter
        return vertices

    def _exportAbcFaces(self, mesh):
        """

        Parameters
        ----------
        mesh :


        Returns
        -------

        """
        geo = mesh.ActivePrimitive.Geometry
        vertArray, faceArray = geo.Get2()

        texProp = self._getTextureProp(mesh, self.texName)
        uvSample = None
        if texProp is not None:
            uvs = texProp.Elements.Array
            uvs = list(zip(*uvs))
            uvD = {uv: i for i, uv in enumerate(set(uvs))}
            uvIdxs = [uvD[uv] for uv in uvs]
            uvs = [None] * len(uvD)
            for uv, idx in six.iteritems(uvD):
                uvs[idx] = uv
            uvSample = mkUvSample(uvs, uvIdxs)

        ptr = 0
        faces = []
        faceCounts = []
        while ptr < len(faceArray):
            count = faceArray[ptr]
            faceCounts.append(count)
            ptr += 1
            indices = reversed(faceArray[ptr : ptr + count])
            ptr += count
            faces.extend(indices)

        abcFaceIndices = IntArray(len(faces))
        for i in range(len(faces)):
            abcFaceIndices[i] = faces[i]

        abcFaceCounts = IntArray(len(faceCounts))
        for i in range(len(faceCounts)):
            abcFaceCounts[i] = faceCounts[i]

        return abcFaceIndices, abcFaceCounts, uvSample

    @classmethod
    def getMeshTopology(cls, mesh, uvName=None):
        """Get the topology of a mesh

        Parameters
        ----------
        mesh : object
            The DCC Mesh to read
        uvName : str, optional
            The name of the uv set to read

        Returns
        -------
        np.array :
            The vertex array
        np.array :
            The "faces" array
        np.array :
            The "counts" array
        np.array :
            The uv positions
        np.array :
            The "uvFaces" array
        """
        geo = mesh.ActivePrimitive.Geometry
        vertArray, faceArray = geo.Get2()

        verts = list(zip(*vertArray))
        texProp = cls._getTextureProp(mesh, uvName)
        uvs, uvIdxs = None, None
        if texProp is not None:
            uvs = texProp.Elements.Array
            uvs = list(zip(*uvs))
            uvD = {uv: i for i, uv in enumerate(set(uvs))}
            uvIdxs = [uvD[uv] for uv in uvs]
            uvs = [None] * len(uvD)
            for uv, idx in six.iteritems(uvD):
                uvs[idx] = uv

        ptr = 0
        faces = []
        faceCounts = []
        while ptr < len(faceArray):
            count = faceArray[ptr]
            faceCounts.append(count)
            ptr += 1
            indices = reversed(faceArray[ptr : ptr + count])
            ptr += count
            faces.extend(indices)

        return verts, faces, faceCounts, uvs, uvIdxs

    def loadMeshTopology(self):
        """ """
        self._faces, self._counts, self._uvs = self._exportAbcFaces(self.mesh)

    def exportAbc(
        self, dccMesh, abcMesh, js, world=False, ensureCorrect=False, pBar=None
    ):
        """ """
        # dccMesh doesn't work in XSI, so just ignore it
        # export the data to alembic
        shapeDict = {i.name: i for i in self.simplex.shapes}
        if js["encodingVersion"] > 1:
            shapeNames = [i["name"] for i in js["shapes"]]
        else:
            shapeNames = js["shapes"]
        shapes = [shapeDict[i] for i in shapeNames]

        faces, counts, uvSample = self._exportAbcFaces(dccMesh)
        schema = abcMesh.getSchema()

        if pBar is not None:
            pBar.show()
            pBar.setMaximum(len(shapes))

        # deactivate evaluation above modeling to insure no deformations are present
        dcc.xsi.DeactivateAbove("%s.modelingmarker" % dccMesh.ActivePrimitive, True)

        for i, shape in enumerate(shapes):
            if pBar is not None:
                pBar.setLabelText("Exporting:\n{0}".format(shape.name))
                pBar.setValue(i)
                QApplication.processEvents()
                if pBar.wasCanceled():
                    return
            verts = self._exportAbcVertices(dccMesh, shape, world)
            if uvSample is None:
                abcSample = OPolyMeshSchemaSample(verts, faces, counts)
            else:
                # I Can't just do iUVs=None. Alembic uses something different for its defaults
                abcSample = OPolyMeshSchemaSample(verts, faces, counts, iUVs=uvSample)
            schema.set(abcSample)

        dcc.xsi.DeactivateAbove("%s.modelingmarker" % dccMesh.ActivePrimitive, "")

    # Revision tracking
    def getRevision(self):
        """ """
        try:
            return self.op.inputPorts["Revision"].parameters["Revision"].value
        except AttributeError:
            return None  # object does not exist

    def incrementRevision(self):
        """ """
        value = self.getRevision()
        if value is None:
            return

        dcc.xsi.SetValue("%s.Revision" % self.op.fullName, value + 1)
        d = self.simplex.buildDefinition()
        jsString = json.dumps(d)
        self.setSimplexString(self.op, jsString)
        return value + 1

    def setRevision(self, val):
        """

        Parameters
        ----------
        val :


        Returns
        -------

        """
        dcc.xsi.SetValue("%s.Revision" % self.op.fullName, val)

    # System level
    @undoable
    def renameSystem(self, name):
        """

        Parameters
        ----------
        name :


        Returns
        -------

        """
        self.name = name
        self.inProp.Name = "%s_inProperty" % name
        self.shapeTree._nativePointer.Name = "%s_IceTree" % name
        self.shapeCluster.Name = "%s_Shapes" % name

        # rename data in the simplex vector setter and getter
        vectorSetter = list(self.op.outputPortList[0].connectedNodes.values())[0]
        vectorGetter = list(self.shapeNode.inputPortList[0].connectedNodes.values())[0]
        # pointSetter = self.shapeNode.outputPortList[0].connectedNodes.values()[0]
        for node in [vectorSetter, vectorGetter]:
            dcc.xsi.SetValue(
                "%s.Reference" % node.fullName, "self._%s_SimplexVector" % name
            )

        # rename the shape nodes in the IceTree by recreating the shape node
        self.recreateShapeNode()

    def recreateShapeNode(self):
        """ """
        # vectorSetter = self.op.outputPortList[0].connectedNodes.values()[0]
        vectorGetter = list(self.shapeNode.inputPortList[0].connectedNodes.values())[0]
        pointSetter = list(self.shapeNode.outputPortList[0].connectedNodes.values())[0]

        self.shapeNode.delete()
        shapeCompound = self.rebuildShapeNode(self.simplex)
        pointSetter.Value.connect(shapeCompound.Result)
        vectorGetter.value.connect(shapeCompound.inputPorts["In"])

        self.shapeNode = shapeCompound
        self._loadShapeIceNodes(self.simplex)

        self.rebuildSliderNode()

    def rebuildSliderNode(self):
        """ """
        if len(self.inProp.Parameters) == 0:
            print("No input sliders")
            return

        if self.sliderNode:
            self.sliderNode.delete()

        sliderNames = [slider.name for slider in self.simplex.sliders]
        # Possibly None
        xmlString = buildSliderIceXML(sliderNames, self.name)

        fHandle, compoundPath = tempfile.mkstemp(".xsicompound", text=True)
        f = os.fdopen(fHandle, "w")
        f.write(xmlString)
        f.close()
        compound = dcc.ice.ICECompoundNode(
            dcc.xsi.AddICECompoundNode(compoundPath, self.shapeTree._nativePointer)
        )
        self.sliderNode = compound
        os.remove(compoundPath)

        self.op.inputPorts["Sliders"].connect(compound.outputPorts["Array"])

        # set the simplex string on simplex node
        self.setSimplexString(self.op, self.simplex.dump())

    def resetShapeIndexes(self):
        """ """
        # set the simplex string on simplex node
        self.setSimplexString(self.op, self.simplex.dump())

        # check the shape node for proper indexes
        for i, shape in enumerate(self.simplex.shapes):
            if shape.thing[2] is None:
                continue
            port = shape.thing[2].InputPorts("index")
            if port:
                if port.Value != i:
                    dcc.xsi.SetValue("%s.index" % shape.thing[2], i)
            else:
                print("SHAPE HAS STRANGENESS", shape.name)
                raise RuntimeError("BAD")

    # Shapes
    @undoable
    def createShape(
        self,
        shape,
        live=False,
        dataReferences=None,
        deleteCombiner=True,
        rebuild=False,
        freeze=True,
    ):
        """

        Parameters
        ----------
        shape :

        live :
             (Default value = False)
        dataReferences :
             (Default value = None)
        deleteCombiner :
             (Default value = True)
        rebuild :
             (Default value = False)
        freeze :
             (Default value = True)

        Returns
        -------

        """

        ret, nn = self.createRawShape(
            shape.name,
            dataReferences=dataReferences,
            deleteCombiner=False,
            rebuild=rebuild,
            freeze=freeze,
        )

        if deleteCombiner:
            self.deleteShapeCombiner()

        if live:
            self.extractShape(shape, live=True, offset=10.0)

        shape.name = nn
        return ret

    def createRawShape(
        self,
        shapeName,
        dataReferences=None,
        elementArray=None,
        deleteCombiner=True,
        rebuild=True,
        freeze=True,
    ):
        """

        Parameters
        ----------
        shapeName :

        dataReferences :
             (Default value = None)
        elementArray :
             (Default value = None)
        deleteCombiner :
             (Default value = True)
        rebuild :
             (Default value = True)
        freeze :
             (Default value = True)

        Returns
        -------

        """

        newShape = self.shapeCluster.Properties(shapeName)
        if newShape is None:
            newShape = dcc.xsi.StoreShapeKey(
                self.shapeCluster,
                shapeName,
                dcc.constants.siShapeObjectReferenceMode,
                1,
                0,
                0,
                dcc.constants.siShapeContentPrimaryShape,
                False,
            )
            # determine whether to do a inbetween shape or not based on the progression
            if elementArray:
                newShape.Elements.Array = elementArray
            else:
                dcc.shape.resetShapeKey(newShape)
            if freeze:
                dcc.xsi.FreezeObj(newShape)

        # create the node structure in the ICETree if not there already
        shapeNodes = self.getShapeIceNodes(newShape, dataReferences)

        if rebuild:
            self.resetShapeIndexes()

        if deleteCombiner:
            self.deleteShapeCombiner()

        return [newShape] + shapeNodes, newShape.Name

    def getInbetweenArray(self, shapes):
        """

        Parameters
        ----------
        shapes :


        Returns
        -------

        """
        blendArray = [0] * 3 * self.mesh.ActivePrimitive.Geometry.Points.Count
        shapeArray = self.getSimplexEvaluation()
        if not shapeArray:
            return None
        shapeList = [shape.name for shape in self.simplex.shapes]

        for shape in shapes:
            if not shape.thing:
                continue

            if len(shapeArray[0]) == 1:
                continue
            idx = shapeList.index(shape.name)
            shapeBlend = shapeArray[0][idx]
            shapeTuple = shape.thing[0].Elements.Array

            for i in range(len(shapeTuple[0])):
                blendArray[i * 3 + 0] += shapeTuple[0][i] * shapeBlend
                blendArray[i * 3 + 1] += shapeTuple[1][i] * shapeBlend
                blendArray[i * 3 + 2] += shapeTuple[2][i] * shapeBlend

        return blendArray

    @undoable
    def getShapeIceNodes(self, shapeKey, dataReferences):
        """build/return the ICE nodes related to the given shapeKey

        Parameters
        ----------
        shapeKey :

        dataReferences :


        Returns
        -------

        """
        simpNode = self.shapeNode
        if not dataReferences:
            dataReferences = DCC.getDataReferences(simpNode)
        ports = simpNode.exposedPorts
        if ports[0][0].isOutput():
            addNode = ports[0][0].parent
            passNode = ports[1][0].parent
        else:
            addNode = ports[1][0].parent
            passNode = ports[0][0].parent

        shapeRef = "%s.positions" % shapeKey.FullName.replace(
            "%s.polymsh" % self.mesh.FullName, "self"
        )
        if shapeRef in list(dataReferences.keys()):
            shapeNode = dataReferences[shapeRef]
        else:
            shapeNode = simpNode.addGetDataNode(shapeRef)

        multNode = shapeNode.outputPorts["value"].connectedNodes
        if "Multiply by Scalar" in list(multNode.keys()):
            multNode = multNode["Multiply by Scalar"]
        else:
            multNode = simpNode.addNode("MultiplyByScalar")

        if multNode.name not in list(
            shapeNode.outputPorts["value"].connectedNodes.keys()
        ):
            shapeNode.outputPorts["value"].connect(multNode.inputPorts["value"])

        if addNode not in list(multNode.outputPorts["result"].connectedNodes.values()):
            addPort = DCC.firstAvailablePort(addNode)
            multNode.outputPorts["result"].connect(addPort)

        indexNode = multNode.inputPorts["factor"].connectedNodes
        if "Select in Array" in list(indexNode.keys()):
            indexNode = indexNode["Select in Array"]
        else:
            indexNode = simpNode.addNode("SelectInArray")
            indexNode.value.connect(multNode.inputPorts["factor"])
            indexNode.inputPorts["array"].connect(passNode.outputPorts["out"])

        return [
            shapeNode._nativePointer,
            indexNode._nativePointer,
            multNode._nativePointer,
        ]

    def checkShapeValidity(self, shape, dataReferences=None):
        """

        Parameters
        ----------
        shape :

        dataReferences :
             (Default value = None)

        Returns
        -------

        """
        s = self.shapeCluster.Properties(shape.name)
        if not s:
            return False

        simpNode = self.shapeNode
        if not dataReferences:
            dataReferences = DCC.getDataReferences(simpNode)
        shapeRef = "%s.positions" % s.FullName.replace(
            "%s.polymsh" % self.mesh.FullName, "self"
        )
        if shapeRef not in list(dataReferences.keys()):
            return False
        return True

    def rebuildShapeNode(self, simp, shapeNames=None):
        """

        Parameters
        ----------
        simp :

        shapeNames :
             (Default value = None)

        Returns
        -------

        """
        if shapeNames is None:
            shapeNames = [shape.name for shape in simp.shapes]
        xmlString = buildIceXML(
            shapeNames, self.name, self.shapeCluster.Name, self.shapeNamePrefix
        )

        fHandle, compoundPath = tempfile.mkstemp(".xsicompound", text=True)
        f = os.fdopen(fHandle, "w")
        f.write(xmlString)
        f.close()

        node = dcc.xsi.AddICECompoundNode(compoundPath, self.shapeTree._nativePointer)
        shapeCompound = dcc.ice.ICECompoundNode(node)
        os.remove(compoundPath)

        return shapeCompound

    @staticmethod
    def firstAvailablePort(node):
        """

        Parameters
        ----------
        node :


        Returns
        -------

        """
        openPorts = [port for port in node.inputPortList if not port.isConnected()]
        if not openPorts:
            return node.addPortAtEnd(node.portAtEnd().name)
        else:
            return openPorts[0]

    @undoable
    def extractShape(self, shape, live=True, offset=10.0):
        """make a mesh representing a shape. Can be live or not

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
        shapeKey = shape.thing[0]
        print("Extracting %s" % shapeKey.Name)
        shapeGeo = self.extractShapeAsGeo(shapeKey)
        shapeGeo.posx.Value = offset
        if live:
            self.connectShape(shape, shapeGeo, live, delete=False)
        return shapeGeo

    @undoable
    def connectShape(
        self, shape, mesh=None, live=False, delete=False, deleteCombiner=True
    ):
        """Force a shape to match a mesh
            The "connect shape" button is:
                mesh=None, delete=True
            The "match shape" button is:
                mesh=someMesh, delete=False
            There is a possibility of a "make live" button:
                live=True, delete=False

        Parameters
        ----------
        shape :

        mesh :
             (Default value = None)
        live :
             (Default value = False)
        delete :
             (Default value = False)
        deleteCombiner :
             (Default value = True)

        Returns
        -------

        """
        # print("Connected {0}".format(shape.name))

        if not mesh:
            mesh = DCC.findExtractedShape(shape.name)
        if not mesh:
            print("No extracted shape found to connect for %s" % shape.name)
            return

        # print("Connected {0}".format(shape.name))

        tempShape = dcc.xsi.SelectShapeKey(
            self.shapeCluster,
            mesh,
            dcc.constants.siShapeObjectReferenceMode,
            live,
            False,
        )[0]
        dcc.xsi.DeleteObj(shape.thing[0])
        tempShape.Name = shape.name
        shape.thing[0] = tempShape

        # print("Connected {0}".format(tempShape.Name))

        if not live:
            dcc.xsi.FreezeObj(tempShape)
        if delete:
            dcc.xsi.DeleteObj(mesh)
        if deleteCombiner:
            self.deleteShapeCombiner()

        # print("Connected {0}".format(tempShape.Name))

    @staticmethod
    def findExtractedShape(shape):
        """

        Parameters
        ----------
        shape :


        Returns
        -------

        """
        testName = "%s_Extract" % shape
        testObj = dcc.xsi.ActiveSceneRoot.FindChild(testName)

        return testObj

    @undoable
    def extractPosedShape(self, shape):
        """

        Parameters
        ----------
        shape :


        Returns
        -------

        """
        pass

    @undoable
    def zeroShape(self, shape):
        """Set the shape to be completely zeroed

        Parameters
        ----------
        shape :


        Returns
        -------

        """
        shapeKey = shape.thing[0]
        dcc.shape.resetShapeKey(shapeKey)
        dcc.xsi.FreezeObj(shapeKey)

        print("Shape %s has been reset" % shape.name)

    @undoable
    def deleteShape(self, toDelShape):
        """Remove a shape from the system

        Parameters
        ----------
        toDelShape :


        Returns
        -------

        """
        dcc.xsi.DeleteObj(toDelShape.thing)

        # rebuild the operator
        self.resetShapeIndexes()

    @undoable
    def renameShape(self, shape, name):
        """Change the name of the shape

        Parameters
        ----------
        shape :

        name :


        Returns
        -------

        """
        shape.thing[0].Name = name
        name = shape.thing[0].Name

        shapeNodeList = shape.thing[1].Reference.Value.split(".")
        shapeNodeList[-2] = name
        shape.thing[1].Reference.Value = ".".join(shapeNodeList)

        self.resetShapeIndexes()

    @undoable
    def convertShapeToCorrective(self, shape):
        """

        Parameters
        ----------
        shape :


        Returns
        -------

        """
        pass

    def deleteShapeCombiner(self):
        """ """
        clsCombiner = dcc.operator.getOperatorFromStack(
            self.mesh, "clustershapecombiner"
        )
        if clsCombiner:
            dcc.xsi.DeleteObj(clsCombiner)

    def freezeAllShapes(self):
        """ """
        toFreeze = [
            shape.thing[0]
            for shape in self.simplex.shapes
            if len(shape.thing[0].NestedObjects) > 2
        ]
        dcc.xsi.FreezeObj(toFreeze)

    # Falloffs
    def createFalloff(self, falloff):
        """

        Parameters
        ----------
        falloff :


        Returns
        -------

        """
        pass  # for eventual live splits

    def duplicateFalloff(self, falloff, newFalloff, newName):
        """

        Parameters
        ----------
        falloff :

        newFalloff :

        newName :


        Returns
        -------

        """
        pass  # for eventual live splits

    def deleteFalloff(self, falloff):
        """

        Parameters
        ----------
        falloff :


        Returns
        -------

        """
        pass  # for eventual live splits

    def setFalloffData(
        self, falloff, splitType, axis, minVal, minHandle, maxHandle, maxVal, mapName
    ):
        """

        Parameters
        ----------
        falloff :

        splitType :

        axis :

        minVal :

        minHandle :

        maxHandle :

        maxVal :

        mapName :


        Returns
        -------

        """
        pass  # for eventual live splits

    def getFalloffThing(self, falloff):
        """

        Parameters
        ----------
        falloff :


        Returns
        -------

        """
        return falloff.name

    # Sliders
    @undoable
    def createSlider(self, slider, rebuildOp=True):
        """Create a new slider with a name

        Parameters
        ----------
        slider :

        rebuildOp :
             (Default value = True)

        Returns
        -------

        """
        name = slider.name
        param = self.createSliderParam(slider, name)

        # connect solver
        if rebuildOp:
            self.rebuildSliderNode()
            self.resetShapeIndexes()
            self.deleteShapeCombiner()
        return param

    @undoable
    def renameSlider(self, slider, name):
        """Set the name of a slider

        Parameters
        ----------
        slider :

        name :


        Returns
        -------

        """
        param = self.createSliderParam(slider, name)
        if slider.thing.IsAnimated(dcc.constants.siAnySource):
            dcc.xsi.CopyAnimation(slider.thing, True, True, False, True, True)
            dcc.xsi.PasteAnimation(param, 1)

        dcc.xsi.RemoveCustomParam(slider.thing)
        slider.thing = param

        self.rebuildSliderNode()
        self.resetShapeIndexes()

    @undoable
    def setSliderRange(self, slider):
        """

        Parameters
        ----------
        slider :


        Returns
        -------

        """
        vals = [v.value for v in slider.prog.pairs]
        dcc.xsi.EditParameterDefinition(
            slider.thing,
            "",
            "",
            -2.0,
            2.0,
            min(vals) * self.sliderMul,
            max(vals) * self.sliderMul,
        )

    @undoable
    def renameCombo(self, combo, name):
        """

        Parameters
        ----------
        combo :

        name :


        Returns
        -------

        """
        pass

    @undoable
    def deleteSlider(self, toDelSlider):
        """Remove a slider

        Parameters
        ----------
        toDelSlider :


        Returns
        -------

        """
        dcc.xsi.RemoveCustomParam(toDelSlider.thing)
        self.rebuildSliderNode()
        self.resetShapeIndexes()

    def createSliderParam(self, slider, name):
        """

        Parameters
        ----------
        slider :

        name :


        Returns
        -------

        """
        vals = [v.value for v in slider.prog.pairs]
        param = self.inProp.AddParameter3(name, dcc.constants.siFloat, 0, -2.0, 2.0)
        dcc.xsi.EditParameterDefinition(
            param,
            "",
            "",
            -2.0,
            2.0,
            min(vals) * self.sliderMul,
            max(vals) * self.sliderMul,
        )
        return param

    @undoable
    def addProgFalloff(self, prog, falloff):
        """

        Parameters
        ----------
        prog :

        falloff :


        Returns
        -------

        """
        pass  # for eventual live splits

    @undoable
    def removeProgFalloff(self, prog, falloff):
        """

        Parameters
        ----------
        prog :

        falloff :


        Returns
        -------

        """
        pass  # for eventual live splits

    @undoable
    def setSlidersWeights(self, sliders, weights):
        """Set the weight of a slider. This does not change the definition

        Parameters
        ----------
        sliders :

        weights :


        Returns
        -------

        """
        for slider, weight in zip(sliders, weights):
            slider.thing.Value = weight

    @undoable
    def setSliderWeight(self, slider, weight):
        """

        Parameters
        ----------
        slider :

        weight :


        Returns
        -------

        """
        slider.thing.Value = weight

    @undoable
    def updateSlidersRange(self, sliders):
        """

        Parameters
        ----------
        sliders :


        Returns
        -------

        """
        for slider in sliders:
            vals = [v.value for v in slider.prog.pairs]
            dcc.xsi.EditParameterDefinition(
                slider.thing,
                "",
                "",
                -2.0,
                2.0,
                min(vals) * self.sliderMul,
                max(vals) * self.sliderMul,
            )

    # Combos
    def _createDelta(self, combo, target, tVal):
        """Part of the combo extraction process.
        Combo shapes are fixit shapes added on top of any sliders.
        This means that the actual combo-shape by itself will not look good by itself,
        and that's bad for artist interaction.
        So we must create a setup to take the final sculpted shape, and subtract
        the any direct slider deformations to get the actual "combo shape" as a delta
        It is this delta shape that is then plugged into the system

        Parameters
        ----------
        combo :

        target :

        tVal :


        Returns
        -------

        """

        # check if delta object already exists
        deltaName = "%s_Delta" % combo.name
        deltaObj = dcc.xsi.ActiveSceneRoot.FindChild(deltaName)
        if deltaObj:
            return deltaObj

        # create and extract a temporary shape to use as a reference
        # of everything but the actual combo shape
        tempShape = dcc.xsi.StoreShapeKey(
            self.shapeCluster,
            "temp",
            dcc.constants.siShapeObjectReferenceMode,
            1,
            0,
            0,
            dcc.constants.siShapeContentPrimaryShape,
            False,
        )
        affected = self.getComboAffected(combo)

        with disconnected(affected[0], self.inProp):
            # set sliders for the combo
            for pair in combo.pairs:
                pair.slider.thing.Value = pair.value * tVal

            tempShape.Elements.Array = self.getInbetweenArray(affected[1])

        # build delta object
        deltaObj = self.extractShapeAsGeo(tempShape)
        deltaObj.Name = deltaName
        deltaObj.Properties("visibility").Parameters("viewvis").Value = False
        deltaObj.posx.Value = 10.0
        deltaObj.posz.Value = -10.0

        # apply shape of target to delta object
        dcc.xsi.SelectShapeKey(
            deltaObj, target, dcc.constants.siShapeObjectReferenceMode, True, True
        )[0]

        # get undeformed shape to apply to get delta, and apply as a shape to delta
        tempBase = self.extractShapeAsGeo(self.simplex.restShape.thing[0])

        dcc.xsi.SelectShapeKey(
            deltaObj, tempBase, dcc.constants.siShapeObjectReferenceMode, False, True
        )[0]

        for param in deltaObj.Properties("ShapeWeights").Parameters:
            dcc.xsi.RemoveAnimation(param)
            param.Value = 1

        dcc.xsi.DeleteObj(tempBase)
        dcc.xsi.DeleteObj(tempShape)

        return deltaObj

    def getComboAffected(self, combo):
        """

        Parameters
        ----------
        combo :


        Returns
        -------
        type


        """
        # Get all related sliders to the combo
        comboSliders = [i.slider for i in combo.pairs]
        comboSlidersSet = set(comboSliders)

        # get list of combo shapes that have an impact on the current combo
        affected = []
        for slider in comboSliders:
            for pair in slider.prog.pairs:
                if pair.shape not in affected:
                    affected.append(pair.shape)
        for c in self.simplex.combos:
            if c == combo:
                continue
            cSliders = set(i.slider for i in c.pairs)
            if cSliders <= comboSlidersSet:
                for pair in c.prog.pairs:
                    affected.append(pair.shape)

        return [comboSliders, affected]

    @undoable
    def extractTraversalShape(self, trav, shape, live=True, offset=10.0):
        """

        Parameters
        ----------
        trav :

        shape :

        live :
             (Default value = True)
        offset :
             (Default value = 10.0)

        Returns
        -------

        """
        pass

    @undoable
    def connectTraversalShape(self, trav, shape, mesh=None, live=True, delete=False):
        """

        Parameters
        ----------
        trav :

        shape :

        mesh :
             (Default value = None)
        live :
             (Default value = True)
        delete :
             (Default value = False)

        Returns
        -------

        """
        pass

    @undoable
    def extractComboShape(self, combo, shape, live=True, offset=10.0):
        """Extract a shape from a combo progression

        Parameters
        ----------
        combo :

        shape :

        live :
             (Default value = True)
        offset :
             (Default value = 10.0)

        Returns
        -------

        """

        # extract the rest shape to use as a base
        tempShape = dcc.xsi.StoreShapeKey(
            self.shapeCluster,
            "temp",
            dcc.constants.siShapeObjectReferenceMode,
            1,
            0,
            0,
            dcc.constants.siShapeContentPrimaryShape,
            False,
        )

        affected = self.getComboAffected(combo)

        with disconnected(affected[0], self.inProp):
            # set the relevant sliders for the combo
            for pair in combo.pairs:
                pair.slider.thing.Value = pair.value

            # also grab the shape that we are affecting
            affected[1].append(shape)

            # get the blendarray
            tempShape.Elements.Array = self.getInbetweenArray(affected[1])

        # extracted = dcc.shape.extractShapeKeyAsGeo(tempShape)
        extracted = self.extractShapeAsGeo(tempShape)
        extracted.Name = "%s_Extract" % shape.name
        extracted.posx.Value = offset

        dcc.xsi.DeleteObj(tempShape)

        if live:
            self.connectComboShape(combo, shape, extracted, live=live, delete=False)

        return extracted

    @undoable
    def connectComboShape(self, combo, shape, mesh=None, live=False, delete=False):
        """Connect a shape into a combo progression

        Parameters
        ----------
        combo :

        shape :

        mesh :
             (Default value = None)
        live :
             (Default value = False)
        delete :
             (Default value = False)

        Returns
        -------

        """
        if not mesh:
            mesh = DCC.findExtractedShape(shape.name)
        if not mesh:
            print("No extracted shape found to connect for %s" % shape.name)
            return
        shapeIdx = combo.prog.getShapeIndex(shape)
        tVal = combo.prog.pairs[shapeIdx].value
        delta = self._createDelta(combo, mesh, tVal)
        self.connectShape(shape, delta, live, delete)
        if delete:
            dcc.xsi.DeleteObj(mesh)

    @undoable
    def extractShapeAsGeo(self, shapeKey):
        """

        Parameters
        ----------
        shapeKey :


        Returns
        -------

        """
        # create new object with same shape as mesh using dirty tricks to set geometry directly
        temp = dcc.xsi.ActiveSceneRoot.AddGeometry(
            "Cube", "MeshSurface", "%s_Extract" % shapeKey.Name
        )
        dcc.xsi.FreezeObj(temp)
        dcc.xsi.DeactivateAbove("%s.modelingmarker" % self.mesh.ActivePrimitive, True)
        vertArray, faceArray = self.mesh.ActivePrimitive.Geometry.Get2()
        temp.ActivePrimitive.Geometry.set(vertArray, faceArray)
        dcc.xsi.DeactivateAbove("%s.modelingmarker" % self.mesh.ActivePrimitive, "")

        # copy over the shape
        tempShape = dcc.xsi.StoreShapeKey(
            temp, "Shape", dcc.constants.siShapeObjectReferenceMode
        )
        tempShape.Elements.Array = shapeKey.Elements.Array
        dcc.xsi.ApplyShapeKey(tempShape, None, None, 100, None, None, None, 2)
        dcc.xsi.FreezeObj(temp)

        return temp

    @staticmethod
    def setDisabled(op):
        """

        Parameters
        ----------
        op :


        Returns
        -------

        """
        nc = op.rootNodeContainer
        pairs = []
        for pName, port in six.iteritems(nc.inputPorts):
            outs = list(port.connectedPorts.values())
            if outs:
                pairs.append((port, outs[0]))
                port.disconnect()
        return pairs

    @staticmethod
    def reEnable(helpers):
        """

        Parameters
        ----------
        helpers :


        Returns
        -------

        """
        for inPort, outPort in helpers:
            inPort.connect(outPort)

    # Data Access
    @staticmethod
    def getSimplexOperatorsOnObject(thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------
        type


        """
        out = []
        for tree in thing.ActivePrimitive.ICETrees:
            simplexNodes = [
                dcc.ice.ICENode(node)
                for node in tree.Nodes
                if node.Type == "SimplexNode"
            ]
            out.extend(simplexNodes)
        return out

    @staticmethod
    def getSimplexOperatorsOnObjectByName(thing, name):
        """

        Parameters
        ----------
        thing :

        name :


        Returns
        -------
        type


        """
        ops = DCC.getSimplexOperatorsOnObject(thing)
        ops = DCC.filterSimplexByName(ops, name)

        if not ops:
            return None
        else:
            return ops[0]

    @staticmethod
    def getSimplexString(op):
        """

        Parameters
        ----------
        op :


        Returns
        -------
        type


        """
        return op.inputPorts["Definition"].parameters["Definition_string"].value

    @staticmethod
    def getSimplexStringOnThing(thing, systemName):
        """

        Parameters
        ----------
        thing :

        systemName :


        Returns
        -------
        type


        """
        op = DCC.getSimplexOperatorsOnObjectByName(thing, systemName)
        return DCC.getSimplexString(op)

    @staticmethod
    def filterSimplexByObject(ops, thing):
        """

        Parameters
        ----------
        ops :

        thing :


        Returns
        -------

        """
        filtered = []
        if not ops:
            return filtered
        for i in ops:
            if not i.Parent3DObject:
                # dcc.xsi.DeleteObj(i)
                continue
            if i.Parent3DObject.IsEqualTo(thing):
                filtered.append(i)
        return filtered

    @staticmethod
    def filterSimplexByName(ops, name):
        """

        Parameters
        ----------
        ops :

        name :


        Returns
        -------

        """
        filtered = []
        if not ops:
            return filtered
        for i in ops:
            js = json.loads(DCC.getSimplexString(i))
            if js["systemName"] == name:
                filtered.append(i)
        return filtered

    @staticmethod
    def setSimplexString(op, val):
        """set the definition string from a simplex operator

        Parameters
        ----------
        op :

        val :


        Returns
        -------

        """
        if op:
            dcc.xsi.SetValue("%s.Definition_string" % op.fullName, val)
            return val
        else:
            return val

    @staticmethod
    def selectObject(thing):
        """Select an object in the DCC

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        dcc.xsi.SelectObj(thing)

    def selectCtrl(self):
        """Select the system's control object"""
        self.selectObject(self.inProp)

    @staticmethod
    def getObjectByName(name):
        """

        Parameters
        ----------
        name :


        Returns
        -------
        type


        """
        return dcc.xsi.Dictionary.GetObject(name, False)

    @staticmethod
    def getObjectName(thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------
        type


        """
        return thing.Name

    @staticmethod
    def getSelectedObjects():
        """ """
        # For maya, only return transform nodes
        return list(dcc.xsi.Selection)

    @staticmethod
    def getDataReferences(node):
        """

        Parameters
        ----------
        node :


        Returns
        -------

        """
        dataDict = {}
        for n in node.nodes:
            if n.type != "SceneReferenceNode":
                continue
            dataDict[n.Reference.Value] = n
        return dataDict

    @staticmethod
    def staticUndoOpen():
        """ """
        dcc.xsi.OpenUndo("SimplexUndo")

    @staticmethod
    def staticUndoClose():
        """ """
        dcc.xsi.CloseUndo()

    def undoOpen(self):
        """ """
        if self.undoDepth == 0:
            self.staticUndoOpen()
        self.undoDepth += 1

    def undoClose(self):
        """ """
        self.undoDepth -= 1
        if self.undoDepth == 0:
            self.staticUndoClose()

    def getSimplexEvaluation(self):
        """ """
        geo = self.mesh.ActivePrimitive.Geometry
        evalArray = geo.GetICEAttributeFromName(
            "_%s_SimplexVector" % self.name
        ).DataArray2D
        return evalArray

    @classmethod
    def getPersistentFalloff(cls, thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        return thing.FullName

    @classmethod
    def loadPersistentFalloff(cls, thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        return cls.getObjectByName(thing)

    @classmethod
    def getPersistentShape(cls, thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        # return cls.getObjectName(thing)
        if thing is None:
            return None
        names = []
        for item in thing:
            app = None if item is None else item.FullName
            names.append(app)
        return names

    @classmethod
    def loadPersistentShape(cls, thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        if thing is None:
            return None
        items = []
        for name in thing:
            items.append(cls.getObjectByName(name))
        return items

    @classmethod
    def getPersistentSlider(cls, thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        return thing.FullName

    @classmethod
    def loadPersistentSlider(cls, thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        return cls.getObjectByName(thing)

    def getFreezeThing(self, combo):
        return []


class SliderDispatch(QtCore.QObject):
    """ """

    valueChanged = Signal()

    def __init__(self, node, parent=None):
        super(SliderDispatch, self).__init__(parent)

    def emitValueChanged(self, *args, **kwargs):
        """

        Parameters
        ----------
        *args :

        **kwargs :


        Returns
        -------

        """
        self.valueChanged.emit()


class Dispatch(QtCore.QObject):
    """ """

    beforeNew = Signal()
    afterNew = Signal()
    beforeOpen = Signal()
    afterOpen = Signal()
    undo = Signal()
    redo = Signal()

    def __init__(self, parent=None):
        super(Dispatch, self).__init__(parent)
        self.callbackIDs = []
        self.connectCallbacks()

    def connectCallbacks(self):
        """ """
        if self.callbackIDs:
            self.disconnectCallbacks()

        # self.callbackIDs.append(om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeNew, self.emitBeforeNew))
        # self.callbackIDs.append(om.MSceneMessage.addCallback(om.MSceneMessage.kAfterNew, self.emitAfterNew))
        # self.callbackIDs.append(om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeOpen, self.emitBeforeOpen))
        # self.callbackIDs.append(om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen, self.emitAfterOpen))
        # self.callbackIDs.append(om.MEventMessage.addEventCallback("Undo", self.emitUndo))
        # self.callbackIDs.append(om.MEventMessage.addEventCallback("Redo", self.emitRedo))

    def disconnectCallbacks(self):
        """ """
        for i in self.callbackIDs:
            # om.MMessage.removeCallback(i)
            pass

    def emitBeforeNew(self, *args, **kwargs):
        """

        Parameters
        ----------
        *args :

        **kwargs :


        Returns
        -------

        """
        self.beforeNew.emit()

    def emitAfterNew(self, *args, **kwargs):
        """

        Parameters
        ----------
        *args :

        **kwargs :


        Returns
        -------

        """
        self.afterNew.emit()

    def emitBeforeOpen(self, *args, **kwargs):
        """

        Parameters
        ----------
        *args :

        **kwargs :


        Returns
        -------

        """
        self.beforeOpen.emit()

    def emitAfterOpen(self, *args, **kwargs):
        """

        Parameters
        ----------
        *args :

        **kwargs :


        Returns
        -------

        """
        self.afterOpen.emit()

    def emitUndo(self, *args, **kwargs):
        """

        Parameters
        ----------
        *args :

        **kwargs :


        Returns
        -------

        """
        self.undo.emit()

    def emitRedo(self, *args, **kwargs):
        """

        Parameters
        ----------
        *args :

        **kwargs :


        Returns
        -------

        """
        self.redo.emit()

    def __del__(self):
        self.disconnectCallbacks()


DISPATCH = Dispatch()


def rootWindow():
    """Returns the currently active QT main window
        Only works for QT UI's like Maya

    Parameters
    ----------

    Returns
    -------

    """
    # for MFC apps there should be no root window
    window = None
    if QApplication.instance():
        inst = QApplication.instance()
        window = inst.activeWindow()
        # Ignore QSplashScreen's, they should never be considered the root window.
        if isinstance(window, QSplashScreen):
            return None
        # If the application does not have focus try to find A top level widget
        # that doesn't have a parent and is a QMainWindow or QDialog
        if window is None:
            windows = []
            dialogs = []
            for w in QApplication.instance().topLevelWidgets():
                if w.parent() is None:
                    if isinstance(w, QMainWindow):
                        windows.append(w)
                    elif isinstance(w, QDialog):
                        dialogs.append(w)
            if windows:
                window = windows[0]
            elif dialogs:
                window = dialogs[0]

        # grab the root window
        if window:
            while True:
                parent = window.parent()
                if not parent:
                    break
                if isinstance(parent, QSplashScreen):
                    break
                window = parent

    return window
