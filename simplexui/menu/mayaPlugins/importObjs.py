from __future__ import absolute_import

import os
from functools import partial

import maya.cmds as cmds
import six

from ...items import Combo, Slider, Traversal
from ...Qt.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
)

try:
    import numpy as np
except ImportError:
    np = None

try:
    from MeshCrawler.commands import setAllVerts
    from MeshCrawler.mesh import Mesh
    from MeshCrawler.meshcrawlerGen import autoCrawlMeshes
except ImportError:
    autoCrawlMeshes = None


def buildMesh(simplex, mesh):
    topo = simplex.DCC.getMeshTopology(mesh)
    faceIdxs, counts = topo[1], topo[2]
    faces = []
    ptr = 0
    for c in counts:
        faces.append(tuple(faceIdxs[ptr : ptr + c]))
        ptr += c
    return Mesh(topo[0], tuple(faces))


def importSimpleObjs(simplex, orders, pBar):
    for shapeName, ctrl, shape, path in orders:
        pBar.setValue(pBar.value() + 1)
        pBar.setLabelText("Loading Obj :\n{0}".format(shapeName))
        QApplication.processEvents()
        if pBar.wasCanceled():
            return

        mesh = simplex.DCC.importObj(path)

        if isinstance(ctrl, Slider):
            simplex.DCC.connectShape(shape, mesh=mesh, live=False, delete=True)
        elif isinstance(ctrl, Combo):
            simplex.DCC.connectComboShape(
                ctrl, shape, mesh=mesh, live=False, delete=True
            )
        elif isinstance(ctrl, Traversal):
            simplex.DCC.connectTraversalShape(
                ctrl, shape, mesh=mesh, live=False, delete=True
            )


def importReorderObjs(simplex, orders, pBar):
    reoMesh = simplex.DCC.extractShape(simplex.restShape, live=False)
    orderMesh = buildMesh(simplex, reoMesh)

    memo = {}

    for shapeName, ctrl, shape, path in orders:
        pBar.setValue(pBar.value() + 1)
        pBar.setLabelText("Loading Obj :\n{0}".format(shapeName))
        QApplication.processEvents()
        if pBar.wasCanceled():
            return

        impMesh = simplex.DCC.importObj(path)
        objMesh = buildMesh(simplex, impMesh)
        reo = memo.setdefault(
            objMesh.faceVertArray, autoCrawlMeshes(orderMesh, objMesh)
        )
        verts = simplex.DCC.getNumpyShape(impMesh)

        setAllVerts(reoMesh, verts[reo])

        if isinstance(ctrl, Slider):
            simplex.DCC.connectShape(shape, mesh=reoMesh, live=False, delete=False)
        elif isinstance(ctrl, Combo):
            simplex.DCC.connectComboShape(
                ctrl, shape, mesh=reoMesh, live=False, delete=False
            )
        elif isinstance(ctrl, Traversal):
            simplex.DCC.connectTraversalShape(
                ctrl, shape, mesh=reoMesh, live=False, delete=False
            )

    cmds.delete(reoMesh)


def importObjList(simplex, paths, pBar, reorder=True):
    """Import all given .obj files

    Parameters
    ----------
    paths : list
        The list of .obj files to import
    """
    shapeDict = {shape.name: shape for shape in simplex.shapes}

    inPairs = {}
    for path in paths:
        shapeName = os.path.splitext(os.path.basename(path))[0]
        shape = shapeDict.get(shapeName)
        if shape is not None:
            inPairs[shapeName] = path
        else:
            sfx = "_Extract"
            if shapeName.endswith(sfx):
                shapeName = shapeName[: -len(sfx)]
                shape = shapeDict.get(shapeName)
                if shape is not None:
                    inPairs[shapeName] = path

    sliderMasters, comboMasters, travMasters = {}, {}, {}
    for masters in [simplex.sliders, simplex.combos, simplex.traversals]:
        for master in masters:
            for pp in master.prog.pairs:
                shape = shapeDict.get(pp.shape.name)
                if shape is not None:
                    if shape.name in inPairs:
                        if isinstance(master, Slider):
                            sliderMasters[shape.name] = master
                        elif isinstance(master, Combo):
                            comboMasters[shape.name] = master
                        elif isinstance(master, Traversal):
                            travMasters[shape.name] = master

    comboDepth = {}
    for k, v in six.iteritems(comboMasters):
        depth = len(v.pairs)
        comboDepth.setdefault(depth, {})[k] = v

    importOrder = []
    for shapeName, slider in six.iteritems(sliderMasters):
        importOrder.append(
            (shapeName, slider, shapeDict[shapeName], inPairs[shapeName])
        )

    for depth in sorted(comboDepth.keys()):
        for shapeName, combo in six.iteritems(comboDepth[depth]):
            importOrder.append(
                (shapeName, combo, shapeDict[shapeName], inPairs[shapeName])
            )

    for shapeName, trav in six.iteritems(travMasters):
        importOrder.append((shapeName, trav, shapeDict[shapeName], inPairs[shapeName]))

    if pBar is not None:
        pBar.setMaximum(len(sliderMasters) + len(comboMasters) + len(travMasters))

    if reorder:
        importReorderObjs(simplex, importOrder, pBar)
    else:
        importSimpleObjs(simplex, importOrder, pBar)

    pBar.close()


def registerTool(window, menu):
    importObjsACT = QAction("Import Obj Folder", window)
    menu.addAction(importObjsACT)
    importObjsACT.triggered.connect(partial(importObjsInterface, window))


def importObjsInterface(window):
    reorder = True
    if np is None or autoCrawlMeshes is None:
        reorder = False

    folder = QFileDialog.getExistingDirectory(window, "Import Obj Folder", "")

    if not os.path.isdir(folder):
        QMessageBox.warning(window, "Warning", "Folder does not exist")
        return

    paths = os.listdir(folder)
    paths = [i for i in paths if i.endswith((".obj", ".OBJ"))]
    if not paths:
        QMessageBox.warning(window, "Warning", "Folder does not contain any .obj files")
        return
    paths = [os.path.join(folder, p) for p in paths]

    pBar = QProgressDialog("Loading from Mesh", "Cancel", 0, 100, window)
    pBar.show()

    importObjList(window.simplex, paths, pBar=pBar, reorder=reorder)
