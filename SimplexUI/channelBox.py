#pylint:disable=unused-import,relative-import,missing-docstring,unused-argument,no-self-use
import os, sys

from Qt.QtCore import (QAbstractItemModel, QModelIndex, Qt,
					   QObject, Signal, QRectF, QEvent, QTimer)
from Qt.QtGui import (QBrush, QColor, QPainter, QPainterPath, QPen, QTextOption, QCursor)
from Qt.QtWidgets import (QTreeView, QListView, QApplication, QStyledItemDelegate)

from fnmatch import fnmatchcase
from utils import getNextName, nested
from contextlib import contextmanager
from interfaceModel import Slider, Group, Simplex, SimplexModel

CONTEXT = os.path.basename(sys.executable)
if CONTEXT == "maya.exe":
	from mayaInterface import DCC
elif CONTEXT == "XSI.exe":
	from xsiInterface import DCC
else:
	from dummyInterface import DCC


class SlideFilter(QObject):
	SLIDE_ENABLED = 0

	slideTick = Signal(float, float, float) #AbsValue, OffsetValue, Multiplier
	slidePressed = Signal()
	slideReleased = Signal()

	def __init__(self, parent):
		super(SlideFilter, self).__init__(parent)

		self.slideCursor = Qt.SizeHorCursor
		self.slideButton = Qt.LeftButton

		self.fastModifier = Qt.ControlModifier
		self.slowModifier = Qt.ShiftModifier

		self.fastMultiplier = 5.0
		self.slowDivisor = 5.0

		# private vars
		self._slideStart = True
		self._overridden = False
		self._pressed = True
		self._prevValue = None

	def doOverrideCursor(self):
		if self._overridden:
			return
		QApplication.setOverrideCursor(self.slideCursor)
		self._overridden = True

	def restoreOverrideCursor(self):
		if not self._overridden:
			return
		QApplication.restoreOverrideCursor()
		self._overridden = False

	def eventFilter(self, obj, event):
		if hasattr(self, "SLIDE_ENABLED"):
			if event.type() == QEvent.MouseButtonPress:
				if event.button() & self.slideButton:
					self.startSlide(obj, event)
					self.doSlide(obj, event)
					self._slideStart = True

			elif event.type() == QEvent.MouseMove:
				if self._slideStart:
					try:
						self.doSlide(obj, event)
					except:
						# fix the cursor if there's an error during slideging
						self.restoreOverrideCursor()
						raise #re-raise the exception
					return True

			elif event.type() == QEvent.MouseButtonRelease:
				if event.button() & self.slideButton:
					self._pressed = False
					self._slideStart = False
					self.myendSlide(obj, event)
					return True

		return super(SlideFilter, self).eventFilter(obj, event)

	def startSlide(self, obj, event):
		self.slidePressed.emit()
		self.doOverrideCursor()

	def doSlide(self, obj, event):
		width = obj.width()
		click = event.pos()
		perc = click.x() / float(width)

		mul = 1.0
		if event.modifiers() & self.fastModifier:
			mul = self.fastMultiplier
		elif event.modifiers() & self.slowModifier:
			mul = 1.0 / self.slowDivisor

		if self._prevValue is None:
			offset = 0.0
		else:
			offset = perc - self._prevValue
		self._prevValue = perc

		self.slideTick.emit(perc, offset, mul)

	def myendSlide(self, obj, event):
		self.restoreOverrideCursor()
		self._slideStart = None
		self.slideReleased.emit()



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
		key = (round(width, 2), round(height, 2), round(left, 2), round(right, 2))
		if key in self.store:
			return self.store[key]

		#off = 0.5
		off = 1.0
		ew = height - off #ellipse width
		eh = height - 2*off #ellipse height
		ts = 0.0 + off # topside
		bs = height - off #bottomside
		ls = 0.0 + off #left side
		rs = width - off #righSide
		lc = height + off # left corner
		rc = width - height - off # left corner

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
		else:
			bgPath.moveTo(ls, ts)

		if right:
			bgPath.lineTo(rc, ts)
			bgPath.arcTo(rc, ts, ew, eh, 90, -180)
		else:
			bgPath.lineTo(rs, ts)
			bgPath.lineTo(rs, bs)

		if left:
			bgPath.lineTo(lc, bs)
			bgPath.arcTo(ls, ts, ew, eh, -90, -180)
		else:
			bgPath.lineTo(ls, bs)
			bgPath.lineTo(ls, ts)

		bgPath.closeSubpath()
		self.store[key] = bgPath
		return bgPath

	def paintSlider(self, delegate, slider, painter, rect, palette):
		painter.save()
		try:
			painter.setRenderHint(QPainter.Antialiasing, True)

			fgColor = slider.color
			bgColor = QColor(slider.color)
			bgColor.setAlpha(128)

			fgBrush = QBrush(fgColor)
			bgBrush = QBrush(bgColor)
			painter.setPen(QPen(palette.foreground().color()))

			rx = rect.x()
			ry = rect.y()
			rw = rect.width()
			rh = rect.height()

			bgLeft = slider.minValue != 0.0
			bgPath = self.roundedPath(rw, rh, left=bgLeft)
			bgPath = bgPath.translated(rx, ry)
			painter.fillPath(bgPath, bgBrush)
			if bgLeft:
				# Double sided slider
				perc = slider.value
				right = perc >= 0.0
				fgPath = self.roundedPath(abs(perc) * rw * 0.5, rh, left=not right, right=right)
				if right:
					fgPath = fgPath.translated(rx + rw * 0.5, ry)
				else:
					fgPath = fgPath.translated(rx + rw * 0.5 * (1 + perc), ry)
				painter.fillPath(fgPath, fgBrush)

			else:
				# Positive only slider
				perc = slider.value
				perc = max(min(perc, 1.0), 0.0) #clamp between 0 and 1
				fgPath = self.roundedPath(rw * perc, rh, left=False)
				fgPath = fgPath.translated(rx, ry)
				painter.fillPath(fgPath, fgBrush)

			opts = QTextOption(Qt.AlignCenter)
			frect = QRectF(rx, ry, rw, rh)
			painter.drawText(frect, slider.name, opts)
			#painter.drawPath(bgPath)
		finally:
			painter.restore()





