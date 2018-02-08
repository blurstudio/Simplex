#pylint:disable=unused-import,relative-import,missing-docstring,unused-argument,no-self-use
import os, sys, copy, json, itertools, gc
from alembic.Abc import OArchive, IArchive, OStringProperty
from alembic.AbcGeom import OXform, OPolyMesh, IXform, IPolyMesh

from Qt.QtCore import QAbstractItemModel, QModelIndex, Qt, QSortFilterProxyModel, QObject, Signal, QSize, QRect, QRectF
from Qt.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QTextOption
from Qt.QtWidgets import QTreeView, QListView, QApplication, QPushButton, QVBoxLayout, QWidget, QStyledItemDelegate


from fnmatch import fnmatchcase
from utils import getNextName, nested
from contextlib import contextmanager
from interfaceModel import Slider, Group, Simplex

CONTEXT = os.path.basename(sys.executable)
if CONTEXT == "maya.exe":
	from mayaInterface import DCC
elif CONTEXT == "XSI.exe":
	from xsiInterface import DCC
else:
	from dummyInterface import DCC



class Channel(object):
	@staticmethod
	def paintSlider(delegate, slider, painter, rect, palette):
		painter.save()
		painter.setRenderHint(QPainter.Antialiasing, True)
		painter.setPen(Qt.NoPen)

		rgb = slider.color.get(id(delegate), (255, 128, 128))
		fgColor = QColor(*rgb)
		bgColor = QColor.fromHsl(
			fgColor.hslHue(),
			fgColor.hslSaturation(),
			min(fgColor.lightness() + 32, 255)
		)
		fgBrush = QBrush(fgColor)
		bgBrush = QBrush(bgColor)
		radius = rect.height() / 2

		painter.fillRect(rect, palette.background())
		bgPath = QPainterPath()
		frect = QRectF(rect.x(), rect.y(), rect.width(), rect.height())
		bgPath.addRoundedRect(frect, radius, radius)
		painter.fillPath(bgPath, bgBrush)

		if slider.minValue == 0.0:
			perc = slider.value / slider.maxValue
			perc = max(min(perc, 1.0), 0.0) #clamp between 0 and 1
			fgPath = QPainterPath()
			overlay = QRectF(rect.x(), rect.y(), rect.width() * perc, rect.height())
			fgPath.addRoundedRect(overlay, radius, radius)
			painter.fillPath(fgPath, fgBrush)

		else:
			perc = (slider.value - slider.minValue) / (slider.maxValue - slider.minValue)
			perc = max(min(perc, 1.0), 0.0) #clamp between 0 and 1

			if perc >= 0.5:
				left = rect.x() + rect.width() * 0.5
				right = rect.x() + rect.width() * perc
			else:
				right = rect.x() + rect.width() * 0.5
				left = rect.x() + rect.width() * perc

			fgPath = QPainterPath()
			overlay = QRectF(left, rect.y(), abs(left - right), rect.height())
			fgPath.addRoundedRect(overlay, radius, radius)
			painter.fillPath(fgPath, fgBrush)

		painter.setPen(QPen(palette.foreground().color()))
		opts = QTextOption(Qt.AlignCenter)
		painter.drawText(frect, slider.name, opts)

		painter.restore()



class ChannelEditor(QWidget):
	editingFinished = Signal()
	def __init__(self, slider, delegate, parent=None):
		super(ChannelEditor, self).__init__(parent)
		self.slider = slider
		self.delegate = delegate
		self.setMouseTracking(True)
		self.setAutoFillBackground(True)

	def paintEvent(self, event):
		print "PAINT"
		painter = QPainter(self)
		Channel.paintSlider(self.delegate, self.slider, painter, self.rect(), self.palette())

	def mouseMoveEvent(self, event):
		print "MOVE"
		xpos = event.x()
		width = float(self.sizeHint().width())
		perc = xpos / width
		val = (perc * (self.slider.maxValue - self.slider.minValue)) + self.slider.minValue
		self.slider.value = max(min(val, self.slider.maxValue), self.slider.minValue)
		self.update()

	def mouseReleaseEvent(self, event):
		print "RELEASE"
		self.editingFinished.emit()



