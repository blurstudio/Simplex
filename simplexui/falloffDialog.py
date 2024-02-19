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

# This module imports QT from PyQt4, PySide or PySide2
# Depending on what's available
from __future__ import absolute_import, print_function

import os
import re

import six
from six.moves import range

from . import Qt as QtLib
from .interfaceModel import FalloffDataModel
from .items import Falloff
from .Qt import QtCompat
from .Qt.QtCore import (
    QByteArray,
    QLineF,
    QPoint,
    QPointF,
    QRectF,
    QSettings,
    Qt,
    Signal,
)
from .Qt.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QStandardItemModel,
)
from .Qt.QtWidgets import (
    QDataWidgetMapper,
    QDialog,
    QInputDialog,
    QMessageBox,
    QSizePolicy,
    QWidget,
)
from .utils import getNextName, getUiFile, Prefs

AT_BLUR = os.environ.get("SIMPLEX_AT_BLUR") == "true"
NAME_CHECK = re.compile(r"[A-Za-z][\w.]*")


class CurveEditWidget(QWidget):
    tangentUpdated = Signal(float, float)

    def __init__(self, parent):
        super(CurveEditWidget, self).__init__(parent)
        self.leftTan = None
        self.rightTan = None
        self._controlPoints = [
            QPointF(0, 1),
            QPointF(0, 1),
            QPointF(1, 0),
            QPointF(1, 0),
        ]
        self.setTangent(leftTan=1 / 3.0, rightTan=2 / 3.0)

        self._activeControlPoint = None
        self.mouseDrag = False
        self.mousePress = QPoint()
        self.startDragDistance = 20

        self.canvasMargin = 16
        self.setMinimumHeight(2 * self.canvasMargin)

        self.bgColor = Qt.white
        self.lineColor = Qt.black
        self.limitColor = Qt.gray

    def setTangent(self, leftTan=None, rightTan=None):
        """Set the falloff tangents, clamped 0 to 1

        Parameters
        ----------
        leftTan : float
            The x-value of the left tangent point
        rightTan : float
            The x-value of the right tangent point
        """
        if leftTan is not None:
            self.leftTan = max(min(leftTan, 1.0), 0.0)
            self._controlPoints[1] = QPointF(self.leftTan, 1)
        if rightTan is not None:
            self.rightTan = max(min(rightTan, 1.0), 0.0)
            self._controlPoints[2] = QPointF(self.rightTan, 0)
        self.update()

    def mapToCanvas(self, point):
        """Map a point from widget space to canvas space
        The "canvas" is a 0-1 parameterized space, centered in the widget
        The size of the canvas relative to the widget is dictated by the canvasMargin

        Parameters
        ----------
        point : QPointF
            The point to map

        Returns
        -------
        : QPointF
            The mapped point
        """
        canvasWidth = self.width() - 2 * self.canvasMargin
        canvasHeight = self.height() - 2 * self.canvasMargin

        x = point.x() * canvasWidth + self.canvasMargin
        y = canvasHeight - point.y() * canvasHeight + self.canvasMargin
        return QPointF(x, y)

    def mapFromCanvas(self, point):
        """Map a point from canvas space to widget space
        The "canvas" is a 0-1 parameterized space, centered in the widget
        The size of the canvas relative to the widget is dictated by the canvasMargin

        Parameters
        ----------
        point : QPointF
            The point to map

        Returns
        -------
        : QPointF
            The mapped point
        """
        canvasWidth = self.width() - 2 * self.canvasMargin
        canvasHeight = self.height() - 2 * self.canvasMargin

        x = (point.x() - self.canvasMargin) / float(canvasWidth)
        y = 1.0 - (point.y() - self.canvasMargin) / float(canvasHeight)
        return QPointF(x, y)

    def _drawCleanLine(self, painter, p1, p2):
        painter.drawLine(p1 + QPointF(0.5, 0.5), p2 + QPointF(0.5, 0.5))

    def _paintBG(self, painter):
        painter.save()
        painter.setBrush(self.palette().color(QPalette.Background))
        painter.drawRect(0, 0, self.width(), self.height())
        painter.restore()

    def _paintLimits(self, painter):
        painter.save()
        # pen = QPen(self.limitColor)
        baseColor = self.palette().color(QPalette.Base)
        pen = QPen(baseColor)
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        self._drawCleanLine(
            painter, self.mapToCanvas(QPoint(0, 0)), self.mapToCanvas(QPoint(1, 0))
        )
        self._drawCleanLine(
            painter, self.mapToCanvas(QPoint(0, 1)), self.mapToCanvas(QPoint(1, 1))
        )
        painter.restore()

    def _paintPath(self, painter, p0, p1, p2, p3):
        painter.save()
        path = QPainterPath()
        path.moveTo(p0)
        path.cubicTo(p1, p2, p3)
        # painter.strokePath(path, QPen(QBrush(self.lineColor), 2))
        foregroundColor = self.palette().color(QPalette.Foreground)
        painter.strokePath(path, QPen(QBrush(foregroundColor), 2))
        painter.restore()

    def _paintTangents(self, painter, p0, p1, p2, p3):
        # draw the tangent lines
        foregroundColor = self.palette().color(QPalette.Foreground)
        pen = QPen(foregroundColor)
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(p0, p1)
        painter.drawLine(p3, p2)

        for i in range(len(self._controlPoints)):
            online = self.indexIsRealPoint(i)
            active = i == self._activeControlPoint
            self.paintControlPoint(self._controlPoints[i], painter, online, active)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        self._paintBG(painter)
        self._paintLimits(painter)

        # load the points
        p0 = self.mapToCanvas(self._controlPoints[0])
        p1 = self.mapToCanvas(self._controlPoints[1])
        p2 = self.mapToCanvas(self._controlPoints[2])
        p3 = self.mapToCanvas(self._controlPoints[3])

        self._paintPath(painter, p0, p1, p2, p3)
        self._paintTangents(painter, p0, p1, p2, p3)

    def indexIsRealPoint(self, i):
        return (i % 3) == 0

    def paintControlPoint(self, point, painter, real, active):
        pointSize = 4

        if real:
            pointSize = 6
            painter.setBrush(QColor(80, 80, 210, 150))
        elif active:
            painter.setBrush(QColor(140, 140, 240, 255))
        else:
            painter.setBrush(QColor(120, 120, 220, 255))

        painter.setPen(QColor(50, 50, 50, 140))

        painter.drawRect(
            QRectF(
                self.mapToCanvas(point).x() - pointSize + 0.5,
                self.mapToCanvas(point).y() - pointSize + 0.5,
                pointSize * 2,
                pointSize * 2,
            )
        )

    def findControlPoint(self, point, tolerance=10):
        d = QLineF(self.mapToCanvas(self._controlPoints[1]), point).length()
        if d < tolerance:
            return 1

        d = QLineF(self.mapToCanvas(self._controlPoints[2]), point).length()
        if d < tolerance:
            return 2
        return None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._activeControlPoint = self.findControlPoint(e.pos())
            if self._activeControlPoint is not None:
                self.mouseMoveEvent(e)
            self.mousePress = e.pos()
            e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._activeControlPoint = None
            self.mouseDrag = False
            e.accept()

    def mouseMoveEvent(self, e):
        if (
            not self.mouseDrag
            and QPoint(self.mousePress - e.pos()).manhattanLength()
            > self.startDragDistance
        ):
            self.mouseDrag = True

        p = self.mapFromCanvas(e.pos())
        if self.mouseDrag and self._activeControlPoint is not None:
            if self._activeControlPoint == 1:
                self.setTangent(leftTan=min(max(p.x(), 0.0), 1.0))
            else:
                self.setTangent(rightTan=min(max(p.x(), 0.0), 1.0))
            self.tangentUpdated.emit(self.leftTan, self.rightTan)
        self.update()


