from typing import Union
import winreg
from ctypes import Structure, c_int, POINTER, windll, byref, sizeof, cast
from ctypes.wintypes import DWORD, HWND, UINT, RECT, LPARAM, MSG, LPRECT
from enum import Enum
from sys import getwindowsversion
import PySide6

import win32api
import win32con
import win32gui

from PySide6.QtCore import Qt, QTimer, QPointF, QSize, Signal, QObject
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QPainterPath, \
    QIcon, QCursor
from PySide6.QtWidgets import QWidget, QToolButton, QLabel, QHBoxLayout
from win32comext.shell import shellcon

from .window_effects import WindowsEffects
from .resources import resources_rc


class APPBARDATA(Structure):
    _fields_ = [
        ('cbSize', DWORD),
        ('hWnd', HWND),
        ('uCallbackMessage', UINT),
        ('uEdge', UINT),
        ('rc', RECT),
        ('lParam', LPARAM)
    ]


class PWINDOWPOS(Structure):
    _fields_ = [
        ('hWnd', HWND),
        ('hwndInsertAfter', HWND),
        ('x', c_int),
        ('y', c_int),
        ('cx', c_int),
        ('cy', c_int),
        ('flags', UINT)
    ]


class NCCALCSIZE_PARAMS(Structure):
    _fields_ = [
        ('rgrc', RECT * 3),
        ('lppos', POINTER(PWINDOWPOS))
    ]


class SYSTEMTHEME:
    IsDarkTheme = False
    AccentColor = 'rgb(0, 120, 215)'

    @classmethod
    def Update(cls):
        path_theme = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        name_theme = r"AppsUseLightTheme"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path_theme) as registry_key:
            value, regtype = winreg.QueryValueEx(registry_key, name_theme)
            cls.IsDarkTheme = not bool(value)

        path_accent = r'SOFTWARE\\Microsoft\Windows\\CurrentVersion\\Explorer\\Accent'
        name_accent =   r"AccentColorMenu"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path_accent) as registry_key:
            value, regtype = winreg.QueryValueEx(registry_key, name_accent)
            accent = value - 4278190080
            accent = str(hex(accent)).split('x')[1]
            accent = accent[4:6]+accent[2:4]+accent[0:2]
            accent = 'rgb'+str(tuple(int(accent[i:i+2], 16) for i in (0, 2, 4)))
            cls.AccentColor = accent

LPNCCALCSIZE_PARAMS = POINTER(NCCALCSIZE_PARAMS)



def is_maximized(h_wnd):
    win_placement = win32gui.GetWindowPlacement(h_wnd)
    if win_placement:
        return win_placement[1] == win32con.SW_MAXIMIZE
    return False


def get_monitor_info(h_wnd, dw_flags):
    monitor = win32api.MonitorFromWindow(h_wnd, dw_flags)
    if monitor:
        return win32api.GetMonitorInfo(monitor)


def is_full_screen(h_wnd):
    if not h_wnd:
        return False
    h_wnd = int(h_wnd)

    win_rect = win32gui.GetWindowRect(h_wnd)
    if not win_rect:
        return False

    monitor_info = get_monitor_info(h_wnd, win32con.MONITOR_DEFAULTTOPRIMARY)
    if not monitor_info:
        return False

    monitor_rect = monitor_info['Monitor']
    return all(i == j for i, j in zip(win_rect, monitor_rect))


def find_window(h_wnd):
    if not h_wnd:
        return

    windows = QGuiApplication.topLevelWindows()
    if not windows:
        return

    for window in windows:
        if window and int(window.winId()) == int(h_wnd):
            return window


def get_resize_border_thickness(h_wnd):
    window = find_window(h_wnd)
    if not window:
        return 0

    result = win32api.GetSystemMetrics(
        win32con.SM_CXSIZEFRAME) + win32api.GetSystemMetrics(92)

    if result > 0:
        return result

    b_result = c_int(0)
    windll.dwmapi.DwmIsCompositionEnabled(byref(b_result))
    thickness = 8 if bool(b_result.value) else 4
    return round(thickness * window.devicePixelRatio())


