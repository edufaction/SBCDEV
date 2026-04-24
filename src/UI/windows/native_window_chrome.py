from __future__ import annotations

import os
import sys
from ctypes import CFUNCTYPE, byref, c_int, c_size_t, c_void_p
from ctypes.util import find_library

from PySide6.QtWidgets import QApplication, QWidget


def apply_native_window_chrome(window: QWidget, *, theme_name: str) -> None:
    """Best-effort native dark window chrome for supported desktop platforms."""

    app = QApplication.instance()
    platform_name = str(app.platformName() if app is not None else "").lower()
    if "offscreen" in platform_name:
        return
    if not window.isWindow():
        return

    wants_dark = theme_name != "light"
    if sys.platform == "win32":
        _apply_windows_dark_titlebar(window, wants_dark=wants_dark)
    elif sys.platform == "darwin":
        _apply_macos_appearance(wants_dark=wants_dark)


def _apply_windows_dark_titlebar(window: QWidget, *, wants_dark: bool) -> None:
    try:
        import ctypes
    except Exception:
        return

    hwnd = int(window.winId())
    if not hwnd:
        return

    value = c_int(1 if wants_dark else 0)
    try:
        dwmapi = ctypes.windll.dwmapi
    except Exception:
        return

    for attribute in (20, 19):
        try:
            result = dwmapi.DwmSetWindowAttribute(hwnd, attribute, byref(value), c_size_t(4))
        except Exception:
            continue
        if result == 0:
            break


def _apply_macos_appearance(*, wants_dark: bool) -> None:
    if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
        return
    objc_path = find_library("objc")
    appkit_path = find_library("AppKit")
    if not objc_path or not appkit_path:
        return

    try:
        import ctypes

        objc = ctypes.cdll.LoadLibrary(objc_path)
        ctypes.cdll.LoadLibrary(appkit_path)
    except Exception:
        return

    objc.objc_getClass.restype = c_void_p
    objc.sel_registerName.restype = c_void_p

    send_obj = CFUNCTYPE(c_void_p, c_void_p, c_void_p)(("objc_msgSend", objc))
    send_obj_arg = CFUNCTYPE(c_void_p, c_void_p, c_void_p, c_void_p)(("objc_msgSend", objc))
    send_void_arg = CFUNCTYPE(None, c_void_p, c_void_p, c_void_p)(("objc_msgSend", objc))

    def objc_class(name: bytes) -> c_void_p:
        return objc.objc_getClass(name)

    def sel(name: bytes) -> c_void_p:
        return objc.sel_registerName(name)

    def nsstring(text: str) -> c_void_p:
        encoded = text.encode("utf-8")
        string_cls = objc_class(b"NSString")
        return send_obj_arg(string_cls, sel(b"stringWithUTF8String:"), ctypes.c_char_p(encoded))

    try:
        app = send_obj(objc_class(b"NSApplication"), sel(b"sharedApplication"))
        appearance_cls = objc_class(b"NSAppearance")
        appearance_name = "NSAppearanceNameDarkAqua" if wants_dark else "NSAppearanceNameAqua"
        appearance = send_obj_arg(appearance_cls, sel(b"appearanceNamed:"), nsstring(appearance_name))
        if app and appearance:
            send_void_arg(app, sel(b"setAppearance:"), appearance)
    except Exception:
        return