class FalloffDialog(QDialog):
    """The ui for interacting with Falloffs"""

    def __init__(self, parent):
        super(FalloffDialog, self).__init__(parent)
        uiPath = getUiFile(__file__)
        QtCompat.loadUi(uiPath, self)
        self.parUI = parent

        self.simplex = None
        self.parUI.simplexLoaded.connect(self.loadSimplex)
        self.foModel = QStandardItemModel()

        self.uiFalloffWID = CurveEditWidget(self)
        policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        # policy.setVerticalStretch(1)
        self.uiFalloffWID.setSizePolicy(policy)
        self.uiFalloffWID.tangentUpdated.connect(self.updateTangents)

        self.uiFalloffLAY.addWidget(self.uiFalloffWID)

        self._falloffMapper = QDataWidgetMapper(self)
        self.uiShapeFalloffCBOX.currentIndexChanged.connect(
            self._falloffMapper.setCurrentIndex
        )

        # Falloff connections
        self.uiShapeFalloffNewBTN.clicked.connect(self.newFalloff)
        self.uiShapeFalloffDuplicateBTN.clicked.connect(self.duplicateFalloff)
        self.uiShapeFalloffDeleteBTN.clicked.connect(self.deleteFalloff)
        self.uiShapeFalloffRenameBTN.clicked.connect(self.renameFalloff)

        self.uiFalloffMaxHandleSPN.valueChanged.connect(self.setLeftTangent)
        self.uiFalloffMinHandleSPN.valueChanged.connect(self.setRightTangent)
        self.loadSimplex()

    def updateTangents(self, leftTangent, rightTangent):
        self.uiFalloffMaxHandleSPN.setValue(leftTangent)
        self.uiFalloffMinHandleSPN.setValue(rightTangent)

        cbIdx = self.uiShapeFalloffCBOX.currentIndex()

        leftTanIdx = self.foModel.index(cbIdx, 5)
        rightTanIdx = self.foModel.index(cbIdx, 4)

        self.foModel.setData(leftTanIdx, leftTangent, role=Qt.EditRole)
        self.foModel.setData(rightTanIdx, rightTangent, role=Qt.EditRole)

    def setLeftTangent(self, val):
        self.uiFalloffWID.setTangent(leftTan=val)

    def setRightTangent(self, val):
        self.uiFalloffWID.setTangent(rightTan=val)

    def loadSimplex(self):
        """Load the Simplex system from the parent UI"""
        system = self.parUI.simplex
        if system == self.simplex:
            return

        if system is None:
            self.foModel = QStandardItemModel()
            self.uiShapeFalloffCBOX.setModel(self.foModel)
            if self._falloffMapper is not None:
                self._falloffMapper.clearMapping()
                self._falloffMapper.setModel(self.foModel)
            self.uiFalloffSettingsGRP.setEnabled(False)
            return
        else:
            self.uiFalloffSettingsGRP.setEnabled(True)

        print("Setting System")
        self.simplex = system

        # Populate Settings widgets
        print("Populating")
        self.foModel = FalloffDataModel(self.simplex, self)
        self.simplex.falloffModels.append(self.foModel)
        self.uiShapeFalloffCBOX.setModel(self.foModel)
        self._falloffMapper.setModel(self.foModel)

        print("Adding Mappings")
        currentIndex = "currentIndex"
        if six.PY3 and (QtLib.IsPySide2 or QtLib.IsPyQt5):
            currentIndex = QByteArray(bytes("Test", encoding="utf-8"))

        self._falloffMapper.addMapping(self.uiFalloffTypeCBOX, 1, currentIndex)
        self._falloffMapper.addMapping(self.uiFalloffAxisCBOX, 2, currentIndex)
        self._falloffMapper.addMapping(self.uiFalloffMinSPN, 3)
        self._falloffMapper.addMapping(self.uiFalloffMinHandleSPN, 4)
        self._falloffMapper.addMapping(self.uiFalloffMaxHandleSPN, 5)
        self._falloffMapper.addMapping(self.uiFalloffMaxSPN, 6)

        print("Setting Index 0")
        self.uiShapeFalloffCBOX.setCurrentIndex(0)
        self._falloffMapper.setCurrentIndex(0)

    # Falloff Settings
    def newFalloff(self):
        """Create a new Falloff object"""
        foNames = [f.name for f in self.simplex.falloffs]
        tempName = getNextName("NewFalloff", foNames)

        newName, good = QInputDialog.getText(
            self, "Rename Falloff", "Enter a new name for the Falloff", text=tempName
        )
        if not good:
            return

        if not NAME_CHECK.match(newName):
            message = "Falloff name can only contain letters and numbers, and cannot start with a number"
            QMessageBox.warning(self, "Warning", message)
            return

        nn = getNextName(newName, foNames)
        Falloff.createPlanar(nn, self.simplex, "X", 1.0, 0.66, 0.33, -1.0)

    def duplicateFalloff(self):
        """Duplicate the selected falloff"""
        if not self.simplex.falloffs:
            self.newFalloff()
            return

        idx = self.uiShapeFalloffCBOX.currentIndex()
        if idx < 0:
            return

        fo = self.simplex.falloffs[idx]

        foNames = [f.name for f in self.simplex.falloffs]
        nn = getNextName(fo.name, foNames)
        fo.duplicate(nn)

    def deleteFalloff(self):
        """Delete the selected falloff"""
        if not self.simplex.falloffs:
            return
        idx = self.uiShapeFalloffCBOX.currentIndex()
        if idx < 0:
            return

        fo = self.simplex.falloffs[idx]
        fo.delete()

    def renameFalloff(self):
        """Rename the selected falloff"""
        if not self.simplex.falloffs:
            return
        idx = self.uiShapeFalloffCBOX.currentIndex()
        if idx < 0:
            return
        fo = self.simplex.falloffs[idx]
        foNames = [f.name for f in self.simplex.falloffs]
        foNames.pop(idx)

        newName, good = QInputDialog.getText(
            self, "Rename Falloff", "Enter a new name for the Falloff", text=fo.name
        )
        if not good:
            return

        if not NAME_CHECK.match(newName):
            message = "Falloff name can only contain letters and numbers, and cannot start with a number"
            QMessageBox.warning(self, "Warning", message)
            return

        nn = getNextName(newName, foNames)
        fo.name = nn

    def storeSettings(self):
        """Store the UI settings for this dialog"""
        pref = Prefs()
        pref.recordProperty("fogeometry", self.saveGeometry())
        pref.save()

    def loadSettings(self):
        """Load the UI settings for this dialog"""
        pref = Prefs()
        geo = pref.restoreProperty("fogeometry", None)
        if geo is not None:
            self.restoreGeometry(geo)

    def hideEvent(self, event):
        """Override the hide event to store settings"""
        self.storeSettings()
        super(FalloffDialog, self).hideEvent(event)

    def showEvent(self, event):
        """Override the show event to restore settings"""
        super(FalloffDialog, self).showEvent(event)
        self.loadSettings()
