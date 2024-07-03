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
from __future__ import absolute_import

import json
import re
from contextlib import contextmanager
from ctypes import c_double, c_float
from functools import wraps

import maya.cmds as cmds
import maya.OpenMaya as om
import six
from alembic.AbcGeom import GeometryScope, OPolyMeshSchemaSample, OV2fGeomParamSample
from imath import IntArray, UnsignedIntArray, V2fArray, V3fArray
from six.moves import map, range, zip

from ..commands.alembicCommon import mkSampleVertexPoints
from ..Qt import QtCore
from ..Qt.QtCore import Signal
from ..Qt.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QMessageBox,
    QSplashScreen,
)

try:
    import numpy as np
except ImportError:
    np = None

try:
    import imathnumpy
except ImportError:
    imathnumpy = None


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
        inst = None
        if args and isinstance(args[0], DCC):
            inst = args[0]
        with undoContext(inst):
            return f(*args, **kwargs)

    return stacker


# temporarily disconnect inputs from a list of nodes and plugs
def doDisconnect(targets, testCnxType=("double", "float")):
    """

    Parameters
    ----------
    targets :

    testCnxType :
         (Default value = ("double")
    "float") :


    Returns
    -------

    """
    if not isinstance(targets, (list, tuple)):
        targets = [targets]
    targets = list(set(targets))
    cnxs = {}
    for target in targets:
        tcnx = {}
        cnxs[target] = tcnx

        cnx = cmds.listConnections(
            target, plugs=True, destination=False, source=True, connections=True
        )
        if cnx is None:
            cnx = []

        for i in range(0, len(cnx), 2):
            cnxType = cmds.getAttr(cnx[i], type=True)
            if cnxType not in testCnxType:
                continue
            tcnx[cnx[i + 1]] = cnx[i]
            cmds.disconnectAttr(cnx[i + 1], cnx[i])
    return cnxs


def doReconnect(cnxs):
    """

    Parameters
    ----------
    cnxs :


    Returns
    -------

    """
    for tdict in six.itervalues(cnxs):
        for s, d in six.iteritems(tdict):
            if not cmds.isConnected(s, d):
                cmds.connectAttr(s, d, force=True)


@contextmanager
def disconnected(targets, testCnxType=("double", "float")):
    """

    Parameters
    ----------
    targets :

    testCnxType :
         (Default value = ("double")
    "float") :


    Returns
    -------

    """
    cnxs = doDisconnect(targets, testCnxType=testCnxType)
    try:
        yield cnxs
    finally:
        doReconnect(cnxs)