class Taskbar:
    LEFT = 0
    TOP = 1
    RIGHT = 2
    BOTTOM = 3
    NO_POSITION = 4

    AUTO_HIDE_THICKNESS = 2

    @staticmethod
    def is_auto_hide():
        appbar_data = APPBARDATA(
            sizeof(APPBARDATA), 0, 0, 0, RECT(0, 0, 0, 0), 0)
        taskbar_state = windll.shell32.SHAppBarMessage(
            shellcon.ABM_GETSTATE, byref(appbar_data))
        return taskbar_state == shellcon.ABS_AUTOHIDE

    @classmethod
    def get_position(cls, h_wnd):
        monitor_info = get_monitor_info(
            h_wnd, win32con.MONITOR_DEFAULTTONEAREST)
        if not monitor_info:
            return cls.NO_POSITION

        monitor = RECT(*monitor_info['Monitor'])
        appbar_data = APPBARDATA(sizeof(APPBARDATA), 0, 0, 0, monitor, 0)
        for position in (cls.LEFT, cls.TOP, cls.RIGHT, cls.BOTTOM):
            appbar_data.uEdge = position
            if windll.shell32.SHAppBarMessage(11, byref(appbar_data)):
                return position

        return cls.NO_POSITION

def invert_color(color):
    inverted_color = ''
    for i in range(0, 5, 2):
        channel = int(color[i:i + 2], base=16)
        inverted_color += hex(round(channel / 6))[2:].upper().zfill(2)
    inverted_color += color[-2:]
    return inverted_color


