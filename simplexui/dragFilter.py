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


from .Qt.QtCore import QEvent, QObject, QPoint, Qt, Signal
from .Qt.QtGui import QCursor, QMouseEvent
from .Qt.QtWidgets import QApplication


class DragFilter(QObject):
    """Drag Event Filter

    This class provides an event filter that can be installed
    on a Qt Widget to take click/drag events and give them slider
    type interaction.

    Signals:
        dragPressed = Signal()
            Emitted when the drag passes the startSensitivity
        dragTick (int, float):
            NumberOfTicks, TickMultiplier
            Emitted after dragPressed every time the drag passes dragSensitivity
        dragReleased = Signal()
            Emitted when the mouse is released after dragPressed

    Instance Options:
        dragSensitivity(int): default=5
            The number of pixels the cursor has to travel to emit a tick
        startSensitivity(int): default=10
            The number of pixels the cursor has to travel to enter into drag mode
        cursorLock(bool): default=False
            Whether the cursor returns to its start position every tick
        wrapBoundary(int): default=10
            When wrapping around the current screen, this is the number of pixels
            in from the edge of the screen that the cursor will appear
        dragCursor(int): default=self.CURSOR_ARROWS
            The cursor that will be displayed while dragging
            CURSOR_ARROWS will show horizontal/vertical drag
            CURSOR_BLANK will hid the cursor
        dragButton(Qt.MouseButton): default=Qt.MiddleButton
            The button that will kick off the drag behavior
        fastModifier(Qt.KeyboardModifier): default=Qt.ControlModifier
            The modifier key that will cause the multiplier to emit with the signal
        fastMultiplier(float): default=5.0
            The size of the multiplier
        slowModifier(Qt.KeyboardModifier): default=Qt.ShiftModifier
            The modifier key that will cause the divisor to emit with the signal
        slowDivisor(float): default=5.0
            The size of the divisor
        isSpinbox(bool): default=False
            This must be set to True if you are setting this as the handler
            for a QSpinBox. The QSpinBox will tick every 0.25s as long as your mouse is
            held down. This option turns that off
    """

    DRAG_ENABLED = 0
    DRAG_NONE = 0
    DRAG_HORIZONTAL = 1
    DRAG_VERTICAL = 2

    CURSOR_NONE = 0
    CURSOR_BLANK = 1
    CURSOR_ARROWS = 2

    dragTick = Signal(int, float)  # NumberOfTicks, TickMultiplier
    dragPressed = Signal()
    dragReleased = Signal()

    def __init__(self, parent):
        super(DragFilter, self).__init__(parent)

        self.dragSensitivity = 5  # pixels for one step
        self.startSensitivity = 10  # pixel move to start the dragging
        self.cursorLock = False
        self.wrapBoundary = 10  # wrap when within boundary of screen edge
        self.dragCursor = self.CURSOR_ARROWS
        self.dragButton = Qt.MiddleButton

        # The QSpinbox has an option where, if you hold down the mouse button
        # it will continually increment. This flag enables a workaround
        # for that problem
        self.isSpinbox = False

        self.fastModifier = Qt.ControlModifier
        self.slowModifier = Qt.ShiftModifier

        self.fastMultiplier = 5.0
        self.slowDivisor = 5.0

        # private vars
        self._lastPos = QPoint()
        self._leftover = 0
        self._dragStart = None
        self._firstDrag = False
        self._dragType = self.DRAG_NONE
        self._overridden = False
        self._screen = None
        self._isDragging = False

    def doOverrideCursor(self):
        """Change the cursor based on the current drag type"""
        if self._overridden:
            return
        if self.dragCursor == self.CURSOR_BLANK:
            QApplication.setOverrideCursor(Qt.BlankCursor)
        elif self.dragCursor == self.CURSOR_ARROWS:
            if self._dragType == self.DRAG_VERTICAL:
                QApplication.setOverrideCursor(Qt.SizeVerCursor)
            elif self._dragType == self.DRAG_HORIZONTAL:
                QApplication.setOverrideCursor(Qt.SizeHorCursor)

        self._overridden = True

    def restoreOverrideCursor(self):
        """Restore the cursor to the normal pointer"""
        if not self._overridden:
            return
        QApplication.restoreOverrideCursor()
        self._overridden = False

    def doDrag(self, o, e):
        """Handle a mouse drag event

        Parameters
        ----------
        o : QObject
            The object that is being dragged
        e : QEvent
            The QEvent of the mouse drag
        """
        if self._dragType == self.DRAG_HORIZONTAL:
            delta = e.pos().x() - self._lastPos.x()
        else:
            delta = self._lastPos.y() - e.pos().y()

        self._leftover += delta
        self._lastPos = e.pos()

        count = int(self._leftover / self.dragSensitivity)
        if count:
            mul = 1.0
            if e.modifiers() & self.fastModifier:
                mul = self.fastMultiplier
            elif e.modifiers() & self.slowModifier:
                mul = 1.0 / self.slowDivisor
            self.dragTick.emit(count, mul)

        # If we start off with negative leftover, then this modulo
        # needs to return negative leftover steps
        neg = self._leftover < 0
        self._leftover %= self.dragSensitivity
        if neg and self._leftover > 0:
            self._leftover -= self.dragSensitivity

        if self.cursorLock:
            QCursor.setPos(self.mapToGlobal(self._dragStart))
            self._lastPos = self._dragStart
        else:
            r = self._screen
            b = self.wrapBoundary
            p = o.mapToGlobal(e.pos())

            # when wrapping move to the other side in by 2*boundary
            # so we don't loop the wrapping
            if p.x() > r.right() - b:
                p.setX(r.left() + 2 * b)

            if p.x() < r.left() + b:
                p.setX(r.right() - 2 * b)

            if p.y() > r.bottom() - b:
                p.setY(r.top() + 2 * b)

            if p.y() < r.top() + b:
                p.setY(r.bottom() - 2 * b)

            if p != e.globalPos():
                QCursor.setPos(p)
                self._lastPos = self.parent().mapFromGlobal(p)
                self._leftover = 0

    def startDrag(self, o, e):
        """Start the drag event handling

        Parameters
        ----------
        o : QObject
            The object that is being dragged
        e : QEvent
            The QEvent of the mouse drag
        """
        if self._dragStart is None:
            self._dragStart = e.pos()
            dtop = QApplication.desktop()
            sn = dtop.screenNumber(o.mapToGlobal(e.pos()))
            self._screen = dtop.availableGeometry(sn)

        if abs(e.x() - self._dragStart.x()) > self.startSensitivity:
            self._dragType = self.DRAG_HORIZONTAL
        elif abs(e.y() - self._dragStart.y()) > self.startSensitivity:
            self._dragType = self.DRAG_VERTICAL

        if self._dragType:
            self._leftover = 0
            self._lastPos = e.pos()
            self._firstDrag = True

            self.dragPressed.emit()
            self.doOverrideCursor()

            if self.isSpinbox:
                if e.buttons() & self.dragButton:
                    # Send mouseRelease to spin buttons when dragging
                    # otherwise the spinbox will keep ticking.  @longClickFix
                    # There's gotta be a better way to do this :-/
                    mouseup = QMouseEvent(
                        QEvent.MouseButtonRelease,
                        e.pos(),
                        self.dragButton,
                        e.buttons(),
                        e.modifiers(),
                    )
                    QApplication.sendEvent(o, mouseup)

    def myendDrag(self, o, e):
        """End the drag event handling.  Can't call it endDrag because that's taken

        Parameters
        ----------
        o : QObject
            The object that is being dragged
        e : QEvent
            The QEvent of the mouse drag
        """

        # Only end dragging if it's *not* the first mouse release. See @longClickFix
        if self._firstDrag and self.isSpinbox:
            self._firstDrag = False

        elif self._dragType:
            self.restoreOverrideCursor()
            self._dragType = self.DRAG_NONE
            self._lastPos = QPoint()
            self._dragStart = None
            self._screen = None
            self.dragReleased.emit()

    def eventFilter(self, o, e):
        """Overridden Qt eventFilter

        Parameters
        ----------
        o : QObject
            The object that is being dragged
        e : QEvent
            The QEvent of the mouse drag
        """
        if hasattr(self, "DRAG_ENABLED"):
            if e.type() == QEvent.MouseMove:
                if self._isDragging:
                    try:
                        if self._dragType != self.DRAG_NONE:
                            self.doDrag(o, e)
                        elif e.buttons() & self.dragButton:
                            self.startDrag(o, e)
                    except Exception:
                        # fix the cursor if there's an error during dragging
                        self.restoreOverrideCursor()
                        raise  # re-raise the exception
                    return True

            elif e.type() == QEvent.MouseButtonRelease:
                self.myendDrag(o, e)
                if e.button() & self.dragButton:
                    # Catch any dragbutton releases and handle them
                    self._isDragging = False
                    return True

            elif e.type() == QEvent.MouseButtonPress:
                if e.button() & self.dragButton:
                    # Catch any dragbutton presses and handle them
                    self._isDragging = True
                    return True

        return super(DragFilter, self).eventFilter(o, e)
