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

from __future__ import absolute_import

from functools import partial

import six
from six.moves import zip

from maya import cmds

from ...interface.mayaInterface import disconnected
from ...interfaceModel import coerceIndexToType
from ...items import Combo


# UI stuff
def registerContext(tree, clickIdx, indexes, menu):
    # The basicBlendshape deformer is included in simplex_maya
    if not cmds.pluginInfo("simplex_maya", query=True, loaded=True):
        try:
            cmds.loadPlugin("simplex_maya")
        except RuntimeError:
            return False

    comboIdxs = coerceIndexToType(indexes, Combo)
    combos = [cidx.model().itemFromIndex(cidx) for cidx in comboIdxs]

    if combos:
        freezeAct = menu.addAction("Freeze Combos")
        unfreezeAct = menu.addAction("Un-Freeze Combos")
        freezeAct.triggered.connect(partial(freezeCombosContext, combos, tree, True))
        unfreezeAct.triggered.connect(partial(freezeCombosContext, combos, tree, False))
        return True
    return False


def freezeCombosContext(combos, tree, doFreeze):
    if doFreeze:
        for combo in combos:
            if not combo.frozen:
                freezeCombo(combo)
    else:
        for combo in combos:
            if combo.frozen:
                unfreezeCombo(combo)

    tree.update()


def freezeCombo(combo):
    """Freeze a combo so you can change the upstream combos and shapes
    without affecting the result that you sculpted for the given combo

    In practice, this snapshots the combo, then live-reads the upstream
    shapes from the main blendshape and builds an up-to-date combo. The
    difference between these two meshes is added back into the combo shape
    """
    simplex = combo.simplex

    tweakShapeGroups = []
    fullGeos = []
    ppFilter = []
    freezeShapes = []

    # disconnect the controller from the operator
    with disconnected(simplex.DCC.op) as sliderCnx:
        for shapeIdx, pp in enumerate(combo.prog.pairs):
            tVal = pp.value
            freezeShape = pp.shape
            if freezeShape.isRest:
                continue

            freezeShapes.append(freezeShape)
            # zero all the sliders
            cnx = sliderCnx[simplex.DCC.op]
            for a in six.itervalues(cnx):
                cmds.setAttr(a, 0.0)

            # set the combo values
            for pair in combo.pairs:
                cmds.setAttr(cnx[pair.slider.thing], pair.value * tVal)

            tweakPairs = []
            for shape in simplex.shapes[1:]:  # skip the restShape
                shapeVal = cmds.getAttr(shape.thing)
                if abs(shapeVal) > 0.0001:
                    tweakPairs.append((shape, shapeVal))

            # Extract this fully-on shape
            fullGeo = cmds.duplicate(
                simplex.DCC.mesh, name="{0}_Freeze".format(freezeShape.name)
            )[0]
            fullGeos.append(fullGeo)

            # Clean any orig shapes for now
            interObjs = cmds.ls(
                cmds.listRelatives(fullGeo, shapes=True), intermediateObjects=True
            )
            cmds.delete(interObjs)

            tweakShapeGroups.append(tweakPairs)
            ppFilter.append(pp)

    simplex.DCC.primeShapes(combo)

    shapePlugFmt = (
        ".inputTarget[{meshIdx}].inputTargetGroup[{shapeIdx}].inputTargetItem[6000]"
    )
    endPlugs = [
        ".inputRelativePointsTarget",
        ".inputRelativeComponentsTarget",
        ".inputPointsTarget",
        ".inputComponentsTarget",
        "",
    ]
    shapeNode = simplex.DCC.shapeNode
    helpers = []
    for geo, tweakPairs, pp, freezeShape in zip(
        fullGeos, tweakShapeGroups, ppFilter, freezeShapes
    ):
        # build the basicBS node
        bbs = cmds.deformer(geo, type="basicBlendShape")[0]
        helpers.append(bbs)
        idx = 0

        for shape, val in tweakPairs:
            if shape == freezeShape:
                continue
            # connect the output shape.thing to the basicBS

            # Create an empty shape. Do it like this to get the automated renaming stuff
            gDup = cmds.duplicate(geo, name="{0}_DeltaCnx".format(shape.name))[0]
            # The 4th value must be 1.0 so the blendshape auto-names
            cmds.blendShape(bbs, edit=True, target=(geo, idx, gDup, 1.0))
            cmds.blendShape(bbs, edit=True, weight=(idx, -val))
            cmds.delete(gDup)

            # Connect the shape plugs
            inPlug = bbs + shapePlugFmt
            inPlug = inPlug.format(meshIdx=0, shapeIdx=idx)

            shapeIdx = simplex.DCC.getShapeIndex(shape)
            outPlug = shapeNode + shapePlugFmt
            outPlug = outPlug.format(meshIdx=0, shapeIdx=shapeIdx)

            # Must connect the individual child plugs rather than the top
            # because otherwise the input geometry plug overrides these deltas
            for ep in endPlugs:
                cmds.connectAttr(outPlug + ep, inPlug + ep)

            idx += 1

        # Connect the basicBS back into freezeShape
        freezeShapeIdx = simplex.DCC.getShapeIndex(pp.shape)
        freezeShapeTarget = shapeNode + shapePlugFmt + ".inputGeomTarget"
        freezeShapeTarget = freezeShapeTarget.format(meshIdx=0, shapeIdx=freezeShapeIdx)
        cmds.connectAttr(geo + ".outMesh", freezeShapeTarget)

        gShapes = cmds.listRelatives(geo, shapes=True)
        if True:
            # Hide the frozen shapenode under the ctrl as an intermediate shape
            for gs in gShapes:
                cmds.setAttr(gs + ".intermediateObject", 1)
                nn = cmds.parent(gs, simplex.DCC.ctrl, shape=True, relative=True)
                helpers.extend(nn)

            # Get rid of the extra transform object
            cmds.delete(geo)
        else:
            helpers.extend(cmds.listRelatives(geo, shapes=True))

    # keep track of the shapes under the ctrl object
    combo.freezeThing = helpers


def unfreezeCombo(combo):
    if combo.freezeThing:
        cmds.delete(combo.freezeThing)
    combo.freezeThing = []


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
                cnx = cmds.listConnections(chkObj + ".input[0].inputGeometry") or [None]
                chkObj = cnx[0]
    return memo


def checkFrozen(combo):
    # If the blendshape shape has an incoming connection whose shape name
    # ends with 'FreezeShape' and the shape's parent is the ctrl
    #
    simplex = combo.simplex

    ret = []
    shapes = combo.prog.getShapes()
    shapes = [i for i in shapes if not i.isRest]

    shapePlugFmt = (
        ".inputTarget[{meshIdx}].inputTargetGroup[{shapeIdx}].inputTargetItem[6000]"
    )

    for shape in shapes:
        shpIdx = simplex.DCC.getShapeIndex(shape)
        shpPlug = (
            simplex.DCC.shapeNode
            + shapePlugFmt.format(meshIdx=0, shapeIdx=shpIdx)
            + ".inputGeomTarget"
        )

        cnx = cmds.listConnections(shpPlug, shapes=True, destination=False) or []
        for cc in cnx:
            if not cc.endswith("FreezeShape"):
                continue
            par = cmds.listRelatives(cc, parent=True)
            if par and par[0] == simplex.DCC.ctrl:
                # Can't use list history to get the chain because it's a pseudo-cycle
                ret.extend(_getDeformerChain(cc))
    return ret