class ChannelBoxModel(QAbstractItemModel):
	def __init__(self, simplex, parent):
		super(ChannelBoxModel, self).__init__(parent)
		self.simplex = simplex
		self.simplex.models.append(self)
		self.channels = []

	def setChannels(self, channels):
		self.beginResetModel()
		self.channels = channels
		self.endResetModel()

	def index(self, row, column=0, parIndex=QModelIndex()):
		try:
			item = self.channels[row]
		except IndexError:
			return QModelIndex()
		return self.createIndex(row, column, item)

	def parent(self, index):
		return QModelIndex()

	def rowCount(self, parent):
		return len(self.channels)

	def columnCount(self, parent):
		return 1

	def data(self, index, role):
		if not index.isValid():
			return None
		item = index.internalPointer()

		if role in (Qt.DisplayRole, Qt.EditRole):
			if isinstance(item, Group):
				return item.name
			elif isinstance(item, Slider):
				return item.name

		elif role == Qt.BackgroundRole:
			if isinstance(item, Group):
				rgb = item.color.get(id(self), (196, 196, 196))
				return QBrush(QColor(*rgb))
			elif isinstance(item, Slider):
				rgb = item.color.get(id(self), (128, 255, 128))
				return QBrush(QColor(*rgb))

		elif role == Qt.TextAlignmentRole:
			return Qt.AlignCenter

		return None

	def flags(self, index):
		return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable

	def itemFromIndex(self, index):
		return index.internalPointer()

	def indexFromItem(self, item):
		try:
			row = self.channels.index(item)
		except ValueError:
			return QModelIndex()
		return self.index(row)

	def typeHandled(self, item):
		if isinstance(item, Group):
			return item.groupType == Slider
		return isinstance(item, Slider)

	def itemDataChanged(self, item):
		if self.typeHandled(item):
			idx = self.indexFromItem(item)
			if idx.isValid():
				self.dataChanged.emit(idx, idx)




class ChannelBoxDelegate(QStyledItemDelegate):
	def paint(self, painter, opt, index):
		item = index.model().itemFromIndex(index)
		if isinstance(item, Slider):
			Channel.paintSlider(self, item, painter, opt.rect, opt.palette)
		else:
			super(ChannelBoxDelegate, self).paint(painter, opt, index)

	def createEditor(self, par, opt, index):
		ip = index.internalPointer()
		if isinstance(ip, Slider):
			print "Creating Editor"
			editor = ChannelEditor(ip, self, par)
			editor.editingFinished.connect(self.commitAndClose)
			return editor
		else:
			return super(ChannelBoxDelegate, self).createEditor(par, opt, index)
	
	def commitAndClose(self):
		print "Commit and Close"
		editor = self.sender()
		self.commitData.emit(editor)
		self.closeEditor.emit(editor)





# DISPLAY TESTS
def testSliderDisplay(smpxPath):
	simp = Simplex.buildSystemFromSmpx(smpxPath)
	channels = []


	redAttrs = set([
		u'lowerLipDepressor_X', u'stretcher_X', u'platysmaFlex_X',
		u'cheekRaiser_X', u'jawOpen', u'lidTightener_X',
		u'outerBrowRaiser_X', u'eyesClosed_X', u'cornerPuller_X',
		u'noseWrinkler_X', u'lipsBlow_X', u'cornerDepressor_X',
		u'funneler', u'browLateral_X', u'innerBrowRaiser_X',
		u'upperLipRaiser_X', u'chinRaiser', u'cheek_SuckBlow_X', u'pucker',
		u'eyeGaze_DownUp_X', u'eyeGaze_RightLeft_X', u'upperLidTweak_X',
		u'lowerLidTweak_X'
	])
	greenAttrs = set([
		u'nasolabialDeepener_X', u'neckStretcher_X', u'lipsPressed_T',
		u'lipsPressed_B', u'throatCompress', u'lipsRolled_InOut_B',
		u'lipsRolled_InOut_T', u'sharpCornerPuller_X', u'dimpler_X',
		u'eyeBlink_X', u'scalpSlide_BackFwd', u'browDown_X',
		u'mouthSwing_RightLeft', u'sternoFlex_X', u'throatOpen'
	])
	blueAttrs = set([
		u'adamsApple', u'noseSwing_RightLeft', u'nostrilCompress_X',
		u'jawThrust_BackFwd', u'eyesWide_X', u'lipsVerticalT_X',
		u'lipsVerticalB_X', u'earPull_X', u'lipsTighten_T',
		u'lipsTighten_B', u'lipsCompress_T', u'lipsCompress_B',
		u'lipsShift_RightLeft_B', u'lipsShift_RightLeft_T',
		u'lipsNarrowT_X', u'lipsNarrowB_X', u'jawSwing_RightLeft',
		u'nostril_SuckFlare_X', u'lipsCorner_DownUp_X', u'jawClench'
	])
	greyAttrs = set([u'lipsTogether'])

	app = QApplication(sys.argv)
	tv = QListView()
	model = ChannelBoxModel(simp, None)
	delegate = ChannelBoxDelegate()

	for g in simp.sliderGroups:
		channels.append(g)
		for item in g.items:
			if item.name in redAttrs:
				item.color[id(delegate)] = (178, 103, 103)
			elif item.name in greenAttrs:
				item.color[id(delegate)] = (90, 161, 27)
			elif item.name in blueAttrs:
				item.color[id(delegate)] = (103, 141, 178)
			elif item.name in greyAttrs:
				item.color[id(delegate)] = (130, 130, 130)
			channels.append(item)

	model.setChannels(channels)

	tv.setModel(model)
	tv.setItemDelegate(delegate)


	tv.show()
	sys.exit(app.exec_())



if __name__ == "__main__":
	basePath = r'D:\Users\tyler\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	#basePath = r'C:\Users\tfox\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	smpxPath = os.path.join(basePath, 'HeadMaleStandard_High_Unsplit.smpx')

	testSliderDisplay(smpxPath)





