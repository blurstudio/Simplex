from interfaceModel import *
from Qt.QtWidgets import QTreeView, QApplication, QPushButton, QVBoxLayout, QWidget


# HELPERS
def expandRecursive(view, model, index=QModelIndex(), depth=0):
	''' helper to expand the whole tree '''
	view.setExpanded(index, True)
	rows = model.rowCount(index)
	for row in range(rows):
		child = model.index(row, 0, index)
		if not child.isValid:
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


# DISPLAY TESTS
def testSliderDisplay(smpxPath, applyFilter=True):
	simp = Simplex.buildSystemFromSmpx(smpxPath)
	model = SimplexModel(simp, None)
	smodel = SliderModel(None)
	smodel.setSourceModel(model)
	if applyFilter:
		fmodel = SliderFilterModel()
		fmodel.setSourceModel(smodel)
		smodel = fmodel
	showTree(smodel)

def testComboDisplay(smpxPath, applyFilter=True):
	simp = Simplex.buildSystemFromSmpx(smpxPath)
	model = SimplexModel(simp, None)
	smodel = ComboModel(None)
	smodel.setSourceModel(model)
	if applyFilter:
		fmodel = ComboFilterModel()
		fmodel.setSourceModel(smodel)
		smodel = fmodel
	showTree(smodel)

def testBaseDisplay(smpxPath):
	simp = Simplex.buildSystemFromSmpx(smpxPath)
	model = SimplexModel(simp, None)
	showTree(model)






# RowAdd Tests
def testDeleteSlider():
	simp = Simplex.buildEmptySystem(None, 'Face')
	model = SimplexModel(simp, None)
	smodel = SliderModel()
	smodel.setSourceModel(model)
	fmodel = SliderFilterModel()
	fmodel.setSourceModel(smodel)
	fmodel.doFilter = False

	app = QApplication(sys.argv)

	topWid = QWidget()
	lay = QVBoxLayout(topWid)

	tv = QTreeView(topWid)
	btn = QPushButton('DELETE', topWid)
	lay.addWidget(tv)
	lay.addWidget(btn)

	tv.setModel(fmodel)
	expandRecursive(tv, fmodel)

	topWid.show()

	s = Slider.createSlider('NewSlider', simp)
	expandRecursive(tv, fmodel)

	btn.clicked.connect(s.delete)

	sys.exit(app.exec_())

def testNewSlider():
	simp = Simplex.buildEmptySystem(None, 'Face')
	model = SimplexModel(simp, None)
	smodel = SliderModel()
	smodel.setSourceModel(model)
	fmodel = SliderFilterModel()
	fmodel.setSourceModel(smodel)
	fmodel.doFilter = False

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


if __name__ == "__main__":
	basePath = r'D:\Users\tyler\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	#basePath = r'C:\Users\tfox\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	smpxPath = os.path.join(basePath, 'HeadMaleStandard_High_Unsplit.smpx')

	# Only works for one at a time
	testBaseDisplay(smpxPath)
	#testSliderDisplay(smpxPath, applyFilter=True)
	#testComboDisplay(smpxPath, applyFilter=True)
	#testNewSlider()
	#testDeleteSlider()



