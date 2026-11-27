# -*- coding: utf-8 -*-
"""Fake PythonQt and fontlab modules for the dark-mode tests (Python 2.7 and 3).

They follow PythonQt where it differs from PyQt: Qt properties such as
objectName, styleSheet, palette, width, and icon read as values, not getters.
"""

from __future__ import absolute_import, division, print_function

import sys
import types
import weakref

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

    def red(self):
        return self.rgba[0]

    def green(self):
        return self.rgba[1]

    def blue(self):
        return self.rgba[2]

    def alpha(self):
        return self.rgba[3]

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
    WA_SetFont = 46
    WA_StyledBackground = 93
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

    def availableSizes(self):
        return []  # no pixels to look at: never white artwork


class QGraphicsEffect(object):
    def __init__(self):
        self.enabled = True
        self._props = {}

    def setEnabled(self, value):
        self.enabled = value

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
        self.font = QFont()  # (a value, as PythonQt reads properties)
        self.effect = None
        self.icon = icon
        self.pixmap = None
        self.autoFillBackground = False
        self.light = light  # what detect_light reports (patched in by the tests)
        self.filters = []
        self.rewrap = False  # True: graphicsEffect() returns a new wrapper, as PythonQt may
        self._actions = []
        self.connections = {}  # signal -> callables, as connect() made them
        self.geometry = FakeGeometry(width, height)
        self.ground = None  # the color grab() shows (an int 0xrrggbb); None: grab() is not available
        self.mapped_ground = None  # the color it shows through an enabled effect, if other
        self.grabs = []  # for each grab(): whether the widget's effect was enabled then

    def grab(self, rect=None):
        if self.ground is None:
            raise AttributeError("grab")
        enabled = self.effect is not None and getattr(self.effect, "enabled", True)
        self.grabs.append(enabled)
        color = self.mapped_ground if enabled and self.mapped_ground is not None else self.ground
        return FakeImage(color)

    def connect(self, signal, slot):
        self.connections.setdefault(signal, []).append(slot)
        return True

    def emit(self, signal):
        for slot in self.connections.get(signal, []):
            slot()

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

    def update(self, *rect):
        self.updates = getattr(self, "updates", 0) + 1

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

    def setFont(self, font):
        self.font = QFont(font)
        self.set_font = font.strategy != 1  # (the fakes' default font: inherited)

    def testAttribute(self, attribute):
        if attribute == Qt.WA_SetPalette:
            return self.set_palette
        if attribute == Qt.WA_SetFont:
            return getattr(self, "set_font", False)
        return attribute in getattr(self, "attributes", ())

    def setAttribute(self, attribute, on=True):
        kept = set(getattr(self, "attributes", ()))
        if on:
            kept.add(attribute)
        else:
            kept.discard(attribute)
        self.attributes = kept

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


class FakeGeometry(object):
    def __init__(self, width, height):
        self._width, self._height = width, height

    def width(self):
        return self._width

    def height(self):
        return self._height


class FakeImage(object):
    """What grab().toImage() gives: one color everywhere."""

    def __init__(self, color, width=40, height=12):
        self.color, self._width, self._height = color, width, height

    def toImage(self):
        return self

    def width(self):
        return self._width

    def height(self):
        return self._height

    def pixel(self, x, y):
        return 0xff000000 | self.color


class FakeApp(object):
    def __init__(self, light_palette):
        self._style = FakeStyle("windowsvista")
        self._palette = QPalette(light_palette)
        self.styleSheet = u""
        self.roots = []
        self.style_sets = 0
        self._font = QFont()
        self.signals = {}

    def font(self):
        return QFont(self._font)

    def setFont(self, font):
        self._font = QFont(font)

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

    def setPalette(self, palette, class_name=None):
        if class_name is not None:  # (a class's own palette, which Qt forgets when the application's is set)
            self.class_palettes = dict(getattr(self, "class_palettes", {}), **{class_name: QPalette(palette)})
            return
        self._palette = QPalette(palette)
        self.class_palettes = {}

    def setStyleSheet(self, sheet):
        self.styleSheet = sheet


class QApplication(object):
    current = None

    @classmethod
    def instance(cls):
        return cls.current


class QTimer(object):
    """A timer that owns up to PythonQt's rule: one made from Python with no parent is deleted the moment
    its last Python reference goes. made holds weak references only (timers() lists the live ones), so a
    timer nothing else holds goes, as it would in FontLab; one that goes while it emits (its own timeout
    let go of its last reference) is noted in deleted_while_emitting, and fire_unheld raises for it."""
    made = []  # weak references to the timers made since install()
    single_shots = []  # (ms, callback) of every QTimer.singleShot
    deleted_while_emitting = []  # (interval, callback) of each parentless timer deleted inside its own timeout
    parented = []  # the timers made with a parent, which Qt holds

    @staticmethod
    def singleShot(ms, callback):
        QTimer.single_shots.append((ms, callback))

    def __init__(self, parent=None):
        self._parent = parent
        self.single = False
        self.interval = None
        self.callback = None
        self.running = False
        emitting = self._emitting = [False]
        owned = parent is None  # (PythonQt's to delete)
        details = self._details = [None, None]

        def gone(_ref):  # (holds nothing of the timer itself)
            if owned and emitting[0]:
                QTimer.deleted_while_emitting.append(tuple(details))
        QTimer.made.append(weakref.ref(self, gone))
        if parent is not None:
            QTimer.parented.append(self)  # (Qt's: alive while its parent is, whoever holds it in Python)

    def parent(self):
        return self._parent

    def metaObject(self):
        return _Meta("QTimer")

    def inherits(self, name):
        return name == "QTimer"

    def isActive(self):
        return self.running

    def setSingleShot(self, value):
        self.single = value

    def setInterval(self, ms):
        self.interval = ms
        self._details[0] = ms

    def connect(self, signal, callback):
        self.callback = callback
        self._details[1] = callback
        return True

    def disconnect(self, signal, callback):
        if self.callback is callback:
            self.callback = None
        return True

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def fire(self):
        if self.running:
            if self.single:
                self.running = False
            self._emitting[0] = True
            try:
                self.callback()
            finally:
                self._emitting[0] = False