class ChannelListModel(QAbstractItemModel):
	def __init__(self, simplex, parent):
		super(ChannelListModel, self).__init__(parent)
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
			if isinstance(item, (Group, Slider)):
				return item.name

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

class ChannelList(QListView):
	def __init__(self, parent=None):
		super(ChannelList, self).__init__(parent)
		self.slider = None
		self._nxt = 0.0
		self.start = False
		self.residual = 0.0

	def slideStart(self):
		p = self.mapFromGlobal(QCursor.pos())
		item = self.indexAt(p).internalPointer()
		if isinstance(item, Slider):
			self.slider = item
			self.start = True

	def slideStop(self):
		self.slider = None

	def slideTick(self, val, offset, mul):
		if self.slider is not None:
			mx = self.slider.maxValue
			mn = self.slider.minValue

			tick = 20.0 / mul

			if self.start or mul == 1.0:
				self.start = False
				val = (val * (mx - mn)) + mn
				rn = round(val * tick) / tick
			else:
				# When working in relative mode, we keep track of the
				# unused residual value and add it to the next tick.
				# Because, unless each mouse move refresh is more than
				# one full tick from the previous, we get no movement
				val = (offset * (mx - mn))
				val = self.slider.value + (val * mul)
				val += self.residual
				rn = round(val * tick) / tick
				self.residual = val - rn

			rn = min(max(rn, mn), mx)
			# Do this to keep the ui snappy
			self._nxt = rn
			QTimer.singleShot(0, self.setval)

	def setval(self):
		if self.slider is not None and self._nxt is not None:
			self.slider.value = self._nxt
		self._nxt = None







class ChannelTreeModel(SimplexModel):
	def getChildItem(self, parent, row):
		try:
			if isinstance(parent, Group):
				return parent.items[row]
			elif parent is None:
				self.simplex.sliderGroups[row]
		except IndexError:
			pass
		return None

	def getItemRow(self, item):
		row = None
		if isinstance(item, Group):
			row = item.simplex.sliderGroups.index(item)
		elif isinstance(item, Slider):
			row = item.group.items.index(item)
		return row

	def getParentItem(self, item):
		par = None
		if isinstance(item, Slider):
			par = item.group
		return par

	def columnCount(self, parent):
		return 1

	def getItemRowCount(self, item):
		if isinstance(item, Group):
			return len(item.items)
		elif item is None:
			return len(self.simplex.sliderGroups)
		return 0

	def getItemAppendRow(self, item):
		return self.getItemRowCount(item)

	def getItemData(self, item, column, role):
		if role in (Qt.DisplayRole, Qt.EditRole):
			if column == 0:
				if isinstance(item, Group):
					return item.name
				elif isinstance(item, Slider):
					return item.name
					#return "{0}: {1:.2f}".format(item.name, item.value)
			print "BAD ICR", item, column, role
			return "BAD"
		return None

	def typeHandled(self, item):
		if isinstance(item, Group):
			return item.groupType == Slider
		return isinstance(item, Slider)