class DCC(object):
    """ """

    program = "maya"

    def __init__(self, simplex, stack=None):
        if not cmds.pluginInfo("simplex_maya", query=True, loaded=True):
            cmds.loadPlugin("simplex_maya")
        self.undoDepth = 0
        self.name = None  # the name of the system
        self.mesh = None  # the mesh object with the system
        self.ctrl = None  # the object that has all the controllers on it
        self.shapeNode = None  # the deformer object
        self.op = None  # the simplex object
        self.simplex = simplex  # the abstract representation of the setup
        self._live = True
        self.sliderMul = self.simplex.sliderMul

    # def __deepcopy__(self, memo):
    # '''
    # I don't actually need to define this here because I know that
    # all of the maya "objects" store here are just strings
    # But if they *weren't* (like in XSI) I would need to skip
    # the maya objects when deepcopying, otherwise I might access
    # a deleted scene node and crash everything
    # And if we did skip things, I would also need to store a
    # persistent accessor to use in case we get back to here
    # through an undo
    # '''
    # pass

    def _checkAllShapeValidity(self, shapeNames):
        """Check shapes to see if they exist, and either gather the missing files, or
        Load the proper data onto the shapes

        Parameters
        ----------
        shapeNames :


        Returns
        -------

        """
        # Keep the set ordered, but make a set for quick checking
        missingNameSet = set()
        missingNames = []
        seen = set()

        # Get the blendshape weight names
        try:
            # GOOD GOD. This is because in maya 2016.5, if you delete a multi-instance
            # then listAttr, *it lists the deleted ones, and skips the ones at the end*
            # So I have to use aliasAttr and filter for the weights
            aliases = cmds.aliasAttr(self.shapeNode, query=True) or []
            attrs = [
                aliases[i]
                for i in range(0, len(aliases), 2)
                if aliases[i + 1].startswith("weight[")
            ]
            attrs = set(attrs)

        except ValueError:
            attrs = set()

        for shapeName in shapeNames:
            if shapeName in seen:
                continue
            seen.add(shapeName)
            if shapeName not in attrs:
                if shapeName not in missingNameSet:
                    missingNameSet.add(shapeName)
                    missingNames.append(shapeName)
        return missingNames, len(attrs)


    @classmethod
    def _removeExtraShapeNodes(cls, tfm):
        shapeNodes = cmds.listRelatives(tfm, shapes=True, noIntermediate=True)
        if len(shapeNodes) > 1:
            keeper = None
            todel = []
            for sn in shapeNodes:
                tfmChk = ''.join(sn.rsplit('Shape', 1))
                if tfmChk == tfm:
                    keeper = sn
                else:
                    todel.append(sn)
            if keeper is not None:
                cmds.delete(todel)


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
        cmds.undoInfo(state=False)
        try:
            if pBar is not None:
                pBar.setLabelText("Loading Connections")
                QApplication.processEvents()
            ev = simpDict["encodingVersion"]

            shapeNames = simpDict.get("shapes")
            if not shapeNames:
                return

            if ev > 1:
                shapeNames = [i["name"] for i in shapeNames]

            toMake, nextIndex = self._checkAllShapeValidity(shapeNames)

            if not toMake:
                return 

            if not create:
                if pBar is not None:
                    msg = "\n".join(
                        [
                            "Some shapes are Missing:",
                            ", ".join(toMake),
                            "",
                            "Create them?",
                        ]
                    )
                    btns = QMessageBox.Yes | QMessageBox.Cancel
                    bret = QMessageBox.question(pBar, "Missing Shapes", msg, btns)
                    if not bret & QMessageBox.Yes:
                        raise RuntimeError("Missing Shapes: {}".format(toMake))
                else:
                    raise RuntimeError("Missing Shapes: {}".format(toMake))

            if pBar is not None:
                spacer = "_" * max(list(map(len, toMake)))
                pBar.setMaximum(len(toMake))
                pBar.setLabelText("Creating Empty Shape:\n{0}".format(spacer))
                pBar.setValue(0)
                QApplication.processEvents()

            baseShape = cmds.duplicate(self.mesh)[0]
            cmds.delete(baseShape, constructionHistory=True)
            self._removeExtraShapeNodes(baseShape)

            for i, shapeName in enumerate(toMake):
                if pBar is not None:
                    pBar.setLabelText("Creating Empty Shape:\n{0}".format(shapeName))
                    pBar.setValue(i)
                    QApplication.processEvents()

                baseShape = cmds.rename(baseShape, shapeName)

                index = self._firstAvailableIndex()
                cmds.blendShape(
                    self.shapeNode, edit=True, target=(self.mesh, index, baseShape, 1.0)
                )
                weightAttr = "{0}.weight[{1}]".format(self.shapeNode, index)
                thing = cmds.ls(weightAttr)[0]

                cmds.connectAttr("{0}.weights[{1}]".format(self.op, nextIndex), thing)
                nextIndex += 1

            cmds.delete(baseShape)
        except Exception:
            cmds.undoInfo(state=True)
            raise


    def postLoad(self, simp, preRet):
        """

        Parameters
        ----------
        simp :

        preRet :

        Returns
        -------

        """
        cmds.undoInfo(state=True)

    def checkForErrors(self, window):
        """ Check for any DCC specific errors

        Parameters
        ----------
        window : QMainWindow
            The simplex window
        """
        shapeNodes = cmds.listRelatives(self.mesh, shapes=True, noIntermediate=True)
        if len(shapeNodes) > 1:
            msg = (
                "The current mesh has multiple shape nodes.",
                "The UI will still mostly work, but extracting/connecting shapes"
                "may fail in unexpected ways."
            )
            QMessageBox.warning(window, "Multiple Shape Nodes", '\n'.join(msg))

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

        # Find all blendshapes in the history
        rawShapeNodes = [
            h for h in cmds.listHistory(thing) if cmds.nodeType(h) == "blendShape"
        ]

        # Find any simplex ops connected to the history
        # that have the given name
        ops = []
        for sn in rawShapeNodes:
            op = cmds.listConnections(
                "{0}.{1}".format(sn, "message"),
                source=False,
                destination=True,
                type="simplex_maya",
            )
            if not op:
                continue
            op = op[0]
            js = cmds.getAttr(op + ".definition") or ""
            sn = json.loads(js).get("systemName")
            if sn == self.name:
                ops.append(op)

        if len(ops) > 1:
            raise RuntimeError(
                "Found too many Simplex systems with the same name on the same object"
            )

        # Back-select the shape nodes connected to those ops
        shapeNodes = []
        for op in ops:
            sn = cmds.listConnections(
                "{0}.{1}".format(op, "shapeMsg"),
                source=True,
                destination=False,
                type="blendShape",
            )
            if sn:
                shapeNodes.append(sn[0])

        # Find the msg connected control object
        ctrlCnx = []
        for op in ops:
            ccnx = cmds.listConnections(
                "{0}.{1}".format(op, "ctrlMsg"),
                source=True,
                destination=False,
            )
            if ccnx:
                ctrlCnx.append(ccnx[0])

        if not shapeNodes:
            if not create:
                raise RuntimeError(
                    "Blendshape operator not found with creation turned off"
                )
            # Unlock the normals on the rest head because blendshapes don't work with locked normals
            # and you can't really do this after the blendshape has been created
            intermediates = [
                shp
                for shp in cmds.listRelatives(self.mesh, shapes=True, path=True)
                if cmds.getAttr(shp + ".intermediateObject")
            ]
            meshToFreeze = self.mesh if not intermediates else intermediates[0]
            isIntermediate = cmds.getAttr(meshToFreeze + ".intermediateObject")
            cmds.polyNormalPerVertex(meshToFreeze, ufn=True)
            cmds.polySoftEdge(meshToFreeze, a=180, ch=1)
            cmds.setAttr(meshToFreeze + ".intermediateObject", 0)
            cmds.delete(meshToFreeze, constructionHistory=True)
            cmds.setAttr(meshToFreeze + ".intermediateObject", isIntermediate)

            self.shapeNode = cmds.blendShape(
                self.mesh, name="{0}_BS".format(self.name), frontOfChain=True
            )[0]
        else:
            self.shapeNode = shapeNodes[0]

        # find/build the operator
        # GODDAMMIT, why does maya return None instead of an empty list?????
        if not ops:
            if not create:
                raise RuntimeError(
                    "Simplex operator not found with creation turned off"
                )
            self.op = cmds.createNode("simplex_maya", name=self.name)
            cmds.addAttr(self.op, longName="revision", attributeType="long")
            cmds.addAttr(self.op, longName="shapeMsg", attributeType="message")
            cmds.addAttr(self.op, longName="ctrlMsg", attributeType="message")
            cmds.connectAttr(
                "{0}.{1}".format(self.shapeNode, "message"),
                "{0}.{1}".format(self.op, "shapeMsg"),
            )
        else:
            self.op = ops[0]

        # find/build the ctrl object
        if not ctrlCnx:
            if not create:
                raise RuntimeError("Control object not found with creation turned off")
            self.ctrl = cmds.group(empty=True, name="{0}_CTRL".format(self.name))
            for attr in [
                ".tx",
                ".ty",
                ".tz",
                ".rx",
                ".ry",
                ".rz",
                ".sx",
                ".sy",
                ".sz",
                ".v",
            ]:
                cmds.setAttr(self.ctrl + attr, keyable=False, channelBox=False)
            cmds.addAttr(self.ctrl, longName="solver", attributeType="message")
            cmds.connectAttr(
                "{0}.{1}".format(self.ctrl, "solver"),
                "{0}.{1}".format(self.op, "ctrlMsg"),
            )
        else:
            self.ctrl = ctrlCnx[0]

    def getShapeThing(self, shapeName):
        """

        Parameters
        ----------
        shapeName :


        Returns
        -------

        """
        s = cmds.ls("{0}.{1}".format(self.shapeNode, shapeName))
        if not s:
            return None
        return s[0]

    def getSliderThing(self, sliderName):
        """

        Parameters
        ----------
        sliderName :


        Returns
        -------

        """
        things = cmds.ls("{0}.{1}".format(self.ctrl, sliderName))
        if not things:
            return None
        return things[0]

    @staticmethod
    @undoable
    def buildRestAbc(abcMesh, name):
        """

        Parameters
        ----------
        abcMesh :

        name :


        Returns
        -------

        """
        if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
            cmds.loadPlugin("AbcImport")
            if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
                raise RuntimeError("Unable to load the AbcImport plugin")

        abcPath = str(abcMesh.getArchive())

        abcNode = cmds.createNode("AlembicNode")
        cmds.setAttr(abcNode + ".abc_File", abcPath, type="string")
        cmds.setAttr(abcNode + ".speed", 24)  # Is this needed anymore?
        cmds.setAttr(abcNode + ".time", 0)

        importHead = cmds.polySphere(
            name="{0}_SIMPLEX".format(name), constructionHistory=False
        )[0]
        importHeadShape = [i for i in cmds.listRelatives(importHead, shapes=True)][0]

        cmds.connectAttr(abcNode + ".outPolyMesh[0]", importHeadShape + ".inMesh")
        cmds.polyEvaluate(importHead, vertex=True)  # Force a refresh
        cmds.disconnectAttr(abcNode + ".outPolyMesh[0]", importHeadShape + ".inMesh")
        cmds.sets(importHead, e=True, forceElement="initialShadingGroup")
        cmds.delete(abcNode)
        return importHead

    @staticmethod
    def vertCount(mesh):
        return cmds.polyEvaluate(mesh, vertex=True)

    @undoable
    def loadAbc(self, abcMesh, js, pBar=None):
        """

        Parameters
        ----------
        abcMesh :

        js :

        pBar :
             (Default value = None)

        Returns
        -------

        """
        # UGH, I *REALLY* hate that this is faster
        # But if I want to be "pure" about it, I should just bite the bullet
        # and do the direct alembic manipulation in C++

        if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
            cmds.loadPlugin("AbcImport")
            if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
                raise RuntimeError("Unable to load the AbcImport plugin")

        abcPath = str(abcMesh.getArchive())

        abcNode = cmds.createNode("AlembicNode")
        cmds.setAttr(abcNode + ".abc_File", abcPath, type="string")

        timeUnits = {
            "game": 15,
            "film": 24,
            "pal": 25,
            "ntsc": 30,
            "show": 48,
            "palf": 50,
            "ntscf": 60,
        }

        fps = cmds.currentUnit(time=True, query=True)
        if isinstance(fps, six.string_types):
            if fps.endswith("fps"):
                fps = fps[:-3]
            if fps in timeUnits:
                fps = timeUnits[fps]
            fps = float(fps)

        cmds.setAttr(abcNode + ".speed", fps)

        shapes = js["shapes"]
        shapeDict = {i.name: i for i in self.simplex.shapes}

        if js["encodingVersion"] > 1:
            shapes = [i["name"] for i in shapes]

        importHead = cmds.polySphere(name="importHead", constructionHistory=False)[0]
        importHeadShape = [i for i in cmds.listRelatives(importHead, shapes=True)][0]

        cmds.connectAttr(abcNode + ".outPolyMesh[0]", importHeadShape + ".inMesh")
        cmds.polyEvaluate(importHead, vertex=True)  # Force a refresh
        cmds.disconnectAttr(abcNode + ".outPolyMesh[0]", importHeadShape + ".inMesh")

        importRest = cmds.duplicate(self.mesh, name="importRest")[0]
        cmds.delete(importRest, constructionHistory=True)
        self._removeExtraShapeNodes(importRest)

        importBS = cmds.blendShape(importRest, importHead)[0]
        cmds.blendShape(importBS, edit=True, weight=[(0, 1.0)])
        # Maybe get shapeNode from self.mesh??
        importOrig = [
            i for i in cmds.listRelatives(importHead, shapes=True) if i.endswith("Orig")
        ][0]
        cmds.connectAttr(abcNode + ".outPolyMesh[0]", importOrig + ".inMesh")
        cmds.delete(importRest)

        if pBar is not None:
            pBar.show()
            pBar.setMaximum(len(shapes))
            longName = max(shapes, key=len)
            pBar.setValue(1)
            pBar.setLabelText("Loading:\n{0}".format("_" * len(longName)))

        for i, shapeName in enumerate(shapes):
            if pBar is not None:
                pBar.setValue(i)
                pBar.setLabelText("Loading:\n{0}".format(shapeName))
                QApplication.processEvents()
                if pBar.wasCanceled():
                    return
            index = self.getShapeIndex(shapeDict[shapeName])
            cmds.setAttr(abcNode + ".time", i)

            outAttr = "{0}.worldMesh[0]".format(importHead)
            tgn = "{0}.inputTarget[0].inputTargetGroup[{1}]".format(
                self.shapeNode, index
            )
            inAttr = "{0}.inputTargetItem[6000].inputGeomTarget".format(tgn)

            cmds.connectAttr(outAttr, inAttr, force=True)
            cmds.disconnectAttr(outAttr, inAttr)
        cmds.delete(abcNode)
        cmds.delete(importHead)

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
        sl = om.MSelectionList()
        sl.add(self.mesh)
        thing = om.MDagPath()
        sl.getDagPath(0, thing)
        meshFn = om.MFnMesh(thing)
        ptCount = meshFn.numVertices()
        with disconnected(self.shapeNode) as cnx:
            shapeCnx = cnx[self.shapeNode]
            for v in six.itervalues(shapeCnx):
                cmds.setAttr(v, 0.0)

            if pBar is not None:
                # find the longest name for displaying stuff
                sns = "_" * max(list(map(len, [s.name for s in shapes])))
                pBar.setLabelText("Getting Shape:\n{0}".format(sns))
                pBar.setMaximum(len(shapes))
                QApplication.processEvents()

            for i, shape in enumerate(shapes):
                if pBar is not None:
                    pBar.setLabelText("Getting Shape:\n{0}".format(shape.name))
                    pBar.setValue(i)
                    QApplication.processEvents()

                cmds.setAttr(shape.thing, 1.0)

                if np is not None:
                    rawPts = meshFn.getRawPoints()
                    cta = (c_float * ptCount * 3).from_address(int(rawPts))
                    out = np.ctypeslib.as_array(cta)
                    out = np.copy(out)
                    out = out.reshape((-1, 3))
                else:
                    flatverts = cmds.xform(
                        "{0}.vtx[*]".format(self.mesh),
                        translation=1,
                        query=1,
                        worldSpace=False,
                    )
                    args = [iter(flatverts)] * 3
                    out = list(zip(*args))

                cmds.setAttr(shape.thing, 0.0)
                shape.verts = out

    def getShapeVertices(self, shape):
        """

        Parameters
        ----------
        shape :

        Returns
        -------

        """
        with disconnected(self.shapeNode) as cnx:
            shapeCnx = cnx[self.shapeNode]
            for v in six.itervalues(shapeCnx):
                cmds.setAttr(v, 0.0)
            cmds.setAttr(shape.thing, 1.0)
            if np is None:
                flatverts = cmds.xform(
                    "{0}.vtx[*]".format(self.mesh),
                    translation=1,
                    query=1,
                    worldSpace=False,
                )
                args = [iter(flatverts)] * 3
                out = list(zip(*args))
            else:
                out = self.getNumpyShape(self.mesh)
            return out

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
        # Get the MDagPath from the name of the mesh
        sl = om.MSelectionList()
        sl.add(mesh)
        thing = om.MDagPath()
        sl.getDagPath(0, thing)
        meshFn = om.MFnMesh(thing)

        vts = om.MPointArray()
        meshFn.getPoints(vts, om.MSpace.kObject)
        verts = [(vts[i].x, vts[i].y, vts[i].z) for i in range(vts.length())]

        faces = []
        counts = []
        rawUvFaces = []

        vIdx = om.MIntArray()

        util = om.MScriptUtil()
        util.createFromInt(0)
        uvIdxPtr = util.asIntPtr()
        uArray = om.MFloatArray()
        vArray = om.MFloatArray()
        meshFn.getUVs(uArray, vArray)
        hasUvs = uArray.length() > 0

        for i in range(meshFn.numPolygons()):
            meshFn.getPolygonVertices(i, vIdx)
            face = []
            for j in reversed(range(vIdx.length())):
                face.append(vIdx[j])
                if hasUvs:
                    meshFn.getPolygonUVid(i, j, uvIdxPtr)
                    uvIdx = util.getInt(uvIdxPtr)
                    if uvIdx >= uArray.length() or uvIdx < 0:
                        uvIdx = 0
                    rawUvFaces.append(uvIdx)

            face = [vIdx[j] for j in reversed(range(vIdx.length()))]
            faces.extend(face)
            counts.append(vIdx.length())

        if hasUvs:
            uvs = [(uArray[i], vArray[i]) for i in range(len(vArray))]
            uvFaces = rawUvFaces
        else:
            uvs = None
            uvFaces = None

        return verts, faces, counts, uvs, uvFaces

    def loadMeshTopology(self):
        """ """
        self._faces, self._counts, self._uvs = self.getAbcFaces(self.mesh)

    @classmethod
    def getNumpyShape(cls, mesh, world=False):
        """Get the np.array shape of the mesh connected to the smpx

        Parameters
        ----------
        mesh : str
            The name of the maya shape object
        world : bool
            Whether to get the points in worldspace, or local space

        Returns
        -------
        : np.array
            The point positions of the mesh

        """
        # This method uses some neat tricks to get data out of an MPointArray
        # Basically, you get an MScriptUtil pointer to the MPointArray data
        # Then you get a ctypes pointer to the MScriptUtil pointer
        # Then you get a numpy pointer to the ctypes pointer
        # Because these are all pointers, you're looking at the exact same
        # data in memory ... So just copy the data out to a numpy array
        # See: https://gist.github.com/tbttfox/9ca775bf629c7a1285c27c8d9d961bca

        # Get the MPointArray of the mesh
        vts = cls._getMeshVertices(mesh, world=world)

        # Get the double4 pointer from the mpointarray
        count = vts.length()
        cc = count * 4
        util = om.MScriptUtil()
        util.createFromList([0.0] * cc, cc)
        ptr = util.asDouble4Ptr()
        vts.get(ptr)

        # Build a ctypes double4 pointer
        cdata = (c_double * 4) * count

        # int(ptr) gives the memory address
        cta = cdata.from_address(int(ptr))

        # This makes numpy look at the same memory as the ctypes array
        # so we can both read from and write to that data through numpy
        npArray = np.ctypeslib.as_array(cta)

        # Copy the data out of the numpy array, which is looking
        # into the cdata array, which is looking into the ptr array
        return npArray[..., :3].copy()

    @staticmethod
    def _getMeshVertices(mesh, world=False):
        """ """
        # Get the MDagPath from the name of the mesh
        sl = om.MSelectionList()
        sl.add(mesh)
        thing = om.MDagPath()
        sl.getDagPath(0, thing)
        meshFn = om.MFnMesh(thing)
        vts = om.MPointArray()
        if world:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        meshFn.getPoints(vts, space)
        return vts

    @classmethod
    def _exportAbcVertices(cls, mesh, world=False):
        """ """
        if np is None or imathnumpy is None:
            vts = cls._getMeshVertices(mesh, world=world)
            vertices = V3fArray(vts.length())
            for i in range(vts.length()):
                vertices[i] = (vts[i].x, vts[i].y, vts[i].z)
        else:
            vts = cls.getNumpyShape(mesh, world=world)
            vertices = mkSampleVertexPoints(vts)
        return vertices

    @staticmethod
    def getAbcFaces(mesh):
        """ """
        # Get the MDagPath from the name of the mesh
        sl = om.MSelectionList()
        sl.add(mesh)
        thing = om.MDagPath()
        sl.getDagPath(0, thing)
        meshFn = om.MFnMesh(thing)

        faces = []
        faceCounts = []
        # uvArray = []
        uvIdxArray = []
        vIdx = om.MIntArray()

        util = om.MScriptUtil()
        util.createFromInt(0)
        uvIdxPtr = util.asIntPtr()
        uArray = om.MFloatArray()
        vArray = om.MFloatArray()
        meshFn.getUVs(uArray, vArray)
        hasUvs = uArray.length() > 0

        for i in range(meshFn.numPolygons()):
            meshFn.getPolygonVertices(i, vIdx)
            face = []
            for j in reversed(range(vIdx.length())):
                face.append(vIdx[j])
                if hasUvs:
                    meshFn.getPolygonUVid(i, j, uvIdxPtr)
                    uvIdx = util.getInt(uvIdxPtr)
                    if uvIdx >= uArray.length() or uvIdx < 0:
                        uvIdx = 0
                    uvIdxArray.append(uvIdx)

            face = [vIdx[j] for j in reversed(range(vIdx.length()))]
            faces.extend(face)
            faceCounts.append(vIdx.length())

        abcFaceIndices = IntArray(len(faces))
        for i in range(len(faces)):
            abcFaceIndices[i] = faces[i]

        abcFaceCounts = IntArray(len(faceCounts))
        for i in range(len(faceCounts)):
            abcFaceCounts[i] = faceCounts[i]

        if hasUvs:
            abcUVArray = V2fArray(len(uArray))
            for i in range(len(vArray)):
                abcUVArray[i] = (uArray[i], vArray[i])
            abcUVIdxArray = UnsignedIntArray(len(uvIdxArray))
            for i in range(len(uvIdxArray)):
                abcUVIdxArray[i] = uvIdxArray[i]
            uv = OV2fGeomParamSample(
                abcUVArray, abcUVIdxArray, GeometryScope.kFacevaryingScope
            )
        else:
            uv = None

        return abcFaceIndices, abcFaceCounts, uv

    def exportAbc(
        self, dccMesh, abcMesh, js, world=False, ensureCorrect=False, pBar=None
    ):
        """ """
        # export the data to alembic
        if dccMesh is None:
            dccMesh = self.mesh

        shapeDict = {i.name: i for i in self.simplex.shapes}

        shapeNames = js["shapes"]
        if js["encodingVersion"] > 1:
            shapeNames = [i["name"] for i in shapeNames]
        shapes = [shapeDict[i] for i in shapeNames]

        faces, counts, uvs = self.getAbcFaces(dccMesh)
        schema = abcMesh.getSchema()

        if pBar is not None:
            pBar.show()
            pBar.setMaximum(len(shapes))
            spacerName = "_" * max(list(map(len, shapeNames)))
            pBar.setLabelText("Exporting:\n{0}".format(spacerName))
            QApplication.processEvents()

        if ensureCorrect:
            # Since this code is used to both export and exportOther
            # I only want to ensure that everything is correct only if
            # I'm doing a normal export
            envelope = cmds.getAttr(self.shapeNode + ".envelope")
            cmds.setAttr(self.shapeNode + ".envelope", 1.0)

        with disconnected(self.shapeNode) as cnx:
            shapeCnx = cnx[self.shapeNode]
            for v in six.itervalues(shapeCnx):
                cmds.setAttr(v, 0.0)
            for i, shape in enumerate(shapes):
                if pBar is not None:
                    pBar.setLabelText("Exporting:\n{0}".format(shape.name))
                    pBar.setValue(i)
                    QApplication.processEvents()
                    if pBar.wasCanceled():
                        return
                cmds.setAttr(shape.thing, 1.0)
                verts = self._exportAbcVertices(dccMesh, world=world)
                if uvs is not None:
                    abcSample = OPolyMeshSchemaSample(verts, faces, counts, uvs)
                else:
                    abcSample = OPolyMeshSchemaSample(verts, faces, counts)
                schema.set(abcSample)
                cmds.setAttr(shape.thing, 0.0)

        if ensureCorrect:
            cmds.setAttr(self.shapeNode + ".envelope", envelope)

    def exportOtherAbc(self, dccMesh, abcMesh, js, world=False, pBar=None):
        """ """
        shapeNames = js["shapes"]
        if js["encodingVersion"] > 1:
            shapeNames = [i["name"] for i in shapeNames]

        if pBar is not None:
            pBar.show()
            pBar.setMaximum(len(shapeNames))
            spacerName = "_" * max(list(map(len, shapeNames)))
            pBar.setLabelText("Exporting:\n{0}".format(spacerName))
            QApplication.processEvents()

        # Get all the sliderVecs
        shapeNames, inVecs, keyIdxs = self.simplex.buildInputVectors()
        sliderVecs = [
            [0.0] * len(self.simplex.sliders) for i in range(len(self.simplex.shapes))
        ]
        for iv, idx in zip(inVecs, keyIdxs):
            sliderVecs[idx] = iv

        # Get all the fully expanded shapes, and the activations per shape
        with disconnected(self.op) as allSliderCnx:
            sliderCnx = allSliderCnx[self.op]
            # zero all slider vals on the op to get the rest shape
            for a in six.itervalues(sliderCnx):
                cmds.setAttr(a, 0.0)
            restVerts = self.getNumpyShape(dccMesh, world=world)

            fullShapes = np.zeros((len(self.simplex.shapes), len(restVerts), 3))
            shpValArray = np.zeros((len(self.simplex.shapes), len(self.simplex.shapes)))
            for shpIdx, shape in enumerate(self.simplex.shapes):
                if pBar is not None:
                    pBar.setLabelText("Reading Full Shapes:\n{0}".format(shape.name))
                    pBar.setValue(shpIdx)
                    QApplication.processEvents()
                    if pBar.wasCanceled():
                        raise RuntimeError("Cancelled!")

                # Set the full vec for this shape
                inVec = sliderVecs[shpIdx]
                for vi, vv in enumerate(inVec):
                    cmds.setAttr(sliderCnx[self.simplex.sliders[vi].thing], vv)

                fullShapes[shpIdx] = self.getNumpyShape(dccMesh, world=world)

                ary = np.array(cmds.getAttr(self.op + ".weights")[0])
                # Get rid of some floating point inaccuracies
                ary[np.isclose(ary, 1.0)] = 1.0
                ary[np.isclose(ary, 0.0)] = 0.0
                shpValArray[shpIdx] = ary

        # Figure out what order to build the deltas
        # so that the deltas exist when I try to combine them
        ctrlOrder = self.simplex.controllersByDepth()
        shapeOrder = [pp.shape for ctrl in ctrlOrder for pp in ctrl.prog.pairs]
        shapeOrder = [i for i in shapeOrder if not i.isRest]

        # Incrementally Build the numpy array of delta shapes
        # build deltaShapeArray as a 2d array because numpy is like 10x faster on 2d arrays
        indexByShape = {v: k for k, v in enumerate(self.simplex.shapes)}
        deltaShapeArray = np.zeros((len(self.simplex.shapes), len(restVerts) * 3))
        for shpOrderIdx, shape in enumerate(shapeOrder):
            if pBar is not None:
                pBar.setLabelText("Collapsing to Deltas:\n{0}".format(shape.name))
                pBar.setValue(shpOrderIdx)
                QApplication.processEvents()
                if pBar.wasCanceled():
                    raise RuntimeError("Cancelled!")

            shpIdx = indexByShape[shape]
            base = np.dot(shpValArray[shpIdx], deltaShapeArray)
            deltaShapeArray[shpIdx] = (
                fullShapes[shpIdx] - restVerts - base.reshape((-1, 3))
            ).flatten()

        # And move that 2d array back into 3d
        deltaShapeArray = deltaShapeArray.reshape((len(self.simplex.shapes), -1, 3))

        # Finally write the outputs
        faces, counts, uvs = self.getAbcFaces(dccMesh)
        schema = abcMesh.getSchema()
        for shpIdx, shape in enumerate(self.simplex.shapes):
            if pBar is not None:
                pBar.setLabelText("writing:\n{0}".format(shape.name))
                pBar.setValue(shpIdx)
                QApplication.processEvents()
                if pBar.wasCanceled():
                    raise RuntimeError("Cancelled!")
            shpVerts = restVerts + deltaShapeArray[shpIdx]
            shpVerts = mkSampleVertexPoints(shpVerts)
            if uvs is not None:
                abcSample = OPolyMeshSchemaSample(shpVerts, faces, counts, uvs)
            else:
                abcSample = OPolyMeshSchemaSample(shpVerts, faces, counts)
            schema.set(abcSample)

    # Revision tracking
    def getRevision(self):
        """ """
        try:
            return cmds.getAttr("{0}.{1}".format(self.op, "revision"))
        except ValueError:
            # object does not exist
            return None

    @undoable
    def incrementRevision(self):
        """ """
        value = self.getRevision()
        if value is None:
            return
        cmds.setAttr("{0}.{1}".format(self.op, "revision"), value + 1)
        jsString = self.simplex.dump()
        self.setSimplexString(self.op, jsString)
        return value + 1

    @undoable
    def setRevision(self, val):
        """

        Parameters
        ----------
        val :


        Returns
        -------

        """
        cmds.setAttr("{0}.{1}".format(self.op, "revision"), val)

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
        if (
            self.mesh is None
            or self.ctrl is None
            or self.shapeNode is None
            or self.op is None
            or self.simplex is None
        ):
            raise ValueError("System is not set up. Cannot rename")

        nn = self.mesh.replace(self.name, name)
        self.mesh = cmds.rename(self.mesh, nn)

        nn = self.ctrl.replace(self.name, name)
        self.ctrl = cmds.rename(self.ctrl, nn)

        oldNodeName = self.shapeNode
        nn = self.shapeNode.replace(self.name, name)
        self.shapeNode = cmds.rename(self.shapeNode, nn)

        nn = self.op.replace(self.name, name)
        self.op = cmds.rename(self.op, nn)

        for shape in self.simplex.shapes:
            shape.thing = shape.thing.replace(oldNodeName, self.shapeNode)

        self.name = name

    @undoable
    def deleteSystem(self):
        """ """
        cmds.delete(self.ctrl)
        cmds.delete(self.shapeNode)
        cmds.delete(self.op)
        self.ctrl = None  # the object that has all the controllers on it
        self.shapeNode = None  # the deformer object
        self.op = None  # the simplex object
        self.simplex = None

    # Shapes
    @undoable
    def createShape(self, shape, live=False, offset=10):
        """

        Parameters
        ----------
        shape :

        live :
             (Default value = False)
        offset :
             (Default value = 10)

        Returns
        -------

        """
        with disconnected(self.shapeNode):
            try:
                attrs = cmds.listAttr("{0}.weight[*]".format(self.shapeNode))
            except ValueError:
                pass
                # Maya throws an error if there aren't any instead of
                # just returning an empty list
            else:
                for attr in attrs:
                    cmds.setAttr("{0}.{1}".format(self.shapeNode, attr), 0.0)
            newShape = cmds.duplicate(self.mesh, name=shape.name)[0]

        cmds.delete(newShape, constructionHistory=True)
        index = self._firstAvailableIndex()
        cmds.blendShape(
            self.shapeNode, edit=True, target=(self.mesh, index, newShape, 1.0)
        )
        weightAttr = "{0}.weight[{1}]".format(self.shapeNode, index)
        thing = cmds.ls(weightAttr)[0]

        shapeIndex = len(shape.simplex.shapes) - 1
        cmds.connectAttr("{0}.weights[{1}]".format(self.op, shapeIndex), thing)

        if live:
            cmds.xform(newShape, relative=True, translation=[offset, 0, 0])
        else:
            cmds.delete(newShape)

        return thing

    def _firstAvailableIndex(self):
        """ """
        aliases = cmds.aliasAttr(self.shapeNode, query=True)
        idxs = set()
        if not aliases:
            return 0
        for alias in aliases:
            match = re.search(r"\[\d+\]", alias)
            if not match:
                continue  # No index found for the current shape
            idxs.add(int(match.group().strip("[]")))

        for i in range(len(idxs) + 1):
            if i not in idxs:
                return i
        # there should be no way to get here, but just in case:
        return len(idxs) + 1

    def getShapeIndex(self, shape):
        """

        Parameters
        ----------
        shape :


        Returns
        -------

        """
        aName = cmds.attributeName(shape.thing)
        aliases = cmds.aliasAttr(self.shapeNode, query=True)
        idx = aliases.index(aName)
        raw = aliases[idx + 1]
        matches = re.findall(r"\[\d+\]", raw)
        if not matches:
            raise IndexError("No index found for the current shape")
        return int(matches[-1].strip("[]"))

    @undoable
    def extractWithDeltaShape(self, shape, live=True, offset=10.0):
        """Make a mesh representing a shape. Can be live or not.
            Also, make a shapenode that is the delta of the change being made

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
        with disconnected(self.shapeNode) as cnx:
            shapeCnx = cnx[self.shapeNode]
            for v in six.itervalues(shapeCnx):
                cmds.setAttr(v, 0.0)

            # store the delta shape
            delta = cmds.duplicate(self.mesh, name="{0}_Delta".format(shape.name))[0]

            # Extract the shape
            cmds.setAttr(shape.thing, 1.0)
            extracted = cmds.duplicate(
                self.mesh, name="{0}_Extract".format(shape.name)
            )[0]

            # Store the initial shape
            init = cmds.duplicate(extracted, name="{0}_Init".format(shape.name))[0]

        # clear old orig objects
        for item in [delta, extracted, init]:
            self._clearShapes(item, doOrig=True)

        # build the deltaObj system
        bs = cmds.blendShape(delta, name="{0}_DeltaBS".format(shape.name))[0]

        cmds.blendShape(bs, edit=True, target=(delta, 0, init, 1.0))
        cmds.blendShape(bs, edit=True, target=(delta, 1, extracted, 1.0))

        cmds.setAttr("{0}.{1}".format(bs, init), -1.0)
        cmds.setAttr("{0}.{1}".format(bs, extracted), 1.0)

        # Cleanup
        nodeDict = dict(Delta=delta, Init=init)
        repDict = self._reparentDeltaShapes(extracted, nodeDict, bs)

        # Shift the extracted shape to the side
        cmds.xform(extracted, relative=True, translation=[offset, 0, 0])

        if live:
            self.connectShape(shape, extracted, live, delete=False)

        return extracted, repDict["Delta"]

    @undoable
    def extractWithDeltaConnection(self, shape, delta, value, live=True, offset=10.0):
        """Extract a shape with a live partial delta added in.
            Useful for updating progressive shapes

        Parameters
        ----------
        shape :

        delta :

        value :

        live :
             (Default value = True)
        offset :
             (Default value = 10.0)

        Returns
        -------

        """
        with disconnected(self.shapeNode):
            for attr in cmds.listAttr("{0}.weight[*]".format(self.shapeNode)):
                cmds.setAttr("{0}.{1}".format(self.shapeNode, attr), 0.0)

            # Pull out the rest shape. we will blend this guy to the extraction
            extracted = cmds.duplicate(
                self.mesh, name="{0}_Extract".format(shape.name)
            )[0]

            cmds.setAttr(shape.thing, 1.0)
            # Store the initial shape
            init = cmds.duplicate(self.mesh, name="{0}_Init".format(shape.name))[0]

        # clear old orig objects
        for item in [init, extracted]:
            self._clearShapes(item, doOrig=True)

        deltaPar = cmds.listRelatives(delta, parent=True)[0]

        # build the restObj system
        cmds.select(clear=True)  # 'cause maya
        bs = cmds.blendShape(extracted, name="{0}_DeltaBS".format(shape.name))[0]
        cmds.blendShape(bs, edit=True, target=(extracted, 0, init, 1.0))
        cmds.blendShape(bs, edit=True, target=(extracted, 1, deltaPar, 1.0))

        cmds.setAttr("{0}.{1}".format(bs, init), 1.0)
        cmds.setAttr("{0}.{1}".format(bs, deltaPar), value)

        outCnx = "{0}.worldMesh[0]".format(delta)
        inCnx = "{0}.inputTarget[0].inputTargetGroup[{1}].inputTargetItem[6000].inputGeomTarget".format(
            bs, 1
        )
        cmds.connectAttr(outCnx, inCnx, force=True)
        cmds.aliasAttr(delta, "{0}.{1}".format(bs, deltaPar))

        # Cleanup
        nodeDict = dict(Init=init)
        self._reparentDeltaShapes(extracted, nodeDict, bs)

        # Remove the tweak node, otherwise editing the input progressives
        # *inverts* the shape
        exShape = cmds.listRelatives(extracted, noIntermediate=1, shapes=1)[0]
        tweak = cmds.listConnections(
            exShape + ".tweakLocation", source=1, destination=0
        )
        if tweak:
            cmds.delete(tweak)

        # Shift the extracted shape to the side
        cmds.xform(extracted, relative=True, translation=[offset, 0, 0])

        if live:
            self.connectShape(shape, extracted, live, delete=False)

        return extracted

    @undoable
    def extractShape(self, shape, live=True, offset=10.0):
        """Make a mesh representing a shape. Can be live or not.
            Can also store its starting shape and delta data

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
        with disconnected(self.shapeNode):
            for attr in cmds.listAttr("{0}.weight[*]".format(self.shapeNode)):
                cmds.setAttr("{0}.{1}".format(self.shapeNode, attr), 0.0)

            cmds.setAttr(shape.thing, 1.0)
            extracted = cmds.duplicate(
                self.mesh, name="{0}_Extract".format(shape.name)
            )[0]

        # Shift the extracted shape to the side
        cmds.xform(extracted, relative=True, translation=[offset, 0, 0])

        if live:
            self.connectShape(shape, extracted, live, delete=False)
        return extracted

    @undoable
    def connectShape(self, shape, mesh=None, live=False, delete=False):
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

        Returns
        -------

        """
        if mesh is None:
            attrName = cmds.attributeName(shape.thing, long=True)
            mesh = "{0}_Extract".format(attrName)

        if not cmds.objExists(mesh):
            return

        index = self.getShapeIndex(shape)
        tgn = "{0}.inputTarget[0].inputTargetGroup[{1}]".format(self.shapeNode, index)
        cnx = mesh + "Shape" if cmds.nodeType(mesh) == "transform" else mesh

        outAttr = "{0}.worldMesh[0]".format(
            cnx
        )  # Make sure to check the right shape object
        inAttr = "{0}.inputTargetItem[6000].inputGeomTarget".format(tgn)

        if not cmds.isConnected(outAttr, inAttr):
            cmds.connectAttr(outAttr, inAttr, force=True)

        if not live:
            cmds.disconnectAttr(outAttr, inAttr)
        if delete:
            cmds.delete(mesh)

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
        index = self.getShapeIndex(shape)
        tgn = "{0}.inputTarget[0].inputTargetGroup[{1}]".format(self.shapeNode, index)
        shapeInput = "{0}.inputTargetItem[6000]".format(tgn)
        cmds.setAttr(
            "{0}.inputPointsTarget".format(shapeInput), 0, (), type="pointArray"
        )
        cmds.setAttr(
            "{0}.inputComponentsTarget".format(shapeInput), 0, "", type="componentList"
        )

    @undoable
    def deleteShape(self, toDelShape):
        """Remove a shape from the system

        Parameters
        ----------
        toDelShape :


        Returns
        -------

        """
        index = self.getShapeIndex(toDelShape)
        tgn = "{0}.inputTarget[0].inputTargetGroup[{1}]".format(self.shapeNode, index)
        cmds.removeMultiInstance(toDelShape.thing, b=True)
        cmds.removeMultiInstance(tgn, b=True)
        cmds.aliasAttr(toDelShape.thing, remove=True)
        self._rebuildShapeConnections()

    def _rebuildShapeConnections(self):
        """ """
        # Rebuild the shape connections in the proper order
        cnxs = (
            cmds.listConnections(
                self.op, plugs=True, source=False, destination=True, connections=True
            )
            or []
        )
        for i, cnx in enumerate(cnxs):
            if i % 2 == 0 and cnx.startswith("{0}.weights[".format(self.op)):
                cmds.disconnectAttr(cnxs[i], cnxs[i + 1])

        for i, shape in enumerate(self.simplex.shapes):
            cmds.connectAttr(
                "{0}.weights[{1}]".format(self.op, i), shape.thing, force=True
            )

    @undoable
    def forceRebuildShapeConnections(self):
        """ """
        self._rebuildShapeConnections()

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
        cmds.aliasAttr(name, shape.thing)
        shape.thing = "{0}.{1}".format(self.shapeNode, name)

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

    # Falloffs
    def createFalloff(self, name):
        """

        Parameters
        ----------
        name :


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
        shape = [i for i in cmds.listRelatives(self.mesh, shapes=True)][0]
        return shape + "." + falloff.name

    # Sliders
    @undoable
    def createSlider(self, slider):
        """

        Parameters
        ----------
        slider :


        Returns
        -------

        """
        index = slider.simplex.sliders.index(slider)
        cmds.addAttr(
            self.ctrl,
            longName=slider.name,
            attributeType="double",
            keyable=True,
            min=slider.minValue * self.sliderMul,
            max=slider.maxValue * self.sliderMul,
        )
        thing = "{0}.{1}".format(self.ctrl, slider.name)
        cmds.connectAttr(thing, "{0}.sliders[{1}]".format(self.op, index))
        return thing

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
        vals = [v.value for v in slider.prog.pairs]
        cnx = cmds.listConnections(
            slider.thing, plugs=True, source=False, destination=True
        )
        cmds.deleteAttr(slider.thing)
        cmds.addAttr(
            self.ctrl,
            longName=name,
            attributeType="double",
            keyable=True,
            min=self.sliderMul * min(vals),
            max=self.sliderMul * max(vals),
        )
        newThing = "{0}.{1}".format(self.ctrl, name)
        slider.thing = newThing
        for c in cnx:
            cmds.connectAttr(newThing, c)

    @undoable
    def setSliderRange(self, slider):
        """Set the range of a slider

        Parameters
        ----------
        slider :


        Returns
        -------

        """
        vals = [v.value for v in slider.prog.pairs]
        attrName = "{0}.{1}".format(self.ctrl, slider.name)
        cmds.addAttr(
            attrName,
            edit=True,
            min=self.sliderMul * min(vals),
            max=self.sliderMul * max(vals),
        )

    @undoable
    def deleteSlider(self, toDelSlider):
        """

        Parameters
        ----------
        toDelSlider :


        Returns
        -------

        """
        cmds.deleteAttr(toDelSlider.thing)

        # Rebuild the slider connections in the proper order
        # Get the sliders connections
        cnxs = cmds.listConnections(
            self.op, plugs=True, source=True, destination=False, connections=True
        )
        for i, cnx in enumerate(cnxs):
            if cnx.startswith("{0}.sliders".format(self.op)):
                cmds.disconnectAttr(cnxs[i + 1], cnxs[i])

        for i, slider in enumerate(self.simplex.sliders):
            cmds.connectAttr(slider.thing, "{0}.sliders[{1}]".format(self.op, i))

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
            try:
                cmds.setAttr(slider.thing, weight)
            except RuntimeError:
                # Probably locked or connected. Just skip it
                pass

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
        try:
            cmds.setAttr(slider.thing, weight)
        except RuntimeError:
            # Probably locked or connected. Just skip it
            pass

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
            cmds.addAttr(
                slider.thing,
                edit=True,
                min=min(vals) * self.sliderMul,
                max=max(vals) * self.sliderMul,
            )

    def _doesDeltaExist(self, combo, target):
        """

        Parameters
        ----------
        combo :

        target :


        Returns
        -------

        """
        dshape = "{0}_DeltaShape".format(combo.name)
        if not cmds.ls(dshape):
            return None
        par = cmds.listRelatives(dshape, allParents=1)
        if not par:
            # there is apparently a transform object with the name
            return None

        par = cmds.ls(par[0], absoluteName=1)
        tar = cmds.ls(target, absoluteName=1)

        if par != tar:
            # the shape exists under a different transform ... ugh
            return None
        return par + "|" + dshape

    def _clearShapes(self, item, doOrig=False):
        """

        Parameters
        ----------
        item :

        doOrig :
             (Default value = False)

        Returns
        -------

        """
        aname = cmds.ls(item, long=1)[0]
        shapes = cmds.ls(cmds.listRelatives(item, shapes=1), long=1)
        baseName = aname.split("|")[-1]

        primary = "{0}|{1}Shape".format(aname, baseName)
        orig = "{0}|{1}ShapeOrig".format(aname, baseName)

        for shape in shapes:
            if shape == primary:
                continue
            elif shape == orig:
                if doOrig:
                    cmds.delete(shape)
            else:
                cmds.delete(shape)

    @undoable
    def forceRebuildSliderConnections(self):
        """ """
        self._rebuildSliderConnections()

    def _rebuildSliderConnections(self):
        # disconnect all outputs from the ctrl
        rcnx = cmds.listConnections(
            self.ctrl, source=False, plugs=True, connections=True
        )
        for i in range(0, len(rcnx), 2):
            src, dst = rcnx[i], rcnx[i + 1]
            if cmds.getAttr(src, type=True) != "double":
                # only disconnect doubles
                continue
            cmds.disconnectAttr(src, dst)

        # Reconnect by name
        for i, sli in enumerate(self.simplex.sliders):
            thing = self.getSliderThing(sli.name)
            cmds.connectAttr(thing, self.op + ".sliders[{0}]".format(i))

    # Combos
    def _reparentDeltaShapes(self, par, nodeDict, bsNode, toDelete=None):
        """Reparent and clean up a single-transform delta system

        Put all the relevant shape nodes from the nodeDict under the par,
        and rename the shapes to maya's convention. Then build a callback
        to ensure the blendshape node isn't left floating

        par: The parent transform node
        nodeDict: A {simpleName: node} dictionary.
        bsNode: The blendshape node.
        toDelete: Any extra nodes to delte after all the node twiddling

        Parameters
        ----------
        par :

        nodeDict :

        bsNode :

        toDelete :
             (Default value = None)

        Returns
        -------

        """
        # Get the shapes and origs
        shapeDict = {}
        origDict = {}

        for name, node in six.iteritems(nodeDict):
            shape = cmds.listRelatives(node, noIntermediate=1, shapes=1)[0]
            shape = cmds.ls(shape, absoluteName=1)[0]
            if shape:
                shapeDict[name] = shape

            orig = shape + "Orig"
            orig = cmds.ls(orig)
            if orig:
                origDict[name] = orig

        for name in nodeDict:
            for d, fmt in [(shapeDict, "{0}Shape{1}"), (origDict, "{0}Shape{1}Orig")]:
                shape = d.get(name)
                if shape is None:
                    continue
                shapeUUID = cmds.ls(shape, uuid=1)[0]
                cmds.parent(shape, par, shape=True, relative=True)
                newShape = cmds.rename(cmds.ls(shapeUUID)[0], fmt.format(par, name))
                d[name] = newShape
                cmds.setAttr(newShape + ".intermediateObject", 1)
                cmds.hide(newShape)

            cmds.delete(nodeDict[name])

        if toDelete:
            cmds.delete(toDelete)

        # Use the simplexDelete message attribute to keep track of what nodes
        # will need to be delete-linked when the file is reopened
        sdNode = par + ".simplexDelete"
        if not cmds.ls(sdNode):
            cmds.addAttr(par, longName="simplexDelete", attributeType="message")
        cmds.connectAttr(bsNode + ".message", sdNode)

        # build the callback setup so the blendshape is deleted with the delta setup
        # along with a persistent scriptjob
        buildDeleterCallback(par, bsNode)
        buildDeleterScriptJob()

        return shapeDict

    def _createTravDelta(self, trav, target, tVal, doReparent=True):
        """Part of the traversal extraction process.
        Very similar to the combo extraction

        Parameters
        ----------
        trav :

        target :

        tVal :


        Returns
        -------

        """
        exists = self._doesDeltaExist(trav, target)
        if exists is not None:
            return exists

        # Traversals *MAY* depend on floaters, but that's complicated
        # I'm just gonna ignore them for now
        floatShapes = [i.thing for i in self.simplex.getFloatingShapes()]

        # Get all traversal shapes
        tShapes = []
        for oTrav in self.simplex.traversals:
            tShapes.extend([i.thing for i in oTrav.prog.getShapes()])

        with disconnected(self.op) as cnx:
            sliderCnx = cnx[self.op]

            # zero all slider vals on the op
            for a in six.itervalues(sliderCnx):
                cmds.setAttr(a, 0.0)

            with disconnected(floatShapes + tShapes):
                # pull out the rest shape
                rest = cmds.duplicate(self.mesh, name="{0}_Rest".format(trav.name))[0]

                sliDict = {}
                for pair in trav.startPoint.pairs:
                    sliDict[pair.slider] = [pair.value]
                for pair in trav.endPoint.pairs:
                    sliDict[pair.slider].append(pair.value)

                for slider, (start, end) in six.iteritems(sliDict):
                    vv = start + tVal * (end - start)
                    cmds.setAttr(sliderCnx[slider.thing], vv)

                deltaObj = cmds.duplicate(
                    self.mesh, name="{0}_Delta".format(trav.name)
                )[0]
                base = cmds.duplicate(deltaObj, name="{0}_Base".format(trav.name))[0]

        # clear out all non-primary shapes so we don't have those 'Orig1' things floating around
        for item in [rest, deltaObj, base]:
            self._clearShapes(item, doOrig=True)

        # Build the delta blendshape setup
        bs = cmds.blendShape(deltaObj, name="{0}_DeltaBS".format(trav.name))[0]
        cmds.blendShape(bs, edit=True, target=(deltaObj, 0, target, 1.0))
        cmds.blendShape(bs, edit=True, target=(deltaObj, 1, base, 1.0))
        cmds.blendShape(bs, edit=True, target=(deltaObj, 2, rest, 1.0))
        cmds.setAttr("{0}.{1}".format(bs, target), 1.0)
        cmds.setAttr("{0}.{1}".format(bs, base), 1.0)
        cmds.setAttr("{0}.{1}".format(bs, rest), 1.0)

        # Cleanup
        if doReparent:
            nodeDict = dict(Delta=deltaObj)
            repDict = self._reparentDeltaShapes(target, nodeDict, bs, [rest, base])
            return repDict["Delta"]
        return deltaObj

    @undoable
    def extractTraversalShape(self, trav, shape, live=True, offset=10.0):
        """Extract a shape from a Traversal progression

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
        floatShapes = self.simplex.getFloatingShapes()
        floatShapes = [i.thing for i in floatShapes]

        shapeIdx = trav.prog.getShapeIndex(shape)
        val = trav.prog.pairs[shapeIdx].value

        # TODO: Do traversals interact? Should I turn off any other traversals?
        # For now, no, but it may be a thing
        # tShapes = []
        # for oTrav in self.simplex.traversals:
        # if oTrav is trav: continue
        # tShapes.extend([i.thing for i in oTrav.prog.getShapes()])

        with disconnected(self.op) as cnx:
            sliderCnx = cnx[self.op]
            # zero all slider vals on the op
            for a in six.itervalues(sliderCnx):
                cmds.setAttr(a, 0.0)

            with disconnected(floatShapes):  # tShapes

                sliDict = {}
                for pair in trav.startPoint.pairs:
                    sliDict[pair.slider] = [pair.value]
                for pair in trav.endPoint.pairs:
                    sliDict[pair.slider].append(pair.value)

                for slider, (start, end) in six.iteritems(sliDict):
                    vv = start + val * (end - start)
                    cmds.setAttr(sliderCnx[slider.thing], vv)

                extracted = cmds.duplicate(
                    self.mesh, name="{0}_Extract".format(shape.name)
                )
                extracted = extracted[0]
                self._clearShapes(extracted)
                cmds.xform(extracted, relative=True, translation=[offset, 0, 0])
        self.connectTraversalShape(trav, shape, extracted, live=live, delete=False)
        cmds.select(extracted)
        return extracted

    @undoable
    def connectTraversalShape(self, trav, shape, mesh=None, live=True, delete=False):
        """Connect a shape into a Traversal progression

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
        if mesh is None:
            attrName = cmds.attributeName(shape.thing, long=True)
            mesh = "{0}_Extract".format(attrName)
        shapeIdx = trav.prog.getShapeIndex(shape)
        tVal = trav.prog.pairs[shapeIdx].value
        delta = self._createTravDelta(trav, mesh, tVal)
        self.connectShape(shape, delta, live, delete)
        if delete:
            cmds.delete(mesh)

    def _createComboDelta(self, combo, target, tVal, doReparent=True):
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
        exists = self._doesDeltaExist(combo, target)
        if exists is not None:
            return exists

        # get floaters
        # As floaters can appear anywhere along any combo, they must
        # always be evaluated in isolation. For this reason, we will
        # always disconnect all floaters
        floatShapes = [i.thing for i in self.simplex.getFloatingShapes()]

        # get my shapes
        myShapes = [i.thing for i in combo.prog.getShapes()]

        with disconnected([self.op] + floatShapes + myShapes) as cnx:
            sliderCnx = cnx[self.op]

            # zero all slider vals on the op
            for a in six.itervalues(sliderCnx):
                cmds.setAttr(a, 0.0)

            # pull out the rest shape
            rest = cmds.duplicate(self.mesh, name="{0}_Rest".format(combo.name))[0]

            # set the combo values
            for pair in combo.pairs:
                cmds.setAttr(sliderCnx[pair.slider.thing], pair.value * tVal)

            # Get the resulting slider values for later
            # weightPairs = []
            # self.shapeNode = None # the deformer object

            deltaObj = cmds.duplicate(self.mesh, name="{0}_Delta".format(combo.name))[0]
            base = cmds.duplicate(deltaObj, name="{0}_Base".format(combo.name))[0]

        # clear out all non-primary shapes so we don't have those 'Orig1' things floating around
        for item in [rest, deltaObj, base]:
            self._clearShapes(item, doOrig=True)

        # Build the delta blendshape setup
        bs = cmds.blendShape(deltaObj, name="{0}_DeltaBS".format(combo.name))[0]
        cmds.blendShape(bs, edit=True, target=(deltaObj, 0, target, 1.0))
        cmds.blendShape(bs, edit=True, target=(deltaObj, 1, base, 1.0))
        cmds.blendShape(bs, edit=True, target=(deltaObj, 2, rest, 1.0))
        cmds.setAttr("{0}.{1}".format(bs, target), 1.0)
        cmds.setAttr("{0}.{1}".format(bs, base), 1.0)
        cmds.setAttr("{0}.{1}".format(bs, rest), 1.0)

        # Cleanup
        if doReparent:
            nodeDict = dict(Delta=deltaObj)
            repDict = self._reparentDeltaShapes(target, nodeDict, bs, [rest, base])
            return repDict["Delta"]
        return deltaObj

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
        floatShapes = self.simplex.getFloatingShapes()
        floatShapes = [i.thing for i in floatShapes]

        shapeIdx = combo.prog.getShapeIndex(shape)
        tVal = combo.prog.pairs[shapeIdx].value

        with disconnected(self.op) as cnx:
            sliderCnx = cnx[self.op]
            # zero all slider vals on the op
            for a in six.itervalues(sliderCnx):
                cmds.setAttr(a, 0.0)

            with disconnected(floatShapes):
                # set the combo values
                for pair in combo.pairs:
                    cmds.setAttr(sliderCnx[pair.slider.thing], pair.value * tVal)

                extracted = cmds.duplicate(
                    self.mesh, name="{0}_Extract".format(shape.name)
                )[0]
                self._clearShapes(extracted)
                cmds.xform(extracted, relative=True, translation=[offset, 0, 0])
        self.connectComboShape(combo, shape, extracted, live=live, delete=False)
        cmds.select(extracted)
        return extracted

    @undoable
    def connectComboShape(self, combo, shape, mesh=None, live=True, delete=False):
        """Connect a shape into a combo progression

        Parameters
        ----------
        combo :

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
        if mesh is None:
            attrName = cmds.attributeName(shape.thing, long=True)
            mesh = "{0}_Extract".format(attrName)
        shapeIdx = combo.prog.getShapeIndex(shape)
        tVal = combo.prog.pairs[shapeIdx].value
        delta = self._createComboDelta(combo, mesh, tVal)
        self.connectShape(shape, delta, live, delete)
        if delete:
            cmds.delete(mesh)

    @staticmethod
    def setDisabled(op):
        """

        Parameters
        ----------
        op :


        Returns
        -------

        """
        bss = list(set(cmds.listConnections(op, type="blendShape")))
        helpers = []
        for bs in bss:
            prop = "{0}.envelope".format(bs)
            val = cmds.getAttr(prop)
            cmds.setAttr(prop, 0.0)
            if val != 0.0:
                helpers.append((prop, val))
        return helpers

    @staticmethod
    def reEnable(helpers):
        """

        Parameters
        ----------
        helpers :


        Returns
        -------

        """
        for prop, val in helpers:
            cmds.setAttr(prop, val)

    @undoable
    def renameCombo(self, combo, name):
        """Set the name of a Combo

        Parameters
        ----------
        combo :

        name :


        Returns
        -------

        """
        pass

    # Data Access
    @staticmethod
    def getSimplexOperators():
        """ """
        return cmds.ls(type="simplex_maya")

    @staticmethod
    def getSimplexOperatorsByName(name):
        """

        Parameters
        ----------
        name :


        Returns
        -------
        type


        """
        return cmds.ls(name, type="simplex_maya")

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
        ops = cmds.ls(type="simplex_maya")
        out = []
        for op in ops:
            shapeNode = cmds.listConnections(
                "{0}.{1}".format(op, "shapeMsg"), source=True, destination=False
            )
            if not shapeNode:
                continue

            # Now that I've got the connected blendshape node, I can check the deformer history
            # to see if I find it. Eventually, I should probably set this up to deal with
            # multi-objects, or branched hierarchies. But for now, it works
            if shapeNode[0] in (cmds.listHistory(thing, pruneDagObjects=True) or []):
                out.append(op)
        return out

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
        return cmds.getAttr(op + ".definition")

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
        ops = DCC.getSimplexOperatorsOnObject(thing)
        for op in ops:
            js = DCC.getSimplexString(op)
            jdict = json.loads(js)
            if jdict["systemName"] == systemName:
                return js
        return None

    @staticmethod
    def setSimplexString(op, val):
        """

        Parameters
        ----------
        op :

        val :


        Returns
        -------
        type


        """
        return cmds.setAttr(op + ".definition", val, type="string")

    @staticmethod
    def selectObject(thing):
        """Select an object in the DCC

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        cmds.select([thing])

    def selectCtrl(self):
        """Select the system's control object"""
        if self.ctrl:
            self.selectObject(self.ctrl)

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
        objs = cmds.ls(name)
        if not objs:
            return None
        return objs[0]

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
        return thing

    @staticmethod
    def staticUndoOpen():
        """ """
        cmds.undoInfo(chunkName="SimplexOperation", openChunk=True)

    @staticmethod
    def staticUndoClose():
        """ """
        cmds.undoInfo(closeChunk=True)

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

    @classmethod
    def getPersistentFalloff(cls, thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        return cls.getObjectName(thing)

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
        return cls.getObjectName(thing)

    @classmethod
    def loadPersistentShape(cls, thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        return cls.getObjectByName(thing)

    @classmethod
    def getPersistentSlider(cls, thing):
        """

        Parameters
        ----------
        thing :


        Returns
        -------

        """
        return cls.getObjectName(thing)

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

    @staticmethod
    def getSelectedObjects():
        """ """
        # For maya, only return transform nodes
        return cmds.ls(sl=True, transforms=True)

    @undoable
    def importObj(self, path):
        """

        Parameters
        ----------
        path :


        Returns
        -------

        """
        current = set(cmds.ls(transforms=True))
        cmds.file(path, i=True, type="OBJ", ignoreVersion=True)
        new = set(cmds.ls(transforms=True))
        shapes = set(cmds.ls(shapes=True))
        new = new - current - shapes
        imp = new.pop()
        return imp

    @staticmethod
    def _getDeformerChain(chkObj):
        # Get a deformer chain
        memo = []
        while chkObj and chkObj not in memo:
            memo.append(chkObj)

            typ = cmds.nodeType(chkObj)
            if typ == "mesh":
                cnx = cmds.listConnections(chkObj + ".inMesh") or [None]
                chkObj = cnx[0]
            elif typ == "groupParts":
                cnx = cmds.listConnections(
                    chkObj + ".inputGeometry", destination=False, shapes=True
                ) or [None]
                chkObj = cnx[0]
            else:
                cnx = cmds.ls(chkObj, type="geometryFilter") or [None]
                chkObj = cnx[0]
                if chkObj:  # we have a deformer
                    cnx = cmds.listConnections(chkObj + ".input[0].inputGeometry") or [
                        None
                    ]
                    chkObj = cnx[0]
        return memo

    # Freezing stuff
    def primeShapes(self, combo):
        """Make sure the upstream shapes of this combo are primed and ready.
        Priming here means the deltas are stored and available on the blendshape node
        """
        # Maya doesn't populate the delta plugs on the blendshape node unless
        # you have a mesh connection while the value for that shape is turned to 1
        upstreams = []
        comboUps = self.simplex.getComboUpstreams(combo)
        for u in comboUps:
            upstreams.append(u.prog.getShapeAtValue(1.0))
        for pair in combo.pairs:
            sli, val = pair.slider, pair.value
            upstreams.append(sli.prog.getShapeAtValue(val))

        with disconnected(self.shapeNode) as cnx:
            shapeCnx = cnx[self.shapeNode]
            for v in six.itervalues(shapeCnx):
                cmds.setAttr(v, 0.0)

            for shape in upstreams:
                cmds.setAttr(shape.thing, 1.0)
                try:
                    # Make sure to check for any already incoming connections
                    index = self.getShapeIndex(shape)
                    tgn = "{0}.inputTarget[0].inputTargetGroup[{1}]".format(
                        self.shapeNode, index
                    )
                    isConnected = cmds.listConnections(
                        tgn, source=True, destination=False
                    )

                    if not isConnected:
                        shapeGeo = cmds.duplicate(self.mesh, name=shape.name)[0]
                        shape.connectShape(mesh=shapeGeo, live=False, delete=True)

                finally:
                    cmds.setAttr(shape.thing, 0.0)

    def getFreezeThing(self, combo):
        # If the blendshape shape has an incoming connection whose shape name
        # ends with 'FreezeShape' and the shape's parent is the ctrl
        ret = []
        shapes = combo.prog.getShapes()
        shapes = [i for i in shapes if not i.isRest]

        shapePlugFmt = (
            ".inputTarget[{meshIdx}].inputTargetGroup[{shapeIdx}].inputTargetItem[6000]"
        )

        for shape in shapes:
            shpIdx = self.getShapeIndex(shape)
            shpPlug = (
                self.shapeNode
                + shapePlugFmt.format(meshIdx=0, shapeIdx=shpIdx)
                + ".inputGeomTarget"
            )

            cnx = cmds.listConnections(shpPlug, shapes=True, destination=False) or []
            for cc in cnx:
                if not cc.endswith("FreezeShape"):
                    continue
                par = cmds.listRelatives(cc, parent=True)
                if par and par[0] == self.ctrl:
                    # Can't use list history to get the chain because it's a pseudo-cycle
                    ret.extend(self._getDeformerChain(cc))

        if ret:
            self.primeShapes(combo)

        return ret


class SliderDispatch(QtCore.QObject):
    valueChanged = Signal()

    def __init__(self, node, parent=None):
        super(SliderDispatch, self).__init__(parent)
        mObject = getMObject(node)
        self.callbackID = om.MNodeMessage.addAttributeChangedCallback(
            mObject, self.emitValueChanged
        )

    def emitValueChanged(self, *args, **kwargs):
        self.valueChanged.emit()

    def disconnectCallbacks(self):
        om.MMessage.removeCallback(self.callbackID)
        self.callbackID = None

    def __del__(self):
        self.disconnectCallbacks()


class Dispatch(QtCore.QObject):
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
        if self.callbackIDs:
            self.disconnectCallbacks()

        self.callbackIDs.append(
            om.MSceneMessage.addCallback(
                om.MSceneMessage.kBeforeNew, self.emitBeforeNew
            )
        )
        self.callbackIDs.append(
            om.MSceneMessage.addCallback(om.MSceneMessage.kAfterNew, self.emitAfterNew)
        )
        self.callbackIDs.append(
            om.MSceneMessage.addCallback(
                om.MSceneMessage.kBeforeOpen, self.emitBeforeOpen
            )
        )
        self.callbackIDs.append(
            om.MSceneMessage.addCallback(
                om.MSceneMessage.kAfterOpen, self.emitAfterOpen
            )
        )
        self.callbackIDs.append(
            om.MEventMessage.addEventCallback("Undo", self.emitUndo)
        )
        self.callbackIDs.append(
            om.MEventMessage.addEventCallback("Redo", self.emitRedo)
        )

    def disconnectCallbacks(self):
        for i in self.callbackIDs:
            om.MMessage.removeCallback(i)
        self.callbackIDs = []

    def emitBeforeNew(self, *args, **kwargs):
        self.beforeNew.emit()

    def emitAfterNew(self, *args, **kwargs):
        self.afterNew.emit()

    def emitBeforeOpen(self, *args, **kwargs):
        self.beforeOpen.emit()

    def emitAfterOpen(self, *args, **kwargs):
        self.afterOpen.emit()

    def emitUndo(self, *args, **kwargs):
        self.undo.emit()

    def emitRedo(self, *args, **kwargs):
        self.redo.emit()

    def __del__(self):
        self.disconnectCallbacks()


DISPATCH = Dispatch()


def rootWindow():
    """Returns the currently active QT main window
    Only works for QT UI's like Maya
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


SIMPLEX_RESET_SCRIPTJOB = """
import maya.cmds as cmds
import maya.OpenMaya as om

def simplexDelCB(node, dgMod, clientData):
    xNode, dName = clientData
    dNode = getMObject(dName)
    if dNode and not dNode.isNull():
        dgMod.deleteNode(dNode)

def getMObject(name):
    selected = om.MSelectionList()
    try:
        selected.add(name, True)
    except RuntimeError:
        return None
    if selected.isEmpty():
        return None
    thing = om.MObject()
    selected.getDependNode(0, thing)
    return thing

# get all .simplexDelete message attributes
delAttrs = cmds.ls("*.simplexDelete")
if delAttrs:
    # get all their connections
    cnx = cmds.listConnections(delAttrs, plugs=True, connections=True, destination=False)

    # Set up the deletion callback
    mmIds = []
    for i in range(0, len(cnx), 2):
        parName, delName = cmds.ls(cnx[i:i+2], long=True, objectsOnly=True)
        pNode = getMObject(parName)
        dNode = getMObject(delName)
        om.MNodeMessage.addNodeAboutToDeleteCallback(pNode, simplexDelCB, (dNode, delName))
"""


def buildDeleterScriptJob():
    dcbName = "SimplexDeleterCallback"
    if not cmds.ls(dcbName):
        cmds.scriptNode(
            scriptType=1,
            beforeScript=SIMPLEX_RESET_SCRIPTJOB,
            name=dcbName,
            sourceType="python",
        )


def simplexDelCB(node, dgMod, clientData):
    xNode, dName = clientData
    dNode = getMObject(dName)
    if dNode and not dNode.isNull():
        dgMod.deleteNode(dNode)


def getMObject(name):
    selected = om.MSelectionList()
    try:
        selected.add(name, True)
    except RuntimeError:
        return None
    if selected.isEmpty():
        return None
    thing = om.MObject()
    selected.getDependNode(0, thing)
    return thing


def buildDeleterCallback(parName, delName):
    pNode = getMObject(parName)
    dNode = getMObject(delName)
    idNum = om.MNodeMessage.addNodeAboutToDeleteCallback(
        pNode, simplexDelCB, (dNode, delName)
    )
    return idNum