def timers():
    """The timers made since install() that are still alive."""
    return [timer for timer in (ref() for ref in QTimer.made) if timer is not None]


def fire_unheld(get):
    """Fire the timer get() gives as Qt does: no Python reference to it held while it emits (Qt's signal
    holds none). Raises when PythonQt would have deleted it from inside its own timeout."""
    ref = weakref.ref(get())
    timer = ref()
    if timer is None or not timer.running:
        return
    if timer.single:
        timer.running = False
    callback, emitting, before = timer.callback, timer._emitting, len(QTimer.deleted_while_emitting)
    emitting[0] = True
    del timer
    try:
        callback()
    finally:
        emitting[0] = False
    if len(QTimer.deleted_while_emitting) > before:
        raise AssertionError("a parentless timer lost its last reference inside its own timeout: "
                             "PythonQt deletes it while it emits")


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
    QTimer.deleted_while_emitting = []
    QTimer.parented = []
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


# -- A window's Cancel button (ak.cancel_button), for each tool's tests: one set of fakes, as every tool shares
# the function (the owner, 2026-11-24: "a 'Cancel' button left of 'Close' could be useful")

class CancelButton(object):
    """A QPushButton as ak.cancel_button uses one: its text, properties, tooltip, help, state, and slots kept."""

    def __init__(self, text=u""):
        self.text, self.props, self.enabled, self.slots = text, {}, True, {}
        self.tip = self.whats = None

    def setProperty(self, name, value):
        self.props[name] = value

    def property(self, name):
        return self.props.get(name)

    def setToolTip(self, text):
        self.tip = text

    def setWhatsThis(self, text):
        self.whats = text

    def setEnabled(self, on):
        self.enabled = bool(on)

    def isEnabled(self):
        return self.enabled

    def connect(self, signal, slot):
        self.slots[signal] = slot


class CancelRow(object):
    """A QHBoxLayout as ak.cancel_button reads and fills one: its items in order (None for a stretch)."""

    def __init__(self, widgets=()):
        self.items = list(widgets)

    def count(self):
        return len(self.items)

    def itemAt(self, k):
        held = self.items[k]
        return type("Item", (object,), {"widget": lambda item: held})()

    def insertWidget(self, k, widget):
        self.items.insert(k, widget)

    def addWidget(self, widget, *args):
        self.items.append(widget)

    def addStretch(self, *args):
        self.items.append(None)


def cancel_made(ak, owner, note, before=(u"Write",)):
    """owner's Cancel button as ak.cancel_button makes it, PythonQt's QPushButton faked (CancelButton), in a
    bottom row of before's buttons then Close: (row, the button, Close)."""
    close = CancelButton(u"Close")
    row = CancelRow([None] + [CancelButton(text) for text in before] + [close])
    real = ak._qt
    ak._qt = lambda: (None, type("QtGui", (object,), {"QPushButton": staticmethod(CancelButton)}))
    try:
        button = ak.cancel_button(owner, row, close, note)
    finally:
        ak._qt = real
    return row, button, close


def follow_cancel(test, ak, holder=None):
    """The Cancel button through a tool's work: holder's busy_start and busy_end (ak's, or a tool's fake of
    them), as they are now, also set the owner's Cancel button as the real ones do (ak.cancel_states), then
    record (the step, whether it may stop, whether Cancel is usable then): (None, None, ...) at busy_end. The
    list of records; holder's own put back at test's end."""
    holder = ak if holder is None else holder
    wrap = staticmethod if isinstance(holder, type) else (lambda function: function)
    start, end = holder.busy_start, holder.busy_end
    seen = []

    def usable(owner):
        button = getattr(owner, "cancel_button", None)
        return None if button is None else bool(button.enabled)

    def started(owner, what=u"", stoppable=True):
        start(owner, what, stoppable=stoppable)
        ak._busy_state(owner).update({"running": True, "stoppable": bool(stoppable)})  # (busy_start's own)
        ak.cancel_states(owner)
        seen.append((what, bool(stoppable), usable(owner)))

    def ended(owner):
        end(owner)
        ak._busy_state(owner)["running"] = False  # (busy_end's own)
        ak.cancel_states(owner)
        seen.append((None, None, usable(owner)))

    holder.busy_start, holder.busy_end = wrap(started), wrap(ended)

    def restore():
        holder.busy_start, holder.busy_end = wrap(start), wrap(end)
    test.addCleanup(restore)
    return seen
