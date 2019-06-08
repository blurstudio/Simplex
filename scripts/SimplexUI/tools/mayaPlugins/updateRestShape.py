import textwrap
import maya.cmds as cmds
from ...Qt.QtWidgets import QAction, QMessageBox
from functools import partial

def registerTool(window, menu):
	updateRestShapeACT = QAction("Update Rest Shape", window)
	menu.addAction(updateRestShapeACT)
	updateRestShapeACT.triggered.connect(partial(updateRestShapeInterface, window))

def updateRestShapeInterface(window):
	sel = cmds.ls(sl=True)
	if not sel:
		QMessageBox.warning(window, "Nothing Selected", "Nothing Selected")
		return
	sel = sel[0]
	mesh = window.simplex.DCC.mesh

	# TODO, Check vert number and blendshape input connections
	selVerts = cmds.polyEvaluate(sel, vertex=1)
	meshVerts = cmds.polyEvaluate(mesh, vertex=1)

	if selVerts != meshVerts:
		msg = "Selected object {0} has {1} verts\nBase Object has {2} verts".format(sel, selVerts, meshVerts)
		QMessageBox.warning(window, "Vert Mismatch", msg)
		return

	# TODO Check for live connections
	bs = window.simplex.DCC.shapeNode
	cnx = cmds.listConnections(bs, plugs=1, destination=0, type='mesh')
	if cnx:
		cnxs = ', '.join([i.split('.')[0] for i in cnx])
		cnxs = textwrap.fill(cnxs)
		msg = ["Some shapes have a live input connection:", cnxs, "",
			"These shapes will not get the update.", "Continue anyway?"]
		msg = '\n'.join(msg)
		btns = QMessageBox.Ok | QMessageBox.Cancel
		bret = QMessageBox.question(window, "Live Connections", msg, btns)
		if not bret & QMessageBox.Ok:
			return

	updateRestShape(mesh, sel, window=window)

def updateRestShape(mesh, newRest, window=None):
	allShapes = cmds.listRelatives(mesh, children=1, shapes=1) or []
	noInter = cmds.listRelatives(mesh, children=1, shapes=1, noIntermediate=1) or []
	hist = cmds.listHistory(mesh)
	inter = (set(allShapes) - set(noInter)) & set(hist)
	if not inter:
		if window is not None:
			QMessageBox.warning(window, "No Intermediates", "No intermediate meshes found")
		return
	inter = list(inter)

	if len(inter) == 1:
		orig = inter[0]
	else:
		origs = [i for i in inter if 'Orig' in i]
		if len(origs) != 1:
			if window is not None:
				QMessageBox.warning(window, "Too Many Intermediates", "Too Many intermediate meshes found: {0}".format(origs))
			return
		orig = origs[0]

	outMesh = '{0}.worldMesh[0]'.format(newRest)
	inMesh = '{0}.inMesh'.format(orig)

	cmds.connectAttr(outMesh, inMesh, force=1)
	cmds.refresh(force=1)
	cmds.disconnectAttr(outMesh, inMesh)

