#FLM: Dark Mode Settings
# -*- coding: utf-8 -*-
"""FreeLab dark mode settings, from FontLab's Scripts menu.

Theme: FontLab's own light look, dark, or mixed (a dark interface with
FontLab's light glyph canvases, font cells, and previews). Shade: how dark the
grays are. Automatic: light while Windows apps are light, the dark theme chosen
above while they are dark, switching as Windows does. The choice applies at once
and is kept for the next launch.

Valid Python 2.7 (FontLab 7) and Python 3.
"""

from __future__ import absolute_import, division, print_function

import os
import sys

DARK_MODE_MODULE = "freelab_dark_mode"
DARK_MODE_FILE = "freelab_dark_mode.py"
LOOKS = (
    ("light", "Light (FontLab's default)"),
    ("dark", "Dark"),
    ("interface", "Mixed (dark interface, light canvases)"),
)
SHADES = (("dark", "Dark grays"), ("medium", "Medium grays"))
AUTOMATIC = "Automatic (matches system theme)"


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
    from PythonQt.QtCore import Qt
    dm = dark_mode_module()
    settings = dm.load_settings()
    dialog = QDialog()
    dialog.setWindowTitle("FreeLab Dark Mode")
    # No "?" in the title bar: it offered help this dialog does not have.
    flags = int(dialog.windowFlags()) if callable(dialog.windowFlags) else int(dialog.windowFlags)
    dialog.setWindowFlags(Qt.WindowFlags(flags & ~int(Qt.WindowContextHelpButtonHint)))
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Theme:"))
    look = current_look(settings, dm)
    buttons = {}
    for key, label in LOOKS:
        button = QRadioButton(label)
        button.setChecked(key == look)
        layout.addWidget(button)
        buttons[key] = button
    layout.addWidget(QLabel("Shade:"))
    shade = settings.get("shade", "dark")
    shade_buttons = {}
    for key, label in SHADES:
        button = QRadioButton(label)
        button.setChecked(key == shade)
        layout.addWidget(button)
        shade_buttons[key] = button
    # Two groups of radio buttons in one dialog: each group needs its own exclusive QButtonGroup.
    from PythonQt.QtGui import QButtonGroup
    look_group, shade_group = QButtonGroup(dialog), QButtonGroup(dialog)
    for button in buttons.values():
        look_group.addButton(button)
    for button in shade_buttons.values():
        shade_group.addButton(button)
    follow = QCheckBox(AUTOMATIC)
    follow.setChecked(bool(settings.get("follow_windows")))
    layout.addWidget(follow)

    def update(*_args):
        """Automatic leaves light to Windows: the light theme is not a choice then, and the dark one
        (dark or mixed) and its shade are. Shades mean nothing to the light theme."""
        auto = follow.isChecked()
        buttons["light"].setEnabled(not auto)
        if auto and buttons["light"].isChecked():
            buttons["dark"].setChecked(True)
        light = buttons["light"].isChecked() and not auto
        for button in shade_buttons.values():
            button.setEnabled(not light)

    for button in buttons.values():
        button.connect("toggled(bool)", update)
    follow.connect("toggled(bool)", update)
    update()
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
    chosen_shade = [key for key, button in shade_buttons.items() if button.isChecked()]
    result = dm.configure(dark=dark, content=content, follow_windows=follow.isChecked(),
                          shade=chosen_shade[0] if chosen_shade else shade)
    print("FreeLab dark mode: %s%s." % (
        dict(LOOKS)["interface" if dark and not content else ("dark" if dark else "light")],
        ", following Windows" if result.get("follow_windows") else ""))
    return result


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_dark_mode_settings":
    show_dialog()
