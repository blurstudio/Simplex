import textwrap
import maya.cmds as cmds
from Qt.QtWidgets import QAction, QMessageBox


def register(window, menu):
	updateRestShapeACT = QAction("Update Rest Shape", window)
	menu.addAction(updateRestShapeACT)
	updateRestShapeACT.triggered.connect(updateRestShapeInterface)

def updateRestShapeInterface(self):
	sel = cmds.ls(sl=True)
	if not sel:
		QMessageBox.warning(self.window, "Nothing Selected", "Nothing Selected")
		return
	sel = sel[0]
	mesh = self.system.DCC.mesh

	# TODO, Check vert number and blendshape input connections
	selVerts = cmds.polyEvaluate(sel, vertex=1)
	meshVerts = cmds.polyEvaluate(mesh, vertex=1)

	if selVerts != meshVerts:
		msg = "Selected object {0} has {1} verts\nBase Object has {2} verts".format(sel, selVerts, meshVerts)
		QMessageBox.warning(self.window, "Vert Mismatch", msg)
		return

	# TODO Check for live connections
	bs = self.system.DCC.shapeNode
	cnx = cmds.listConnections(bs, plugs=1, destination=0, type='mesh')
	if cnx:
		cnxs = ', '.join([i.split('.')[0] for i in cnx])
		cnxs = textwrap.fill(cnxs)
		msg = ["Some shapes have a live input connection:", cnxs, "",
			"These shapes will not get the update.", "Continue anyway?"]
		msg = '\n'.join(msg)
		btns = QMessageBox.Ok | QMessageBox.Cancel
		bret = QMessageBox.question(self.window, "Live Connections", msg, btns)
		if not bret & QMessageBox.Ok:
			return

	updateRestShape(mesh, sel)


def updateRestShape(mesh, newRest):
	allShapes = cmds.listRelatives(mesh, children=1, shapes=1) or []
	noInter = cmds.listRelatives(mesh, children=1, shapes=1, noIntermediate=1) or []
	inter = list(set(allShapes) - set(noInter))
	if not inter:
		return

	if len(inter) == 1:
		orig = inter[0]
	else:
		origs = [i for i in inter if i.endswith('Orig')]
		if len(origs) != 1:
			return
		orig = origs[0]

	outMesh = '{0}.worldMesh[0]'.format(newRest)
	inMesh = '{0}.inMesh'.format(orig)

	cmds.connectAttr(outMesh, inMesh, force=1)
	cmds.refresh(force=1)
	cmds.disconnectAttr(outMesh, inMesh)

