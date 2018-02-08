#pylint:disable=unused-import,relative-import,missing-docstring,unused-argument,no-self-use
import os, sys, copy, json, itertools, gc
from alembic.Abc import OArchive, IArchive, OStringProperty
from alembic.AbcGeom import OXform, OPolyMesh, IXform, IPolyMesh

from Qt.QtCore import QAbstractItemModel, QModelIndex, Qt, QSortFilterProxyModel, QObject, Signal, QSize, QRect, QRectF
from Qt.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QTextOption, QCursor
from Qt.QtWidgets import QTreeView, QListView, QApplication, QPushButton, QVBoxLayout, QWidget, QStyledItemDelegate

from dragFilter import DragFilter

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
	def __init__(self, parent=None):
		super(ChannelBoxDelegate, self).__init__(parent)
		self.store = {}

	def paint(self, painter, opt, index):
		item = index.model().itemFromIndex(index)
		if isinstance(item, Slider):
			self.paintSlider(self, item, painter, opt.rect, opt.palette)
		else:
			super(ChannelBoxDelegate, self).paint(painter, opt, index)

	def roundedPath(self, width, height, left=True, right=True):
		key = (width, height, left, right)
		if key in self.store:
			return self.store[key]

		ew = height * 2 #ellipse width
		ts = 0.0 # topside
		bs = height #bottomside
		ls = 0.0 #left side
		rs = width #righSide
		lc = ew # left corner
		rc = width - ew # left corner

		# If we're too narrow then flatten the points
		if left and right:
			if width < 2 * ew:
				lc = width * 0.5
				rc = lc
				ew = lc
		else:
			if left:
				if width < ew:
					lc = rs
					ew = width
			elif right:
				if width < ew:
					rc = ls
					ew = width

		bgPath = QPainterPath()
		if left:
			bgPath.moveTo(lc, ts)
		if right:
			bgPath.lineTo(rc, ts)
			bgPath.arcTo(rc, ts, ew, bs, 90, -180)
		else:
			bgPath.lineTo(rs, ts)
			bgPath.lineTo(rs, bs)

		if left:
			bgPath.lineTo(lc, bs)
			bgPath.arcTo(ls, ts, ew, bs, -90, -180)
		else:
			bgPath.lineTo(ls, bs)
			bgPath.lineTo(ls, ts)

		bgPath.closeSubpath()
		self.store[key] = bgPath
		return bgPath

	def angledPath(self, width, height, left=True, right=True):
		key = (width, height, left, right)
		if key in self.store:
			return self.store[key]

		hh = height * 0.5 #half height
		ts = 0.0 # topside
		bs = height #bottomside
		ls = 0.0 #left side
		rs = width #righSide
		aw = height * 0.5 # angle width
		lc = aw # left corner
		rc = width - aw # right corner

		# If we're too narrow then flatten the points
		if left and right:
			if width < 2 * aw:
				lc = width * 0.5
				rc = lc
		else:
			if left:
				if width < aw:
					lc = rs
			elif right:
				if width < aw:
					rc = ls

		bgPath = QPainterPath()
		if left:
			bgPath.moveTo(lc, ts)

		if right:
			bgPath.lineTo(rc, ts)
			bgPath.lineTo(rs, hh)
			bgPath.lineTo(rc, bs)
		else:
			bgPath.lineTo(rs, ts)
			bgPath.lineTo(rs, bs)

		if left:
			bgPath.lineTo(lc, bs)
			bgPath.lineTo(ls, hh)
		else:
			bgPath.lineTo(ls, bs)

		bgPath.closeSubpath()

		self.store[key] = bgPath

		return bgPath

	def paintSlider(self, delegate, slider, painter, rect, palette):
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
		painter.setPen(QPen(palette.foreground().color()))

		frect = QRectF(rect.x(), rect.y(), rect.width(), rect.height())
		painter.fillRect(frect, palette.background())

		pointLeft = slider.minValue != 0.0

		bgPath = self.angledPath(rect.width(), rect.height(), left=pointLeft)
		bgPath = bgPath.translated(rect.x(), rect.y())
		painter.fillPath(bgPath, bgBrush)
		painter.drawPath(bgPath)

		if slider.minValue == 0.0:
			perc = slider.value
			perc = max(min(perc, 1.0), 0.0) #clamp between 0 and 1
			fgPath = self.angledPath(rect.width() * perc, rect.height(), left=False)
			fgPath = fgPath.translated(rect.x(), rect.y())
			painter.fillPath(fgPath, fgBrush)

		else:
			perc = slider.value
			side = perc >= 0.0
			width = abs(perc) * rect.width() * 0.5
			fgPath = self.angledPath(rect.width() * abs(perc) * 0.5, rect.height(), left=not side, right=side)
			if side:
				fgPath = fgPath.translated(rect.x() + rect.width() * 0.5, rect.y())
			else:
				fgPath = fgPath.translated(rect.x() + rect.width() * 0.5 * (1 + perc), rect.y())
			painter.fillPath(fgPath, fgBrush)
		opts = QTextOption(Qt.AlignCenter)
		painter.drawText(frect, slider.name, opts)

		painter.restore()
 

class ChannelBox(QListView):
	def __init__(self, parent=None):
		super(ChannelBox, self).__init__(parent)
		self.dragging = None
		self.setMouseTracking(True)

	def dragStart(self):
		p = self.mapFromGlobal(QCursor.pos())
		item = self.indexAt(p).internalPointer()
		if isinstance(item, Slider):
			self.dragging = item

	def dragStop(self):
		self.dragging = None

	def dragTick(self, ticks, mul):
		if self.dragging is not None:
			val = self.dragging.value
			val += 0.01 * ticks * mul
			val = min(max(val, self.dragging.minValue), self.dragging.maxValue)
			self.dragging.value = val



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
	tv = ChannelBox()
	model = ChannelBoxModel(simp, None)
	delegate = ChannelBoxDelegate()

	dragFilter = DragFilter(tv.viewport())
	dragFilter.dragButton = Qt.LeftButton
	tv.viewport().installEventFilter(dragFilter)
	dragFilter.dragPressed.connect(tv.dragStart)
	dragFilter.dragReleased.connect(tv.dragStop)
	dragFilter.dragTick.connect(tv.dragTick)

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
	#basePath = r'D:\Users\tyler\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	basePath = r'C:\Users\tfox\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	smpxPath = os.path.join(basePath, 'HeadMaleStandard_High_Unsplit.smpx')

	testSliderDisplay(smpxPath)





