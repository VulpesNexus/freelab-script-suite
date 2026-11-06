# -*- coding: utf-8 -*-
"""Fake PythonQt and fontlab modules for the dark-mode tests (Python 2.7 and 3).

They follow PythonQt where it differs from PyQt: Qt properties such as
objectName, styleSheet, palette, width, and icon read as values, not getters.
"""

from __future__ import absolute_import, division, print_function

import sys
import types

ROLES = (
    "Window", "WindowText", "Base", "AlternateBase", "ToolTipBase", "ToolTipText", "Text", "Button",
    "ButtonText", "BrightText", "Light", "Midlight", "Mid", "Dark", "Shadow", "Highlight",
    "HighlightedText", "Link", "LinkVisited", "PlaceholderText",
)


class QColor(object):
    HexRgb, HexArgb = 0, 1

    def __init__(self, *args):
        if len(args) == 1 and isinstance(args[0], QColor):
            self.rgba = args[0].rgba
        elif len(args) == 1:
            digits = args[0].lstrip("#")
            alpha = int(digits[:2], 16) if len(digits) == 8 else 255
            digits = digits[-6:]
            self.rgba = (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16), alpha)
        else:
            self.rgba = tuple(args) + (255,) * (4 - len(args))

    def name(self, fmt=0):
        r, g, b, a = self.rgba
        return u"#%02x%02x%02x%02x" % (a, r, g, b) if fmt == QColor.HexArgb else u"#%02x%02x%02x" % (r, g, b)

    def __eq__(self, other):
        return isinstance(other, QColor) and other.rgba == self.rgba

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return "QColor(%s)" % self.name(QColor.HexArgb)


class QPalette(object):
    Active, Inactive, Disabled = 0, 1, 2

    def __init__(self, other=None):
        self.colors = dict(other.colors) if other is not None else {}

    def setColor(self, *args):
        if len(args) == 2:
            for group in (0, 1, 2):
                self.colors[(group, args[0])] = args[1]
        else:
            self.colors[(args[0], args[1])] = args[2]

    def color(self, *args):
        group, role = (0, args[0]) if len(args) == 1 else args
        return self.colors.get((group, role), QColor("#000000"))

    def resolve(self):
        return len(set(role for _group, role in self.colors))

    def __eq__(self, other):
        return isinstance(other, QPalette) and other.colors == self.colors

    def __ne__(self, other):
        return not self == other


for _role in ROLES:
    setattr(QPalette, _role, _role)


class Qt(object):
    WA_SetPalette = 13
    LogicalCoordinates = 0


class QFont(object):
    NoSubpixelAntialias = 0x0800

    def __init__(self, other=None):
        self.strategy = other.strategy if other is not None else 1

    def styleStrategy(self):
        return self.strategy

    def setStyleStrategy(self, value):
        self.strategy = value

    def __eq__(self, other):
        return isinstance(other, QFont) and other.strategy == self.strategy

    def __ne__(self, other):
        return not self == other


class QPoint(object):
    def __init__(self, x=0, y=0):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class QRect(object):
    def __init__(self, *args):
        self.args = args


class _Meta(object):
    def __init__(self, name):
        self.name = name

    def className(self):
        return self.name


class FakeStyle(object):
    def __init__(self, name):
        self.objectName = name  # a property: a value under PythonQt


class QStyleFactory(object):
    available = ("Fusion", "windowsvista", "Windows")

    @classmethod
    def create(cls, name):
        return FakeStyle(name) if name in cls.available else None


class FakeIcon(object):
    keys = [0]

    def __init__(self, label="icon"):
        FakeIcon.keys[0] += 1
        self.key = FakeIcon.keys[0]
        self.label = label

    def isNull(self):
        return False

    def cacheKey(self):
        return self.key


class QGraphicsEffect(object):
    def __init__(self):
        self.enabled = True
        self._props = {}

    def property(self, name):
        return self._props.get(name)

    def setProperty(self, name, value):
        self._props[name] = value


class OtherWrapper(object):
    """What PythonQt may return for an effect: another Python object for the same Qt object."""

    def __init__(self, effect):
        self._effect = effect

    def property(self, name):
        return self._effect.property(name)


class FakeEvent(object):
    def __init__(self, kind):
        self.kind = kind

    def type(self):
        return self.kind


class Deleted(Exception):
    pass


class QObject(object):
    widget = False

    def __init__(self, cls, name=u"", inherits=()):
        self._cls = cls
        self.objectName = name
        self._props = {}
        self._inherits = set(inherits) | set([cls])
        self.deleted = False
        self.icon = None

    def metaObject(self):
        if self.deleted:
            raise Deleted("destroyed")
        return _Meta(self._cls)

    def property(self, name):
        return self._props.get(name)

    def setProperty(self, name, value):
        if value is None:
            self._props.pop(name, None)
        else:
            self._props[name] = value
        return False

    def inherits(self, name):
        return name in self._inherits

    def isWidgetType(self):
        return self.widget

    def setIcon(self, icon):
        self.icon = icon


class QAction(QObject):
    def __init__(self, icon=None):
        QObject.__init__(self, "QAction")
        self.icon = icon


