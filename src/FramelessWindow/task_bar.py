import win32con
from ctypes import windll, byref, sizeof
from ctypes.wintypes import RECT
from win32comext.shell import shellcon

from .utils import APPBARDATA, get_monitor_info

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