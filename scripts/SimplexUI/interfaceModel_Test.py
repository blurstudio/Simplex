import os, sys, json
from interfaceModel import *
from Qt.QtWidgets import QTreeView, QApplication, QPushButton, QVBoxLayout, QWidget


# HELPERS
def expandRecursive(view, model, index=QModelIndex(), depth=0):
	''' helper to expand the whole tree '''
	view.setExpanded(index, True)
	rows = model.rowCount(index)

	item = model.itemFromIndex(index)
	print "   "*depth + "Name {0}, children {1}".format(item.name if item else None, rows)
	print "   "*depth + "Depth {0}, Row {1}, Col {2}".format(depth, index.row(), index.column())

	for row in range(rows):
		child = model.index(row, 0, index)
		if not child.isValid():
			continue
		expandRecursive(view, model, child, depth+1)

def showTree(model):
	app = QApplication(sys.argv)
	tv = QTreeView()
	tv.setModel(model)
	expandRecursive(tv, model)
	tv.resizeColumnToContents(0)
	tv.show()
	sys.exit(app.exec_())

def buildDummyJsonSystem(path, name="Face"):
	jsonPath = r'D:\Users\tyler\Documents\GitHub\Simplex\Useful\male_traversal3.json'
	with open(jsonPath, 'r') as f:
		jsDict = json.load(f)
	simp = Simplex.buildEmptySystem(None, name)
	simp.loadDefinition(jsDict, create=False)
	return simp



# DISPLAY TESTS
def testSliderDisplay(smpxPath, applyFilter=True):
	simp = Simplex.buildSystemFromSmpx(smpxPath)
	model = SimplexModel(simp, None)
	model = SliderModel(model)
	if applyFilter:
		model = SliderFilterModel(model)
	showTree(model)

def testComboDisplay(smpxPath, applyFilter=True):
	simp = Simplex.buildSystemFromSmpx(smpxPath)
	model = SimplexModel(simp, None)
	model = ComboModel(model)
	if applyFilter:
		model = ComboFilterModel(model)
	showTree(model)

def testTraversalDisplay(smpxPath, applyFilter=True):
	jsonPath = r'D:\Users\tyler\Documents\GitHub\Simplex\Useful\male_traversal3.json'
	simp = buildDummyJsonSystem(jsonPath)

	model = SimplexModel(simp, None)
	model = TraversalModel(model)
	if applyFilter:
		model = TraversalFilterModel(model)
	showTree(model)

def testBaseDisplay(smpxPath):
	#simp = Simplex.buildSystemFromSmpx(smpxPath)
	jsonPath = r'D:\Users\tyler\Documents\GitHub\Simplex\Useful\male_traversal3.json'
	simp = buildDummyJsonSystem(jsonPath)

	model = SimplexModel(simp, None)
	showTree(model)

def testEmptySimplex():
	simp = Simplex.buildEmptySystem(None, "Face")
	model = SimplexModel(simp, None)
	model = SliderModel(model)
	showTree(model)


# RowAdd Tests
def testNewSlider():
	simp = Simplex.buildEmptySystem(None, 'Face')
	model = SimplexModel(simp, None)
	smodel = SliderModel(model)
	fmodel = SliderFilterModel(smodel)
	fmodel.doFilter = True

	app = QApplication(sys.argv)

	topWid = QWidget()
	lay = QVBoxLayout(topWid)

	tv = QTreeView(topWid)
	btn = QPushButton('NEW', topWid)
	lay.addWidget(tv)
	lay.addWidget(btn)

	tv.setModel(fmodel)
	expandRecursive(tv, fmodel)
	topWid.show()

	newSlider = lambda: Slider.createSlider('NewSlider', simp)
	btn.clicked.connect(newSlider)

	sys.exit(app.exec_())

def testDeleteBase():
	simp = Simplex.buildSystemFromSmpx(smpxPath)
	model = SimplexModel(simp, None)
	model = SliderModel(model)
	model = SliderFilterModel(model)

	app = QApplication(sys.argv)

	topWid = QWidget()
	lay = QVBoxLayout(topWid)

	tv = QTreeView(topWid)

	btn = QPushButton('DELETE', topWid)
	lay.addWidget(tv)
	lay.addWidget(btn)

	tv.setModel(model)
	topWid.show()

	expandRecursive(tv, model)
	tv.resizeColumnToContents(0)

	def delCallback():
		sel = tv.selectedIndexes()
		sel = [i for i in sel if i.column() == 0]
		items = [s.model().itemFromIndex(s) for s in sel]
		items[0].delete()
		tv.model().invalidateFilter()

	btn.clicked.connect(delCallback)

	sys.exit(app.exec_())

def testNewChild():
	simp = Simplex.buildSystemFromSmpx(smpxPath)
	model = SimplexModel(simp, None)
	model = SliderModel(model)
	model = SliderFilterModel(model)

	app = QApplication(sys.argv)

	topWid = QWidget()
	lay = QVBoxLayout(topWid)

	tv = QTreeView(topWid)

	btn = QPushButton('NEW', topWid)
	lay.addWidget(tv)
	lay.addWidget(btn)

	tv.setModel(model)
	topWid.show()

	expandRecursive(tv, model)
	tv.resizeColumnToContents(0)

	def newCallback():
		sel = tv.selectedIndexes()
		sel = [i for i in sel if i.column() == 0]
		items = [s.model().itemFromIndex(s) for s in sel]
		item = items[0]

		# TODO
		# find the child type of item
		# make a new one of those

		tv.model().invalidateFilter()

	btn.clicked.connect(newCallback)

	sys.exit(app.exec_())



if __name__ == "__main__":
	#basePath = r'D:\Users\tyler\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	basePath = r'C:\Users\tfox\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	smpxPath = os.path.join(basePath, 'Themale_Simplex_v005_Split.smpx')
	#smpxPath = os.path.join(basePath, 'sphere_abcd_50.smpx')

	# Only works for one at a time
	#testEmptySimplex()
	testBaseDisplay(smpxPath)
	#testSliderDisplay(smpxPath, applyFilter=True)
	#testComboDisplay(smpxPath, applyFilter=True)
	#testTraversalDisplay(smpxPath, applyFilter=True)
	#testNewSlider()
	#testDeleteBase()


