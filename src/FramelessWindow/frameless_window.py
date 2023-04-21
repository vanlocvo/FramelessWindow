from ctypes import POINTER, cast
from ctypes.wintypes import MSG, LPRECT
from sys import getwindowsversion

import win32con

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtWidgets import QWidget

from .window_effects import WindowsEffects
from .utils import *
from .system_theme import SYSTEMTHEME
from .task_bar import Taskbar
from .title_bar import TitleBar, TitleBarButtonState

LPNCCALCSIZE_PARAMS = POINTER(NCCALCSIZE_PARAMS)

class FramelessWindowBase(QWidget):
    COLOR_LIGHT = "FCFCFC99"
    COLOR_DARK = "2C2C2C99"
    BORDER_WIDTH = 4
    def __init__(self):
        """ FramelessWindowBase

        Parameters
        ----------
        """
        super().__init__()
        self.setObjectName("FramelessWindowBase")

        # set margins for title bar
        self.setContentsMargins(0, 30, 0, 0)
        self.is_win11 = getwindowsversion().build >= 22000
        self.use_mica = self.is_win11
        
        self.effect_enabled = False
        self._effect_timer = QTimer(self)
        self._effect_timer.setInterval(100)
        self._effect_timer.setSingleShot(True)
        self._effect_timer.timeout.connect(self.set_effect)

        SYSTEMTHEME.Update()

        self.is_apply_dark_theme = SYSTEMTHEME.IsDarkTheme
        self.accent_color = SYSTEMTHEME.AccentColor

        if SYSTEMTHEME.IsDarkTheme:
            self.acrylic_color = self.COLOR_DARK
        else:
            self.acrylic_color = self.COLOR_LIGHT

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
        if self.effect_enabled == enable and SYSTEMTHEME.IsDarkTheme == self.is_apply_dark_theme and self.accent_color == SYSTEMTHEME.AccentColor:
            return
        
        self.is_apply_dark_theme = SYSTEMTHEME.IsDarkTheme
        self.accent_color = SYSTEMTHEME.AccentColor

        if SYSTEMTHEME.IsDarkTheme:
            self.acrylic_color = self.COLOR_DARK
        else:
            self.acrylic_color = self.COLOR_LIGHT

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


FramelessWindow = FramelessWindowBase
    