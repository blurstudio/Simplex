# Copyright 2016, Blur Studio
#
# This file is part of Simplex.
#
# Simplex is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Simplex is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.

""" The ChannelBox
A Super-minimal ui for interacting with a Simplex System
Currently VERY WIP. Probably shouldn't have committed it to master, but whatever
"""

# pylint:disable=unused-import,relative-import,missing-docstring,unused-argument,no-self-use
from __future__ import absolute_import, print_function

import os
import sys

from .interfaceModel import Group, Simplex, SimplexModel, Slider
from .Qt.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QObject,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from .Qt.QtGui import QBrush, QColor, QCursor, QPainter, QPainterPath, QPen, QTextOption
from .Qt.QtWidgets import QApplication, QListView, QStyledItemDelegate, QTreeView


class SlideFilter(QObject):
    """A simplified drag filter, specialized for this purpose"""

    SLIDE_ENABLED = 0

    slideTick = Signal(float, float, float)  # AbsValue, OffsetValue, Multiplier
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
        """Override the cursor"""
        if self._overridden:
            return
        QApplication.setOverrideCursor(self.slideCursor)
        self._overridden = True

    def restoreOverrideCursor(self):
        """Restore the overridden cursor"""
        if not self._overridden:
            return
        QApplication.restoreOverrideCursor()
        self._overridden = False

    def eventFilter(self, obj, event):
        """Event filter override

        Parameters
        ----------
        obj : QObject
            The object to get events for
        event : QEvent
            The event being filtered

        Returns
        -------

        """
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
                    except Exception:
                        # fix the cursor if there's an error during slideging
                        self.restoreOverrideCursor()
                        raise  # re-raise the exception
                    return True

            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() & self.slideButton:
                    self._pressed = False
                    self._slideStart = False
                    self.myendSlide(obj, event)
                    return True

        return super(SlideFilter, self).eventFilter(obj, event)

    def startSlide(self, obj, event):
        """Start the slide operation

        Parameters
        ----------
        obj : QObject
            The object to get events for
        event : QEvent
            The event being filtered

        Returns
        -------

        """
        self.slidePressed.emit()
        self.doOverrideCursor()

    def doSlide(self, obj, event):
        """Do a slide tick

        Parameters
        ----------
        obj : QObject
            The object to get events for
        event : QEvent
            The event being filtered

        Returns
        -------

        """
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
        """End the slide operation

        Parameters
        ----------
        obj : QObject
            The object to get events for
        event : QEvent
            The event being filtered

        Returns
        -------

        """
        self.restoreOverrideCursor()
        self._slideStart = None
        self.slideReleased.emit()


class ChannelBoxDelegate(QStyledItemDelegate):
    """Delegate to draw the slider items"""

    def __init__(self, parent=None):
        super(ChannelBoxDelegate, self).__init__(parent)
        self.store = {}

    def paint(self, painter, opt, index):
        """Overridden paint function"""
        item = index.model().itemFromIndex(index)
        if isinstance(item, Slider):
            self.paintSlider(self, item, painter, opt.rect, opt.palette)
        else:
            super(ChannelBoxDelegate, self).paint(painter, opt, index)

    def roundedPath(self, width, height, left=True, right=True):
        """Get a path with rounded corners for drawing

        Parameters
        ----------
        width : float
            The width of the rectangle
        height : float
            The height of the rectangle
        left : bool
            Round the left side of the rectangle (Default value = True)
        right : bool
            Round the right side of the rectangle (Default value = True)

        Returns
        -------
        QPainterPath
            The requested path

        """
        key = (round(width, 2), round(height, 2), round(left, 2), round(right, 2))
        if key in self.store:
            return self.store[key]

        # off = 0.5
        off = 1.0
        ew = height - off  # ellipse width
        eh = height - 2 * off  # ellipse height
        ts = 0.0 + off  # topside
        bs = height - off  # bottomside
        ls = 0.0 + off  # left side
        rs = width - off  # righSide
        lc = height + off  # left corner
        rc = width - height - off  # left corner

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
        """Paint a slider

        Parameters
        ----------
        delegate : QStyledItemDelegate
            The paint delegate
        slider : Slider
            The slider to paint
        painter : QPainter
            The painter to paint with
        rect : QRectF
            The rectangle to fill
        palette : QPalette
            The palette to use

        Returns
        -------

        """
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
                fgPath = self.roundedPath(
                    abs(perc) * rw * 0.5, rh, left=not right, right=right
                )
                if right:
                    fgPath = fgPath.translated(rx + rw * 0.5, ry)
                else:
                    fgPath = fgPath.translated(rx + rw * 0.5 * (1 + perc), ry)
                painter.fillPath(fgPath, fgBrush)

            else:
                # Positive only slider
                perc = slider.value
                perc = max(min(perc, 1.0), 0.0)  # clamp between 0 and 1
                fgPath = self.roundedPath(rw * perc, rh, left=False)
                fgPath = fgPath.translated(rx, ry)
                painter.fillPath(fgPath, fgBrush)

            opts = QTextOption(Qt.AlignCenter)
            frect = QRectF(rx, ry, rw, rh)
            painter.drawText(frect, slider.name, opts)
            # painter.drawPath(bgPath)
        finally:
            painter.restore()


