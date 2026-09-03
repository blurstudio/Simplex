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
from __future__ import annotations
import struct
from .interfaceModel import FalloffDataModel
from .items.falloff import PlanarFalloff
from Qt import QtCompat
from Qt.QtCore import (
    QByteArray,
    QLineF,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    Signal,
)
from Qt.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPaintEvent,
    QMouseEvent,
    QHideEvent,
    QShowEvent,
)
from Qt.QtWidgets import (
    QComboBox,
    QDataWidgetMapper,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from .utils import getNextName, getUiFile, Prefs
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .simplexDialog import SimplexDialog
    from .items import Simplex


class CurveEditWidget(QWidget):
    tangentUpdated = Signal(float, float)

    def __init__(self, parent: Optional[QWidget]):
        super().__init__(parent)
        self.leftTan: Optional[float] = None
        self.rightTan: Optional[float] = None
        self._controlPoints: list[QPointF] = [
            QPointF(0, 1),
            QPointF(0, 1),
            QPointF(1, 0),
            QPointF(1, 0),
        ]
        self.setTangent(leftTan=1 / 3.0, rightTan=2 / 3.0)

        self._activeControlPoint: Optional[int] = None
        self.mouseDrag: bool = False
        self.mousePress: QPoint = QPoint()
        self.startDragDistance: int = 20

        self.canvasMargin: int = 16
        self.setMinimumHeight(2 * self.canvasMargin)

        self.bgColor: Qt.GlobalColor = Qt.GlobalColor.white
        self.lineColor: Qt.GlobalColor = Qt.GlobalColor.black
        self.limitColor: Qt.GlobalColor = Qt.GlobalColor.gray

    def setTangent(
        self, leftTan: Optional[float] = None, rightTan: Optional[float] = None
    ):
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

    def mapToCanvas(self, point: QPointF) -> QPointF:
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

    def mapFromCanvas(self, point: QPointF) -> QPointF:
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

    def _drawCleanLine(self, painter: QPainter, p1: QPointF, p2: QPointF):
        painter.drawLine(p1 + QPointF(0.5, 0.5), p2 + QPointF(0.5, 0.5))

    def _paintBG(self, painter: QPainter):
        painter.save()
        painter.setBrush(self.palette().color(QPalette.ColorRole.Window))
        painter.drawRect(0, 0, self.width(), self.height())
        painter.restore()

    def _paintLimits(self, painter: QPainter):
        painter.save()
        # pen = QPen(self.limitColor)
        baseColor = self.palette().color(QPalette.ColorRole.Base)
        pen = QPen(baseColor)
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        self._drawCleanLine(
            painter, self.mapToCanvas(QPointF(0, 0)), self.mapToCanvas(QPointF(1, 0))
        )
        self._drawCleanLine(
            painter, self.mapToCanvas(QPointF(0, 1)), self.mapToCanvas(QPointF(1, 1))
        )
        painter.restore()

    def _paintPath(
        self, painter: QPainter, p0: QPointF, p1: QPointF, p2: QPointF, p3: QPointF
    ):
        painter.save()
        path = QPainterPath()
        path.moveTo(p0)
        path.cubicTo(p1, p2, p3)
        # painter.strokePath(path, QPen(QBrush(self.lineColor), 2))
        foregroundColor = self.palette().color(QPalette.ColorRole.WindowText)
        painter.strokePath(path, QPen(QBrush(foregroundColor), 2))
        painter.restore()

    def _paintTangents(
        self, painter: QPainter, p0: QPointF, p1: QPointF, p2: QPointF, p3: QPointF
    ):
        # draw the tangent lines
        foregroundColor = self.palette().color(QPalette.ColorRole.WindowText)
        pen = QPen(foregroundColor)
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(p0, p1)
        painter.drawLine(p3, p2)

        for i in range(len(self._controlPoints)):
            online = self.indexIsRealPoint(i)
            active = i == self._activeControlPoint
            self.paintControlPoint(self._controlPoints[i], painter, online, active)

    def paintEvent(self, e: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._paintBG(painter)
        self._paintLimits(painter)

        # load the points
        p0 = self.mapToCanvas(self._controlPoints[0])
        p1 = self.mapToCanvas(self._controlPoints[1])
        p2 = self.mapToCanvas(self._controlPoints[2])
        p3 = self.mapToCanvas(self._controlPoints[3])

        self._paintPath(painter, p0, p1, p2, p3)
        self._paintTangents(painter, p0, p1, p2, p3)

    def indexIsRealPoint(self, i: int):
        return (i % 3) == 0

    def paintControlPoint(
        self, point: QPointF, painter: QPainter, real: bool, active: bool
    ):
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

    def findControlPoint(self, point: QPointF, tolerance: int = 10) -> Optional[int]:
        d = QLineF(self.mapToCanvas(self._controlPoints[1]), point).length()
        if d < tolerance:
            return 1

        d = QLineF(self.mapToCanvas(self._controlPoints[2]), point).length()
        if d < tolerance:
            return 2
        return None

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._activeControlPoint = self.findControlPoint(e.position())
            if self._activeControlPoint is not None:
                self.mouseMoveEvent(e)
            self.mousePress = e.pos()
            e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._activeControlPoint = None
            self.mouseDrag = False
            e.accept()

    def mouseMoveEvent(self, e: QMouseEvent):
        if (
            not self.mouseDrag
            and QPoint(self.mousePress - e.pos()).manhattanLength()
            > self.startDragDistance
        ):
            self.mouseDrag = True

        p = self.mapFromCanvas(e.position())
        if self.mouseDrag and self._activeControlPoint is not None:
            if self._activeControlPoint == 1:
                self.setTangent(leftTan=min(max(p.x(), 0.0), 1.0))
            else:
                self.setTangent(rightTan=min(max(p.x(), 0.0), 1.0))
            self.tangentUpdated.emit(self.leftTan, self.rightTan)
        self.update()


class FalloffDialog(QDialog):
    """The ui for interacting with Falloffs"""

    uiFalloffSettingsGRP: QGroupBox
    uiShapeFalloffLBL: QLabel
    uiShapeFalloffCBOX: QComboBox
    uiShapeFalloffRenameBTN: QPushButton
    uiShapeFalloffNewBTN: QPushButton
    uiShapeFalloffDuplicateBTN: QPushButton
    uiShapeFalloffDeleteBTN: QPushButton
    uiFalloffLAY: QVBoxLayout
    uiFalloffTypeCBOX: QComboBox
    uiFalloffAxisCBOX: QComboBox
    uiFalloffMaxSPN: QDoubleSpinBox
    uiFalloffMaxHandleSPN: QDoubleSpinBox
    uiFalloffMinHandleSPN: QDoubleSpinBox
    uiFalloffMinSPN: QDoubleSpinBox

    def __init__(self, parent: SimplexDialog):
        super().__init__(parent)
        uiPath = getUiFile(__file__)
        QtCompat.loadUi(uiPath, self)
        self.parUI: SimplexDialog = parent

        self.simplex: Optional[Simplex] = None
        self.parUI.simplexLoaded.connect(self.loadSimplex)
        self.foModel = FalloffDataModel(None, self)

        self.uiFalloffWID = CurveEditWidget(self)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
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

    def updateTangents(self, leftTangent: float, rightTangent: float):
        self.uiFalloffMaxHandleSPN.setValue(leftTangent)
        self.uiFalloffMinHandleSPN.setValue(rightTangent)

        cbIdx = self.uiShapeFalloffCBOX.currentIndex()

        leftTanIdx = self.foModel.index(cbIdx, 5)
        rightTanIdx = self.foModel.index(cbIdx, 4)

        self.foModel.setData(leftTanIdx, leftTangent, role=Qt.ItemDataRole.EditRole)
        self.foModel.setData(rightTanIdx, rightTangent, role=Qt.ItemDataRole.EditRole)

    def setLeftTangent(self, val: float):
        self.uiFalloffWID.setTangent(leftTan=val)

    def setRightTangent(self, val: float):
        self.uiFalloffWID.setTangent(rightTan=val)

    def loadSimplex(self):
        """Load the Simplex system from the parent UI"""
        system = self.parUI.simplex
        if system == self.simplex:
            return

        if system is None:
            self.foModel = FalloffDataModel(None, self)
            self.uiShapeFalloffCBOX.setModel(self.foModel)
            if self._falloffMapper is not None:
                self._falloffMapper.clearMapping()
                self._falloffMapper.setModel(self.foModel)
            self.uiFalloffSettingsGRP.setEnabled(False)
            return
        else:
            self.uiFalloffSettingsGRP.setEnabled(True)

        self.simplex = system

        # Populate Settings widgets
        self.foModel = FalloffDataModel(self.simplex, self)
        self.uiShapeFalloffCBOX.setModel(self.foModel)
        self._falloffMapper.setModel(self.foModel)

        currentIndex = QByteArray("currentIndex".encode())

        self._falloffMapper.addMapping(self.uiFalloffTypeCBOX, 1, currentIndex)
        self._falloffMapper.addMapping(self.uiFalloffAxisCBOX, 2, currentIndex)
        self._falloffMapper.addMapping(self.uiFalloffMinSPN, 3)
        self._falloffMapper.addMapping(self.uiFalloffMinHandleSPN, 4)
        self._falloffMapper.addMapping(self.uiFalloffMaxHandleSPN, 5)
        self._falloffMapper.addMapping(self.uiFalloffMaxSPN, 6)

        self.uiShapeFalloffCBOX.setCurrentIndex(0)
        self._falloffMapper.setCurrentIndex(0)

    # Falloff Settings
    def newFalloff(self):
        """Create a new Falloff object"""
        if self.simplex is None:
            return
        foNames = [f.name for f in self.simplex.falloffs]
        tempName = getNextName("NewFalloff", foNames)

        newName, good = QInputDialog.getText(
            self, "Rename Falloff", "Enter a new name for the Falloff", text=tempName
        )
        if not good:
            return

        if not newName.isidentifier():
            message = "Falloff name can only contain letters and numbers, and cannot start with a number"
            QMessageBox.warning(self, "Warning", message)
            return

        nn = getNextName(newName, foNames)
        PlanarFalloff.createPlanar(nn, self.simplex, "X", 1.0, 0.66, 0.33, -1.0)

    def duplicateFalloff(self):
        """Duplicate the selected falloff"""
        if self.simplex is None:
            return
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
        if not self.simplex or not self.simplex.falloffs:
            return
        idx = self.uiShapeFalloffCBOX.currentIndex()
        if idx < 0:
            return

        fo = self.simplex.falloffs[idx]
        fo.delete()

    def renameFalloff(self):
        """Rename the selected falloff"""
        if not self.simplex or not self.simplex.falloffs:
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

        if not newName.isidentifier():
            message = "Falloff name can only contain letters and numbers, and cannot start with a number"
            QMessageBox.warning(self, "Warning", message)
            return

        nn = getNextName(newName, foNames)
        fo.name = nn

    def storeSettings(self):
        """Store the UI settings for this dialog"""
        pref = Prefs()
        pref.recordProperty("fogeometry", self.saveGeometry().data())
        pref.save()

    def loadSettings(self):
        """Load the UI settings for this dialog"""
        pref = Prefs()
        geo = pref.restoreProperty("fogeometry", None)
        if geo is not None:
            if isinstance(geo, bytes):
                geo = QByteArray(geo)
            self.restoreGeometry(geo)

    def hideEvent(self, event: QHideEvent):
        """Override the hide event to store settings"""
        self.storeSettings()
        super().hideEvent(event)

    def showEvent(self, event: QShowEvent):
        """Override the show event to restore settings"""
        super().showEvent(event)
        self.loadSettings()
