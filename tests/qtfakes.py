# -*- coding: utf-8 -*-
"""Fake PythonQt modules for the dark-mode tests (Python 2.7 and 3)."""

from __future__ import absolute_import, division, print_function

import sys
import types

ROLES = (
    "Window", "WindowText", "Base", "AlternateBase", "ToolTipBase", "ToolTipText", "Text", "Button",
    "ButtonText", "BrightText", "Light", "Midlight", "Mid", "Dark", "Shadow", "Highlight",
    "HighlightedText", "Link", "LinkVisited", "PlaceholderText",
)


class QColor(object):
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, QColor) and other.value == self.value

    def __ne__(self, other):
        return not self == other


class QPalette(object):
    Disabled = "Disabled"
    All = "All"

    def __init__(self, other=None):
        self.colors = dict(other.colors) if other is not None else {}

    def setColor(self, *args):
        if len(args) == 2:
            self.colors[("All", args[0])] = args[1]
        else:
            self.colors[(args[0], args[1])] = args[2]

    def __eq__(self, other):
        return isinstance(other, QPalette) and other.colors == self.colors

    def __ne__(self, other):
        return not self == other


for _role in ROLES:
    setattr(QPalette, _role, _role)


class FakeStyle(object):
    def __init__(self, name):
        self.name = name

    def objectName(self):
        return self.name


class QStyleFactory(object):
    available = ("Fusion", "windowsvista", "Windows")

    @classmethod
    def create(cls, name):
        return FakeStyle(name) if name in cls.available else None


class FakeApp(object):
    def __init__(self):
        self._style = FakeStyle("windowsvista")
        self._palette = QPalette()
        self._palette.setColor(QPalette.Window, QColor("#f0f0f0"))
        self._sheet = u"QWidget#fontlab { color: black; }"

    def style(self):
        return self._style

    def setStyle(self, style):
        self._style = style

    def palette(self):
        return QPalette(self._palette)

    def setPalette(self, palette):
        self._palette = QPalette(palette)

    def styleSheet(self):
        return self._sheet

    def setStyleSheet(self, sheet):
        self._sheet = sheet


class QApplication(object):
    current = None

    @classmethod
    def instance(cls):
        return cls.current


class QTimer(object):
    made = []

    def __init__(self):
        self.single = False
        self.interval = None
        self.callback = None
        self.running = False
        QTimer.made.append(self)

    def setSingleShot(self, value):
        self.single = value

    def setInterval(self, ms):
        self.interval = ms

    def connect(self, signal, callback):
        self.callback = callback
        return True

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def fire(self):
        if self.running:
            if self.single:
                self.running = False
            self.callback()


def install(remove_placeholder=False):
    """Install fake PythonQt modules; returns the fake application."""
    QApplication.current = FakeApp()
    QTimer.made = []
    if remove_placeholder and hasattr(QPalette, "PlaceholderText"):
        delattr(QPalette, "PlaceholderText")
    elif not hasattr(QPalette, "PlaceholderText"):
        QPalette.PlaceholderText = "PlaceholderText"
    pkg = types.ModuleType("PythonQt")
    core = types.ModuleType("PythonQt.QtCore")
    gui = types.ModuleType("PythonQt.QtGui")
    core.QTimer = QTimer
    gui.QColor = QColor
    gui.QPalette = QPalette
    gui.QApplication = QApplication
    gui.QStyleFactory = QStyleFactory
    pkg.QtCore = core
    pkg.QtGui = gui
    sys.modules["PythonQt"] = pkg
    sys.modules["PythonQt.QtCore"] = core
    sys.modules["PythonQt.QtGui"] = gui
    return QApplication.current


def uninstall():
    for name in ("PythonQt", "PythonQt.QtCore", "PythonQt.QtGui"):
        sys.modules.pop(name, None)
    QApplication.current = None
    if not hasattr(QPalette, "PlaceholderText"):
        QPalette.PlaceholderText = "PlaceholderText"