class ChannelListModel(QAbstractItemModel):
    """A model to handle a list of sliders
    Many functions will be un-documented. They're just overrides
    for the QAbstractItemModel. Look at the Qt docs if you really
    want to know

    Parameters
    ----------
    simplex : Simplex
        The simplex system
    parent : QObject
        The parent of this model
    """

    def __init__(self, simplex, parent):
        super(ChannelListModel, self).__init__(parent)
        self.simplex = simplex
        self.simplex.models.append(self)
        self.channels = []

    def setChannels(self, channels):
        """Set the channels to display in this model

        Parameters
        ----------
        channels : [object, ...]
            A list of tree objects to show in Channel Box

        Returns
        -------

        """
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
    """A list to display the chosen channels"""

    def __init__(self, parent=None):
        super(ChannelList, self).__init__(parent)
        self.slider = None
        self._nxt = 0.0
        self.start = False
        self.residual = 0.0

    def slideStart(self):
        """Handle user sliding values"""
        p = self.mapFromGlobal(QCursor.pos())
        item = self.indexAt(p).internalPointer()
        if isinstance(item, Slider):
            self.slider = item
            self.start = True

    def slideStop(self):
        """End the user sliding values"""
        self.slider = None

    def slideTick(self, val, offset, mul):
        """Handle the ticks from the slider Filter"""
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
                val = offset * (mx - mn)
                val = self.slider.value + (val * mul)
                val += self.residual
                rn = round(val * tick) / tick
                self.residual = val - rn

            rn = min(max(rn, mn), mx)
            # Do this to keep the ui snappy
            self._nxt = rn
            QTimer.singleShot(0, self.setval)

    def setval(self):
        """Set the value of a slider"""
        if self.slider is not None and self._nxt is not None:
            self.slider.value = self._nxt
        self._nxt = None


class ChannelTreeModel(SimplexModel):
    """A model to handle a tree of sliders from a simplex system
    Many functions will be un-documented. They're just overrides
    for the QAbstractItemModel or the SimplexModel.
    """

    def getChildItem(self, parent, row):
        try:
            if isinstance(parent, Group):
                return parent.items[row]
            elif parent is None:
                return self.simplex.sliderGroups[row]
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
                    # return "{0}: {1:.2f}".format(item.name, item.value)
            print("BAD ICR", item, column, role)
            return "BAD"
        return None

    def typeHandled(self, item):
        if isinstance(item, Group):
            return item.groupType == Slider
        return isinstance(item, Slider)


class ChannelTree(QTreeView):
    """Display the channels in a Tree form"""

    def __init__(self, parent=None):
        super(ChannelTree, self).__init__(parent)
        self.slider = None
        self._nxt = 0.0
        self.start = False
        self.residual = 0.0

    def slideStart(self):
        """Handle starting a slide drag operation"""
        p = self.mapFromGlobal(QCursor.pos())
        item = self.indexAt(p).internalPointer()
        if isinstance(item, Slider):
            self.slider = item
            self.start = True

    def slideStop(self):
        """Handle ending a slide drag operation"""
        self.slider = None

    def slideTick(self, val, offset, mul):
        """Handle the ticks from the SliderFilter"""
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
                val = offset * (mx - mn)
                val = self.slider.value + (val * mul)
                val += self.residual
                rn = round(val * tick) / tick
                self.residual = val - rn

            rn = min(max(rn, mn), mx)
            # Do this to keep the ui snappy
            self._nxt = rn
            QTimer.singleShot(0, self.setval)

    def setval(self):
        """Set the value of a slider"""
        if self.slider is not None and self._nxt is not None:
            self.slider.value = self._nxt
        self._nxt = None


