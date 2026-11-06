#FLM: FreeLab: Dark Mode Settings
# -*- coding: utf-8 -*-
"""FreeLab dark mode settings, from FontLab's Scripts menu.

Look: FontLab's own light look, dark, or a dark interface with FontLab's light
glyph canvases, font cells, and previews. And whether to follow Windows: dark
while Windows apps are set to dark, light otherwise, switching as Windows does.
The choice applies at once and is kept for the next launch.

Valid Python 2.7 (FontLab 7) and Python 3.
"""

from __future__ import absolute_import, division, print_function

import os
import sys

DARK_MODE_MODULE = "freelab_dark_mode"
DARK_MODE_FILE = "freelab_dark_mode.py"
LOOKS = (
    ("light", "Light: FontLab's own look"),
    ("dark", "Dark"),
    ("interface", "Dark interface, light glyphs and canvas"),
)


def dark_mode_module():
    """The running dark mode, or the one next to this file, loaded without switching anything."""
    module = sys.modules.get(DARK_MODE_MODULE)
    if module is not None:
        return module
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, DARK_MODE_FILE)
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(DARK_MODE_MODULE)
            module.__file__ = path
            sys.modules[DARK_MODE_MODULE] = module
            with open(path, "rb") as handle:
                source = handle.read()
            exec(compile(source, DARK_MODE_FILE, "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(DARK_MODE_MODULE, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[DARK_MODE_MODULE] = module
            spec.loader.exec_module(module)
    finally:
        del os.environ["FREELAB_NO_AUTOSTART"]
    return module


def current_look(settings, dm):
    if not settings.get("enabled"):
        return "light"
    return "dark" if dm.content_setting(settings) else "interface"


def show_dialog():
    from PythonQt.QtGui import QDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QCheckBox, QPushButton, QLabel
    dm = dark_mode_module()
    settings = dm.load_settings()
    dialog = QDialog()
    dialog.setWindowTitle("FreeLab Dark Mode")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Look:"))
    look = current_look(settings, dm)
    buttons = {}
    for key, label in LOOKS:
        button = QRadioButton(label)
        button.setChecked(key == look)
        layout.addWidget(button)
        buttons[key] = button
    follow = QCheckBox("Follow Windows: dark while Windows apps are dark (uses the dark look chosen above)")
    follow.setChecked(bool(settings.get("follow_windows")))
    layout.addWidget(follow)
    row = QHBoxLayout()
    row.addStretch(1)
    ok, cancel = QPushButton("OK"), QPushButton("Cancel")
    ok.setDefault(True)
    row.addWidget(ok)
    row.addWidget(cancel)
    layout.addLayout(row)
    ok.connect("clicked()", dialog.accept)
    cancel.connect("clicked()", dialog.reject)
    if not dialog.exec_():
        return None
    chosen = [key for key, button in buttons.items() if button.isChecked()]
    chosen = chosen[0] if chosen else look
    # Following Windows needs a dark look to switch to: "light" with it means the full dark look.
    content = chosen != "interface"
    dark = chosen != "light" or follow.isChecked()
    result = dm.configure(dark=dark, content=content, follow_windows=follow.isChecked())
    print("FreeLab dark mode: %s%s." % (
        dict(LOOKS)["interface" if dark and not content else ("dark" if dark else "light")],
        ", following Windows" if result.get("follow_windows") else ""))
    return result


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_dark_mode_settings":
    show_dialog()
