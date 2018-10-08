import maya.cmds as cmds
import maya.OpenMaya as om

from Qt.QtWidgets import QAction

def registerTool(window, menu):
	softSelectToClusterACT = QAction("Soft Select To Cluster", window)
	menu.addAction(softSelectToClusterACT)
	softSelectToClusterACT.triggered.connect(softSelectToClusterInterface)

def softSelectToClusterInterface(self):
	sel = cmds.ls(sl=True, objectsOnly=True)
	if sel:
		softSelectToCluster(sel[0], "{0}_Soft".format(sel[0]))

def softSelectToCluster(mesh, name):
	# Get the manipulator position for the selection
	cmds.setToolTo('Move')
	currentMoveMode = cmds.manipMoveContext('Move', query=True, mode=True) #Get the original mode
	cmds.manipMoveContext('Move', edit=True, mode=0) #set to the correct mode
	pos = cmds.manipMoveContext('Move', query=True, position=True) # get the position
	cmds.manipMoveContext('Move', edit=True, mode=currentMoveMode) # and reset

	# Grab the soft selection values using the API
	selection = om.MSelectionList()
	ssel = om.MRichSelection()
	ssel.getSelection(selection)

	dagPath = om.MDagPath()
	component = om.MObject()

	vertIter = om.MItSelectionList(selection, om.MFn.kMeshVertComponent)
	weights = []

	# TODO Be a bit more explicit here with the mesh, its shapeNode, and the dagPath
	# so we can make sure we don't have multiple meshes with verts selected

	softSel = {}
	while not vertIter.isDone():
		vertIter.getDagPath(dagPath, component)
		dagPath.pop() #Grab the parent of the shape node
		#node = dagPath.fullPathName()
		fnComp = om.MFnSingleIndexedComponent(component)
		getWeight = lambda i: fnComp.weight(i).influence() if fnComp.hasWeights() else 1.0

		for i in range(fnComp.elementCount()):
			softSel[fnComp.element(i)] = getWeight(i)
		vertIter.next()

	if not softSel:
		print "No Soft Selection"
		return

	# Build the Cluster and set the weights
	clusterNode, clusterHandle = cmds.cluster(mesh, name=name)
	vnum = cmds.polyEvaluate(mesh, vertex=1)
	weights = [softSel.get(i, 0.0) for i in range(vnum)]
	cmds.setAttr('{0}.weightList[0].weights[0:{1}]'.format(clusterNode, vnum-1), *weights, size=vnum)

	# Reposition the cluster
	cmds.xform(clusterHandle, a=True, ws=True, piv=(pos[0], pos[1], pos[2]))
	clusterShape = cmds.listRelatives(clusterHandle, children=True, shapes=True)
	cmds.setAttr(clusterShape[0] + '.origin', pos[0], pos[1], pos[2])