# DISPLAY TESTS
def testSliderListDisplay(smpxPath):
    """

    Parameters
    ----------
    smpxPath :


    Returns
    -------

    """
    simp = Simplex.buildSystemFromSmpx(smpxPath)
    channels = []

    redAttrs = set(
        [
            "lowerLipDepressor_X",
            "stretcher_X",
            "platysmaFlex_X",
            "cheekRaiser_X",
            "jawOpen",
            "lidTightener_X",
            "outerBrowRaiser_X",
            "eyesClosed_X",
            "cornerPuller_X",
            "noseWrinkler_X",
            "lipsBlow_X",
            "cornerDepressor_X",
            "funneler",
            "browLateral_X",
            "innerBrowRaiser_X",
            "upperLipRaiser_X",
            "chinRaiser",
            "cheek_SuckBlow_X",
            "pucker",
            "eyeGaze_DownUp_X",
            "eyeGaze_RightLeft_X",
            "upperLidTweak_X",
            "lowerLidTweak_X",
        ]
    )
    greenAttrs = set(
        [
            "nasolabialDeepener_X",
            "neckStretcher_X",
            "lipsPressed_T",
            "lipsPressed_B",
            "throatCompress",
            "lipsRolled_InOut_B",
            "lipsRolled_InOut_T",
            "sharpCornerPuller_X",
            "dimpler_X",
            "eyeBlink_X",
            "scalpSlide_BackFwd",
            "browDown_X",
            "mouthSwing_RightLeft",
            "sternoFlex_X",
            "throatOpen",
        ]
    )
    blueAttrs = set(
        [
            "adamsApple",
            "noseSwing_RightLeft",
            "nostrilCompress_X",
            "jawThrust_BackFwd",
            "eyesWide_X",
            "lipsVerticalT_X",
            "lipsVerticalB_X",
            "earPull_X",
            "lipsTighten_T",
            "lipsTighten_B",
            "lipsCompress_T",
            "lipsCompress_B",
            "lipsShift_RightLeft_B",
            "lipsShift_RightLeft_T",
            "lipsNarrowT_X",
            "lipsNarrowB_X",
            "jawSwing_RightLeft",
            "nostril_SuckFlare_X",
            "lipsCorner_DownUp_X",
            "jawClench",
        ]
    )
    greyAttrs = set(["lipsTogether"])

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
    """

    Parameters
    ----------
    smpxPath :


    Returns
    -------

    """
    simp = Simplex.buildSystemFromSmpx(smpxPath)

    redAttrs = set(
        [
            "lowerLipDepressor_X",
            "stretcher_X",
            "platysmaFlex_X",
            "cheekRaiser_X",
            "jawOpen",
            "lidTightener_X",
            "outerBrowRaiser_X",
            "eyesClosed_X",
            "cornerPuller_X",
            "noseWrinkler_X",
            "lipsBlow_X",
            "cornerDepressor_X",
            "funneler",
            "browLateral_X",
            "innerBrowRaiser_X",
            "upperLipRaiser_X",
            "chinRaiser",
            "cheek_SuckBlow_X",
            "pucker",
            "eyeGaze_DownUp_X",
            "eyeGaze_RightLeft_X",
            "upperLidTweak_X",
            "lowerLidTweak_X",
        ]
    )
    greenAttrs = set(
        [
            "nasolabialDeepener_X",
            "neckStretcher_X",
            "lipsPressed_T",
            "lipsPressed_B",
            "throatCompress",
            "lipsRolled_InOut_B",
            "lipsRolled_InOut_T",
            "sharpCornerPuller_X",
            "dimpler_X",
            "eyeBlink_X",
            "scalpSlide_BackFwd",
            "browDown_X",
            "mouthSwing_RightLeft",
            "sternoFlex_X",
            "throatOpen",
        ]
    )
    blueAttrs = set(
        [
            "adamsApple",
            "noseSwing_RightLeft",
            "nostrilCompress_X",
            "jawThrust_BackFwd",
            "eyesWide_X",
            "lipsVerticalT_X",
            "lipsVerticalB_X",
            "earPull_X",
            "lipsTighten_T",
            "lipsTighten_B",
            "lipsCompress_T",
            "lipsCompress_B",
            "lipsShift_RightLeft_B",
            "lipsShift_RightLeft_T",
            "lipsNarrowT_X",
            "lipsNarrowB_X",
            "jawSwing_RightLeft",
            "nostril_SuckFlare_X",
            "lipsCorner_DownUp_X",
            "jawClench",
        ]
    )
    greyAttrs = set(["lipsTogether"])

    app = QApplication(sys.argv)
    # tv = ChannelTree()
    tv = QTreeView()
    model = ChannelTreeModel(simp, None)
    # delegate = ChannelBoxDelegate()

    # slideFilter = SlideFilter(tv.viewport())
    # slideFilter.slideButton = Qt.LeftButton
    # tv.viewport().installEventFilter(slideFilter)
    # slideFilter.slidePressed.connect(tv.slideStart)
    # slideFilter.slideReleased.connect(tv.slideStop)
    # slideFilter.slideTick.connect(tv.slideTick)

    # for g in simp.sliderGroups:
    # for item in g.items:
    # if item.name in redAttrs:
    # item.color = QColor(178, 103, 103)
    # elif item.name in greenAttrs:
    # item.color = QColor(90, 161, 27)
    # elif item.name in blueAttrs:
    # item.color = QColor(103, 141, 178)
    # elif item.name in greyAttrs:
    # item.color = QColor(130, 130, 130)

    tv.setModel(model)
    # tv.setItemDelegate(delegate)

    tv.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    basePath = r"D:\Users\tyler\Documents\GitHub\Simplex\Useful"
    smpxPath = os.path.join(basePath, "HeadMaleStandard_High_Unsplit.smpx")

    testSliderTreeDisplay(smpxPath)
