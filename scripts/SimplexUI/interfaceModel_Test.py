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
	simp = Simplex.buildFromAbc(smpxPath)
	model = SliderModel(simp, None)
	if applyFilter:
		fmodel = SliderFilterModel()
		fmodel.setSourceModel(model)
		model = fmodel
	showTree(model)

def testComboDisplay(smpxPath, applyFilter=True):
	simp = Simplex.buildFromAbc(smpxPath)
	model = ComboModel(simp, None)
	if applyFilter:
		fmodel = ComboFilterModel()
		fmodel.setSourceModel(model)
		model = fmodel
	showTree(model)


# RowAdd Tests
def testDeleteSlider():
	simp = Simplex.buildBlank(None, 'Face')
	model = SliderModel(simp, None)
	fmodel = SliderFilterModel()
	fmodel.setSourceModel(model)
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
	simp = Simplex.buildBlank(None, 'Face')
	model = SliderModel(simp, None)
	fmodel = SliderFilterModel()
	fmodel.setSourceModel(model)
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
	#basePath = r'D:\Users\tyler\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	basePath = r'C:\Users\tfox\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	smpxPath = os.path.join(basePath, 'HeadMaleStandard_High_Unsplit.smpx')

	# Only works for one at a time
	#testSliderDisplay(smpxPath, applyFilter=False)
	testComboDisplay(smpxPath, applyFilter=False)
	#testNewSlider()
	#testDeleteSlider()