class FakeWidget(QObject):
    widget = True

    def __init__(self, cls="QWidget", name=u"", parent=None, sheet=u"", visible=True, width=100, height=20, y=0,
                 inherits=(), window=False, icon=None, light=None):
        QObject.__init__(self, cls, name, inherits)
        self._parent = parent
        self._children = []
        if parent is not None:
            parent._children.append(self)
        self.styleSheet = sheet
        self.sheet_sets = 0
        self.visible = visible
        self.width, self.height, self.y = width, height, y
        self.window = window
        self.palette = QPalette()
        self.set_palette = False
        self.effect = None
        self.icon = icon
        self.pixmap = None
        self.autoFillBackground = False
        self.light = light  # what detect_light reports (patched in by the tests)
        self.filters = []
        self.rewrap = False  # True: graphicsEffect() returns a new wrapper, as PythonQt may
        self._actions = []

    def parentWidget(self):
        return self._parent

    def children(self):
        return list(self._children)

    def findChildren(self, _cls):
        found = []
        for child in self._children:
            found.append(child)
            found.extend(child.findChildren(_cls))
        return found

    def isAncestorOf(self, other):
        if other is self:
            return True  # as Qt's QWidget::isAncestorOf
        parent = other.parentWidget()
        while parent is not None:
            if parent is self:
                return True
            parent = parent.parentWidget()
        return False

    def isVisible(self):
        return self.visible

    def isWindow(self):
        return self.window

    def setStyleSheet(self, sheet):
        self.styleSheet = sheet
        self.sheet_sets += 1
        for watcher in list(self.filters):  # Qt sends QEvent::StyleChange through installed filters
            watcher.eventFilter(self, FakeEvent(100))

    def installEventFilter(self, watcher):
        if watcher not in self.filters:
            self.filters.append(watcher)

    def removeEventFilter(self, watcher):
        if watcher in self.filters:
            self.filters.remove(watcher)

    def graphicsEffect(self):
        if self.rewrap and self.effect is not None and isinstance(self.effect, QGraphicsEffect):
            return OtherWrapper(self.effect)
        return self.effect

    def setGraphicsEffect(self, effect):
        self.effect = effect

    def setPalette(self, palette):
        self.palette = QPalette(palette)
        self.set_palette = palette.resolve() != 0

    def testAttribute(self, attribute):
        return attribute == Qt.WA_SetPalette and self.set_palette

    def setPixmap(self, pixmap):
        self.pixmap = pixmap

    def setAutoFillBackground(self, value):
        self.autoFillBackground = value

    def actions(self):
        return list(self._actions)

    def walk(self):
        yield self
        for child in self._children:
            for widget in child.walk():
                yield widget


class FakeApp(object):
    def __init__(self, light_palette):
        self._style = FakeStyle("windowsvista")
        self._palette = QPalette(light_palette)
        self.styleSheet = u""
        self.roots = []
        self.style_sets = 0
        self._font = QFont()

    def font(self):
        return QFont(self._font)

    def setFont(self, font):
        self._font = QFont(font)
        self.signals = {}

    def connect(self, signal, callback):
        self.signals.setdefault(signal, []).append(callback)
        return True

    def emit(self, signal, *args):
        for callback in self.signals.get(signal, []):
            callback(*args)

    def allWidgets(self):
        return [w for root in self.roots for w in root.walk()]

    def style(self):
        return self._style

    def setStyle(self, style):
        self._style = style
        self.style_sets += 1

    def palette(self):
        return QPalette(self._palette)

    def setPalette(self, palette):
        self._palette = QPalette(palette)

    def setStyleSheet(self, sheet):
        self.styleSheet = sheet


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


class Preferences(object):
    color_workspace = QColor("#ffacacac")

    @property
    def colorWorkspace(self):
        return QColor(Preferences.color_workspace)

    @colorWorkspace.setter
    def colorWorkspace(self, color):
        Preferences.color_workspace = QColor(color)


LIGHT_WINDOW = "#f0f0f0"
QT_VERSION = ["5.14.2"]


def install(remove_placeholder=False):
    """Install fake PythonQt and fontlab modules; returns the fake application."""
    light = QPalette()
    light.setColor(QPalette.Window, QColor(LIGHT_WINDOW))
    QApplication.current = FakeApp(light)
    QTimer.made = []
    QT_VERSION[0] = "5.14.2"
    Preferences.color_workspace = QColor("#ffacacac")
    if remove_placeholder and hasattr(QPalette, "PlaceholderText"):
        delattr(QPalette, "PlaceholderText")
    elif not hasattr(QPalette, "PlaceholderText"):
        QPalette.PlaceholderText = "PlaceholderText"
    pkg = types.ModuleType("PythonQt")
    core = types.ModuleType("PythonQt.QtCore")
    gui = types.ModuleType("PythonQt.QtGui")
    core.QTimer, core.Qt, core.QPoint, core.QRect = QTimer, Qt, QPoint, QRect
    core.qVersion = lambda: QT_VERSION[0]
    for name, value in (("QColor", QColor), ("QPalette", QPalette), ("QApplication", QApplication),
                        ("QStyleFactory", QStyleFactory), ("QGraphicsEffect", QGraphicsEffect),
                        ("QWidget", FakeWidget), ("QFont", QFont)):
        setattr(gui, name, value)
    pkg.QtCore, pkg.QtGui = core, gui
    fontlab = types.ModuleType("fontlab")
    fontlab.flPreferences = Preferences
    sys.modules.update({"PythonQt": pkg, "PythonQt.QtCore": core, "PythonQt.QtGui": gui, "fontlab": fontlab})
    return QApplication.current


def uninstall():
    for name in ("PythonQt", "PythonQt.QtCore", "PythonQt.QtGui", "fontlab"):
        sys.modules.pop(name, None)
    QApplication.current = None
    if not hasattr(QPalette, "PlaceholderText"):
        QPalette.PlaceholderText = "PlaceholderText"
