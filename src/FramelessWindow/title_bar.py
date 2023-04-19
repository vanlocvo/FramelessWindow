from enum import Enum

import win32api
import win32con
import win32gui

from PySide6.QtCore import Qt, QPointF, QSize
from PySide6.QtGui import QPainter, QPen, QPainterPath, QIcon
from PySide6.QtWidgets import QWidget, QToolButton, QLabel, QHBoxLayout

from .utils import *
from .system_theme import SYSTEMTHEME
from .resources import resources_rc

class TitleBarButtonState(Enum):
    NORMAL = 0
    HOVER = 1
    PRESSED = 2


class TitleBarButton(QToolButton):
    def __init__(self, parent):
        super().__init__(parent)
        color_dark = "F" * 6
        color_white = "0" * 6
        self.colors = {
            True: ("transparent", "#20" + color_dark, "#40" + color_dark),
            False: ("transparent", "#20" + color_white, "#40" + color_white)
        }
        self._icon_color = {
            True: Qt.GlobalColor.white,
            False: Qt.GlobalColor.black
        } 
        self._style = """
        border: none;
        margin: 0px;
        """
        self._state = TitleBarButtonState.NORMAL
        self.set_state(TitleBarButtonState.NORMAL)
        self.setFixedSize(46, 32)

    def get_state(self):
        return self._state

    def set_state(self, state):
        self._state = state
        self.setStyleSheet(
            f"background-color: {self.colors[SYSTEMTHEME.IsDarkTheme][state.value]};\n{self._style}")
        

    def enterEvent(self, e):
        self.set_state(TitleBarButtonState.HOVER)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.set_state(TitleBarButtonState.NORMAL)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.set_state(TitleBarButtonState.PRESSED)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self.set_state(TitleBarButtonState.HOVER)
        super().mouseReleaseEvent(e)


class MinimizeButton(TitleBarButton):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(self._icon_color[SYSTEMTHEME.IsDarkTheme])
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawLine(18, 16, 28, 16)


class MaximizeButton(TitleBarButton):
    def __init__(self, parent):
        super().__init__(parent)
        self.is_max = False

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(self._icon_color[SYSTEMTHEME.IsDarkTheme])
        pen.setCosmetic(True)
        painter.setPen(pen)

        r = self.devicePixelRatioF()
        painter.scale(1 / r, 1 / r)
        if not self.is_max:
            painter.drawRect(
                int(18 * r), int(11 * r), int(10 * r), int(10 * r))
        else:
            r_18, r_8 = int(18 * r), int(8 * r)
            painter.drawRect(r_18, int(13 * r), r_8, r_8)
            x0 = r_18 + int(2 * r)
            y0 = 13 * r
            dw = int(2 * r)
            path = QPainterPath(QPointF(x0, y0))
            path.lineTo(x0, y0 - dw)
            path.lineTo(x0 + 8 * r, y0 - dw)
            path.lineTo(x0 + 8 * r, y0 - dw + 8 * r)
            path.lineTo(x0 + 8 * r - dw, y0 - dw + 8 * r)
            painter.drawPath(path)


class CloseButton(TitleBarButton):
    def __init__(self, parent):
        super().__init__(parent)
        self.colors = {
            True: ("transparent", "#C42B1C", "#C83C30"),
            False: ("transparent", "#C42B1C", "#C83C30")
        }
        self.set_state(TitleBarButtonState.NORMAL)
        self._white_icon = QIcon(r":close_btn/white")
        self._black_icon = QIcon(r":close_btn/black")
        if SYSTEMTHEME.IsDarkTheme:
            self.setIcon(self._white_icon)
        else:
            self.setIcon(self._black_icon)
        self.setIconSize(QSize(46, 32))

    def enterEvent(self, event):
        if not SYSTEMTHEME.IsDarkTheme:
            self.setIcon(self._white_icon)
        super().enterEvent(event)
    
    def paintEvent(self, args) -> None:
        if SYSTEMTHEME.IsDarkTheme:
            self.setIcon(self._white_icon)
        else:
            self.setIcon(self._black_icon)
        return super().paintEvent(args)

    def leaveEvent(self, event):
        if not SYSTEMTHEME.IsDarkTheme:
            self.setIcon(self._black_icon)
        super().leaveEvent(event)


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedHeight(32)

        self.icon = QLabel(self)
        self.title = QLabel(self)
        self.min_btn = MinimizeButton(self)
        self.max_btn = MaximizeButton(self)
        self.close_btn = CloseButton(self)
        self.h_box_layout = QHBoxLayout(self)

        if SYSTEMTHEME.IsDarkTheme:
            self.title.setStyleSheet("color: white")
        else:
            self.title.setStyleSheet("color: black")
        self.icon.setFixedSize(10, 16)
        self.h_box_layout.setSpacing(0)
        self.h_box_layout.setContentsMargins(0, 0, 0, 0)

        self.h_box_layout.addWidget(self.icon)
        self.h_box_layout.addWidget(self.title)
        self.h_box_layout.addWidget(self.min_btn)
        self.h_box_layout.addWidget(self.max_btn)
        self.h_box_layout.addWidget(self.close_btn)

        self.min_btn.clicked.connect(self.window().showMinimized)
        self.max_btn.clicked.connect(self.__toggle_max_state)
        self.close_btn.clicked.connect(self.window().close)
    
    def paintEvent(self, event) -> None:
        if SYSTEMTHEME.IsDarkTheme:
            self.title.setStyleSheet("color: white")
        else:
            self.title.setStyleSheet("color: black")
        return super().paintEvent(event)

    def __toggle_max_state(self):
        is_max = self.window().isMaximized()
        self.max_btn.is_max = not is_max
        if is_max:
            self.window().showNormal()
        else:
            self.window().showMaximized()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.__toggle_max_state()

    def mouseMoveEvent(self, event):
        if not event.pos().x() < self.width() - 46 * 3:
            return
        win32gui.ReleaseCapture()
        win32api.SendMessage(
            int(self.window().winId()),
            win32con.WM_SYSCOMMAND, win32con.SC_MOVE | win32con.HTCAPTION, 0
        )
