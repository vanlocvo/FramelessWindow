from ctypes import Structure, c_int, POINTER, windll, byref
from ctypes.wintypes import DWORD, HWND, LPARAM, UINT, RECT

import win32api
import win32con
import win32gui

from PySide6.QtGui import QGuiApplication


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

class APPBARDATA(Structure):
    _fields_ = [
        ('cbSize', DWORD),
        ('hWnd', HWND),
        ('uCallbackMessage', UINT),
        ('uEdge', UINT),
        ('rc', RECT),
        ('lParam', LPARAM)
    ]



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

def invert_color(color):
    inverted_color = ''
    for i in range(0, 5, 2):
        channel = int(color[i:i + 2], base=16)
        inverted_color += hex(round(channel / 6))[2:].upper().zfill(2)
    inverted_color += color[-2:]
    return inverted_color