class FramelessWindowBase(QWidget):
    COLOR = "F2F2F299"
    BORDER_WIDTH = 4
    def __init__(self):
        """ FramelessWindowBase

        Parameters
        ----------
        """
        super().__init__()
        self.is_win11 = getwindowsversion().build >= 22000
        self.use_mica = self.is_win11
        
        self.effect_enabled = False
        self._effect_timer = QTimer(self)
        self._effect_timer.setInterval(100)
        self._effect_timer.setSingleShot(True)
        self._effect_timer.timeout.connect(self.set_effect)

        SYSTEMTHEME.Update()

        self.is_apply_dark_theme = SYSTEMTHEME.IsDarkTheme

        if SYSTEMTHEME.IsDarkTheme:
            self.acrylic_color = invert_color(self.COLOR)
        else:
            self.acrylic_color = self.COLOR

        self.title_bar = None
        self.max_btn_hovered = False
        self.title_bar = TitleBar(self)

        self.win_effects = WindowsEffects()
        self.win_effects.add_window_animation(self.winId())
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.win_effects.add_window_animation(self.winId())
        self.set_effect()
        if self.is_win11:
            self.win_effects.add_blur_behind_window(self.winId())
            self.win_effects.add_shadow_effect(self.winId())
        self.setStyleSheet("FramelessWindowBase { background:transparent; }")


    def set_effect(self, enable=True):
        if self.effect_enabled == enable and SYSTEMTHEME.IsDarkTheme == self.is_apply_dark_theme:
            return
        
        self.is_apply_dark_theme = SYSTEMTHEME.IsDarkTheme

        if SYSTEMTHEME.IsDarkTheme:
            self.acrylic_color = invert_color(self.COLOR)
        else:
            self.acrylic_color = self.COLOR

        self.effect_enabled = enable
        if enable and self.use_mica:
            self.win_effects.add_mica_effect(self.winId(), SYSTEMTHEME.IsDarkTheme)
        elif enable:
            self.win_effects.add_acrylic_effect(
                self.winId(), self.acrylic_color)
        else:
            self.win_effects.remove_background_effect(self.winId())
        self.update()
        self.title_bar.repaint()

    def _temporary_disable_effect(self):
        self.set_effect(False)
        self._effect_timer.stop()
        self._effect_timer.start()
    
    def moveEvent(self, event):
        if self.is_win11 or not self._effect_timer:
            return super().moveEvent(event)
        self._temporary_disable_effect()

    def paintEvent(self, event):
        if self.effect_enabled:
            return super().paintEvent(event)
        painter = QPainter(self)
        painter.setOpacity(0.8)
        if SYSTEMTHEME.IsDarkTheme:
            painter.setBrush(Qt.GlobalColor.black)
        else:
            painter.setBrush(Qt.GlobalColor.white)
        painter.drawRect(self.rect())

    def setWindowTitle(self, title):
        self.title_bar.title.setText(title)
        super().setWindowTitle(title)

    def setWindowIcon(self, icon):
        self.title_bar.icon.setFixedWidth(32)
        self.title_bar.icon.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.title_bar.icon.setPixmap(icon.pixmap(16, 16))
        super().setWindowIcon(icon)

    def resizeEvent(self, event):
        if not self.title_bar:  # if not initialized
            return
        self.title_bar.setFixedWidth(self.width())
        if not self.use_mica:
            self._temporary_disable_effect()

    def nativeEvent(self, event_type, message):
        msg = MSG.from_address(int(message))
        if not msg.hWnd:
            return False, 0
        if msg.message == win32con.WM_NCHITTEST:
            pos = QCursor.pos()
            x = pos.x() - self.x()
            y = pos.y() - self.y()
            if self.is_win11 and self.title_bar.childAt(
                    pos - self.geometry().topLeft()) is self.title_bar.max_btn:
                self.max_btn_hovered = True
                self.title_bar.max_btn.set_state(TitleBarButtonState.HOVER)
                return True, win32con.HTMAXBUTTON
            lx = x < self.BORDER_WIDTH
            rx = x > self.width() - self.BORDER_WIDTH
            ty = y < self.BORDER_WIDTH
            by = y > self.height() - self.BORDER_WIDTH
            if rx and by:
                return True, win32con.HTBOTTOMRIGHT
            elif rx and ty:
                return True, win32con.HTTOPRIGHT
            elif lx and by:
                return True, win32con.HTBOTTOMLEFT
            elif lx and ty:
                return True, win32con.HTTOPLEFT
            elif rx:
                return True, win32con.HTRIGHT
            elif by:
                return True, win32con.HTBOTTOM
            elif lx:
                return True, win32con.HTLEFT
            elif ty:
                return True, win32con.HTTOP
        elif self.is_win11 and self.max_btn_hovered:
            if msg.message == win32con.WM_NCLBUTTONDOWN:
                self.title_bar.max_btn.set_state(TitleBarButtonState.PRESSED)
                return True, 0
            elif msg.message in [win32con.WM_NCLBUTTONUP,
                                 win32con.WM_NCRBUTTONUP]:
                self.title_bar.max_btn.click()
            elif msg.message in [0x2A2, win32con.WM_MOUSELEAVE] \
                    and self.title_bar.max_btn.get_state() != 0:
                self.max_btn_hovered = False
                self.title_bar.max_btn.set_state(TitleBarButtonState.NORMAL)

        elif msg.message == win32con.WM_NCCALCSIZE:
            if msg.wParam:
                rect = cast(msg.lParam, LPNCCALCSIZE_PARAMS).contents.rgrc[0]
            else:
                rect = cast(msg.lParam, LPRECT).contents

            is_max = is_maximized(msg.hWnd)
            is_full = is_full_screen(msg.hWnd)

            # Adjust the size of client rect
            if is_max and not is_full:
                thickness = get_resize_border_thickness(msg.hWnd)
                rect.top += thickness
                rect.left += thickness
                rect.right -= thickness
                rect.bottom -= thickness

            # Handle the situation that an auto-hide taskbar is enabled
            if (is_max or is_full) and Taskbar.is_auto_hide():
                position = Taskbar.get_position(msg.hWnd)
                if position == Taskbar.LEFT:
                    rect.top += Taskbar.AUTO_HIDE_THICKNESS
                elif position == Taskbar.BOTTOM:
                    rect.bottom -= Taskbar.AUTO_HIDE_THICKNESS
                elif position == Taskbar.LEFT:
                    rect.left += Taskbar.AUTO_HIDE_THICKNESS
                elif position == Taskbar.RIGHT:
                    rect.right -= Taskbar.AUTO_HIDE_THICKNESS

            res = 0 if not msg.wParam else win32con.WVR_REDRAW
            return True, res
        elif msg.message == win32con.WM_SETTINGCHANGE:
            SYSTEMTHEME.Update()
            self.set_effect()

        return False, 0


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
    
    def paintEvent(self, arg__1: PySide6.QtGui.QPaintEvent) -> None:
        if SYSTEMTHEME.IsDarkTheme:
            self.setIcon(self._white_icon)
        else:
            self.setIcon(self._black_icon)
        return super().paintEvent(arg__1)

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
    
    def paintEvent(self, event: PySide6.QtGui.QPaintEvent) -> None:
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


FramelessWindow = FramelessWindowBase
    