class ChannelTree(QTreeView):
	def __init__(self, parent=None):
		super(ChannelTree, self).__init__(parent)
		self.slider = None
		self._nxt = 0.0
		self.start = False
		self.residual = 0.0

	def slideStart(self):
		p = self.mapFromGlobal(QCursor.pos())
		item = self.indexAt(p).internalPointer()
		if isinstance(item, Slider):
			self.slider = item
			self.start = True

	def slideStop(self):
		self.slider = None

	def slideTick(self, val, offset, mul):
		if self.slider is not None:
			mx = self.slider.maxValue
			mn = self.slider.minValue

			tick = 20.0 / mul

			if self.start or mul == 1.0:
				self.start = False
				val = (val * (mx - mn)) + mn
				rn = round(val * tick) / tick
			else:
				# When working in relative mode, we keep track of the
				# unused residual value and add it to the next tick.
				# Because, unless each mouse move refresh is more than
				# one full tick from the previous, we get no movement
				val = (offset * (mx - mn))
				val = self.slider.value + (val * mul)
				val += self.residual
				rn = round(val * tick) / tick
				self.residual = val - rn

			rn = min(max(rn, mn), mx)
			# Do this to keep the ui snappy
			self._nxt = rn
			QTimer.singleShot(0, self.setval)

	def setval(self):
		if self.slider is not None and self._nxt is not None:
			self.slider.value = self._nxt
		self._nxt = None







# DISPLAY TESTS
def testSliderListDisplay(smpxPath):
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
	tv = ChannelList()
	model = ChannelListModel(simp, None)
	delegate = ChannelBoxDelegate()

	slideFilter = SlideFilter(tv.viewport())
	slideFilter.slideButton = Qt.LeftButton
	tv.viewport().installEventFilter(slideFilter)
	slideFilter.slidePressed.connect(tv.slideStart)
	slideFilter.slideReleased.connect(tv.slideStop)
	slideFilter.slideTick.connect(tv.slideTick)

	for g in simp.sliderGroups:
		channels.append(g)
		for item in g.items:
			if item.name in redAttrs:
				item.color = QColor(178, 103, 103)
			elif item.name in greenAttrs:
				item.color = QColor(90, 161, 27)
			elif item.name in blueAttrs:
				item.color = QColor(103, 141, 178)
			elif item.name in greyAttrs:
				item.color = QColor(130, 130, 130)
			channels.append(item)

	model.setChannels(channels)

	tv.setModel(model)
	tv.setItemDelegate(delegate)

	tv.show()
	sys.exit(app.exec_())

def testSliderTreeDisplay(smpxPath):
	simp = Simplex.buildSystemFromSmpx(smpxPath)

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
	#tv = ChannelTree()
	tv = QTreeView()
	model = ChannelTreeModel(simp, None)
	#delegate = ChannelBoxDelegate()

	#slideFilter = SlideFilter(tv.viewport())
	#slideFilter.slideButton = Qt.LeftButton
	#tv.viewport().installEventFilter(slideFilter)
	#slideFilter.slidePressed.connect(tv.slideStart)
	#slideFilter.slideReleased.connect(tv.slideStop)
	#slideFilter.slideTick.connect(tv.slideTick)

	#for g in simp.sliderGroups:
		#for item in g.items:
			#if item.name in redAttrs:
				#item.color = QColor(178, 103, 103)
			#elif item.name in greenAttrs:
				#item.color = QColor(90, 161, 27)
			#elif item.name in blueAttrs:
				#item.color = QColor(103, 141, 178)
			#elif item.name in greyAttrs:
				#item.color = QColor(130, 130, 130)

	tv.setModel(model)
	#tv.setItemDelegate(delegate)

	tv.show()
	sys.exit(app.exec_())





if __name__ == "__main__":
	basePath = r'D:\Users\tyler\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	#basePath = r'C:\Users\tfox\Documents\GitHub\Simplex\scripts\SimplexUI\build'
	smpxPath = os.path.join(basePath, 'HeadMaleStandard_High_Unsplit.smpx')

	testSliderTreeDisplay(smpxPath)

