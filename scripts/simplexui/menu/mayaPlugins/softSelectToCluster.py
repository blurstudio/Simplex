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

from __future__ import absolute_import, print_function

import maya.cmds as cmds
import maya.OpenMaya as om
from six.moves import range

from ...Qt.QtWidgets import QAction


def registerTool(window, menu):
    softSelectToClusterACT = QAction("Soft Select To Cluster", window)
    menu.addAction(softSelectToClusterACT)
    softSelectToClusterACT.triggered.connect(softSelectToClusterInterface)


def softSelectToClusterInterface():
    sel = cmds.ls(sl=True, objectsOnly=True)
    if sel:
        name = sel[0].split('|')[-1]
        softSelectToCluster(sel[0], "{0}_Soft".format(name))


def getSoftSelectionValues(myNode, returnSimpleIndices=True):
    """Get the current soft selection values"""
    softOn = cmds.softSelect(query=True, softSelectEnabled=True)
    richSelList = om.MSelectionList()

    if softOn:
        richSel = om.MRichSelection()
        try:
            om.MGlobal.getRichSelection(richSel)
        except RuntimeError:
            return []
        richSel.getSelection(richSelList)
    else:
        om.MGlobal.getActiveSelectionList(richSelList)
    toReturn = {}
    if richSelList.isEmpty():
        return toReturn

    uVal = om.MScriptUtil()
    uVal.createFromInt(0)
    ptru = uVal.asIntPtr()

    vVal = om.MScriptUtil()
    vVal.createFromInt(0)
    ptrv = vVal.asIntPtr()

    wVal = om.MScriptUtil()
    wVal.createFromInt(0)
    ptrw = wVal.asIntPtr()

    iterSel = om.MItSelectionList(richSelList)

    while not iterSel.isDone():
        component = om.MObject()
        dagPath = om.MDagPath()
        try:
            iterSel.getDagPath(dagPath, component)
        except Exception:
            iterSel.next()
            continue

        depNode_name = dagPath.fullPathName()

        # hack in a quick check so it only works with
        # shapes under the given transform
        if not depNode_name.startswith(myNode):
            iterSel.next()
            continue

        elementIndices = []
        elementWeights = []

        if component.isNull():
            toReturn[depNode_name] = (elementIndices, elementWeights)
            continue

        componentFn = om.MFnComponent(component)
        count = componentFn.elementCount()
        ctyp = componentFn.componentType()

        if ctyp == om.MFn.kMeshPolygonComponent:
            polyIter = om.MItMeshPolygon(dagPath, component)
            setOfVerts = set()
            while not polyIter.isDone():
                connectedVertices = om.MIntArray()
                polyIter.getVertices(connectedVertices)
                for j in range(connectedVertices.length()):
                    setOfVerts.add(connectedVertices[j])
                polyIter.next()
            lstVerts = list(setOfVerts)
            lstVerts.sort()
            for vtx in lstVerts:
                elementIndices.append(vtx)
                elementWeights.append(1)
        elif ctyp == om.MFn.kMeshEdgeComponent:
            edgeIter = om.MItMeshEdge(dagPath, component)
            setOfVerts = set()
            while not edgeIter.isDone():
                setOfVerts.add(edgeIter.index(0))
                setOfVerts.add(edgeIter.index(1))
                edgeIter.next()
            lstVerts = list(setOfVerts)
            lstVerts.sort()
            for vtx in lstVerts:
                elementIndices.append(vtx)
                elementWeights.append(1)
        elif ctyp in (om.MFn.kCurveCVComponent, om.MFn.kMeshVertComponent):
            singleFn = om.MFnSingleIndexedComponent(component)
            for i in range(count):
                weight = componentFn.weight(i).influence() if softOn else 1
                elementIndices.append(singleFn.element(i))
                elementWeights.append(weight)
        elif ctyp == om.MFn.kSurfaceCVComponent:
            spansV = cmds.getAttr(depNode_name + ".spansV")
            degreesV = cmds.getAttr(depNode_name + ".degreeV")
            numCVsInV_ = spansV + degreesV

            doubleFn = om.MFnDoubleIndexedComponent(component)
            for i in range(count):
                weight = componentFn.weight(i).influence() if softOn else 1
                doubleFn.getElement(i, ptru, ptrv)
                u = uVal.getInt(ptru)
                v = vVal.getInt(ptrv)
                if returnSimpleIndices:
                    elementIndices.append(numCVsInV_ * u + v)
                else:
                    elementIndices.append((u, v))
                elementWeights.append(weight)
        elif ctyp == om.MFn.kLatticeComponent:
            div_s = cmds.getAttr(depNode_name + ".sDivisions")
            div_t = cmds.getAttr(depNode_name + ".tDivisions")
            div_u = cmds.getAttr(depNode_name + ".uDivisions")

            tripleFn = om.MFnTripleIndexedComponent(component)
            for i in range(count):
                tripleFn.getElement(i, ptru, ptrv, ptrw)
                s = uVal.getInt(ptru)
                t = vVal.getInt(ptrv)
                u = wVal.getInt(ptrw)
                weight = componentFn.weight(i).influence() if softOn else 1

                if returnSimpleIndices:
                    simpleIndex = (u * div_s * div_t) + (t * div_s) + s
                    elementIndices.append(simpleIndex)
                else:
                    elementIndices.append((s, t, u))
                elementWeights.append(weight)

        toReturn[depNode_name] = (elementIndices, elementWeights)
        iterSel.next()
    return toReturn


def softSelectToCluster(tfm, name):
    # Get the manipulator position for the selection
    cmds.setToolTo("Move")
    currentMoveMode = cmds.manipMoveContext("Move", query=True, mode=True)
    cmds.manipMoveContext("Move", edit=True, mode=0)  # set to the correct mode
    pos = cmds.manipMoveContext("Move", query=True, position=True)  # get the position
    cmds.manipMoveContext("Move", edit=True, mode=currentMoveMode)  # and reset

    tfm = cmds.ls(tfm, long=True)[0]
    vnum = cmds.polyEvaluate(tfm, vertex=True)
    softSelDict = getSoftSelectionValues(tfm)

    shapes = [k for k in softSelDict if k.startswith(tfm)]
    if not shapes:
        print("No selection found on the given mesh: {0}".format(tfm))
        return

    elementIndices, elementWeights = softSelDict[shapes[0]]
    weightDict = dict(zip(elementIndices, elementWeights))
    weights = [weightDict.get(i, 0.0) for i in range(vnum)]

    # Build the Cluster and set the weights
    # Currently this part is polymesh specific
    clusterNode, clusterHandle = cmds.cluster(tfm, name=name)
    attr = "{0}.weightList[0].weights[0:{1}]".format(clusterNode, vnum - 1)
    cmds.setAttr(attr, *weights, size=vnum)

    # Reposition the cluster
    cmds.xform(clusterHandle, absolute=True, worldSpace=True, pivots=pos)
    clusterShape = cmds.listRelatives(clusterHandle, children=True, shapes=True)
    cmds.setAttr(clusterShape[0] + ".origin", *pos)

